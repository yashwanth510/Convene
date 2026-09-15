"""Transactional storage shared by local SQLite and hosted PostgreSQL."""

import hashlib
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import ssl

from sqlalchemy import (
    MetaData,
    Table,
    Column,
    String,
    Text,
    Float,
    Integer,
    JSON,
    ForeignKey,
    UniqueConstraint,
    select,
    update,
    delete,
    func,
    event,
)
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

meta = MetaData()
users = Table(
    "users",
    meta,
    Column("id", String, primary_key=True),
    Column("email", String, unique=True, nullable=False),
    Column("password", Text, nullable=False),
    Column("created", Float, nullable=False),
)
sessions = Table(
    "sessions",
    meta,
    Column("token_hash", String, primary_key=True),
    Column(
        "user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    ),
    Column("expires", Float, nullable=False),
)
conversations = Table(
    "conversations",
    meta,
    Column("id", String, primary_key=True),
    Column("owner_id", String, ForeignKey("users.id"), nullable=False, index=True),
    Column("title", Text, nullable=False),
    Column("created", Float, nullable=False),
    Column("updated", Float, nullable=False),
    Column("active_run_id", String),
)
messages = Table(
    "messages",
    meta,
    Column("id", String, primary_key=True),
    Column(
        "conversation_id",
        String,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("role", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("created", Float, nullable=False),
    Column("result", JSON),
)
runs = Table(
    "runs",
    meta,
    Column("id", String, primary_key=True),
    Column("owner_id", String, ForeignKey("users.id"), nullable=False, index=True),
    Column(
        "conversation_id",
        String,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("request_key", String, nullable=False),
    Column("request", JSON, nullable=False),
    Column("status", String, nullable=False),
    Column("created", Float, nullable=False),
    Column("updated", Float, nullable=False),
    Column("event_seq", Integer, nullable=False, default=0),
    Column("result", JSON),
    Column("feedback", Integer),
    UniqueConstraint("owner_id", "request_key"),
)
events = Table(
    "run_events",
    meta,
    Column(
        "run_id", String, ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("seq", Integer, primary_key=True),
    Column("kind", String, nullable=False),
    Column("data", JSON, nullable=False),
    Column("created", Float, nullable=False),
)
usage_entries = Table(
    "usage_entries",
    meta,
    Column("id", String, primary_key=True),
    Column(
        "owner_id",
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("created", Float, nullable=False),
)
TERMINAL = {"complete", "partial", "failed", "cancelled", "interrupted"}


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


class StoreError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Database:
    def __init__(self, database_url):
        url = make_url(database_url)
        options = {}
        if url.drivername in ("postgres", "postgresql", "postgresql+asyncpg"):
            query = dict(url.query)
            sslmode = query.pop("sslmode", "require")
            query.pop("channel_binding", None)
            url = url.set(drivername="postgresql+asyncpg", query=query)
            options["connect_args"] = (
                {"ssl": ssl.create_default_context()} if sslmode != "disable" else {}
            )
            options.update(pool_size=3, max_overflow=2)
        elif url.drivername.startswith("sqlite"):
            url = url.set(drivername="sqlite+aiosqlite")
            if url.database and url.database != ":memory:":
                Path(url.database).parent.mkdir(parents=True, exist_ok=True)
            options["connect_args"] = {"timeout": 30}
        self.engine = create_async_engine(url, pool_pre_ping=True, **options)
        if url.drivername.startswith("sqlite"):

            @event.listens_for(self.engine.sync_engine, "connect")
            def sqlite_setup(connection, _):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()

    async def initialize(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(meta.create_all)

    async def close(self):
        await self.engine.dispose()

    async def user_for_token(self, token):
        digest = hashlib.sha256(token.encode()).hexdigest()
        async with self.engine.connect() as c:
            row = (
                (
                    await c.execute(
                        select(users.c.id, users.c.email)
                        .join(sessions)
                        .where(
                            sessions.c.token_hash == digest,
                            sessions.c.expires > time.time(),
                        )
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row else None

    async def create_conversation(self, owner):
        row = dict(
            id=str(uuid.uuid4()),
            owner_id=owner,
            title="New conversation",
            created=time.time(),
            updated=time.time(),
        )
        async with self.engine.begin() as c:
            await c.execute(conversations.insert().values(**row))
        return {
            "id": row["id"],
            "title": row["title"],
            "created_at": stamp(row["created"]),
        }

    async def conversation(self, owner, cid):
        async with self.engine.connect() as c:
            row = (
                (
                    await c.execute(
                        select(conversations).where(
                            conversations.c.id == cid, conversations.c.owner_id == owner
                        )
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise StoreError("Conversation not found", 404)
            msgs = (
                (
                    await c.execute(
                        select(messages)
                        .where(messages.c.conversation_id == cid)
                        .order_by(messages.c.created, messages.c.id)
                    )
                )
                .mappings()
                .all()
            )
        return {
            "id": cid,
            "title": row["title"],
            "active_run_id": row["active_run_id"],
            "created_at": stamp(row["created"]),
            "updated_at": stamp(row["updated"]),
            "messages": [
                dict(
                    id=m["id"],
                    role=m["role"],
                    content=m["content"],
                    timestamp=stamp(m["created"]),
                    result=m["result"],
                )
                for m in msgs
            ],
        }

    async def list_conversations(self, owner):
        async with self.engine.connect() as c:
            rows = (
                (
                    await c.execute(
                        select(conversations)
                        .where(conversations.c.owner_id == owner)
                        .order_by(conversations.c.updated.desc())
                        .limit(100)
                    )
                )
                .mappings()
                .all()
            )
        return [
            dict(
                id=r["id"],
                title=r["title"],
                updated_at=stamp(r["updated"]),
                active_run_id=r["active_run_id"],
            )
            for r in rows
        ]

    async def delete_conversation(self, owner, cid):
        async with self.engine.begin() as c:
            row = (
                (
                    await c.execute(
                        select(conversations).where(
                            conversations.c.id == cid, conversations.c.owner_id == owner
                        )
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise StoreError("Conversation not found", 404)
            if row["active_run_id"]:
                raise StoreError(
                    "Stop the current answer before deleting this conversation", 409
                )
            deleted = await c.execute(
                delete(conversations).where(
                    conversations.c.id == cid, conversations.c.active_run_id.is_(None)
                )
            )
            if not deleted.rowcount:
                raise StoreError(
                    "Stop the current answer before deleting this conversation", 409
                )

    async def create_run(self, owner, cid, request, daily_limit):
        now = time.time()
        async with self.engine.begin() as c:
            # Serialize per-user quota/idempotency checks across requests and workers.
            await c.execute(
                update(users).where(users.c.id == owner).values(email=users.c.email)
            )
            old = (
                (
                    await c.execute(
                        select(runs).where(
                            runs.c.owner_id == owner,
                            runs.c.request_key == request["request_key"],
                        )
                    )
                )
                .mappings()
                .first()
            )
            if old:
                if old["conversation_id"] != cid or old["request"] != request:
                    raise StoreError(
                        "This request key was already used for another message", 409
                    )
                return dict(old), False
            count = await c.scalar(
                select(func.count())
                .select_from(usage_entries)
                .where(
                    usage_entries.c.owner_id == owner,
                    usage_entries.c.created >= now - 86400,
                )
            )
            if count >= daily_limit:
                raise StoreError(
                    "Daily question limit reached. Please try again tomorrow.", 429
                )
            rid = str(uuid.uuid4())
            claimed = await c.execute(
                update(conversations)
                .where(
                    conversations.c.id == cid,
                    conversations.c.owner_id == owner,
                    conversations.c.active_run_id.is_(None),
                )
                .values(active_run_id=rid, updated=now)
            )
            if not claimed.rowcount:
                exists = await c.scalar(
                    select(conversations.c.id).where(
                        conversations.c.id == cid, conversations.c.owner_id == owner
                    )
                )
                raise StoreError(
                    "A question is already running in this conversation"
                    if exists
                    else "Conversation not found",
                    409 if exists else 404,
                )
            row = dict(
                id=rid,
                owner_id=owner,
                conversation_id=cid,
                request_key=request["request_key"],
                request=request,
                status="queued",
                created=now,
                updated=now,
                event_seq=0,
            )
            await c.execute(runs.insert().values(**row))
            await c.execute(
                usage_entries.insert().values(id=rid, owner_id=owner, created=now)
            )
            count = await c.scalar(
                select(func.count())
                .select_from(messages)
                .where(messages.c.conversation_id == cid)
            )
            if not count:
                await c.execute(
                    update(conversations)
                    .where(conversations.c.id == cid)
                    .values(title=request["content"][:70].strip())
                )
            await c.execute(
                messages.insert().values(
                    id=str(uuid.uuid4()),
                    conversation_id=cid,
                    role="user",
                    content=request["content"],
                    created=now,
                )
            )
        return row, True

    async def run_for_request(self, owner, request_key):
        async with self.engine.connect() as c:
            row = (
                (
                    await c.execute(
                        select(runs).where(
                            runs.c.owner_id == owner, runs.c.request_key == request_key
                        )
                    )
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    async def get_run(self, owner, rid):
        async with self.engine.connect() as c:
            row = (
                (
                    await c.execute(
                        select(runs).where(runs.c.id == rid, runs.c.owner_id == owner)
                    )
                )
                .mappings()
                .first()
            )
        if not row:
            raise StoreError("Run not found", 404)
        return dict(row)

    async def recent_documents(self, owner, cid):
        async with self.engine.connect() as c:
            requests = (
                (
                    await c.execute(
                        select(runs.c.request)
                        .where(runs.c.owner_id == owner, runs.c.conversation_id == cid)
                        .order_by(runs.c.created.desc())
                        .limit(8)
                    )
                )
                .scalars()
                .all()
            )
        result, seen = [], set()
        for request in requests:
            for doc in request.get("documents", []):
                digest = hashlib.sha256(doc["text"].encode()).hexdigest()
                if digest not in seen:
                    result.append(doc)
                    seen.add(digest)
        return result[:3]

    async def _event(self, c, rid, kind, data):
        seq = (
            await c.execute(
                update(runs)
                .where(runs.c.id == rid)
                .values(event_seq=runs.c.event_seq + 1, updated=time.time())
                .returning(runs.c.event_seq)
            )
        ).scalar_one()
        await c.execute(
            events.insert().values(
                run_id=rid, seq=seq, kind=kind, data=data, created=time.time()
            )
        )

    async def emit(self, rid, kind, data):
        async with self.engine.begin() as c:
            await self._event(c, rid, kind, data)

    async def checkpoint(self, rid, result):
        async with self.engine.begin() as c:
            await c.execute(
                update(runs)
                .where(runs.c.id == rid, runs.c.status.not_in(TERMINAL))
                .values(status="running", result=result, updated=time.time())
            )

    async def finish(self, rid, status, result):
        async with self.engine.begin() as c:
            row = (
                await c.execute(
                    update(runs)
                    .where(runs.c.id == rid, runs.c.status.not_in(TERMINAL))
                    .values(status=status, result=result, updated=time.time())
                    .returning(runs.c.conversation_id)
                )
            ).first()
            if not row:
                return
            cid = row[0]
            if result.get("content"):
                await c.execute(
                    messages.insert().values(
                        id=str(uuid.uuid4()),
                        conversation_id=cid,
                        role="assistant",
                        content=result["content"],
                        result=result,
                        created=time.time(),
                    )
                )
            await c.execute(
                update(conversations)
                .where(conversations.c.id == cid, conversations.c.active_run_id == rid)
                .values(active_run_id=None, updated=time.time())
            )
            await self._event(c, rid, "finished", {"status": status, "result": result})

    async def events_after(self, rid, after):
        async with self.engine.connect() as c:
            rows = (
                (
                    await c.execute(
                        select(events)
                        .where(events.c.run_id == rid, events.c.seq > after)
                        .order_by(events.c.seq)
                        .limit(100)
                    )
                )
                .mappings()
                .all()
            )
        return [dict(r) for r in rows]

    async def recover_interrupted(self):
        async with self.engine.connect() as c:
            unfinished = (
                (await c.execute(select(runs).where(runs.c.status.not_in(TERMINAL))))
                .mappings()
                .all()
            )
        for row in unfinished:
            result = dict(row["result"] or {})
            result.update(
                status="interrupted",
                notice="The server restarted. Your saved progress is available; send the question again to continue.",
            )
            await self.finish(row["id"], "interrupted", result)

    async def feedback(self, owner, rid, value):
        async with self.engine.begin() as c:
            result = await c.execute(
                update(runs)
                .where(
                    runs.c.id == rid,
                    runs.c.owner_id == owner,
                    runs.c.status.in_(TERMINAL),
                )
                .values(feedback=value)
            )
            if not result.rowcount:
                raise StoreError("Completed run not found", 404)

    async def telemetry(self, owner):
        async with self.engine.connect() as c:
            rows = (
                (
                    await c.execute(
                        select(runs.c.status, runs.c.result, runs.c.feedback)
                        .where(runs.c.owner_id == owner)
                        .order_by(runs.c.created.desc())
                        .limit(100)
                    )
                )
                .mappings()
                .all()
            )
        return {
            "runs": len(rows),
            "complete": sum(r["status"] == "complete" for r in rows),
            "positive_feedback": sum(r["feedback"] == 1 for r in rows),
            "tokens": sum(
                (r["result"] or {}).get("usage", {}).get("total_tokens", 0)
                for r in rows
            ),
        }
