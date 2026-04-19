# Phase 4: Performance Tracking Design

## Goal

Compute and persist trading performance metrics from closed paper trades every 15 minutes, giving Phase 5 (Frontend Dashboard) a stable, always-fresh row to read per pair.

## Architecture

A new `performance/` package contains a single module `stats.py`. It reads closed trades from the existing `trades` table, computes metrics using pandas, and upserts one row per pair into a new `stats` table. A `stats_15m` scheduler job runs every 15 minutes — the same cadence as signals and execution.

No new dependencies. Drawdown computation uses pandas (already a dependency). All store I/O goes through `storage/store.py` following the existing pattern.

**Files created:**
- `performance/__init__.py` — empty package marker
- `performance/stats.py` — `compute_stats` and `run_stats_cycle`

**Files modified:**
- `storage/schema.sql` — add `stats` table
- `storage/store.py` — add `write_stats`, `get_stats`
- `scheduler/jobs.py` — add `stats_15m` job
- `tests/test_stats.py` — unit tests for compute logic
- `tests/test_stats_store.py` — integration tests for store functions

## Data Model

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

`pair` is the primary key — one row per pair, upserted on every run. `avg_win_pips`, `avg_loss_pips`, and `profit_factor` are nullable (NULL when no wins or no losses exist yet).

## Metric Definitions

| Metric | Definition |
|---|---|
| `trade_count` | COUNT of all closed trades for the pair |
| `win_count` | COUNT where `pnl_usd > 0` |
| `loss_count` | COUNT where `pnl_usd < 0` |
| `win_rate` | `win_count / trade_count` — 0.0 if no trades |
| `total_pnl_pips` | SUM of `pnl_pips` across all closed trades |
| `total_pnl_usd` | SUM of `pnl_usd` across all closed trades |
| `avg_win_pips` | AVG `pnl_pips` where `pnl_usd > 0` — NULL if no wins |
| `avg_loss_pips` | AVG `pnl_pips` where `pnl_usd < 0` — NULL if no losses |
| `profit_factor` | `SUM(pnl_usd where > 0) / ABS(SUM(pnl_usd where < 0))` — NULL if no losses |
| `max_drawdown_usd` | Largest peak-to-trough drop in cumulative `pnl_usd` ordered by `closed_at` — 0.0 if fewer than 2 trades |

## Computation Logic

### `compute_stats(db_path: str, pair: str) -> dict`

Pure computation, no side effects:

1. Load all closed trades: `store.get_closed_trades(db_path, pair, n=10000)`
2. If DataFrame is empty → return zeroed dict with `updated_at=int(time.time())`
3. Compute counts and sums with pandas
4. Drawdown:
   - `cumulative = trades["pnl_usd"].cumsum()`
   - `running_max = cumulative.cummax()`
   - `drawdown = cumulative - running_max`
   - `max_drawdown_usd = abs(drawdown.min())` — 0.0 if result is positive (no drawdown yet)
5. Return dict with all `stats` table columns

### `run_stats_cycle(db_path: str, pair: str) -> None`

Public entry point called by the scheduler:

- Calls `compute_stats`, then `store.write_stats`
- Wraps in `try/except` → calls `store.write_fetch_log(db_path, pair, "15m", "stats", "error", str(exc), None)` on failure
- Never raises

## Store Functions

### `write_stats(db_path: str, stats: dict) -> None`

`INSERT OR REPLACE INTO stats` — upserts by `pair` primary key.

### `get_stats(db_path: str, pair: str) -> dict | None`

Returns the stats row as a plain dict, or `None` if no row exists for the pair yet.

## Scheduler

Add to `create_scheduler` in `scheduler/jobs.py`:

```python
scheduler.add_job(
    run_stats_cycle,
    trigger="interval",
    minutes=15,
    id="stats_15m",
    kwargs={"db_path": config.DB_PATH, "pair": config.PAIR},
    misfire_grace_time=15 * 60,
)
```

## Testing

### `tests/test_stats.py` (unit — mocks store)

| Test | What it checks |
|---|---|
| `test_empty_trades_returns_zeros` | No closed trades → all defaults, no crash |
| `test_all_winning_trades` | win_rate=1.0, loss_count=0, avg_loss_pips=None, profit_factor=None |
| `test_mixed_trades_win_rate` | 3 wins + 2 losses → win_rate=0.6 |
| `test_total_pnl_correct` | SUM of pnl_usd and pnl_pips correct |
| `test_profit_factor_correct` | gross_win / abs(gross_loss) |
| `test_max_drawdown_correct` | Known sequence produces correct peak-to-trough |
| `test_no_drawdown_returns_zero` | Monotonically increasing pnl → max_drawdown=0.0 |
| `test_exception_logs_and_does_not_raise` | store raises → write_fetch_log called, no re-raise |

### `tests/test_stats_store.py` (integration — real DB via `db_path` fixture)

| Test | What it checks |
|---|---|
| `test_write_stats_creates_row` | Row exists after write |
| `test_get_stats_returns_dict` | Returns dict with correct values |
| `test_get_stats_returns_none_if_missing` | Returns None for unknown pair |
| `test_write_stats_upserts` | Second write with different values overwrites first |
| `test_write_stats_pair_isolation` | Writing GBPUSD row does not affect EURUSD query |

### `tests/test_analyzer.py`

Update `test_scheduler_has_analysis_job` → add assertion that `stats_15m` job exists with 15-minute interval.
