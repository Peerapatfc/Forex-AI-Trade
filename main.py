import logging
import sys

import config
from data.fetcher import backfill
from execution.paper_broker import PaperBroker
from scheduler.jobs import create_scheduler
from storage import store

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
    if not config.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY is not set. Add it to .env")
        sys.exit(1)
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set. Add it to .env")
        sys.exit(1)
    if config.BROKER_MODE == "live":
        logger.error("BROKER_MODE=live is not yet implemented. Use BROKER_MODE=paper.")
        sys.exit(1)

    logger.info("Initialising database at %s", config.DB_PATH)
    store.init_db(config.DB_PATH)
    store.seed_account(config.DB_PATH, config.PAPER_BALANCE)
    logger.info("Paper account balance: $%.2f", store.get_account_balance(config.DB_PATH))

    logger.info("Backfilling history for %s...", config.PAIR)
    for timeframe in config.TIMEFRAMES:
        backfill(config.DB_PATH, config.ALPHA_VANTAGE_API_KEY, config.PAIR, timeframe)

    broker = PaperBroker(config.DB_PATH)
    logger.info("Starting scheduler. Press Ctrl+C to stop.")
    scheduler = create_scheduler(broker)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
