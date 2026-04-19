"""Tests for LiveBroker — MT5 is fully mocked, no real MT5 connection required."""
import sys
import types
import pytest
from unittest.mock import MagicMock, patch, call

from storage import store


# ---------------------------------------------------------------------------
# Helpers to build trade / signal fixtures
# ---------------------------------------------------------------------------

_SIGNAL = {
    "pair": "EURUSD", "timeframe": "15m", "timestamp": 1705334400,
    "created_at": 1705334500, "direction": "BUY", "confidence": 0.75,
    "sl_pips": 15.0, "tp_pips": 30.0, "claude_direction": "BUY",
    "claude_confidence": 0.78, "gemini_direction": "BUY",
    "gemini_confidence": 0.72, "reasoning": "test",
}


def _make_trade(signal_id: int, direction: str = "BUY") -> dict:
    return {
        "pair": "EURUSD", "timeframe": "15m", "signal_id": signal_id,
        "direction": direction, "entry_price": 1.0850,
        "sl_price": 1.0835, "tp_price": 1.0880,
        "lot_size": 0.67, "sl_pips": 15.0, "tp_pips": 30.0,
        "opened_at": 1705334600,
    }


# ---------------------------------------------------------------------------
# MT5 mock factory
# ---------------------------------------------------------------------------

def _make_mt5_mock(
    initialize_ok: bool = True,
    login_ok: bool = True,
    order_retcode: int = None,          # None → use TRADE_RETCODE_DONE
    order_result_none: bool = False,    # True → order_send returns None
    position_type: int = None,          # None → POSITION_TYPE_BUY
    no_open_position: bool = False,     # True → positions_get returns ()
    close_retcode: int = None,          # None → use TRADE_RETCODE_DONE
    close_result_none: bool = False,    # True → close order_send returns None
    account_info_none: bool = False,
    equity: float = 10000.0,
) -> MagicMock:
    mt5 = MagicMock()

    # Constants
    mt5.TRADE_RETCODE_DONE = 10009
    mt5.ORDER_TYPE_BUY = 0
    mt5.ORDER_TYPE_SELL = 1
    mt5.TRADE_ACTION_DEAL = 1
    mt5.ORDER_TIME_GTC = 0
    mt5.ORDER_FILLING_IOC = 1
    mt5.POSITION_TYPE_BUY = 0
    mt5.POSITION_TYPE_SELL = 1

    # Connection
    mt5.initialize.return_value = initialize_ok
    mt5.login.return_value = login_ok
    mt5.last_error.return_value = (1, "mock error")
    mt5.shutdown.return_value = None

    # Tick
    tick = MagicMock()
    tick.ask = 1.0851
    tick.bid = 1.0849
    mt5.symbol_info_tick.return_value = tick

    # Build open result
    if order_result_none:
        open_result = None
    else:
        open_result = MagicMock()
        open_result.retcode = mt5.TRADE_RETCODE_DONE if order_retcode is None else order_retcode
        open_result.order = 12345

    # Build close result
    if close_result_none:
        close_result = None
    else:
        close_result = MagicMock()
        close_result.retcode = mt5.TRADE_RETCODE_DONE if close_retcode is None else close_retcode
        close_result.order = 12346

    # Distinguish open vs close calls by the presence of the "position" key in the
    # request dict (close orders always carry a position ticket, open orders do not).
    def _order_send_side_effect(request):
        if "position" in request:
            return close_result
        return open_result

    mt5.order_send.side_effect = _order_send_side_effect

    # positions_get
    if no_open_position:
        mt5.positions_get.return_value = ()
    else:
        pos = MagicMock()
        pos.symbol = "EURUSD"
        pos.volume = 0.67
        pos.type = mt5.POSITION_TYPE_BUY if position_type is None else position_type
        mt5.positions_get.return_value = (pos,)

    # account_info
    if account_info_none:
        mt5.account_info.return_value = None
    else:
        acct = MagicMock()
        acct.equity = equity
        mt5.account_info.return_value = acct

    return mt5


