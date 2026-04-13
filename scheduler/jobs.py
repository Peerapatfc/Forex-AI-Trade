import logging

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from data.fetcher import run_fetch_cycle

logger = logging.getLogger(__name__)


def create_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler()

    for timeframe, interval_minutes in [("15m", 15), ("1H", 60)]:
        scheduler.add_job(
            run_fetch_cycle,
            trigger="interval",
            minutes=interval_minutes,
            id=f"fetch_{timeframe}",
            kwargs={
                "db_path": config.DB_PATH,
                "api_key": config.ALPHA_VANTAGE_API_KEY,
                "pair": config.PAIR,
                "timeframe": timeframe,
            },
            misfire_grace_time=interval_minutes * 30,
        )
        logger.info(
            "Scheduled %s %s job every %d minutes",
            config.PAIR, timeframe, interval_minutes,
        )

    return scheduler
