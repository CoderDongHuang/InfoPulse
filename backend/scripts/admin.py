"""Explicit local administrator promotion; public registration never promotes."""
import argparse
import asyncio
from sqlalchemy import func, select
from app.core.database import _get_sessionmaker
from app.models.user import User


async def promote(email: str) -> None:
    async with _get_sessionmaker()() as db:
        user = await db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
        if not user or not user.is_active:
            raise SystemExit("Register an active account first; no account was changed.")
        user.is_admin = True
        await db.commit()
        print("Administrator granted to the specified existing account.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    asyncio.run(promote(parser.parse_args().email))
