import os
import pytest
import psycopg2
from storage.store import init_db

_TABLES = ["indicators", "fetch_log", "signals", "trades", "stats", "account", "candles"]


@pytest.fixture
def db_path():
    url = os.environ["DATABASE_URL"]
    init_db(url)
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            for table in _TABLES:
                cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
        conn.commit()
    finally:
        conn.close()
    yield url
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            for table in _TABLES:
                cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
        conn.commit()
    finally:
        conn.close()