# ---------------------------------------------------------------------------
# Context manager that patches MetaTrader5 in sys.modules and in live_broker
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def _patch_mt5(mt5_mock: MagicMock):
    """Replace the MetaTrader5 module everywhere for the duration of the block."""
    with patch.dict(sys.modules, {"MetaTrader5": mt5_mock}):
        # Re-import live_broker with the patched module
        import importlib
        import execution.live_broker as lb_mod
        old_mt5 = lb_mod.mt5
        lb_mod.mt5 = mt5_mock
        try:
            yield lb_mod
        finally:
            lb_mod.mt5 = old_mt5


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLiveBrokerConnect:
    def test_initialize_failure_raises(self, db_path):
        mt5_mock = _make_mt5_mock(initialize_ok=False)
        with _patch_mt5(mt5_mock) as lb_mod:
            with pytest.raises(RuntimeError, match="MT5 initialize failed"):
                lb_mod.LiveBroker(db_path, 123, "pw", "Demo-Server")

    def test_login_failure_raises(self, db_path):
        mt5_mock = _make_mt5_mock(login_ok=False)
        with _patch_mt5(mt5_mock) as lb_mod:
            with pytest.raises(RuntimeError, match="MT5 login failed"):
                lb_mod.LiveBroker(db_path, 123, "pw", "Demo-Server")
            mt5_mock.shutdown.assert_called_once()

    def test_successful_connect(self, db_path):
        mt5_mock = _make_mt5_mock()
        with _patch_mt5(mt5_mock) as lb_mod:
            broker = lb_mod.LiveBroker(db_path, 123, "pw", "Demo-Server")
        mt5_mock.initialize.assert_called_once()
        mt5_mock.login.assert_called_once_with(123, "pw", "Demo-Server")


class TestOpenTrade:
    def _broker_and_signal(self, db_path, mt5_mock, lb_mod):
        broker = lb_mod.LiveBroker(db_path, 123, "pw", "Demo-Server")
        signal_id = store.write_signal(db_path, _SIGNAL)
        return broker, signal_id

    def test_open_trade_calls_order_send(self, db_path):
        mt5_mock = _make_mt5_mock()
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, signal_id = self._broker_and_signal(db_path, mt5_mock, lb_mod)
            broker.open_trade(_make_trade(signal_id))
        mt5_mock.order_send.assert_called_once()
        request = mt5_mock.order_send.call_args[0][0]
        assert request["symbol"] == "EURUSD"
        assert request["type"] == mt5_mock.ORDER_TYPE_BUY
        assert request["magic"] == lb_mod.MT5_MAGIC

    def test_open_trade_writes_to_db(self, db_path):
        mt5_mock = _make_mt5_mock()
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, signal_id = self._broker_and_signal(db_path, mt5_mock, lb_mod)
            broker.open_trade(_make_trade(signal_id))
        open_trades = store.get_open_trades(db_path, "EURUSD")
        assert len(open_trades) == 1
        assert open_trades.iloc[0]["direction"] == "BUY"

    def test_open_trade_stores_ticket(self, db_path):
        mt5_mock = _make_mt5_mock()
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, signal_id = self._broker_and_signal(db_path, mt5_mock, lb_mod)
            broker.open_trade(_make_trade(signal_id))
        open_trades = store.get_open_trades(db_path, "EURUSD")
        trade_id = int(open_trades.iloc[0]["id"])
        ticket = store.get_trade_ticket(db_path, trade_id)
        assert ticket == 12345  # from mock open_result.order

    def test_open_trade_sell_uses_bid_price(self, db_path):
        mt5_mock = _make_mt5_mock()
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, signal_id = self._broker_and_signal(db_path, mt5_mock, lb_mod)
            broker.open_trade(_make_trade(signal_id, direction="SELL"))
        request = mt5_mock.order_send.call_args[0][0]
        assert request["type"] == mt5_mock.ORDER_TYPE_SELL
        assert request["price"] == 1.0849  # bid

    def test_open_trade_order_send_none_raises(self, db_path):
        mt5_mock = _make_mt5_mock(order_result_none=True)
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, signal_id = self._broker_and_signal(db_path, mt5_mock, lb_mod)
            with pytest.raises(RuntimeError, match="MT5 order_send failed"):
                broker.open_trade(_make_trade(signal_id))

    def test_open_trade_bad_retcode_raises(self, db_path):
        mt5_mock = _make_mt5_mock(order_retcode=10004)  # not DONE
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, signal_id = self._broker_and_signal(db_path, mt5_mock, lb_mod)
            with pytest.raises(RuntimeError, match="MT5 order_send failed"):
                broker.open_trade(_make_trade(signal_id))


