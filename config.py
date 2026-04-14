import os
from dotenv import load_dotenv

load_dotenv()

ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
DB_PATH: str = os.getenv("DB_PATH", "forex.db")
PAIR: str = "EURUSD"
TIMEFRAMES: list[str] = ["15m", "1H"]
BACKFILL_CANDLES: int = 200

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
