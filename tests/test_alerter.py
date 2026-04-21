import logging
import smtplib
import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from alerts.alerter import Alerter
from execution.executor import run_execution_cycle
from tests.test_executor import _candle, _signal, _open_trade


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_alerter(
    tg_token="bot123",
    tg_chat="chat456",
    smtp_host="smtp.example.com",
    smtp_user="user@example.com",
    smtp_to="to@example.com",
    smtp_password="secret",
):
    return Alerter(
        telegram_token=tg_token,
        telegram_chat_id=tg_chat,
        smtp_host=smtp_host,
        smtp_user=smtp_user,
        smtp_to=smtp_to,
        smtp_password=smtp_password,
    )


def _telegram_only():
    return Alerter(telegram_token="tok", telegram_chat_id="cid")


def _email_only():
    return Alerter(smtp_host="smtp.example.com", smtp_user="u@x.com", smtp_to="t@x.com", smtp_password="secret")


def _no_config():
    return Alerter()


# ---------------------------------------------------------------------------
# send() — channel routing
# ---------------------------------------------------------------------------

@patch("alerts.alerter.requests.post")
def test_send_telegram_enabled_calls_requests_post(mock_post):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    alerter = _telegram_only()
    alerter.send("Subject", "Body")

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "sendMessage" in call_kwargs[0][0]


@patch("alerts.alerter.smtplib.SMTP")
def test_send_email_enabled_calls_smtp(mock_smtp_cls):
    smtp_instance = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=smtp_instance)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    alerter = _email_only()
    alerter.send("Subject", "Body")

    mock_smtp_cls.assert_called_once()


@patch("alerts.alerter.requests.post")
@patch("alerts.alerter.smtplib.SMTP")
def test_send_no_config_does_nothing(mock_smtp_cls, mock_post):
    alerter = _no_config()
    alerter.send("Subject", "Body")

    mock_post.assert_not_called()
    mock_smtp_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Failure resilience
# ---------------------------------------------------------------------------

@patch("alerts.alerter.requests.post", side_effect=Exception("network error"))
def test_send_telegram_failure_logs_and_does_not_raise(mock_post, caplog):
    alerter = _telegram_only()
    with caplog.at_level(logging.ERROR, logger="alerts.alerter"):
        alerter.send("Subject", "Body")  # must not raise
    assert any("Telegram alert failed" in r.message for r in caplog.records)


@patch("alerts.alerter.smtplib.SMTP", side_effect=Exception("connection refused"))
def test_send_email_failure_logs_and_does_not_raise(mock_smtp, caplog):
    alerter = _email_only()
    with caplog.at_level(logging.ERROR, logger="alerts.alerter"):
        alerter.send("Subject", "Body")  # must not raise
    assert any("Email alert failed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# alert_trade_opened
# ---------------------------------------------------------------------------

def test_alert_trade_opened_correct_subject_body():
    alerter = _no_config()
    sent = []
    alerter.send = lambda subject, body: sent.append((subject, body))

    trade = {
        "direction": "BUY",
        "pair": "EURUSD",
        "entry_price": 1.08550,
        "lot_size": 0.67,
        "sl_price": 1.08400,
        "tp_price": 1.08850,
    }
    alerter.alert_trade_opened(trade)

    assert len(sent) == 1
    subject, body = sent[0]
    assert subject == "Trade Opened: BUY EURUSD"
    assert "BUY" in body
    assert "EURUSD" in body
    assert "1.08550" in body
    assert "0.67" in body
    assert "1.08400" in body
    assert "1.08850" in body


# ---------------------------------------------------------------------------
# alert_trade_closed
# ---------------------------------------------------------------------------

def test_alert_trade_closed_win_shows_checkmark():
    alerter = _no_config()
    sent = []
    alerter.send = lambda subject, body: sent.append((subject, body))

    alerter.alert_trade_closed(42, "EURUSD", "BUY", "tp", 30.0, 20.10)

    subject, body = sent[0]
    assert "\u2705" in subject  # green checkmark
    assert "Trade ID: 42" in body
    assert "+30.0 pips" in body
    assert "$+20.10" in body


def test_alert_trade_closed_loss_shows_cross():
    alerter = _no_config()
    sent = []
    alerter.send = lambda subject, body: sent.append((subject, body))

    alerter.alert_trade_closed(7, "EURUSD", "SELL", "sl", -15.0, -10.05)

    subject, body = sent[0]
    assert "\u274c" in subject  # red cross
    assert "SL" in subject
    assert "-15.0 pips" in body
    assert "$-10.05" in body


# ---------------------------------------------------------------------------
# alert_error
# ---------------------------------------------------------------------------

def test_alert_error_correct_subject_body():
    alerter = _no_config()
    sent = []
    alerter.send = lambda subject, body: sent.append((subject, body))

    alerter.alert_error("executor", "DB connection failed")

    subject, body = sent[0]
    assert subject == "Error in executor"
    assert "executor" in body
    assert "DB connection failed" in body


# ---------------------------------------------------------------------------
# Executor integration: alerter called on trade open
# ---------------------------------------------------------------------------

@patch("execution.executor.store")
def test_run_execution_cycle_calls_alert_trade_opened(mock_store):
    mock_store.get_latest_candles.return_value = _candle(close=1.0855)
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="BUY", sl=15.0, tp=30.0)

    broker = MagicMock()
    broker.get_balance.return_value = 10000.0

    alerter = MagicMock()
    run_execution_cycle("test.db", "EURUSD", "15m", broker, alerter=alerter)

    alerter.alert_trade_opened.assert_called_once()
    trade_arg = alerter.alert_trade_opened.call_args[0][0]
    assert trade_arg["direction"] == "BUY"
    assert trade_arg["pair"] == "EURUSD"


