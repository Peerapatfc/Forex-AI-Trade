import pytest
import time
import pandas as pd
from unittest.mock import MagicMock, patch
from execution.executor import run_execution_cycle, SIGNAL_MAX_AGE_SECONDS


def _candle(high=1.0870, low=1.0840, close=1.0855, ts=None):
    ts = ts or int(time.time()) - 60
    return pd.DataFrame([{
        "id": 1, "pair": "EURUSD", "timeframe": "15m", "timestamp": ts,
        "open": 1.0850, "high": high, "low": low, "close": close, "volume": 1000.0,
    }])


def _signal(direction="BUY", sl=15.0, tp=30.0, ts=None):
    ts = ts or int(time.time()) - 60
    return pd.DataFrame([{
        "id": 1, "pair": "EURUSD", "timeframe": "15m", "timestamp": ts,
        "created_at": ts + 10, "direction": direction, "confidence": 0.75,
        "sl_pips": sl, "tp_pips": tp, "reasoning": "test",
        "claude_direction": direction, "claude_confidence": 0.75,
        "gemini_direction": direction, "gemini_confidence": 0.75,
    }])


def _open_trade(direction="BUY", sl_price=1.0835, tp_price=1.0880):
    return pd.DataFrame([{
        "id": 1, "pair": "EURUSD", "direction": direction,
        "entry_price": 1.0850, "sl_price": sl_price, "tp_price": tp_price,
        "lot_size": 0.67, "sl_pips": 15.0, "tp_pips": 30.0,
        "opened_at": int(time.time()) - 200, "status": "open",
    }])


def _mock_broker(balance=10000.0):
    broker = MagicMock()
    broker.get_balance.return_value = balance
    return broker


@patch("execution.executor.store")
def test_no_candles_skips_cycle(mock_store):
    mock_store.get_latest_candles.return_value = pd.DataFrame()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()
    broker.close_trade.assert_not_called()


@patch("execution.executor.store")
def test_no_signal_skips_open(mock_store):
    mock_store.get_latest_candles.return_value = _candle()
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = pd.DataFrame()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_stale_signal_skips_open(mock_store):
    stale_ts = int(time.time()) - SIGNAL_MAX_AGE_SECONDS - 100
    mock_store.get_latest_candles.return_value = _candle()
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(ts=stale_ts)
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_hold_signal_skips_open(mock_store):
    mock_store.get_latest_candles.return_value = _candle()
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="HOLD", sl=None, tp=None)
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_existing_open_trade_skips_new_open(mock_store):
    # Candle that does NOT trigger the open trade's SL or TP
    # open trade: sl_price=1.0835, tp_price=1.0880; candle: low=1.0840, high=1.0870 → no hit
    # get_open_trades is called twice: first for SL/TP check, then for one-trade-at-a-time guard
    mock_store.get_latest_candles.return_value = _candle(high=1.0870, low=1.0840)
    mock_store.get_open_trades.side_effect = [_open_trade(), _open_trade()]
    mock_store.get_latest_signals.return_value = _signal()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_null_sl_pips_skips_open(mock_store):
    mock_store.get_latest_candles.return_value = _candle()
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="BUY", sl=None, tp=None)
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_buy_signal_opens_trade_with_correct_prices(mock_store):
    mock_store.get_latest_candles.return_value = _candle(close=1.0855)
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="BUY", sl=15.0, tp=30.0)
    broker = _mock_broker(balance=10000.0)
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_called_once()
    trade = broker.open_trade.call_args[0][0]
    assert trade["direction"] == "BUY"
    assert trade["sl_price"] == pytest.approx(1.0855 - 15 * 0.0001, abs=1e-5)
    assert trade["tp_price"] == pytest.approx(1.0855 + 30 * 0.0001, abs=1e-5)
    assert trade["lot_size"] > 0


@patch("execution.executor.store")
def test_sell_signal_opens_trade_with_correct_prices(mock_store):
    mock_store.get_latest_candles.return_value = _candle(close=1.0855)
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="SELL", sl=15.0, tp=30.0)
    broker = _mock_broker(balance=10000.0)
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_called_once()
    trade = broker.open_trade.call_args[0][0]
    assert trade["direction"] == "SELL"
    assert trade["sl_price"] == pytest.approx(1.0855 + 15 * 0.0001, abs=1e-5)
    assert trade["tp_price"] == pytest.approx(1.0855 - 30 * 0.0001, abs=1e-5)


@patch("execution.executor.store")
def test_buy_sl_hit_closes_trade(mock_store):
    trade = _open_trade("BUY", sl_price=1.0835, tp_price=1.0880)
    # low=1.0830 goes below sl_price=1.0835 → SL hit
    mock_store.get_latest_candles.return_value = _candle(high=1.0845, low=1.0830, close=1.0832)
    mock_store.get_open_trades.side_effect = [trade, pd.DataFrame()]
    mock_store.get_latest_signals.return_value = pd.DataFrame()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.close_trade.assert_called_once()
    assert broker.close_trade.call_args[0][2] == "sl"


@patch("execution.executor.store")
def test_buy_tp_hit_closes_trade(mock_store):
    trade = _open_trade("BUY", sl_price=1.0835, tp_price=1.0880)
    # high=1.0885 goes above tp_price=1.0880 → TP hit
    mock_store.get_latest_candles.return_value = _candle(high=1.0885, low=1.0860, close=1.0882)
    mock_store.get_open_trades.side_effect = [trade, pd.DataFrame()]
    mock_store.get_latest_signals.return_value = pd.DataFrame()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.close_trade.assert_called_once()
    assert broker.close_trade.call_args[0][2] == "tp"


@patch("execution.executor.store")
def test_sl_takes_priority_over_tp_gap(mock_store):
    trade = _open_trade("BUY", sl_price=1.0835, tp_price=1.0880)
    # Both SL and TP hit in same candle (gap) — SL wins
    mock_store.get_latest_candles.return_value = _candle(high=1.0900, low=1.0820, close=1.0850)
    mock_store.get_open_trades.side_effect = [trade, pd.DataFrame()]
    mock_store.get_latest_signals.return_value = pd.DataFrame()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.close_trade.assert_called_once()
    assert broker.close_trade.call_args[0][2] == "sl"


@patch("execution.executor.store")
def test_null_tp_pips_skips_open(mock_store):
    mock_store.get_latest_candles.return_value = _candle()
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="BUY", sl=15.0, tp=None)
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_zero_balance_skips_open(mock_store):
    mock_store.get_latest_candles.return_value = _candle()
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="BUY", sl=15.0, tp=30.0)
    broker = _mock_broker(balance=0.0)
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_zero_lot_size_skips_open(mock_store):
    # Balance of 1.0 with sl=10000 pips produces lot < 0.01 → zero lot size
    mock_store.get_latest_candles.return_value = _candle()
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="BUY", sl=10000.0, tp=20000.0)
    broker = _mock_broker(balance=1.0)
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_exception_logs_to_fetch_log_and_does_not_raise(mock_store):
    mock_store.get_latest_candles.side_effect = Exception("DB error")
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    mock_store.write_fetch_log.assert_called_once_with(
        "test.db", "EURUSD", "15m", "executor", "error", "DB error", None
    )
