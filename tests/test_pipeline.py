import sqlite3
import pytest
import pandas as pd
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


def test_get_latest_candles_returns_dataframe(db_path):
    for i in range(5):
        store.write_candle(db_path, "EURUSD", "15m",
                           {"timestamp": 1705334400 + i * 900,
                            "open": 1.085, "high": 1.086, "low": 1.084,
                            "close": 1.0855, "volume": 1000.0})

    df = store.get_latest_candles(db_path, "EURUSD", "15m", 3)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert list(df.columns[:2]) == ["id", "pair"]
    assert df["timestamp"].is_monotonic_increasing


def test_get_latest_candles_respects_timeframe_filter(db_path):
    store.write_candle(db_path, "EURUSD", "15m",
                       {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
                        "low": 1.084, "close": 1.0855, "volume": 1000.0})
    store.write_candle(db_path, "EURUSD", "1H",
                       {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
                        "low": 1.084, "close": 1.0855, "volume": 1000.0})

    df_15m = store.get_latest_candles(db_path, "EURUSD", "15m", 10)
    df_1h = store.get_latest_candles(db_path, "EURUSD", "1H", 10)

    assert len(df_15m) == 1
    assert len(df_1h) == 1


def test_get_candle_with_indicators_returns_dict(db_path):
    candle = {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
              "low": 1.084, "close": 1.0855, "volume": 1000.0}
    candle_id = store.write_candle(db_path, "EURUSD", "15m", candle)
    store.write_indicators(db_path, candle_id,
                           {"ema20": 1.0850, "ema50": None, "ema200": None,
                            "rsi14": 55.0, "macd": None, "macd_signal": None, "macd_hist": None,
                            "bb_upper": None, "bb_mid": None, "bb_lower": None,
                            "atr14": 0.0008, "stoch_k": None, "stoch_d": None})

    result = store.get_candle_with_indicators(db_path, "EURUSD", "15m", 1705334400)

    assert isinstance(result, dict)
    assert result["pair"] == "EURUSD"
    assert result["close"] == pytest.approx(1.0855, abs=1e-6)
    assert result["ema20"] == pytest.approx(1.0850, abs=1e-6)


def test_get_latest_indicators_returns_dataframe(db_path):
    candle = {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
              "low": 1.084, "close": 1.0855, "volume": 1000.0}
    candle_id = store.write_candle(db_path, "EURUSD", "15m", candle)
    store.write_indicators(db_path, candle_id,
                           {"ema20": 1.085, "ema50": None, "ema200": None,
                            "rsi14": 55.0, "macd": None, "macd_signal": None, "macd_hist": None,
                            "bb_upper": None, "bb_mid": None, "bb_lower": None,
                            "atr14": 0.0008, "stoch_k": None, "stoch_d": None})

    df = store.get_latest_indicators(db_path, "EURUSD", "15m", 5)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert "ema20" in df.columns
    assert df["ema20"].iloc[0] == pytest.approx(1.085, abs=1e-6)


def test_get_candle_with_indicators_returns_empty_dict_for_missing(db_path):
    result = store.get_candle_with_indicators(db_path, "EURUSD", "15m", 9999999999)
    assert result == {}
