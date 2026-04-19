# Phase 3: Trading Execution — Design Spec

**Date:** 2026-04-14
**Project:** Forex AI Trading System
**Phase:** 3 of 6 — Trading Execution
**Status:** Approved

---

## Overview

Phase 3 adds a paper trading execution layer on top of the Phase 2 signal pipeline. A dedicated APScheduler job reads the latest signal and open trades every 15m, applies position sizing and SL/TP monitoring logic, and writes trade results to SQLite. A clean `Broker` protocol allows `PaperBroker` (fully implemented) and `LiveBroker` (stub) to be swapped without touching the executor.

No live broker connection. No frontend. Just a reliable, auditable paper trade record.

---

## Decisions

| Dimension | Decision | Rationale |
|---|---|---|
| Execution mode | Paper trading first, live stub | Validate signal quality before risking real money |
| Broker abstraction | Protocol with `open_trade` / `close_trade` / `get_balance` | Single-class swap to go live later |
| Risk model | Fixed % of account balance per trade | Adjusts automatically as balance changes; industry standard |
| Default risk | 1% per trade (`RISK_PCT=0.01`) | Conservative; configurable via `.env` |
| Position sizing | `lot_size = (balance × risk_pct) / (sl_pips × 10)` | EURUSD pip value = $10/lot; rounds to 2dp, min 0.01 |
| SL/TP monitoring | Candle high/low comparison every 15m | Realistic fills vs close-only; data already available |
| Concurrency | One open trade at a time | Simple, safe for signal quality validation phase |
| Signal freshness | Ignore signals older than 15m | Prevents stale signals acting after scheduler gaps |
| Starting balance | Configurable via `PAPER_BALANCE` (default $10,000) | Seeded on first run |
| Broker mode | `BROKER_MODE=paper|live` in `.env` | Startup exits with clear error if `live` is set |

---

## Architecture & Module Structure

```
forex-ai/
├── execution/
│   ├── __init__.py
│   ├── broker.py          # Broker Protocol (open_trade, close_trade, get_balance)
│   ├── paper_broker.py    # PaperBroker: reads/writes trades + account tables
│   ├── live_broker.py     # LiveBroker: stub, raises NotImplementedError
│   ├── position_sizer.py  # calculate_lot_size(balance, risk_pct, sl_pips) -> float
│   └── executor.py        # run_execution_cycle — orchestrates the full cycle
├── storage/
│   ├── schema.sql         # + trades table, account table
│   └── store.py           # + write_trade, get_open_trades, close_trade, account ops
├── scheduler/
│   └── jobs.py            # + execution job every 15m
└── config.py              # + PAPER_BALANCE, RISK_PCT, BROKER_MODE
```

### Data Flow

```
APScheduler (every 15m)
  → executor.run_execution_cycle(db_path, pair, timeframe, broker)
      → store.get_latest_candles(pair, timeframe, 1)        # latest candle high/low/close
      → store.get_open_trades(db_path, pair)                # open trades
      → [for each open trade] check SL/TP → store.close_trade() + store.update_account_balance()
      → store.get_latest_signals(db_path, pair, timeframe, 1)
      → [if signal fresh + BUY/SELL + no open trade]
          → store.get_account_balance()
          → position_sizer.calculate_lot_size(balance, risk_pct, sl_pips)
          → broker.open_trade(trade_dict)
          → store.write_trade(trade_dict)
```

---

## Storage

### account table

```sql
CREATE TABLE IF NOT EXISTS account (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    balance    REAL    NOT NULL,
    updated_at INTEGER NOT NULL
);
```

- Single-row table (id=1 enforced by CHECK constraint).
- Seeded with `PAPER_BALANCE` on first run if the row does not exist.
- Updated on every trade close: `balance += pnl_usd`.

### trades table

