"""Create the initial Convene schema without printing database credentials."""

import asyncio
from backend.config import config
from backend.storage.database import Database


async def main():
    db = Database(config.DATABASE_URL)
    try:
        await db.initialize()
        print("Convene database schema is ready.")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
