"""Dedicated production worker entrypoint."""
import argparse
import asyncio

import app.models  # noqa: F401
from app.core.database import close_db, init_db
from app.core.observability import configure_logging
from app.services.automation import scheduler_loop
from app.services.knowledge import knowledge_worker_loop
from app.services.orchestration import orchestration_worker_loop


async def run(role: str):
    configure_logging()
    await init_db()
    stop = asyncio.Event()
    tasks = []
    if role in {"scheduler", "all"}: tasks.append(asyncio.create_task(scheduler_loop(stop)))
    if role in {"knowledge", "all"}: tasks.append(asyncio.create_task(knowledge_worker_loop(stop)))
    if role in {"orchestration", "all"}: tasks.append(asyncio.create_task(orchestration_worker_loop(stop)))
    try:
        await asyncio.gather(*tasks)
    finally:
        stop.set()
        await close_db()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["scheduler", "knowledge", "orchestration", "all"], required=True)
    args = parser.parse_args()
    try: asyncio.run(run(args.role))
    except KeyboardInterrupt: pass


if __name__ == "__main__": main()
