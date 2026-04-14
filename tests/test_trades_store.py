import pytest
from storage import store


_SIGNAL = {
    "pair": "EURUSD", "timeframe": "15m", "timestamp": 1705334400,
    "created_at": 1705334500, "direction": "BUY", "confidence": 0.75,
    "sl_pips": 15.0, "tp_pips": 30.0, "claude_direction": "BUY",
    "claude_confidence": 0.78, "gemini_direction": "BUY",
    "gemini_confidence": 0.72, "reasoning": "test",
}


def _trade(signal_id: int) -> dict:
    return {
        "pair": "EURUSD", "timeframe": "15m", "signal_id": signal_id,
        "direction": "BUY", "entry_price": 1.0850,
        "sl_price": 1.0835, "tp_price": 1.0880,
        "lot_size": 0.67, "sl_pips": 15.0, "tp_pips": 30.0,
        "opened_at": 1705334600,
    }


def test_seed_account_sets_initial_balance(db_path):
    store.seed_account(db_path, 10000.0)
    assert store.get_account_balance(db_path) == pytest.approx(10000.0)


def test_seed_account_is_idempotent(db_path):
    store.seed_account(db_path, 10000.0)
    store.seed_account(db_path, 99999.0)
    assert store.get_account_balance(db_path) == pytest.approx(10000.0)


def test_get_account_balance_returns_zero_if_not_seeded(db_path):
    assert store.get_account_balance(db_path) == pytest.approx(0.0)


def test_update_account_balance(db_path):
    store.seed_account(db_path, 10000.0)
    store.update_account_balance(db_path, 10500.0)
    assert store.get_account_balance(db_path) == pytest.approx(10500.0)


def test_write_trade_returns_row_id(db_path):
    signal_id = store.write_signal(db_path, _SIGNAL)
    row_id = store.write_trade(db_path, _trade(signal_id))
    assert isinstance(row_id, int) and row_id > 0


def test_get_open_trades_returns_only_open(db_path):
    signal_id = store.write_signal(db_path, _SIGNAL)
    store.write_trade(db_path, _trade(signal_id))
    df = store.get_open_trades(db_path, "EURUSD")
    assert len(df) == 1
    assert df.iloc[0]["status"] == "open"


def test_get_open_trades_filters_by_pair(db_path):
    signal_id = store.write_signal(db_path, _SIGNAL)
    store.write_trade(db_path, _trade(signal_id))
    df = store.get_open_trades(db_path, "GBPUSD")
    assert len(df) == 0


def test_close_trade_updates_all_fields(db_path):
    signal_id = store.write_signal(db_path, _SIGNAL)
    trade_id = store.write_trade(db_path, _trade(signal_id))
    store.close_trade(db_path, trade_id, 1.0880, "tp", 30.0, 201.0)
    assert len(store.get_open_trades(db_path, "EURUSD")) == 0
    closed = store.get_closed_trades(db_path, "EURUSD", 1)
    assert len(closed) == 1
    row = closed.iloc[0]
    assert row["close_reason"] == "tp"
    assert row["close_price"] == pytest.approx(1.0880)
    assert row["pnl_pips"] == pytest.approx(30.0)
    assert row["pnl_usd"] == pytest.approx(201.0)
    assert row["status"] == "closed"


def test_close_trade_is_idempotent(db_path):
    signal_id = store.write_signal(db_path, _SIGNAL)
    trade_id = store.write_trade(db_path, _trade(signal_id))
    store.close_trade(db_path, trade_id, 1.0880, "tp", 30.0, 201.0)
    store.close_trade(db_path, trade_id, 1.0900, "tp2", 99.0, 999.0)  # should be no-op
    row = store.get_closed_trades(db_path, "EURUSD", 1).iloc[0]
    assert row["close_price"] == pytest.approx(1.0880)
    assert row["pnl_usd"] == pytest.approx(201.0)
    assert row["close_reason"] == "tp"


def test_get_closed_trades_excludes_open(db_path):
    signal_id = store.write_signal(db_path, _SIGNAL)
    store.write_trade(db_path, _trade(signal_id))
    assert len(store.get_closed_trades(db_path, "EURUSD", 10)) == 0
