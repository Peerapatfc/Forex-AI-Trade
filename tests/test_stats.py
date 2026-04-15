import pytest
import pandas as pd
from unittest.mock import patch
from performance.stats import compute_stats, run_stats_cycle


def _trades(*pnl_usd_values):
    """Build a minimal closed trades DataFrame with given pnl_usd values."""
    return pd.DataFrame([
        {
            "id": i + 1, "pair": "EURUSD",
            "pnl_usd": v, "pnl_pips": round(v / 6.7, 2),
            "closed_at": 1705334400 + i * 900,
        }
        for i, v in enumerate(pnl_usd_values)
    ])


@patch("performance.stats.store")
def test_empty_trades_returns_zeros(mock_store):
    mock_store.get_closed_trades.return_value = pd.DataFrame()
    result = compute_stats("test.db", "EURUSD")
    assert result["trade_count"] == 0
    assert result["win_count"] == 0
    assert result["loss_count"] == 0
    assert result["win_rate"] == 0.0
    assert result["total_pnl_pips"] == 0.0
    assert result["total_pnl_usd"] == 0.0
    assert result["profit_factor"] is None
    assert result["max_drawdown_usd"] == 0.0
    assert result["avg_win_pips"] is None
    assert result["avg_loss_pips"] is None


@patch("performance.stats.store")
def test_all_winning_trades(mock_store):
    mock_store.get_closed_trades.return_value = _trades(100.0, 200.0, 150.0)
    result = compute_stats("test.db", "EURUSD")
    assert result["win_rate"] == pytest.approx(1.0)
    assert result["loss_count"] == 0
    assert result["avg_loss_pips"] is None
    assert result["profit_factor"] is None  # no losses → undefined


@patch("performance.stats.store")
def test_mixed_trades_win_rate(mock_store):
    mock_store.get_closed_trades.return_value = _trades(100.0, -50.0, 80.0, -30.0, 60.0)
    result = compute_stats("test.db", "EURUSD")
    assert result["trade_count"] == 5
    assert result["win_count"] == 3
    assert result["loss_count"] == 2
    assert result["win_rate"] == pytest.approx(0.6)


@patch("performance.stats.store")
def test_total_pnl_correct(mock_store):
    mock_store.get_closed_trades.return_value = _trades(100.0, -50.0, 80.0)
    result = compute_stats("test.db", "EURUSD")
    assert result["total_pnl_usd"] == pytest.approx(130.0)


@patch("performance.stats.store")
def test_profit_factor_correct(mock_store):
    # gross_win = 100 + 80 = 180, gross_loss = abs(-50) = 50 → pf = 3.6
    mock_store.get_closed_trades.return_value = _trades(100.0, -50.0, 80.0)
    result = compute_stats("test.db", "EURUSD")
    assert result["profit_factor"] == pytest.approx(3.6)


@patch("performance.stats.store")
def test_max_drawdown_correct(mock_store):
    # cumulative: 100, 50, 130, 100, 160
    # running_max: 100, 100, 130, 130, 160
    # drawdown:      0, -50,   0, -30,   0  → max_drawdown = 50
    mock_store.get_closed_trades.return_value = _trades(100.0, -50.0, 80.0, -30.0, 60.0)
    result = compute_stats("test.db", "EURUSD")
    assert result["max_drawdown_usd"] == pytest.approx(50.0)


@patch("performance.stats.store")
def test_no_drawdown_returns_zero(mock_store):
    # monotonically increasing cumulative → drawdown never negative
    mock_store.get_closed_trades.return_value = _trades(10.0, 20.0, 30.0)
    result = compute_stats("test.db", "EURUSD")
    assert result["max_drawdown_usd"] == pytest.approx(0.0)


@patch("performance.stats.store")
def test_exception_logs_and_does_not_raise(mock_store):
    mock_store.get_closed_trades.side_effect = Exception("DB error")
    run_stats_cycle("test.db", "EURUSD")  # must not raise
    mock_store.write_fetch_log.assert_called_once_with(
        "test.db", "EURUSD", "15m", "stats", "error", "DB error", None
    )
