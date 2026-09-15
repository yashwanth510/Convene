"""Import original JSON conversations into an explicitly chosen existing account.
Run: python -m scripts.import_legacy --email you@example.com
Original files are never changed. Existing conversation IDs are skipped.
"""

import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path
from sqlalchemy import select
from backend.config import config
from backend.storage.database import Database, users, conversations, messages


async def main(email, folder):
    db = Database(config.DATABASE_URL)
    try:
        await db.initialize()
        async with db.engine.connect() as c:
            owner = await c.scalar(
                select(users.c.id).where(users.c.email == email.strip().lower())
            )
        if not owner:
            raise SystemExit(
                "Create this account in Convene before importing its conversations."
            )
        imported = skipped = 0
        for path in sorted(Path(folder).glob("*.json")):
            raw = json.loads(path.read_text())
            cid = str(uuid.UUID(raw["id"]))
            async with db.engine.begin() as c:
                if await c.scalar(
                    select(conversations.c.id).where(conversations.c.id == cid)
                ):
                    skipped += 1
                    continue
                await c.execute(
                    conversations.insert().values(
                        id=cid,
                        owner_id=owner,
                        title=raw.get("title", "Imported conversation"),
                        created=time.time(),
                        updated=time.time(),
                    )
                )
                for i, m in enumerate(raw.get("messages", [])):
                    result = None
                    if m.get("debate_result"):
                        result = {
                            "content": m.get("content", ""),
                            "status": "imported",
                            "notice": "Imported from the original app. Legacy confidence and verification scores are not treated as verified evidence.",
                            "sources": [],
                            "positions": [],
                            "evidence": {"status": "unknown", "claims": []},
                        }
                    await c.execute(
                        messages.insert().values(
                            id=str(uuid.uuid4()),
                            conversation_id=cid,
                            role=m["role"],
                            content=m.get("content", ""),
                            created=time.time() + i * 0.001,
                            result=result,
                        )
                    )
                imported += 1
        print(
            f"Imported {imported} conversations; skipped {skipped} existing IDs. Original files preserved."
        )
    finally:
        await db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--folder", default="data/conversations")
    args = parser.parse_args()
    asyncio.run(main(args.email, args.folder))
