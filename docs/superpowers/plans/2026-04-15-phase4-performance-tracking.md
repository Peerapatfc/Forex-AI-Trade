# Phase 4: Performance Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute and persist trading performance metrics (win rate, P&L, drawdown, profit factor) from closed trades every 15 minutes into a `stats` SQLite table.

**Architecture:** A new `performance/stats.py` module reads closed trades via `store.get_closed_trades`, computes metrics with pandas, and upserts a single row per pair into a new `stats` table. A `stats_15m` scheduler job drives it every 15 minutes — the same cadence as the rest of the system.

**Tech Stack:** Python 3.11, SQLite (`storage/store.py` pattern), pandas, APScheduler 3.x, pytest

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `storage/schema.sql` | Modify | Add `stats` table |
| `storage/store.py` | Modify | Add `write_stats`, `get_stats` |
| `performance/__init__.py` | Create | Empty package marker |
| `performance/stats.py` | Create | `compute_stats`, `run_stats_cycle` |
| `scheduler/jobs.py` | Modify | Add `stats_15m` job |
| `tests/test_stats_store.py` | Create | Integration tests for store functions |
| `tests/test_stats.py` | Create | Unit tests for compute logic |
| `tests/test_analyzer.py` | Modify | Add assertion for `stats_15m` job |

---

## Task 1: Stats schema and store functions

**Files:**
- Modify: `storage/schema.sql`
- Modify: `storage/store.py`
- Create: `tests/test_stats_store.py`

### Context

`storage/schema.sql` has five existing tables (`candles`, `indicators`, `fetch_log`, `signals`, `account`, `trades`). Add the `stats` table at the end.

`storage/store.py` follows this pattern for every function — open connection, execute, commit, close in `finally`:

```python
def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn
```

`conn.row_factory = sqlite3.Row` means `dict(row)` works to convert a fetched row to a plain dict.

Tests use the `db_path` fixture from `tests/conftest.py` which creates a temp DB via `init_db(path)`. `init_db` runs `schema.sql` — so any new table added to schema.sql is automatically available in tests.

---

- [ ] **Step 1: Write the failing integration tests**

Create `tests/test_stats_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
py -m pytest tests/test_stats_store.py -v
```

Expected: FAIL with `AttributeError: module 'storage.store' has no attribute 'write_stats'`

- [ ] **Step 3: Add the `stats` table to `storage/schema.sql`**

Append after the `trades` table (before the final blank line):

```sql
CREATE TABLE IF NOT EXISTS stats (
    pair             TEXT    NOT NULL PRIMARY KEY,
    updated_at       INTEGER NOT NULL,
    trade_count      INTEGER NOT NULL DEFAULT 0,
    win_count        INTEGER NOT NULL DEFAULT 0,
    loss_count       INTEGER NOT NULL DEFAULT 0,
    win_rate         REAL    NOT NULL DEFAULT 0.0,
    total_pnl_pips   REAL    NOT NULL DEFAULT 0.0,
    total_pnl_usd    REAL    NOT NULL DEFAULT 0.0,
    avg_win_pips     REAL,
    avg_loss_pips    REAL,
    profit_factor    REAL,
    max_drawdown_usd REAL    NOT NULL DEFAULT 0.0
);
```

- [ ] **Step 4: Add `write_stats` and `get_stats` to `storage/store.py`**

Append at the end of the file:

