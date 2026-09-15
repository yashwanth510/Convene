import json
import httpx
import pytest
import pytest_asyncio
from backend.config import config
from backend.llm.gateway import Gateway
from backend.main import create_app


@pytest.fixture
def provider_keys(monkeypatch):
    for name in [
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "MISTRAL_API_KEY",
        "TAVILY_API_KEY",
    ]:
        monkeypatch.setattr(config, name, "synthetic-test-key")
    monkeypatch.setattr(config, "APP_ENV", "development")
    monkeypatch.setattr(config, "INVITE_CODE", "")


def fake_transport(request):
    data = json.loads(request.content)
    if request.url.path == "/search":
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Reference",
                        "url": "https://example.org/reference",
                        "content": "A triangle has three sides. This is a geometric definition.",
                    }
                ]
            },
        )
    prompt = data["messages"][-1]["content"]
    model = data["model"]
    if model == "openrouter/free":
        model = "some/independent-model"
    if "Rank these anonymized" in prompt:
        items = json.loads(prompt.split("\n", 1)[1])
        content = json.dumps(
            {
                "ranking": [i["id"] for i in items],
                "feedback": "Explain the example more clearly.",
            }
        )
    elif "Assess at most" in prompt:
        content = json.dumps(
            {
                "claims": [
                    {
                        "claim": "A triangle has three sides.",
                        "status": "supported",
                        "source_id": "S1",
                        "excerpt": "A triangle has three sides.",
                        "note": "Matches the source.",
                    }
                ]
            }
        )
    else:
        content = "A triangle has three sides. [S1]\n\nThis is an example answer with clear limitations."
    usage = {"prompt_tokens": 120, "completion_tokens": 40}
    if data.get("stream"):
        parts = [content[:25], content[25:]]
        frames = [
            "data: "
            + json.dumps(
                {
                    "model": model,
                    "choices": [{"delta": {"content": p}, "finish_reason": None}],
                }
            )
            + "\n\n"
            for p in parts
        ]
        frames += [
            "data: "
            + json.dumps(
                {
                    "model": model,
                    "choices": [{"delta": {}, "finish_reason": "stop"}],
                    "usage": usage,
                }
            )
            + "\n\n",
            "data: [DONE]\n\n",
        ]
        return httpx.Response(
            200, text="".join(frames), headers={"content-type": "text/event-stream"}
        )
    return httpx.Response(
        200,
        json={
            "model": model,
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": usage,
        },
    )


@pytest_asyncio.fixture
async def client(tmp_path, provider_keys):
    app = create_app(
        "sqlite+aiosqlite:///" + str(tmp_path / "test.db"),
        gateway_factory=lambda: Gateway(
            httpx.AsyncClient(transport=httpx.MockTransport(fake_transport))
        ),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c, app


async def register(client, email="one@example.com"):
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "a-secure-test-password"},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}
