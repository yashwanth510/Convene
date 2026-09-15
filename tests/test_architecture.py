from backend.config import config
import asyncio
from datetime import datetime
import pytest
import httpx
from backend.core.types import Position, Review
from backend.core.debate import Debate
from backend.core.evidence import validate_assessments
from backend.core.orchestrator import build_context, choose_mode
from backend.llm.gateway import Gateway, Budget, BudgetExceeded, ProviderFailure
from tests.conftest import register


def positions():
    return [
        Position(
            agent_id=x,
            model_name=x,
            content=x,
            timestamp=datetime.now(),
        )
        for x in "abc"
    ]


def review(reviewer, order):
    return Review(
        reviewer_id=reviewer,
        reviewer_model=reviewer,
        ranked_positions=[(x, i + 1, "") for i, x in enumerate(order)],
        comment="",
        timestamp=datetime.now(),
    )


def test_agreement_is_reviewer_agreement():
    assert (
        Debate.rank_positions(
            positions(), [review("one", "abc"), review("two", "abc")]
        ).convergence_score
        == 1
    )
    assert (
        Debate.rank_positions(
            positions(), [review("one", "abc"), review("two", "cba")]
        ).convergence_score
        == 0
    )
    assert not Debate.rank_positions(positions(), []).consensus_reached
    assert not Debate.rank_positions(
        positions(), [review("one", "abc")]
    ).consensus_reached
    assert not Debate.rank_positions(
        positions(), [review("one", "abc"), review("one", "abc")]
    ).consensus_reached
    assert not Debate.rank_positions(
        positions(), [review("one", "ab")]
    ).consensus_reached


def test_evidence_cannot_invent_a_source():
    rows = {
        "claims": [
            {
                "claim": "A triangle has three sides",
                "status": "supported",
                "source_id": "S1",
                "excerpt": "A triangle has three sides.",
            }
        ]
    }
    assert validate_assessments(rows, [])[0]["status"] == "unknown"
    sources = [{"id": "S1", "content": "A triangle has three sides."}]
    assert validate_assessments(rows, sources)[0]["status"] == "supported"
    rows["claims"][0]["excerpt"] = "A triangle actually has five sides."
    assert validate_assessments(rows, sources)[0]["status"] == "unknown"


def test_history_and_routing():
    history = [
        {
            "id": str(i),
            "role": "user",
            "content": "My project name is Basil." if i == 0 else "A different turn",
        }
        for i in range(9)
    ]
    context = build_context(history, "What is my project name?", [])
    assert "Basil" in context["relevant_older_turns"]
    assert len(context["recent_conversation"]) <= 11000
    assert choose_mode("Hello", "auto", []) == "fast"
    assert choose_mode("Compare two architectures", "auto", []) == "council"
    assert choose_mode("Hello", "council", []) == "council"


async def test_budget_concurrent_reservations():
    b = Budget(max_calls=2, max_tokens=500)
    results = await asyncio.gather(
        *(b.reserve("hello", 100) for _ in range(3)), return_exceptions=True
    )
    assert sum(isinstance(r, BudgetExceeded) for r in results) == 1
    assert b.calls == 2


async def test_rate_limit_circuit(provider_keys):
    count = 0

    def response(req):
        nonlocal count
        count += 1
        return httpx.Response(429, headers={"retry-after": "60"})

    g = Gateway(httpx.AsyncClient(transport=httpx.MockTransport(response)))
    for _ in range(2):
        with pytest.raises(ProviderFailure):
            await g.ask("groq_gpt_oss", "hello", Budget())
    assert count == 1
    assert not g.available(g.model("groq_gpt_oss"))
    await g.close()


async def test_stream_disconnect_preserves_partial_and_does_not_fallback(provider_keys):
    count = 0

    def response(req):
        nonlocal count
        count += 1
        return httpx.Response(
            200, text='data: {"choices":[{"delta":{"content":"partial answer"}}]}\n\n'
        )

    g = Gateway(httpx.AsyncClient(transport=httpx.MockTransport(response)))
    chunks = []

    async def receive(chunk):
        chunks.append(chunk)

    with pytest.raises(ProviderFailure):
        await g.ask("groq_gpt_oss", "question", Budget(), stream=receive, fallback=True)
    assert chunks == ["partial answer"] and count == 1
    await g.close()


async def test_auth_ownership_and_logout(client):
    c, app = client
    assert (await c.get("/api/conversations")).status_code == 401
    a = await register(c)
    b = await register(c, "two@example.com")
    conv = (await c.post("/api/conversations", headers=a)).json()["id"]
    assert (await c.get("/api/conversations/" + conv, headers=b)).status_code == 404
    assert (await c.delete("/api/conversations/" + conv, headers=b)).status_code == 404
    assert (await c.get("/api/conversations", headers=b)).json() == []
    await c.post("/api/auth/logout", headers=a)
    assert (await c.get("/api/conversations", headers=a)).status_code == 401


