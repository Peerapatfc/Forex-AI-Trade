import logging
import time

import pandas as pd

from execution.broker import Broker
from execution.position_sizer import PIP_VALUE_PER_LOT, calculate_lot_size
from storage import store

logger = logging.getLogger(__name__)

SIGNAL_MAX_AGE_SECONDS = 900  # 15 minutes
_PIP = 0.0001  # EURUSD pip size


def run_execution_cycle(
    db_path: str,
    pair: str,
    timeframe: str,
    broker: Broker,
    risk_pct: float = 0.01,
    alerter=None,
) -> None:
    """
    Execute one full cycle: check SL/TP on open trades, then open a new trade if warranted.
    Never raises — all exceptions are logged to fetch_log with provider='executor'.
    """
    try:
        _cycle(db_path, pair, timeframe, broker, risk_pct, alerter)
    except Exception as exc:
        logger.error("Execution cycle failed for %s %s: %s", pair, timeframe, exc)
        store.write_fetch_log(db_path, pair, timeframe, "executor", "error", str(exc), None)
        if alerter is not None:
            alerter.alert_error("executor", str(exc))


def _cycle(
    db_path: str, pair: str, timeframe: str, broker: Broker, risk_pct: float, alerter=None
) -> None:
    # Step 1: Get latest candle for SL/TP checking and entry price
    candles = store.get_latest_candles(db_path, pair, timeframe, 1)
    if candles.empty:
        logger.warning("No candles available for %s %s — skipping execution", pair, timeframe)
        return
    candle = candles.iloc[-1]

    # Step 2: Check SL/TP on all open trades
    open_trades = store.get_open_trades(db_path, pair)
    for _, trade in open_trades.iterrows():
        _check_sl_tp(trade, candle, broker, alerter)

    # Step 3: Get latest signal
    signals = store.get_latest_signals(db_path, pair, timeframe, 1)
    if signals.empty:
        logger.debug("No signal for %s %s — skipping open", pair, timeframe)
        return
    signal = signals.iloc[-1]

    # Step 4: Signal freshness guard
    now = int(time.time())
    if signal["timestamp"] < now - SIGNAL_MAX_AGE_SECONDS:
        logger.debug("Signal for %s %s is stale — skipping open", pair, timeframe)
        return

    # Step 5: HOLD → nothing to open
    if signal["direction"] == "HOLD":
        return

    # Step 6: One trade at a time (re-check after SL/TP closures above)
    open_trades_after = store.get_open_trades(db_path, pair)
    if not open_trades_after.empty:
        logger.debug("Trade already open for %s — ignoring new signal", pair)
        return

    # Step 7: Validate sl_pips and tp_pips
    sl_pips = signal["sl_pips"]
    tp_pips = signal["tp_pips"]
    if pd.isna(sl_pips) or sl_pips <= 0 or pd.isna(tp_pips) or tp_pips <= 0:
        logger.warning("Signal for %s has no valid sl_pips/tp_pips — skipping open", pair)
        return

    # Step 8: Validate balance
    balance = broker.get_balance()
    if balance <= 0:
        logger.warning("Account balance is %.2f — skipping trade", balance)
        return

    # Step 9: Calculate position size
    lot_size = calculate_lot_size(balance, risk_pct, sl_pips)
    if lot_size == 0.0:
        logger.warning(
            "Lot size rounds to 0 for %s (balance=%.2f, sl=%.1f) — skipping",
            pair, balance, sl_pips,
        )
        return

    # Step 10: Open trade at candle close price
    entry_price = float(candle["close"])
    direction = signal["direction"]
    if direction == "BUY":
        sl_price = round(entry_price - sl_pips * _PIP, 5)
        tp_price = round(entry_price + tp_pips * _PIP, 5)
    else:  # SELL
        sl_price = round(entry_price + sl_pips * _PIP, 5)
        tp_price = round(entry_price - tp_pips * _PIP, 5)

    trade = {
        "pair": pair,
        "timeframe": timeframe,
        "signal_id": int(signal["id"]),
        "direction": direction,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "lot_size": lot_size,
        "sl_pips": float(sl_pips),
        "tp_pips": float(tp_pips),
        "opened_at": now,
    }
    broker.open_trade(trade)
    logger.info(
        "Opened %s %s: entry=%.5f SL=%.5f TP=%.5f lot=%.2f",
        direction, pair, entry_price, sl_price, tp_price, lot_size,
    )
    if alerter is not None:
        alerter.alert_trade_opened(trade)


def _check_sl_tp(trade, candle, broker: Broker, alerter=None) -> None:
    """Check if the open trade's SL or TP was hit by the current candle."""
    direction = trade["direction"]
    high = float(candle["high"])
    low = float(candle["low"])
    entry = float(trade["entry_price"])
    sl_price = float(trade["sl_price"])
    tp_price = float(trade["tp_price"])
    lot_size = float(trade["lot_size"])
    trade_id = int(trade["id"])

    hit_sl = (direction == "BUY" and low <= sl_price) or (direction == "SELL" and high >= sl_price)
    hit_tp = (direction == "BUY" and high >= tp_price) or (direction == "SELL" and low <= tp_price)

    if not hit_sl and not hit_tp:
        return

    # SL takes priority if both hit (gap scenario — conservative)
    if hit_sl:
        close_price = sl_price
        close_reason = "sl"
    else:
        close_price = tp_price
        close_reason = "tp"

    if direction == "BUY":
        pnl_pips = (close_price - entry) / _PIP
    else:
        pnl_pips = (entry - close_price) / _PIP

    pnl_usd = pnl_pips * PIP_VALUE_PER_LOT * lot_size

    broker.close_trade(trade_id, close_price, close_reason, pnl_pips, pnl_usd)
    logger.info(
        "Closed %s trade %d on %s: %.1f pips / $%.2f",
        direction, trade_id, close_reason.upper(), pnl_pips, pnl_usd,
    )
    if alerter is not None:
        pair = str(trade.get("pair", "?"))
        alerter.alert_trade_closed(trade_id, pair, direction, close_reason, pnl_pips, pnl_usd)