class TestCloseTrade:
    def _setup(self, db_path, mt5_mock, lb_mod):
        broker = lb_mod.LiveBroker(db_path, 123, "pw", "Demo-Server")
        signal_id = store.write_signal(db_path, _SIGNAL)
        # Write trade directly to DB and set ticket manually
        trade_id = store.write_trade(db_path, _make_trade(signal_id))
        store.set_trade_ticket(db_path, trade_id, 12345)
        return broker, trade_id

    def test_close_trade_calls_order_send(self, db_path):
        mt5_mock = _make_mt5_mock()
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, trade_id = self._setup(db_path, mt5_mock, lb_mod)
            # Reset call count from open (there was no open_trade call here)
            mt5_mock.order_send.reset_mock()
            broker.close_trade(trade_id, 1.0880, "tp", 30.0, 201.0)
        mt5_mock.order_send.assert_called_once()
        request = mt5_mock.order_send.call_args[0][0]
        assert request["position"] == 12345
        assert request["type"] == mt5_mock.ORDER_TYPE_SELL  # closing BUY → SELL

    def test_close_trade_updates_db(self, db_path):
        mt5_mock = _make_mt5_mock()
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, trade_id = self._setup(db_path, mt5_mock, lb_mod)
            broker.close_trade(trade_id, 1.0880, "tp", 30.0, 201.0)
        closed = store.get_closed_trades(db_path, "EURUSD", 1)
        assert len(closed) == 1
        row = closed.iloc[0]
        assert row["close_reason"] == "tp"
        assert row["pnl_usd"] == pytest.approx(201.0)

    def test_close_trade_no_ticket_raises(self, db_path):
        mt5_mock = _make_mt5_mock()
        with _patch_mt5(mt5_mock) as lb_mod:
            broker = lb_mod.LiveBroker(db_path, 123, "pw", "Demo-Server")
            signal_id = store.write_signal(db_path, _SIGNAL)
            trade_id = store.write_trade(db_path, _make_trade(signal_id))
            # Do NOT set ticket
            with pytest.raises(RuntimeError, match="No MT5 ticket"):
                broker.close_trade(trade_id, 1.0880, "tp", 30.0, 201.0)

    def test_close_trade_position_not_found_skips_order_send(self, db_path):
        """If MT5 position is already gone, we skip order_send but still update DB."""
        mt5_mock = _make_mt5_mock(no_open_position=True)
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, trade_id = self._setup(db_path, mt5_mock, lb_mod)
            mt5_mock.order_send.reset_mock()
            broker.close_trade(trade_id, 1.0880, "tp", 30.0, 201.0)
        mt5_mock.order_send.assert_not_called()
        closed = store.get_closed_trades(db_path, "EURUSD", 1)
        assert len(closed) == 1

    def test_close_trade_sell_position_uses_ask(self, db_path):
        mt5_mock = _make_mt5_mock(position_type=1)  # POSITION_TYPE_SELL=1
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, trade_id = self._setup(db_path, mt5_mock, lb_mod)
            mt5_mock.order_send.reset_mock()
            broker.close_trade(trade_id, 1.0830, "tp", 20.0, 134.0)
        request = mt5_mock.order_send.call_args[0][0]
        assert request["type"] == mt5_mock.ORDER_TYPE_BUY
        assert request["price"] == 1.0851  # ask

    def test_close_trade_order_send_none_raises(self, db_path):
        mt5_mock = _make_mt5_mock(close_result_none=True, order_result_none=False)
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, trade_id = self._setup(db_path, mt5_mock, lb_mod)
            with pytest.raises(RuntimeError, match="MT5 close order failed"):
                broker.close_trade(trade_id, 1.0880, "tp", 30.0, 201.0)

    def test_close_trade_bad_retcode_raises(self, db_path):
        """Simulate close order_send returning bad retcode while open succeeds."""
        mt5_mock = _make_mt5_mock(close_retcode=10004)
        with _patch_mt5(mt5_mock) as lb_mod:
            broker, trade_id = self._setup(db_path, mt5_mock, lb_mod)
            with pytest.raises(RuntimeError, match="MT5 close order failed"):
                broker.close_trade(trade_id, 1.0880, "tp", 30.0, 201.0)