async def test_complete_run_and_event_replay(client):
    c, app = client
    headers = await register(c)
    conv = (await c.post("/api/conversations", headers=headers)).json()["id"]
    payload = {
        "content": "Compare two approaches to explaining triangles",
        "request_key": "test-request-001",
        "mode": "council",
        "panel_size": 4,
        "web_search_enabled": True,
    }
    r = await c.post(f"/api/conversations/{conv}/runs", headers=headers, json=payload)
    assert r.status_code == 202, r.text
    rid = r.json()["id"]
    duplicate = await c.post(
        f"/api/conversations/{conv}/runs", headers=headers, json=payload
    )
    assert duplicate.json()["id"] == rid
    task = app.state.runs.tasks.get(rid)
    if task:
        await task
    run = (await c.get(f"/api/runs/{rid}", headers=headers)).json()
    assert run["status"] == "complete", run
    result = run["result"]
    assert len(result["positions"]) == 4
    assert result["rounds"][0]["agreement"] == 1
    assert result["evidence"]["claims"][0]["status"] == "supported"
    assert result["usage"]["total_tokens"] > 0
    conv_data = (await c.get(f"/api/conversations/{conv}", headers=headers)).json()
    assert len(conv_data["messages"]) == 2
    assert conv_data["active_run_id"] is None
    stream = await c.get(f"/api/runs/{rid}/events", headers=headers)
    assert "event: finished" in stream.text
    all_events = await app.state.db.events_after(rid, 0)
    ids = [e["seq"] for e in all_events]
    assert ids == list(range(1, len(ids) + 1))
    replay = await c.get(f"/api/runs/{rid}/events?after={ids[-2]}", headers=headers)
    assert replay.text.count("event: ") == 1
    assert (
        await c.post(f"/api/runs/{rid}/feedback", headers=headers, json={"value": 1})
    ).status_code == 204
    assert (await c.get("/api/telemetry", headers=headers)).json()[
        "positive_feedback"
    ] == 1
    exported = (
        await c.get(f"/api/conversations/{conv}/download", headers=headers)
    ).text
    assert (
        payload["content"] in exported
        and "Reference" in exported
        and "Evidence:" in exported
    )


async def test_concurrent_run_claim_and_cancellation(client):
    c, app = client
    headers = await register(c)
    conv = (await c.post("/api/conversations", headers=headers)).json()["id"]
    blocker = asyncio.Event()

    async def slow(*args, **kw):
        await blocker.wait()

    app.state.gateway.ask = slow

    async def start(key):
        return await c.post(
            f"/api/conversations/{conv}/runs",
            headers=headers,
            json={"content": "Hello", "request_key": key, "web_search_enabled": False},
        )

    responses = await asyncio.gather(start("concurrent-one"), start("concurrent-two"))
    assert sorted(r.status_code for r in responses) == [202, 409]
    rid = next(r.json()["id"] for r in responses if r.status_code == 202)
    await asyncio.sleep(0.02)
    assert (await c.post(f"/api/runs/{rid}/cancel", headers=headers)).status_code == 204
    assert (await c.get(f"/api/runs/{rid}", headers=headers)).json()[
        "status"
    ] == "cancelled"
    assert (await c.get(f"/api/conversations/{conv}", headers=headers)).json()[
        "active_run_id"
    ] is None


async def test_unknown_model_and_upload_limits(client):
    c, app = client
    h = await register(c)
    conv = (await c.post("/api/conversations", headers=h)).json()["id"]
    r = await c.post(
        f"/api/conversations/{conv}/runs",
        headers=h,
        json={
            "content": "hello",
            "request_key": "unknown-model",
            "enabled_models": ["google_gemini"],
        },
    )
    assert r.status_code == 422
    r = await c.post(
        "/api/files/parse",
        headers=h,
        files={"files": ("notes.txt", b"These are my notes.", "text/plain")},
    )
    assert (
        r.status_code == 200 and r.json()["files"][0]["text"] == "These are my notes."
    )
    r = await c.post(
        "/api/files/parse",
        headers=h,
        files={"files": ("notes.txt", b"x" * (5 * 1024 * 1024 + 1), "text/plain")},
    )
    assert r.status_code == 413


async def test_deleting_chat_does_not_reset_daily_quota(client, monkeypatch):
    c, app = client
    monkeypatch.setattr(config, "DAILY_RUN_LIMIT", 1)
    h = await register(c)
    cid = (await c.post("/api/conversations", headers=h)).json()["id"]
    payload = {
        "content": "Hello",
        "request_key": "daily-limit-first",
        "mode": "fast",
        "web_search_enabled": False,
    }
    r = await c.post(f"/api/conversations/{cid}/runs", headers=h, json=payload)
    assert r.status_code == 202
    task = app.state.runs.tasks.get(r.json()["id"])
    if task:
        await task
    assert (await c.delete(f"/api/conversations/{cid}", headers=h)).status_code == 204
    cid = (await c.post("/api/conversations", headers=h)).json()["id"]
    payload["request_key"] = "daily-limit-second"
    assert (
        await c.post(f"/api/conversations/{cid}/runs", headers=h, json=payload)
    ).status_code == 429


