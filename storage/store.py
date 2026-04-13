import sqlite3
import time
from pathlib import Path

import pandas as pd

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    conn.close()


def write_candle(db_path: str, pair: str, timeframe: str, candle: dict) -> int | None:
    """Insert a candle. Returns new row id, or None if a duplicate (same pair/timeframe/timestamp)."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO candles "
            "(pair, timeframe, timestamp, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pair, timeframe, candle["timestamp"], candle["open"], candle["high"],
             candle["low"], candle["close"], candle["volume"]),
        )
        conn.commit()
        return cur.lastrowid if cur.rowcount > 0 else None
    finally:
        conn.close()


def write_indicators(db_path: str, candle_id: int, ind: dict) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO indicators "
            "(candle_id, ema20, ema50, ema200, rsi14, macd, macd_signal, macd_hist, "
            "bb_upper, bb_mid, bb_lower, atr14, stoch_k, stoch_d) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                candle_id,
                ind.get("ema20"), ind.get("ema50"), ind.get("ema200"),
                ind.get("rsi14"),
                ind.get("macd"), ind.get("macd_signal"), ind.get("macd_hist"),
                ind.get("bb_upper"), ind.get("bb_mid"), ind.get("bb_lower"),
                ind.get("atr14"),
                ind.get("stoch_k"), ind.get("stoch_d"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def write_fetch_log(
    db_path: str,
    pair: str,
    timeframe: str,
    provider: str,
    status: str,
    error_msg: str | None = None,
    duration_ms: int | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO fetch_log (timestamp, pair, timeframe, provider, status, error_msg, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (int(time.time()), pair, timeframe, provider, status, error_msg, duration_ms),
        )
        conn.commit()
    finally:
        conn.close()
