import logging

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from ai.analyzer import run_analysis_cycle
from data.fetcher import run_fetch_cycle
from execution.broker import Broker
from execution.executor import run_execution_cycle
from performance.stats import run_stats_cycle

logger = logging.getLogger(__name__)


def create_scheduler(broker: Broker) -> BlockingScheduler:
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
            misfire_grace_time=interval_minutes * 60,
        )
        logger.info(
            "Scheduled %s %s fetch job every %d minutes",
            config.PAIR, timeframe, interval_minutes,
        )

    scheduler.add_job(
        run_analysis_cycle,
        trigger="interval",
        minutes=15,
        id="analyze_15m",
        kwargs={
            "db_path": config.DB_PATH,
            "pair": config.PAIR,
            "timeframe": "15m",
        },
        misfire_grace_time=15 * 60,
    )
    logger.info("Scheduled %s 15m analysis job every 15 minutes", config.PAIR)

    scheduler.add_job(
        run_execution_cycle,
        trigger="interval",
        minutes=15,
        id="execute_15m",
        kwargs={
            "db_path": config.DB_PATH,
            "pair": config.PAIR,
            "timeframe": "15m",
            "broker": broker,
            "risk_pct": config.RISK_PCT,
        },
        misfire_grace_time=15 * 60,
    )
    logger.info("Scheduled %s 15m execution job every 15 minutes", config.PAIR)

    scheduler.add_job(
        run_stats_cycle,
        trigger="interval",
        minutes=15,
        id="stats_15m",
        kwargs={"db_path": config.DB_PATH, "pair": config.PAIR},
        misfire_grace_time=15 * 60,
    )
    logger.info("Scheduled %s 15m stats job every 15 minutes", config.PAIR)

    return scheduler
