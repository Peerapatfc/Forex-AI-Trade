import os
from dotenv import load_dotenv

load_dotenv()

# Data provider
ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
DB_PATH: str = os.getenv("DB_PATH", "forex.db")

# Trading parameters
PAIR: str = "EURUSD"
TIMEFRAMES: list[str] = ["15m", "1H"]
BACKFILL_CANDLES: int = 200
RISK_PCT: float = float(os.getenv("RISK_PCT", "0.01"))  # 1% risk per trade

# AI models
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Broker
BROKER_MODE: str = os.getenv("BROKER_MODE", "paper")
PAPER_BALANCE: float = float(os.getenv("PAPER_BALANCE", "10000.0"))

# MT5 live broker credentials
MT5_LOGIN: int = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD: str = os.getenv("MT5_PASSWORD", "")
MT5_SERVER: str = os.getenv("MT5_SERVER", "")