```sql
CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pair         TEXT    NOT NULL,
    timeframe    TEXT    NOT NULL,
    signal_id    INTEGER NOT NULL REFERENCES signals(id),
    direction    TEXT    NOT NULL,
    entry_price  REAL    NOT NULL,
    sl_price     REAL    NOT NULL,
    tp_price     REAL    NOT NULL,
    lot_size     REAL    NOT NULL,
    sl_pips      REAL    NOT NULL,
    tp_pips      REAL    NOT NULL,
    opened_at    INTEGER NOT NULL,
    closed_at    INTEGER,
    close_price  REAL,
    close_reason TEXT,
    pnl_pips     REAL,
    pnl_usd      REAL,
    status       TEXT    NOT NULL DEFAULT 'open'
);
```

- `sl_price` / `tp_price` stored at open time — monitor loop is a simple comparison.
- `close_reason`: `'sl'` or `'tp'`.
- `status`: `'open'` or `'closed'`.

### store.py additions

```python
def seed_account(db_path: str, initial_balance: float) -> None: ...
    # INSERT OR IGNORE into account (id=1) with initial_balance

def get_account_balance(db_path: str) -> float: ...

def update_account_balance(db_path: str, new_balance: float) -> None: ...

def write_trade(db_path: str, trade: dict) -> int: ...
    # INSERT, returns rowid

def get_open_trades(db_path: str, pair: str) -> pd.DataFrame: ...
    # SELECT WHERE status='open' AND pair=pair

def close_trade(db_path: str, trade_id: int, close_price: float,
                close_reason: str, pnl_pips: float, pnl_usd: float) -> None: ...
    # UPDATE trades SET status='closed', closed_at=..., close_price=..., etc.
```

---

## Broker Protocol

```python
from typing import Protocol

class Broker(Protocol):
    def open_trade(self, trade: dict) -> None: ...
    def close_trade(self, trade_id: int, close_price: float,
                    close_reason: str, pnl_pips: float, pnl_usd: float) -> None: ...
    def get_balance(self) -> float: ...
```

### PaperBroker

Delegates directly to `store.*` functions. Holds `db_path` as instance state.

```python
class PaperBroker:
    def __init__(self, db_path: str) -> None: ...
    def open_trade(self, trade: dict) -> None: ...
    def close_trade(self, trade_id: int, close_price: float,
                    close_reason: str, pnl_pips: float, pnl_usd: float) -> None: ...
    def get_balance(self) -> float: ...
```

### LiveBroker

```python
class LiveBroker:
    def open_trade(self, trade: dict) -> None:
        raise NotImplementedError("Live execution not yet implemented")
    def close_trade(self, ...) -> None:
        raise NotImplementedError("Live execution not yet implemented")
    def get_balance(self) -> float:
        raise NotImplementedError("Live execution not yet implemented")
```

---

## Position Sizer

```python
PIP_VALUE_PER_LOT = 10.0  # USD per pip per standard lot, EURUSD

def calculate_lot_size(balance: float, risk_pct: float, sl_pips: float) -> float:
    """
    Returns lot size rounded to 2dp, minimum 0.01.
    Returns 0.0 if sl_pips <= 0 or result rounds below minimum.
    """
    risk_amount = balance * risk_pct
    raw = risk_amount / (sl_pips * PIP_VALUE_PER_LOT)
    lot = round(raw, 2)
    return lot if lot >= 0.01 else 0.0
```

---

## Executor Logic

```python
SIGNAL_MAX_AGE_SECONDS = 900  # 15 minutes

def run_execution_cycle(db_path: str, pair: str, timeframe: str, broker: Broker) -> None:
    """Never raises. All exceptions logged to fetch_log with provider='executor'."""
```

**Cycle steps:**

1. Get latest candle (`store.get_latest_candles(db_path, pair, timeframe, 1)`). If empty → skip, log warning.
2. Get open trades (`store.get_open_trades(db_path, pair)`).
3. For each open trade, check SL/TP:
   - **BUY:** SL hit if `candle.low <= trade.sl_price`; TP hit if `candle.high >= trade.tp_price`
   - **SELL:** SL hit if `candle.high >= trade.sl_price`; TP hit if `candle.low <= trade.tp_price`
   - On hit: calculate P&L, call `broker.close_trade(...)`, call `store.update_account_balance(...)`.
   - If both SL and TP are hit in the same candle (gap): SL takes priority (conservative).
