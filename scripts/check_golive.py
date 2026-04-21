#!/usr/bin/env python3
"""Check whether paper trading stats meet go-live criteria."""
import argparse
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from performance.stats import compute_stats


def check_criteria(stats: dict, args: argparse.Namespace) -> list[tuple[str, bool, str]]:
    """
    Returns list of (label, passed, detail) tuples.
    passed=None means SKIP.
    """
    results = []

    # Trades
    trades = stats["trade_count"]
    results.append((
        "Trades",
        trades >= args.min_trades,
        f"{trades} >= {args.min_trades}",
    ))

    # Win rate
    wr = stats["win_rate"] * 100
    threshold_wr = args.min_win_rate * 100
    results.append((
        "Win rate",
        wr >= threshold_wr,
        f"{wr:.1f}% >= {threshold_wr:.1f}%",
    ))

    # Total P&L
    pnl = stats["total_pnl_usd"]
    results.append((
        "Total P&L",
        pnl >= args.min_pnl,
        f"${pnl:.2f} >= ${args.min_pnl:.2f}",
    ))

    # Max drawdown
    dd = stats["max_drawdown_usd"]
    results.append((
        "Max drawdown",
        dd <= args.max_drawdown,
        f"${dd:.2f} <= ${args.max_drawdown:.2f}",
    ))

    # Profit factor (skip if None)
    pf = stats["profit_factor"]
    if pf is None:
        results.append(("Profit factor", None, "no closed losing trades yet"))
    else:
        results.append((
            "Profit factor",
            pf >= args.min_profit_factor,
            f"{pf:.2f} >= {args.min_profit_factor:.2f}",
        ))

    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check go-live criteria")
    parser.add_argument("--db", default="forex.db", help="Path to SQLite DB")
    parser.add_argument("--pair", default="EURUSD")
    parser.add_argument("--min-trades", type=int, default=30)
    parser.add_argument("--min-win-rate", type=float, default=0.50)
    parser.add_argument("--min-pnl", type=float, default=0.0)
    parser.add_argument("--max-drawdown", type=float, default=500.0)
    parser.add_argument("--min-profit-factor", type=float, default=1.2)
    args = parser.parse_args(argv)

    stats = compute_stats(args.db, args.pair)

    print(f"\n=== Go-Live Criteria Check ===")
    print(f"Pair: {args.pair}\n")

    results = check_criteria(stats, args)
    failed = 0
    for label, passed, detail in results:
        if passed is None:
            print(f"  [SKIP] {label}: {detail}")
        elif passed:
            print(f"  [PASS] {label}: {detail}")
        else:
            print(f"  [FAIL] {label}: {detail}")
            failed += 1

    print()
    if failed == 0:
        print("Result: READY TO GO LIVE")
        return 0
    else:
        noun = "criterion" if failed == 1 else "criteria"
        print(f"Result: NOT READY ({failed} {noun} failed)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
