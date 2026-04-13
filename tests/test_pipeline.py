import sqlite3
import pytest
from storage import store


def test_init_db_creates_tables(db_path):
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert {"candles", "indicators", "fetch_log"} <= tables


def test_write_candle_returns_row_id(db_path):
    candle = {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
              "low": 1.084, "close": 1.0855, "volume": 1000.0}
    row_id = store.write_candle(db_path, "EURUSD", "15m", candle)
    assert isinstance(row_id, int)
    assert row_id > 0


def test_write_candle_duplicate_returns_none(db_path):
    candle = {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
              "low": 1.084, "close": 1.0855, "volume": 1000.0}
    store.write_candle(db_path, "EURUSD", "15m", candle)
    second = store.write_candle(db_path, "EURUSD", "15m", candle)
    assert second is None


def test_write_indicators_stores_all_fields(db_path):
    candle = {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
              "low": 1.084, "close": 1.0855, "volume": 1000.0}
    candle_id = store.write_candle(db_path, "EURUSD", "15m", candle)
    ind = {"ema20": 1.0850, "ema50": 1.0840, "ema200": 1.0830,
           "rsi14": 55.0, "macd": 0.0003, "macd_signal": 0.0002, "macd_hist": 0.0001,
           "bb_upper": 1.0870, "bb_mid": 1.0855, "bb_lower": 1.0840,
           "atr14": 0.0008, "stoch_k": 60.0, "stoch_d": 58.0}
    store.write_indicators(db_path, candle_id, ind)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT * FROM indicators WHERE candle_id=?", (candle_id,)).fetchone()
    conn.close()
    assert row is not None
    assert abs(row[2] - 1.0850) < 1e-6  # ema20 is column index 2


def test_write_fetch_log_stores_entry(db_path):
    store.write_fetch_log(db_path, "EURUSD", "15m", "alpha_vantage", "ok", None, 312)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT provider, status, duration_ms FROM fetch_log").fetchone()
    conn.close()
    assert row == ("alpha_vantage", "ok", 312)
