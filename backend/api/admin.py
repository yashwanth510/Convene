"""Read-only administration; access is checked on every request."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import Integer, cast, func, select

from backend.api.auth import current_admin
from backend.storage.database import conversations, runs, usage_entries, users, stamp

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("/overview")
async def overview(
    request: Request,
    response: Response,
    days: int = Query(default=30),
    page: int = Query(default=1, ge=1, le=100000),
):
    if days not in (7, 30, 90):
        raise HTTPException(422, "Choose a 7, 30, or 90 day period")
    response.headers["Cache-Control"] = "no-store"
    now = time.time()
    # Include today and the preceding N-1 UTC calendar days.
    first_day = int(now // 86400) - days + 1
    since = first_day * 86400
    async with request.app.state.db.engine.connect() as c:

        async def count(table, *conditions):
            return (
                await c.execute(
                    select(func.count()).select_from(table).where(*conditions)
                )
            ).scalar_one()

        total_users = await count(users)
        signups = await count(users, users.c.created >= since)
        total_conversations = await count(conversations)
        submitted = await count(usage_entries, usage_entries.c.created >= since)
        active = (
            await c.execute(
                select(func.count(func.distinct(usage_entries.c.owner_id))).where(
                    usage_entries.c.created >= since
                )
            )
        ).scalar_one()
        statuses = dict(
            (
                await c.execute(
                    select(runs.c.status, func.count())
                    .where(runs.c.created >= since)
                    .group_by(runs.c.status)
                )
            ).all()
        )
        tokens = (
            await c.execute(
                select(
                    func.coalesce(
                        func.sum(runs.c.result["usage"]["total_tokens"].as_integer()), 0
                    )
                ).where(runs.c.created >= since)
            )
        ).scalar_one()
        day = cast(func.floor(users.c.created / 86400), Integer)
        daily = dict(
            (
                await c.execute(
                    select(day, func.count())
                    .where(users.c.created >= since)
                    .group_by(day)
                )
            ).all()
        )
        last_active = (
            select(
                usage_entries.c.owner_id,
                func.max(usage_entries.c.created).label("last_active"),
            )
            .group_by(usage_entries.c.owner_id)
            .subquery()
        )
        rows = (
            (
                await c.execute(
                    select(
                        users.c.id,
                        users.c.email,
                        users.c.created,
                        last_active.c.last_active,
                    )
                    .outerjoin(last_active, users.c.id == last_active.c.owner_id)
                    .order_by(users.c.created.desc(), users.c.id)
                    .offset((page - 1) * 20)
                    .limit(20)
                )
            )
            .mappings()
            .all()
        )
    return {
        "generated_at": stamp(now),
        "days": days,
        "since": stamp(since),
        "total_users": total_users,
        "signups": signups,
        "total_conversations": total_conversations,
        "active_users": active,
        "submitted_runs": submitted,
        "run_statuses": statuses,
        "recorded_tokens": tokens,
        "daily_signups": [
            {
                "date": datetime.fromtimestamp(d * 86400, timezone.utc)
                .date()
                .isoformat(),
                "count": daily.get(d, 0),
            }
            for d in range(first_day, first_day + days)
        ],
        "users": [
            {
                "id": row["id"],
                "email": row["email"],
                "created": stamp(row["created"]),
                "last_active": stamp(row["last_active"])
                if row["last_active"] is not None
                else None,
            }
            for row in rows
        ],
        "page": page,
        "page_size": 20,
    }
