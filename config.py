import os
from dotenv import load_dotenv

load_dotenv()

# Data provider
ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# Trading parameters
PAIR: str = "EURUSD"
TIMEFRAMES: list[str] = ["15m", "1H"]
BACKFILL_CANDLES: int = 200
RISK_PCT: float = float(os.getenv("RISK_PCT", "0.01"))  # 1% risk per trade

# AI models
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Broker
BROKER_MODE: str = os.getenv("BROKER_MODE", "paper")
PAPER_BALANCE: float = float(os.getenv("PAPER_BALANCE", "10000.0"))

# MT5 live broker credentials
MT5_LOGIN: int | None = int(os.getenv("MT5_LOGIN")) if os.getenv("MT5_LOGIN") else None
MT5_PASSWORD: str = os.getenv("MT5_PASSWORD", "")
MT5_SERVER: str = os.getenv("MT5_SERVER", "")

# Alerting
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_TO: str = os.getenv("SMTP_TO", "")
