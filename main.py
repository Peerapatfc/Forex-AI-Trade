import logging
import sys

import config
from data.fetcher import backfill
from scheduler.jobs import create_scheduler
from storage.store import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("forex_ai.log"),
    ],
)

logger = logging.getLogger(__name__)


def main() -> None:
    if not config.ALPHA_VANTAGE_API_KEY:
        logger.error(
            "ALPHA_VANTAGE_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )
        sys.exit(1)

    logger.info("Initialising database at %s", config.DB_PATH)
    init_db(config.DB_PATH)

    logger.info("Backfilling history for %s...", config.PAIR)
    for timeframe in config.TIMEFRAMES:
        backfill(config.DB_PATH, config.ALPHA_VANTAGE_API_KEY, config.PAIR, timeframe)

    logger.info("Starting scheduler. Press Ctrl+C to stop.")
    scheduler = create_scheduler()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
