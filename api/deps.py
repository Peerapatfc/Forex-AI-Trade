import os
from dotenv import load_dotenv

load_dotenv()


def get_db_path() -> str:
    return os.getenv("DB_PATH", "forex.db")


def get_paper_balance() -> float:
    return float(os.getenv("PAPER_BALANCE", "10000.0"))
