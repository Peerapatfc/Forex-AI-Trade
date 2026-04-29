import pytest
import pandas as pd
from storage import store


_SIGNAL = {
    "pair": "EURUSD",
    "timeframe": "15m",
    "timestamp": 1705334400,
    "created_at": 1705334500,
    "direction": "BUY",
    "confidence": 0.75,
    "sl_pips": 15.0,
    "tp_pips": 30.0,
    "claude_direction": "BUY",
    "claude_confidence": 0.78,
    "gemini_direction": "BUY",
    "gemini_confidence": 0.72,
    "reasoning": "Strong upward momentum",
}


def test_write_signal_returns_row_id(db_path):
    row_id = store.write_signal(db_path, _SIGNAL)
    assert isinstance(row_id, int) and row_id > 0


def test_write_signal_duplicate_returns_none(db_path):
    store.write_signal(db_path, _SIGNAL)
    assert store.write_signal(db_path, _SIGNAL) is None


def test_write_signal_hold_allows_null_sl_tp(db_path):
    signal = {**_SIGNAL, "timestamp": 1705334401, "direction": "HOLD",
              "confidence": 0.0, "sl_pips": None, "tp_pips": None,
              "claude_direction": "BUY", "gemini_direction": "SELL",
              "reasoning": "Models disagreed: claude=BUY, gemini=SELL"}
    row_id = store.write_signal(db_path, signal)
    assert row_id is not None


def test_get_latest_signals_returns_dataframe(db_path):
    for i in range(3):
        store.write_signal(db_path, {**_SIGNAL, "timestamp": 1705334400 + i * 900,
                                      "created_at": 1705334500 + i * 900})
    df = store.get_latest_signals(db_path, "EURUSD", "15m", 2)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df["timestamp"].is_monotonic_increasing


def test_get_latest_signals_sorted_oldest_first(db_path):
    for i in range(5):
        store.write_signal(db_path, {**_SIGNAL, "timestamp": 1705334400 + i * 900,
                                      "created_at": 1705334500 + i * 900})
    df = store.get_latest_signals(db_path, "EURUSD", "15m", 5)
    assert list(df["timestamp"]) == sorted(df["timestamp"])


def test_get_latest_signals_respects_pair_and_timeframe(db_path):
    store.write_signal(db_path, {**_SIGNAL, "timeframe": "1H", "timestamp": 9999999})
    df = store.get_latest_signals(db_path, "EURUSD", "15m", 10)
    assert len(df) == 0


def test_write_signal_stores_all_fields(db_path):
    import psycopg2
    store.write_signal(db_path, _SIGNAL)
    conn = psycopg2.connect(db_path)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT direction FROM signals WHERE timestamp = %s",
                        (_SIGNAL["timestamp"],))
            row = cur.fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == "BUY"