class TestGetBalance:
    def test_get_balance_returns_equity(self, db_path):
        mt5_mock = _make_mt5_mock(equity=12345.67)
        with _patch_mt5(mt5_mock) as lb_mod:
            broker = lb_mod.LiveBroker(db_path, 123, "pw", "Demo-Server")
            balance = broker.get_balance()
        assert balance == pytest.approx(12345.67)

    def test_get_balance_account_info_none_raises(self, db_path):
        mt5_mock = _make_mt5_mock(account_info_none=True)
        with _patch_mt5(mt5_mock) as lb_mod:
            broker = lb_mod.LiveBroker(db_path, 123, "pw", "Demo-Server")
            with pytest.raises(RuntimeError, match="MT5 account_info failed"):
                broker.get_balance()


class TestShutdown:
    def test_shutdown_calls_mt5_shutdown(self, db_path):
        mt5_mock = _make_mt5_mock()
        with _patch_mt5(mt5_mock) as lb_mod:
            broker = lb_mod.LiveBroker(db_path, 123, "pw", "Demo-Server")
            mt5_mock.shutdown.reset_mock()
            broker.shutdown()
        mt5_mock.shutdown.assert_called_once()


class TestStoreTicketFunctions:
    """Unit tests for the new store helper functions."""

    def test_set_and_get_trade_ticket(self, db_path):
        signal_id = store.write_signal(db_path, _SIGNAL)
        trade_id = store.write_trade(db_path, _make_trade(signal_id))
        store.set_trade_ticket(db_path, trade_id, 99999)
        assert store.get_trade_ticket(db_path, trade_id) == 99999

    def test_get_trade_ticket_returns_none_when_not_set(self, db_path):
        signal_id = store.write_signal(db_path, _SIGNAL)
        trade_id = store.write_trade(db_path, _make_trade(signal_id))
        assert store.get_trade_ticket(db_path, trade_id) is None

    def test_get_trade_ticket_nonexistent_trade_returns_none(self, db_path):
        assert store.get_trade_ticket(db_path, 9999) is None

    def test_overwrite_ticket(self, db_path):
        signal_id = store.write_signal(db_path, _SIGNAL)
        trade_id = store.write_trade(db_path, _make_trade(signal_id))
        store.set_trade_ticket(db_path, trade_id, 111)
        store.set_trade_ticket(db_path, trade_id, 222)
        assert store.get_trade_ticket(db_path, trade_id) == 222

    def test_set_trade_ticket_nonexistent_raises(self, db_path):
        with pytest.raises(RuntimeError, match="set_trade_ticket: trade 9999 not found"):
            store.set_trade_ticket(db_path, 9999, 12345)
