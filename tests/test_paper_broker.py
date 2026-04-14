import pytest
from storage import store
from execution.paper_broker import PaperBroker


_SIGNAL = {
    "pair": "EURUSD", "timeframe": "15m", "timestamp": 1705334400,
    "created_at": 1705334500, "direction": "BUY", "confidence": 0.75,
    "sl_pips": 15.0, "tp_pips": 30.0, "claude_direction": "BUY",
    "claude_confidence": 0.78, "gemini_direction": "BUY",
    "gemini_confidence": 0.72, "reasoning": "test",
}


def _open_trade(signal_id: int, direction: str = "BUY") -> dict:
    return {
        "pair": "EURUSD", "timeframe": "15m", "signal_id": signal_id,
        "direction": direction, "entry_price": 1.0850,
        "sl_price": 1.0835, "tp_price": 1.0880,
        "lot_size": 0.67, "sl_pips": 15.0, "tp_pips": 30.0,
        "opened_at": 1705334600,
    }


def test_open_trade_writes_to_db(db_path):
    store.seed_account(db_path, 10000.0)
    broker = PaperBroker(db_path)
    signal_id = store.write_signal(db_path, _SIGNAL)
    broker.open_trade(_open_trade(signal_id))
    open_trades = store.get_open_trades(db_path, "EURUSD")
    assert len(open_trades) == 1
    assert open_trades.iloc[0]["direction"] == "BUY"


def test_get_balance_returns_seeded_amount(db_path):
    store.seed_account(db_path, 10000.0)
    broker = PaperBroker(db_path)
    assert broker.get_balance() == pytest.approx(10000.0)


def test_close_trade_on_tp_increases_balance(db_path):
    store.seed_account(db_path, 10000.0)
    broker = PaperBroker(db_path)
    signal_id = store.write_signal(db_path, _SIGNAL)
    broker.open_trade(_open_trade(signal_id))
    trade = store.get_open_trades(db_path, "EURUSD").iloc[0]
    # BUY TP hit: +30 pips * $10/lot * 0.67 lot = +$201
    pnl_pips, pnl_usd = 30.0, 30.0 * 10 * float(trade["lot_size"])
    broker.close_trade(int(trade["id"]), 1.0880, "tp", pnl_pips, pnl_usd)
    assert broker.get_balance() == pytest.approx(10000.0 + pnl_usd)
    closed = store.get_closed_trades(db_path, "EURUSD", 1)
    assert closed.iloc[0]["close_reason"] == "tp"


def test_close_trade_on_sl_reduces_balance(db_path):
    store.seed_account(db_path, 10000.0)
    broker = PaperBroker(db_path)
    signal_id = store.write_signal(db_path, _SIGNAL)
    broker.open_trade(_open_trade(signal_id))
    trade = store.get_open_trades(db_path, "EURUSD").iloc[0]
    # BUY SL hit: -15 pips * $10/lot * 0.67 lot = -$100.5
    pnl_pips, pnl_usd = -15.0, -15.0 * 10 * float(trade["lot_size"])
    broker.close_trade(int(trade["id"]), 1.0835, "sl", pnl_pips, pnl_usd)
    assert broker.get_balance() == pytest.approx(10000.0 + pnl_usd)
    closed = store.get_closed_trades(db_path, "EURUSD", 1)
    assert closed.iloc[0]["close_reason"] == "sl"