async def test_recovery_keeps_partial_answer_and_documents(client):
    c, app = client
    h = await register(c)
    owner = (await c.get("/api/auth/me", headers=h)).json()["id"]
    cid = (await c.post("/api/conversations", headers=h)).json()["id"]
    doc = {"name": "notes.txt", "text": "A triangle has three sides."}
    run, _ = await app.state.db.create_run(
        owner,
        cid,
        {
            "content": "Explain my notes",
            "request_key": "recovery-test",
            "documents": [doc],
        },
        15,
    )
    await app.state.db.checkpoint(
        run["id"], {"content": "Saved partial answer", "positions": []}
    )
    await app.state.db.recover_interrupted()
    recovered = await app.state.db.get_run(owner, run["id"])
    assert recovered["status"] == "interrupted"
    conv = await app.state.db.conversation(owner, cid)
    assert conv["active_run_id"] is None
    assert conv["messages"][-1]["content"] == "Saved partial answer"
    assert await app.state.db.recent_documents(owner, cid) == [doc]


def test_malformed_evidence_remains_unknown():
    assert validate_assessments({"claims": None}, []) == []
    rows = validate_assessments(
        {"claims": [{"claim": "Example", "source_id": [], "status": "supported"}]}, []
    )
    assert rows[0]["status"] == "unknown"


async def test_retry_is_idempotent_even_when_queue_is_full(client, monkeypatch):
    c, app = client
    headers = await register(c)
    cid = (await c.post("/api/conversations", headers=headers)).json()["id"]
    body = {"content": "Hello", "request_key": "full-queue-retry", "mode": "fast"}
    first = await c.post(f"/api/conversations/{cid}/runs", headers=headers, json=body)
    task = app.state.runs.tasks.get(first.json()["id"])
    if task:
        await task
    # A zero admission capacity exercises retries while rejecting new work.
    monkeypatch.setattr(config, "MAX_ACTIVE_RUNS", 0)
    retry = await c.post(f"/api/conversations/{cid}/runs", headers=headers, json=body)
    assert retry.status_code == 202
    assert retry.json()["id"] == first.json()["id"]
    body["request_key"] = "new-work-while-full"
    assert (
        await c.post(f"/api/conversations/{cid}/runs", headers=headers, json=body)
    ).status_code == 429


async def test_search_is_opt_in_and_sends_only_the_question(provider_keys):
    from backend.core.evidence import EvidenceService

    requests = []

    def handler(request):
        import json

        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        service = EvidenceService(http)
        await service.search("A current question", False)
        assert not requests
        await service.search("A current question", True)
        await service.search("A current question", True)
        assert len(requests) == 1  # Reuses the five-minute cache.
        assert requests[0]["query"] == "A current question"
        assert "documents" not in requests[0]


async def test_removed_models_cannot_be_selected(client):
    c, _ = client
    h = await register(c)
    cid = (await c.post("/api/conversations", headers=h)).json()["id"]
    for model in [
        "mistral_large",
        "cerebras_gpt_oss_120b",
        "sambanova_deepseek_v32",
        "openrouter_gpt_oss_20b",
    ]:
        r = await c.post(
            f"/api/conversations/{cid}/runs",
            headers=h,
            json={
                "content": "Hello",
                "request_key": "removed-model-check",
                "enabled_models": [model],
            },
        )
        assert r.status_code == 422


async def test_cancellation_waits_for_inflight_database_write(client, monkeypatch):
    c, app = client
    headers = await register(c)
    conv = (await c.post("/api/conversations", headers=headers)).json()["id"]
    db = app.state.runs.db
    written, release = asyncio.Event(), asyncio.Event()
    original = db._event

    async def paused_event(connection, rid, kind, data):
        await original(connection, rid, kind, data)
        if kind == "queued":
            written.set()
            await release.wait()

    monkeypatch.setattr(db, "_event", paused_event)
    response = await c.post(
        f"/api/conversations/{conv}/runs",
        headers=headers,
        json={"content": "Hello", "request_key": "cancel-during-write"},
    )
    assert response.status_code == 202
    rid = response.json()["id"]
    await asyncio.wait_for(written.wait(), 5)
    cancellation = asyncio.create_task(c.post(f"/api/runs/{rid}/cancel", headers=headers))
    try:
        await asyncio.sleep(0.05)
        assert not cancellation.done()
    finally:
        release.set()
    assert (await asyncio.wait_for(cancellation, 5)).status_code == 204
    assert (await c.get(f"/api/runs/{rid}", headers=headers)).json()["status"] == "cancelled"
    assert (await c.get(f"/api/conversations/{conv}", headers=headers)).json()["active_run_id"] is None
