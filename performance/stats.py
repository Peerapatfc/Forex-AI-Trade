import logging
import time

import pandas as pd

from storage import store

logger = logging.getLogger(__name__)


def compute_stats(db_path: str, pair: str) -> dict:
    """
    Compute performance metrics from all closed trades for the given pair.
    Returns a dict ready to pass to store.write_stats. Never raises.
    """
    trades = store.get_closed_trades(db_path, pair, n=10000)
    now = int(time.time())

    if trades.empty:
        return {
            "pair": pair, "updated_at": now,
            "trade_count": 0, "win_count": 0, "loss_count": 0,
            "win_rate": 0.0, "total_pnl_pips": 0.0, "total_pnl_usd": 0.0,
            "avg_win_pips": None, "avg_loss_pips": None,
            "profit_factor": None, "max_drawdown_usd": 0.0,
        }

    wins = trades[trades["pnl_usd"] > 0]
    losses = trades[trades["pnl_usd"] < 0]

    trade_count = len(trades)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / trade_count
    total_pnl_pips = float(trades["pnl_pips"].sum())
    total_pnl_usd = float(trades["pnl_usd"].sum())
    avg_win_pips = float(wins["pnl_pips"].mean()) if not wins.empty else None
    avg_loss_pips = float(losses["pnl_pips"].mean()) if not losses.empty else None

    if not losses.empty:
        gross_win = float(wins["pnl_usd"].sum()) if not wins.empty else 0.0
        gross_loss = abs(float(losses["pnl_usd"].sum()))
        profit_factor = gross_win / gross_loss if gross_loss > 0 else None
    else:
        profit_factor = None

    cumulative = trades["pnl_usd"].cumsum()
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    max_drawdown_usd = float(abs(drawdown.min())) if drawdown.min() < 0 else 0.0

    return {
        "pair": pair, "updated_at": now,
        "trade_count": trade_count, "win_count": win_count, "loss_count": loss_count,
        "win_rate": win_rate, "total_pnl_pips": total_pnl_pips, "total_pnl_usd": total_pnl_usd,
        "avg_win_pips": avg_win_pips, "avg_loss_pips": avg_loss_pips,
        "profit_factor": profit_factor, "max_drawdown_usd": max_drawdown_usd,
    }


def run_stats_cycle(db_path: str, pair: str) -> None:
    """
    Compute and persist stats for the given pair.
    Never raises — exceptions are logged to fetch_log with provider='stats'.
    """
    try:
        stats = compute_stats(db_path, pair)
        store.write_stats(db_path, stats)
    except Exception as exc:
        logger.error("Stats cycle failed for %s: %s", pair, exc)
        store.write_fetch_log(db_path, pair, "15m", "stats", "error", str(exc), None)