4. Get latest signal (`store.get_latest_signals(db_path, pair, timeframe, 1)`). If empty → done.
5. Check signal freshness: `signal.timestamp > now - SIGNAL_MAX_AGE_SECONDS`. If stale → done.
6. If `signal.direction == 'HOLD'` → done.
7. If open trade exists (after step 3 closures) → done (one trade at a time).
8. If `signal.sl_pips` is null or zero → log warning, done.
9. Get balance. Calculate lot size. If lot size is 0.0 → log warning, done.
10. Build trade dict, call `broker.open_trade(trade_dict)`.

**P&L formulas:**

```
BUY:  pnl_pips = (close_price - entry_price) / 0.0001
SELL: pnl_pips = (entry_price - close_price) / 0.0001
pnl_usd     = pnl_pips × PIP_VALUE_PER_LOT × lot_size
new_balance = balance + pnl_usd
```

---

## Error Handling

| Failure mode | Behaviour |
|---|---|
| No candles available | Skip cycle, log warning |
| No signal in last 15m | Skip execution, log debug |
| Signal older than 15m | Skip execution, log debug |
| `sl_pips` is null or zero on signal | Skip opening trade, log warning |
| Lot size rounds to 0.0 | Skip opening trade, log warning |
| Balance ≤ 0 | Skip opening trade, log warning |
| `write_trade` / `close_trade` fails | Log error, never crash scheduler |
| `BROKER_MODE=live` at startup | Log error, `sys.exit(1)` |
| Any unexpected exception | Log to `fetch_log` with `provider='executor'`, continue |

---

## Config Additions

```python
PAPER_BALANCE: float = float(os.getenv("PAPER_BALANCE", "10000"))
RISK_PCT: float = float(os.getenv("RISK_PCT", "0.01"))
BROKER_MODE: str = os.getenv("BROKER_MODE", "paper")
```

`main.py` additions:
- Seed account on startup: `store.seed_account(config.DB_PATH, config.PAPER_BALANCE)`
- Validate `BROKER_MODE`: if `live`, log error and `sys.exit(1)` (live not yet implemented)
- Pass `PaperBroker(config.DB_PATH)` into scheduler jobs

---

## Scheduler Addition

```python
scheduler.add_job(
    run_execution_cycle,
    trigger="interval",
    minutes=15,
    id="execute_15m",
    kwargs={
        "db_path": config.DB_PATH,
        "pair": config.PAIR,
        "timeframe": "15m",
        "broker": paper_broker,
    },
    misfire_grace_time=15 * 30,
)
```

---

## Testing Strategy

```
tests/
├── test_position_sizer.py   # pure math: various balance/risk/sl combinations, edge cases
├── test_executor.py         # mock broker + store: all 10 decision branches
├── test_paper_broker.py     # real SQLite: open trade, SL hit, TP hit, balance update
└── test_trades_store.py     # write_trade, get_open_trades, close_trade, account ops
```

**Coverage requirements:**
- `test_position_sizer.py`: normal case, sl_pips=0, result below min lot, large balance
- `test_executor.py`: no candles, no signal, stale signal, HOLD, open trade exists, null sl_pips, zero lot, BUY open, SELL open, SL close, TP close
- `test_paper_broker.py`: open → SL close, open → TP close, balance updates correctly
- `test_trades_store.py`: seed_account (idempotent), write_trade, get_open_trades (filters closed), close_trade

No real broker calls in tests. Store ops use temporary in-memory SQLite (`":memory:"`).

---

## New Dependencies

None. All libraries already present in `requirements.txt`.

---

## Phase 3 Contract for Phase 4

Phase 4 (Performance Tracking) reads trades via:
```python
store.get_open_trades(db_path, pair) -> pd.DataFrame
# and a new:
store.get_closed_trades(db_path, pair, n) -> pd.DataFrame
```

The `trades` and `account` table schemas are the stable interface. Phase 4 must not depend on `execution/` internals.