```python
def write_stats(db_path: str, stats: dict) -> None:
    """Upsert performance stats for a pair (INSERT OR REPLACE by pair primary key)."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO stats "
            "(pair, updated_at, trade_count, win_count, loss_count, win_rate, "
            "total_pnl_pips, total_pnl_usd, avg_win_pips, avg_loss_pips, "
            "profit_factor, max_drawdown_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stats["pair"], stats["updated_at"],
                stats["trade_count"], stats["win_count"], stats["loss_count"],
                stats["win_rate"], stats["total_pnl_pips"], stats["total_pnl_usd"],
                stats.get("avg_win_pips"), stats.get("avg_loss_pips"),
                stats.get("profit_factor"), stats["max_drawdown_usd"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_stats(db_path: str, pair: str) -> dict | None:
    """Return the stats row for the given pair as a plain dict, or None if not yet computed."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM stats WHERE pair = ?", (pair,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests to verify they pass**

```
py -m pytest tests/test_stats_store.py -v
```

Expected: 5 PASS

- [ ] **Step 6: Commit**

```bash
git add storage/schema.sql storage/store.py tests/test_stats_store.py
git commit -m "feat: add stats table and write_stats/get_stats store functions"
```

---

## Task 2: compute_stats function

**Files:**
- Create: `performance/__init__.py`
- Create: `performance/stats.py`
- Create: `tests/test_stats.py`

### Context

`store.get_closed_trades(db_path, pair, n)` returns a pandas DataFrame sorted oldest-first with columns including `pnl_usd`, `pnl_pips`, `closed_at`. When no trades exist it returns an empty DataFrame (`.empty` is `True`).

The drawdown algorithm:
1. `cumulative = trades["pnl_usd"].cumsum()` — running total P&L
2. `running_max = cumulative.cummax()` — highest cumulative value seen so far
3. `drawdown = cumulative - running_max` — always ≤ 0
4. `max_drawdown_usd = abs(drawdown.min())` if `drawdown.min() < 0` else `0.0`

Tests use `@patch("performance.stats.store")` to mock the store module, so `compute_stats` never touches a real DB.

---

- [ ] **Step 1: Write the failing unit tests**

Create `tests/test_stats.py`:

```python
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
    assert result["win_rate"] == 0.0
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
py -m pytest tests/test_stats.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'performance'`

- [ ] **Step 3: Create `performance/__init__.py`**

Create an empty file at `performance/__init__.py`. No content needed.

- [ ] **Step 4: Create `performance/stats.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```
py -m pytest tests/test_stats.py -v
```

Expected: 8 PASS

- [ ] **Step 6: Run full suite to check for regressions**

```
py -m pytest tests/ -q
```

Expected: all previously passing tests still pass

- [ ] **Step 7: Commit**

```bash
git add performance/__init__.py performance/stats.py tests/test_stats.py
git commit -m "feat: add performance stats module with compute_stats and run_stats_cycle"
```

---

## Task 3: Scheduler wiring

**Files:**
- Modify: `scheduler/jobs.py`
- Modify: `tests/test_analyzer.py`

### Context

`scheduler/jobs.py` currently imports and schedules three jobs: `run_fetch_cycle`, `run_analysis_cycle`, `run_execution_cycle`. The pattern to follow for adding a job:

```python
scheduler.add_job(
    <function>,
    trigger="interval",
    minutes=15,
    id="<job_id>",
    kwargs={"db_path": config.DB_PATH, "pair": config.PAIR},
    misfire_grace_time=15 * 60,
)
logger.info("Scheduled %s 15m <name> job every 15 minutes", config.PAIR)
```

`tests/test_analyzer.py` already has `test_scheduler_has_analysis_job` that tests the `analyze_15m` job. Add a new parallel test `test_scheduler_has_stats_job` for the `stats_15m` job. Do **not** modify the existing test.

---

- [ ] **Step 1: Write the failing scheduler test**

Add to `tests/test_analyzer.py` (after the existing `test_scheduler_has_analysis_job` function):

```python
def test_scheduler_has_stats_job():
    from scheduler.jobs import create_scheduler
    from unittest.mock import MagicMock
    broker = MagicMock()
    scheduler = create_scheduler(broker)
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert "stats_15m" in job_ids
    stats_job = next(j for j in scheduler.get_jobs() if j.id == "stats_15m")
    assert stats_job.trigger.interval.total_seconds() == 900  # 15 minutes
    assert "db_path" in stats_job.kwargs
    assert "pair" in stats_job.kwargs
    scheduler.remove_all_jobs()
```

- [ ] **Step 2: Run test to verify it fails**

```
py -m pytest tests/test_analyzer.py::test_scheduler_has_stats_job -v
```

Expected: FAIL with `AssertionError: assert 'stats_15m' in {...}`

- [ ] **Step 3: Add the stats job to `scheduler/jobs.py`**

Add the import at the top of the file (after the existing imports):

```python
from performance.stats import run_stats_cycle
```

Then add the job inside `create_scheduler`, after the `execute_15m` block and before `return scheduler`:

```python
    scheduler.add_job(
        run_stats_cycle,
        trigger="interval",
        minutes=15,
        id="stats_15m",
        kwargs={"db_path": config.DB_PATH, "pair": config.PAIR},
        misfire_grace_time=15 * 60,
    )
    logger.info("Scheduled %s 15m stats job every 15 minutes", config.PAIR)
```

- [ ] **Step 4: Run the new test to verify it passes**

```
py -m pytest tests/test_analyzer.py::test_scheduler_has_stats_job -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```
py -m pytest tests/ -v
```

Expected: all tests pass (124 + 14 new = 138 total)

- [ ] **Step 6: Commit**

```bash
git add scheduler/jobs.py tests/test_analyzer.py
git commit -m "feat: wire stats job into scheduler every 15 minutes"
```
