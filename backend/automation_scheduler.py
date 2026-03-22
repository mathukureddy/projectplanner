import asyncio
import os

from db import get_database
from automation_logic import is_automation_enabled, scan_overdue_alerts_for_projects


def scheduler_enabled() -> bool:
    # Avoid background loops during unit tests.
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return os.getenv("AUTOMATION_SCHEDULER_ENABLED", "true").lower() == "true"


async def overdue_automation_loop(interval_seconds: int) -> None:
    """
    Background loop for time-based triggers (overdue alerts).
    """
    while True:
        db = get_database()

        enabled_projects: list[str] = []
        async for pdoc in db["projects"].find():
            if is_automation_enabled(pdoc, "overdue_alert"):
                enabled_projects.append(str(pdoc["_id"]))

        try:
            await scan_overdue_alerts_for_projects(db, enabled_projects)
        except Exception:
            # Best-effort: don't kill the loop if Mongo is temporarily unavailable.
            pass

        await asyncio.sleep(interval_seconds)


def get_interval_seconds() -> int:
    try:
        return int(os.getenv("AUTOMATION_SCHEDULER_INTERVAL_SECONDS", "60"))
    except Exception:
        return 60


def start_overdue_scheduler(loop: asyncio.AbstractEventLoop) -> None:
    interval = get_interval_seconds()
    loop.create_task(overdue_automation_loop(interval))

