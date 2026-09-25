import time
from datetime import datetime, timezone

from sqlalchemy import update

from backend.config import config
from backend.storage.database import users, conversations, runs, usage_entries
from tests.conftest import register


async def test_admin_access_is_explicit_and_revocable(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(config, "ADMIN_USER_IDS", [])
    assert (await c.get("/api/admin/overview")).status_code == 401
    headers = await register(c)
    me = (await c.get("/api/auth/me", headers=headers)).json()
    assert me["is_admin"] is False
    assert (await c.get("/api/admin/overview", headers=headers)).status_code == 403
    monkeypatch.setattr(config, "ADMIN_USER_IDS", [me["id"]])
    assert (await c.get("/api/auth/me", headers=headers)).json()["is_admin"] is True
    member = await register(c, email="member@example.com")
    assert (await c.get("/api/admin/overview", headers=member)).status_code == 403
    login = await c.post(
        "/api/auth/login",
        json={"email": me["email"], "password": "a-secure-test-password"},
    )
    assert login.json()["user"]["is_admin"] is True
    response = await c.get("/api/admin/overview", headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["recorded_tokens"] == 0
    assert (
        await c.get("/api/admin/overview?days=8", headers=headers)
    ).status_code == 422
    assert (
        await c.get("/api/admin/overview?page=0", headers=headers)
    ).status_code == 422
    monkeypatch.setattr(config, "ADMIN_USER_IDS", [])
    assert (await c.get("/api/admin/overview", headers=headers)).status_code == 403


async def test_admin_metrics_pagination_and_private_fields(client, monkeypatch):
    c, app = client
    headers = await register(c)
    uid = (await c.get("/api/auth/me", headers=headers)).json()["id"]
    monkeypatch.setattr(config, "ADMIN_USER_IDS", [uid])
    now = time.time()
    today = int(now // 86400) * 86400
    async with app.state.db.engine.begin() as db:
        await db.execute(
            update(users).where(users.c.id == uid).values(created=today + 1)
        )
        await db.execute(
            users.insert(),
            [
                {
                    "id": f"user-{i}",
                    "email": f"user-{i}@example.com",
                    "password": "private-hash",
                    "created": today - 40 * 86400,
                }
                for i in range(21)
            ],
        )
        # Yesterday after noon tests PostgreSQL's rounding versus UTC day flooring.
        await db.execute(
            update(users).where(users.c.id == "user-0").values(created=today - 3600)
        )
        await db.execute(
            conversations.insert().values(
                id="chat", owner_id=uid, title="Private title", created=now, updated=now
            )
        )
        await db.execute(
            runs.insert(),
            [
                {
                    "id": "r1",
                    "owner_id": uid,
                    "conversation_id": "chat",
                    "request_key": "one",
                    "request": {"content": "private prompt"},
                    "status": "complete",
                    "created": now,
                    "updated": now,
                    "result": {
                        "content": "private answer",
                        "usage": {"total_tokens": 120},
                    },
                },
                {
                    "id": "r2",
                    "owner_id": "user-0",
                    "conversation_id": "chat",
                    "request_key": "two",
                    "request": {},
                    "status": "failed",
                    "created": now,
                    "updated": now,
                    "result": None,
                },
            ],
        )
        await db.execute(
            usage_entries.insert(),
            [
                {"id": "r1", "owner_id": uid, "created": now},
                {"id": "r2", "owner_id": "user-0", "created": now},
                {"id": "deleted-run", "owner_id": uid, "created": now},
                {"id": "old-run", "owner_id": "user-1", "created": today - 40 * 86400},
            ],
        )
    response = await c.get("/api/admin/overview?days=7", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_users"] == 22
    assert data["signups"] == 2
    assert data["active_users"] == 2
    assert data["submitted_runs"] == 3
    assert data["recorded_tokens"] == 120
    assert data["run_statuses"] == {"complete": 1, "failed": 1}
    assert data["total_conversations"] == 1
    assert len(data["daily_signups"]) == 7
    assert data["daily_signups"][-2]["count"] == 1
    assert data["daily_signups"][-1]["count"] == 1
    assert (
        data["daily_signups"][-1]["date"]
        == datetime.fromtimestamp(today, timezone.utc).date().isoformat()
    )
    assert len(data["users"]) == 20
    for private in (
        "private-hash",
        "private prompt",
        "private answer",
        "Private title",
        "token_hash",
        "password",
    ):
        assert private not in response.text
    second = (await c.get("/api/admin/overview?page=2", headers=headers)).json()
    assert len(second["users"]) == 2
    assert not {u["id"] for u in data["users"]} & {u["id"] for u in second["users"]}
