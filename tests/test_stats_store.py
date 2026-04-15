import pytest
from storage import store


_STATS = {
    "pair": "EURUSD", "updated_at": 1705334400,
    "trade_count": 10, "win_count": 7, "loss_count": 3,
    "win_rate": 0.7, "total_pnl_pips": 120.0, "total_pnl_usd": 805.0,
    "avg_win_pips": 25.0, "avg_loss_pips": -12.0,
    "profit_factor": 2.5, "max_drawdown_usd": 150.0,
}


def test_write_stats_creates_row(db_path):
    store.write_stats(db_path, _STATS)
    result = store.get_stats(db_path, "EURUSD")
    assert result is not None


def test_get_stats_returns_dict(db_path):
    store.write_stats(db_path, _STATS)
    result = store.get_stats(db_path, "EURUSD")
    assert result["trade_count"] == 10
    assert result["win_rate"] == pytest.approx(0.7)
    assert result["profit_factor"] == pytest.approx(2.5)


def test_get_stats_returns_none_if_missing(db_path):
    assert store.get_stats(db_path, "EURUSD") is None


def test_write_stats_upserts(db_path):
    store.write_stats(db_path, _STATS)
    updated = {**_STATS, "trade_count": 20, "win_rate": 0.65}
    store.write_stats(db_path, updated)
    result = store.get_stats(db_path, "EURUSD")
    assert result["trade_count"] == 20
    assert result["win_rate"] == pytest.approx(0.65)


def test_write_stats_pair_isolation(db_path):
    store.write_stats(db_path, _STATS)
    store.write_stats(db_path, {**_STATS, "pair": "GBPUSD", "trade_count": 5})
    assert store.get_stats(db_path, "EURUSD")["trade_count"] == 10
    assert store.get_stats(db_path, "GBPUSD")["trade_count"] == 5
