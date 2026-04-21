"""Tests for scripts/check_golive.py go-live criteria checker."""
import argparse
from unittest.mock import patch

import pytest

from scripts.check_golive import main, check_criteria

PASSING_STATS = {
    "trade_count": 50, "win_count": 28, "win_rate": 0.56,
    "total_pnl_usd": 400.0, "max_drawdown_usd": 200.0, "profit_factor": 1.5,
}

FAILING_STATS = {
    "trade_count": 10, "win_count": 4, "win_rate": 0.40,
    "total_pnl_usd": -50.0, "max_drawdown_usd": 700.0, "profit_factor": 0.8,
}

EMPTY_STATS = {
    "trade_count": 0, "win_count": 0, "win_rate": 0.0,
    "total_pnl_usd": 0.0, "max_drawdown_usd": 0.0, "profit_factor": None,
}


def _make_args(**overrides):
    """Build a Namespace with default thresholds, optionally overridden."""
    defaults = dict(
        db="forex.db",
        pair="EURUSD",
        min_trades=30,
        min_win_rate=0.50,
        min_pnl=0.0,
        max_drawdown=500.0,
        min_profit_factor=1.2,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# 1. All passing -> returns 0
# ---------------------------------------------------------------------------
def test_all_passing_returns_0():
    with patch("scripts.check_golive.compute_stats", return_value=PASSING_STATS):
        result = main(["--db", "forex.db", "--pair", "EURUSD"])
    assert result == 0


# ---------------------------------------------------------------------------
# 2. All failing -> returns 1
# ---------------------------------------------------------------------------
def test_all_failing_returns_1():
    with patch("scripts.check_golive.compute_stats", return_value=FAILING_STATS):
        result = main(["--db", "forex.db", "--pair", "EURUSD"])
    assert result == 1


# ---------------------------------------------------------------------------
# 3. profit_factor=None -> SKIP, not counted as failure
# ---------------------------------------------------------------------------
def test_profit_factor_none_is_skipped():
    stats = {**PASSING_STATS, "profit_factor": None}
    args = _make_args()
    results = check_criteria(stats, args)
    pf_result = next(r for r in results if r[0] == "Profit factor")
    label, passed, detail = pf_result
    assert passed is None  # SKIP
    assert "no closed losing trades yet" in detail

    # Should still return 0 overall (other criteria all pass)
    with patch("scripts.check_golive.compute_stats", return_value=stats):
        rc = main(["--db", "forex.db", "--pair", "EURUSD"])
    assert rc == 0


# ---------------------------------------------------------------------------
# 4. Exactly 1 failure -> "1 criterion failed" (singular)
# ---------------------------------------------------------------------------
def test_singular_criterion_message(capsys):
    # Only win rate fails (0.40 < 0.50), everything else passes
    stats = {**PASSING_STATS, "win_rate": 0.40}
    with patch("scripts.check_golive.compute_stats", return_value=stats):
        rc = main(["--db", "forex.db", "--pair", "EURUSD"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "1 criterion failed" in captured.out


# ---------------------------------------------------------------------------
# 5. Multiple failures -> "N criteria failed" (plural)
# ---------------------------------------------------------------------------
def test_plural_criteria_message(capsys):
    with patch("scripts.check_golive.compute_stats", return_value=FAILING_STATS):
        rc = main(["--db", "forex.db", "--pair", "EURUSD"])
    assert rc == 1
    captured = capsys.readouterr()
    # Should say "criteria" (plural) since multiple fail
    assert "criteria failed" in captured.out
    # Verify the count is > 1
    import re
    match = re.search(r"(\d+) criteria failed", captured.out)
    assert match and int(match.group(1)) > 1


# ---------------------------------------------------------------------------
# 6. Custom --min-trades 5 -> passes with 10 trades
# ---------------------------------------------------------------------------
def test_custom_min_trades():
    stats = {**PASSING_STATS, "trade_count": 10}
    with patch("scripts.check_golive.compute_stats", return_value=stats):
        rc = main(["--db", "forex.db", "--pair", "EURUSD", "--min-trades", "5"])
    assert rc == 0


# ---------------------------------------------------------------------------
# 7. check_criteria returns correct tuple structure
# ---------------------------------------------------------------------------
def test_check_criteria_structure():
    args = _make_args()
    results = check_criteria(PASSING_STATS, args)

    # Should have exactly 5 entries
    assert len(results) == 5

    # Each entry is a 3-tuple
    for item in results:
        assert len(item) == 3, f"Expected 3-tuple, got {len(item)}-tuple"
        label, passed, detail = item
        assert isinstance(label, str)
        assert passed in (True, False, None)
        assert isinstance(detail, str)

    # All should pass with PASSING_STATS
    for label, passed, detail in results:
        assert passed is True, f"{label} expected PASS but got {passed!r}"


# ---------------------------------------------------------------------------
# 8. Zero trades -> output contains [WARN]
# ---------------------------------------------------------------------------
def test_zero_trades_warn(capsys):
    with patch("scripts.check_golive.compute_stats", return_value=EMPTY_STATS):
        main(["--db", "forex.db", "--pair", "EURUSD"])
    out = capsys.readouterr().out
    assert "[WARN]" in out


# ---------------------------------------------------------------------------
# Bonus: check FAIL detail strings use correct comparison symbols
# ---------------------------------------------------------------------------
def test_fail_detail_strings(capsys):
    with patch("scripts.check_golive.compute_stats", return_value=FAILING_STATS):
        main(["--db", "forex.db", "--pair", "EURUSD"])
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "[PASS]" not in out  # FAILING_STATS must fail all criteria
