import os
from dotenv import load_dotenv

load_dotenv()


def get_db_url() -> str:
    return os.getenv("DATABASE_URL", "")


def get_paper_balance() -> float:
    return float(os.getenv("PAPER_BALANCE", "10000.0"))
