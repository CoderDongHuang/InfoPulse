from __future__ import annotations
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import get_settings
from app.core.database import _get_sessionmaker, close_db
from app.services.retention import apply_retention


async def main():
    async with _get_sessionmaker()() as db:
        result = await apply_retention(db, get_settings().DATA_RETENTION_DAYS)
        await db.commit()
        print(result)
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