@patch("execution.executor.store")
def test_run_execution_cycle_calls_alert_trade_closed_on_tp(mock_store):
    trade = _open_trade("BUY", sl_price=1.0835, tp_price=1.0880)
    # high=1.0885 → TP hit
    mock_store.get_latest_candles.return_value = _candle(high=1.0885, low=1.0860, close=1.0882)
    mock_store.get_open_trades.side_effect = [trade, pd.DataFrame()]
    mock_store.get_latest_signals.return_value = pd.DataFrame()

    broker = MagicMock()
    broker.get_balance.return_value = 10000.0

    alerter = MagicMock()
    run_execution_cycle("test.db", "EURUSD", "15m", broker, alerter=alerter)

    alerter.alert_trade_closed.assert_called_once()
    args = alerter.alert_trade_closed.call_args[0]
    assert args[3] == "tp"  # close_reason


@patch("execution.executor.store")
def test_run_execution_cycle_calls_alert_error_on_exception(mock_store):
    mock_store.get_latest_candles.side_effect = Exception("DB error")

    broker = MagicMock()
    alerter = MagicMock()

    run_execution_cycle("test.db", "EURUSD", "15m", broker, alerter=alerter)

    alerter.alert_error.assert_called_once_with("executor", "DB error")


@patch("execution.executor.store")
def test_run_execution_cycle_no_alerter_still_works(mock_store):
    """Passing no alerter (None) should not break anything."""
    mock_store.get_latest_candles.return_value = _candle(close=1.0855)
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="BUY", sl=15.0, tp=30.0)

    broker = MagicMock()
    broker.get_balance.return_value = 10000.0

    # Should not raise
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_called_once()


# ---------------------------------------------------------------------------
# alert_trade_closed — breakeven boundary
# ---------------------------------------------------------------------------

def test_alert_trade_closed_breakeven_shows_checkmark():
    alerter = _no_config()
    sent = []
    alerter.send = lambda subject, body: sent.append((subject, body))
    alerter.alert_trade_closed(1, "EURUSD", "BUY", "sl", 0.0, 0.0)
    subject, _ = sent[0]
    assert "\u2705" in subject


# ---------------------------------------------------------------------------
# Executor integration: alerter called on SL hit
# ---------------------------------------------------------------------------

@patch("execution.executor.store")
def test_run_execution_cycle_calls_alert_trade_closed_on_sl(mock_store):
    trade = _open_trade("BUY", sl_price=1.0835, tp_price=1.0880)
    # low=1.0830 <= sl_price=1.0835 → SL hit
    mock_store.get_latest_candles.return_value = _candle(high=1.0860, low=1.0830, close=1.0840)
    mock_store.get_open_trades.side_effect = [trade, pd.DataFrame()]
    mock_store.get_latest_signals.return_value = pd.DataFrame()

    broker = MagicMock()
    broker.get_balance.return_value = 10000.0

    alerter = MagicMock()
    run_execution_cycle("test.db", "EURUSD", "15m", broker, alerter=alerter)

    alerter.alert_trade_closed.assert_called_once()
    args = alerter.alert_trade_closed.call_args[0]
    assert args[3] == "sl"  # close_reason
