import os
from dotenv import load_dotenv

load_dotenv()

ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
DB_PATH: str = os.getenv("DB_PATH", "forex.db")
PAIR: str = "EURUSD"
TIMEFRAMES: list[str] = ["15m", "1H"]
BACKFILL_CANDLES: int = 200
