# Phase 3: Trading Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add paper trading execution — read Phase 2 signals, open/close simulated trades with fixed-% risk sizing and SL/TP monitoring, and record results to SQLite.

**Architecture:** A new `execution/` package contains a `Broker` protocol, `PaperBroker` (writes to SQLite), `LiveBroker` (stub), a position sizer (pure math), and an executor orchestrator. A new APScheduler job calls `run_execution_cycle()` every 15m. All broker operations are isolated behind the `Broker` protocol so swapping to live later requires implementing one class.

**Tech Stack:** Python 3.11, SQLite via `sqlite3`, `pandas`, `APScheduler 3.x`, `pytest`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `storage/schema.sql` | Add `account` + `trades` tables |
| Modify | `storage/store.py` | Add account + trade CRUD functions |
| Create | `tests/test_trades_store.py` | Tests for new store functions |
| Create | `execution/__init__.py` | Package marker |
| Create | `execution/position_sizer.py` | `calculate_lot_size()` — pure math, no I/O |
| Create | `tests/test_position_sizer.py` | Tests for position sizing |
| Create | `execution/broker.py` | `Broker` Protocol (structural subtyping) |
| Create | `execution/paper_broker.py` | `PaperBroker` — delegates to store |
| Create | `execution/live_broker.py` | `LiveBroker` — stub, raises NotImplementedError |
| Create | `tests/test_paper_broker.py` | Integration tests for PaperBroker |
| Create | `execution/executor.py` | `run_execution_cycle()` orchestrator |
| Create | `tests/test_executor.py` | All decision branches for executor |
| Modify | `config.py` | Add `PAPER_BALANCE`, `RISK_PCT`, `BROKER_MODE` |
| Modify | `main.py` | Validate BROKER_MODE, seed account, pass broker to scheduler |
| Modify | `scheduler/jobs.py` | Accept broker arg, add execution job |
| Modify | `tests/test_analyzer.py` | Update scheduler test to pass mock broker |

---

### Task 1: Storage — account + trades schema and store functions

**Files:**
- Modify: `storage/schema.sql`
- Modify: `storage/store.py`
- Create: `tests/test_trades_store.py`

- [ ] **Step 1: Write failing tests for account operations**

Create `tests/test_trades_store.py`:

```python
import pytest
from storage import store


_SIGNAL = {
    "pair": "EURUSD", "timeframe": "15m", "timestamp": 1705334400,
    "created_at": 1705334500, "direction": "BUY", "confidence": 0.75,
    "sl_pips": 15.0, "tp_pips": 30.0, "claude_direction": "BUY",
    "claude_confidence": 0.78, "gemini_direction": "BUY",
    "gemini_confidence": 0.72, "reasoning": "test",
}


def _trade(signal_id: int) -> dict:
    return {
        "pair": "EURUSD", "timeframe": "15m", "signal_id": signal_id,
        "direction": "BUY", "entry_price": 1.0850,
        "sl_price": 1.0835, "tp_price": 1.0880,
        "lot_size": 0.67, "sl_pips": 15.0, "tp_pips": 30.0,
        "opened_at": 1705334600,
    }


def test_seed_account_sets_initial_balance(db_path):
    store.seed_account(db_path, 10000.0)
    assert store.get_account_balance(db_path) == pytest.approx(10000.0)


def test_seed_account_is_idempotent(db_path):
    store.seed_account(db_path, 10000.0)
    store.seed_account(db_path, 99999.0)
    assert store.get_account_balance(db_path) == pytest.approx(10000.0)


def test_get_account_balance_returns_zero_if_not_seeded(db_path):
    assert store.get_account_balance(db_path) == pytest.approx(0.0)


def test_update_account_balance(db_path):
    store.seed_account(db_path, 10000.0)
    store.update_account_balance(db_path, 10500.0)
    assert store.get_account_balance(db_path) == pytest.approx(10500.0)


def test_write_trade_returns_row_id(db_path):
    signal_id = store.write_signal(db_path, _SIGNAL)
    row_id = store.write_trade(db_path, _trade(signal_id))
    assert isinstance(row_id, int) and row_id > 0


def test_get_open_trades_returns_only_open(db_path):
    signal_id = store.write_signal(db_path, _SIGNAL)
    store.write_trade(db_path, _trade(signal_id))
    df = store.get_open_trades(db_path, "EURUSD")
    assert len(df) == 1
    assert df.iloc[0]["status"] == "open"


def test_get_open_trades_filters_by_pair(db_path):
    signal_id = store.write_signal(db_path, _SIGNAL)
    store.write_trade(db_path, _trade(signal_id))
    df = store.get_open_trades(db_path, "GBPUSD")
    assert len(df) == 0


def test_close_trade_updates_all_fields(db_path):
    signal_id = store.write_signal(db_path, _SIGNAL)
    trade_id = store.write_trade(db_path, _trade(signal_id))
    store.close_trade(db_path, trade_id, 1.0880, "tp", 30.0, 201.0)
    assert len(store.get_open_trades(db_path, "EURUSD")) == 0
    closed = store.get_closed_trades(db_path, "EURUSD", 1)
    assert len(closed) == 1
    row = closed.iloc[0]
    assert row["close_reason"] == "tp"
    assert row["close_price"] == pytest.approx(1.0880)
    assert row["pnl_pips"] == pytest.approx(30.0)
    assert row["pnl_usd"] == pytest.approx(201.0)
    assert row["status"] == "closed"


def test_get_closed_trades_excludes_open(db_path):
    signal_id = store.write_signal(db_path, _SIGNAL)
    store.write_trade(db_path, _trade(signal_id))
    assert len(store.get_closed_trades(db_path, "EURUSD", 10)) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd forex-ai
py -m pytest tests/test_trades_store.py -v
```

Expected: FAIL — `AttributeError: module 'storage.store' has no attribute 'seed_account'`

- [ ] **Step 3: Add account + trades tables to schema.sql**

Append to `storage/schema.sql` (after the existing signals table):

```sql
CREATE TABLE IF NOT EXISTS account (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    balance    REAL    NOT NULL,
    updated_at INTEGER NOT NULL
);

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

- [ ] **Step 4: Add store functions to storage/store.py**

Append to the end of `storage/store.py`:

```python
def seed_account(db_path: str, initial_balance: float) -> None:
    """Seed account with initial_balance on first run. Idempotent — no-op if row exists."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO account (id, balance, updated_at) VALUES (1, ?, ?)",
            (initial_balance, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def get_account_balance(db_path: str) -> float:
    """Return current account balance. Returns 0.0 if account not yet seeded."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT balance FROM account WHERE id = 1").fetchone()
        return float(row["balance"]) if row else 0.0
    finally:
        conn.close()


def update_account_balance(db_path: str, new_balance: float) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE account SET balance = ?, updated_at = ? WHERE id = 1",
            (new_balance, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def write_trade(db_path: str, trade: dict) -> int:
    """Insert a new trade. Returns the new row id."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO trades "
            "(pair, timeframe, signal_id, direction, entry_price, sl_price, tp_price, "
            "lot_size, sl_pips, tp_pips, opened_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trade["pair"], trade["timeframe"], trade["signal_id"],
                trade["direction"], trade["entry_price"],
                trade["sl_price"], trade["tp_price"],
                trade["lot_size"], trade["sl_pips"], trade["tp_pips"],
                trade["opened_at"],
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_open_trades(db_path: str, pair: str) -> pd.DataFrame:
    """Return all open trades for the given pair."""
    conn = get_connection(db_path)
    try:
        return pd.read_sql_query(
            "SELECT * FROM trades WHERE pair = ? AND status = 'open'",
            conn,
            params=(pair,),
        )
    finally:
        conn.close()


def close_trade(
    db_path: str,
    trade_id: int,
    close_price: float,
    close_reason: str,
    pnl_pips: float,
    pnl_usd: float,
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE trades SET status='closed', closed_at=?, close_price=?, "
            "close_reason=?, pnl_pips=?, pnl_usd=? WHERE id=?",
            (int(time.time()), close_price, close_reason, pnl_pips, pnl_usd, trade_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_closed_trades(db_path: str, pair: str, n: int) -> pd.DataFrame:
    """Return the n most recent closed trades for the given pair, sorted oldest-first."""
    conn = get_connection(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM trades WHERE pair = ? AND status = 'closed' "
            "ORDER BY closed_at DESC LIMIT ?",
            conn,
            params=(pair, n),
        )
        return df.sort_values("closed_at").reset_index(drop=True)
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests to verify they pass**

```
py -m pytest tests/test_trades_store.py -v
```

Expected: 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add storage/schema.sql storage/store.py tests/test_trades_store.py
git commit -m "feat: add account and trades tables with store functions"
```

---

### Task 2: Position sizer

**Files:**
- Create: `execution/__init__.py`
- Create: `execution/position_sizer.py`
- Create: `tests/test_position_sizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_position_sizer.py`:

```python
import pytest
from execution.position_sizer import calculate_lot_size


def test_normal_case():
    # $10,000 * 1% / (15 pips * $10/pip/lot) = $100 / $150 = 0.6666... → 0.67
    result = calculate_lot_size(10000.0, 0.01, 15.0)
    assert result == pytest.approx(0.67)


def test_large_balance():
    # $100,000 * 2% / (20 pips * $10) = $2,000 / $200 = 10.0 lots
    result = calculate_lot_size(100000.0, 0.02, 20.0)
    assert result == pytest.approx(10.0)


def test_sl_pips_zero_returns_zero():
    result = calculate_lot_size(10000.0, 0.01, 0.0)
    assert result == 0.0


def test_sl_pips_negative_returns_zero():
    result = calculate_lot_size(10000.0, 0.01, -5.0)
    assert result == 0.0


def test_result_below_minimum_returns_zero():
    # $100 * 1% / (1000 pips * $10) = $1 / $10,000 = 0.0001 → rounds to 0.0
    result = calculate_lot_size(100.0, 0.01, 1000.0)
    assert result == 0.0


def test_rounds_to_two_decimal_places():
    # $10,000 * 1% / (7 pips * $10) = $100 / $70 = 1.42857... → 1.43
    result = calculate_lot_size(10000.0, 0.01, 7.0)
    assert result == pytest.approx(1.43)
```

- [ ] **Step 2: Run tests to verify they fail**

```
py -m pytest tests/test_position_sizer.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'execution'`

- [ ] **Step 3: Create execution package and position sizer**

Create `execution/__init__.py` (empty):
```python
```

Create `execution/position_sizer.py`:

```python
PIP_VALUE_PER_LOT = 10.0  # USD per pip per standard lot for EURUSD


def calculate_lot_size(balance: float, risk_pct: float, sl_pips: float) -> float:
    """
    Calculate EURUSD position size.

    Args:
        balance: Account balance in USD.
        risk_pct: Fraction of balance to risk (e.g. 0.01 = 1%).
        sl_pips: Stop-loss distance in pips.

    Returns:
        Lot size rounded to 2 decimal places, minimum 0.01.
        Returns 0.0 if sl_pips <= 0 or result is below minimum lot size.
    """
    if sl_pips <= 0:
        return 0.0
    risk_amount = balance * risk_pct
    raw = risk_amount / (sl_pips * PIP_VALUE_PER_LOT)
    lot = round(raw, 2)
    return lot if lot >= 0.01 else 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

```
py -m pytest tests/test_position_sizer.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add execution/__init__.py execution/position_sizer.py tests/test_position_sizer.py
git commit -m "feat: add position sizer with fixed-percent risk calculation"
```

---

### Task 3: Broker protocol, PaperBroker, LiveBroker

**Files:**
- Create: `execution/broker.py`
- Create: `execution/paper_broker.py`
- Create: `execution/live_broker.py`
- Create: `tests/test_paper_broker.py`

- [ ] **Step 1: Write failing tests for PaperBroker**

Create `tests/test_paper_broker.py`:

```python
import pytest
from storage import store
from execution.paper_broker import PaperBroker


_SIGNAL = {
    "pair": "EURUSD", "timeframe": "15m", "timestamp": 1705334400,
    "created_at": 1705334500, "direction": "BUY", "confidence": 0.75,
    "sl_pips": 15.0, "tp_pips": 30.0, "claude_direction": "BUY",
    "claude_confidence": 0.78, "gemini_direction": "BUY",
    "gemini_confidence": 0.72, "reasoning": "test",
}


def _open_trade(signal_id: int, direction: str = "BUY") -> dict:
    return {
        "pair": "EURUSD", "timeframe": "15m", "signal_id": signal_id,
        "direction": direction, "entry_price": 1.0850,
        "sl_price": 1.0835, "tp_price": 1.0880,
        "lot_size": 0.67, "sl_pips": 15.0, "tp_pips": 30.0,
        "opened_at": 1705334600,
    }


def test_open_trade_writes_to_db(db_path):
    store.seed_account(db_path, 10000.0)
    broker = PaperBroker(db_path)
    signal_id = store.write_signal(db_path, _SIGNAL)
    broker.open_trade(_open_trade(signal_id))
    open_trades = store.get_open_trades(db_path, "EURUSD")
    assert len(open_trades) == 1
    assert open_trades.iloc[0]["direction"] == "BUY"


def test_get_balance_returns_seeded_amount(db_path):
    store.seed_account(db_path, 10000.0)
    broker = PaperBroker(db_path)
    assert broker.get_balance() == pytest.approx(10000.0)


def test_close_trade_on_tp_increases_balance(db_path):
    store.seed_account(db_path, 10000.0)
    broker = PaperBroker(db_path)
    signal_id = store.write_signal(db_path, _SIGNAL)
    broker.open_trade(_open_trade(signal_id))
    trade = store.get_open_trades(db_path, "EURUSD").iloc[0]
    # BUY TP hit: +30 pips * $10/lot * 0.67 lot = +$201
    pnl_pips, pnl_usd = 30.0, 30.0 * 10 * float(trade["lot_size"])
    broker.close_trade(int(trade["id"]), 1.0880, "tp", pnl_pips, pnl_usd)
    assert broker.get_balance() == pytest.approx(10000.0 + pnl_usd)
    closed = store.get_closed_trades(db_path, "EURUSD", 1)
    assert closed.iloc[0]["close_reason"] == "tp"


def test_close_trade_on_sl_reduces_balance(db_path):
    store.seed_account(db_path, 10000.0)
    broker = PaperBroker(db_path)
    signal_id = store.write_signal(db_path, _SIGNAL)
    broker.open_trade(_open_trade(signal_id))
    trade = store.get_open_trades(db_path, "EURUSD").iloc[0]
    # BUY SL hit: -15 pips * $10/lot * 0.67 lot = -$100.5
    pnl_pips, pnl_usd = -15.0, -15.0 * 10 * float(trade["lot_size"])
    broker.close_trade(int(trade["id"]), 1.0835, "sl", pnl_pips, pnl_usd)
    assert broker.get_balance() == pytest.approx(10000.0 + pnl_usd)
    closed = store.get_closed_trades(db_path, "EURUSD", 1)
    assert closed.iloc[0]["close_reason"] == "sl"
```

- [ ] **Step 2: Run tests to verify they fail**

```
py -m pytest tests/test_paper_broker.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'execution.paper_broker'`

- [ ] **Step 3: Create broker.py**

Create `execution/broker.py`:

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class Broker(Protocol):
    def open_trade(self, trade: dict) -> None: ...

    def close_trade(
        self,
        trade_id: int,
        close_price: float,
        close_reason: str,
        pnl_pips: float,
        pnl_usd: float,
    ) -> None: ...

    def get_balance(self) -> float: ...
```

- [ ] **Step 4: Create paper_broker.py**

Create `execution/paper_broker.py`:

```python
from storage import store


class PaperBroker:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def open_trade(self, trade: dict) -> None:
        store.write_trade(self._db_path, trade)

    def close_trade(
        self,
        trade_id: int,
        close_price: float,
        close_reason: str,
        pnl_pips: float,
        pnl_usd: float,
    ) -> None:
        store.close_trade(self._db_path, trade_id, close_price, close_reason, pnl_pips, pnl_usd)
        balance = store.get_account_balance(self._db_path)
        store.update_account_balance(self._db_path, balance + pnl_usd)

    def get_balance(self) -> float:
        return store.get_account_balance(self._db_path)
```

- [ ] **Step 5: Create live_broker.py**

Create `execution/live_broker.py`:

```python
class LiveBroker:
    def open_trade(self, trade: dict) -> None:
        raise NotImplementedError("Live execution not yet implemented")

    def close_trade(
        self,
        trade_id: int,
        close_price: float,
        close_reason: str,
        pnl_pips: float,
        pnl_usd: float,
    ) -> None:
        raise NotImplementedError("Live execution not yet implemented")

    def get_balance(self) -> float:
        raise NotImplementedError("Live execution not yet implemented")
```

- [ ] **Step 6: Run tests to verify they pass**

```
py -m pytest tests/test_paper_broker.py -v
```

Expected: 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add execution/broker.py execution/paper_broker.py execution/live_broker.py tests/test_paper_broker.py
git commit -m "feat: add Broker protocol, PaperBroker, and LiveBroker stub"
```

---

### Task 4: Executor

**Files:**
- Create: `execution/executor.py`
- Create: `tests/test_executor.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_executor.py`:

```python
import pytest
import time
import pandas as pd
from unittest.mock import MagicMock, patch
from execution.executor import run_execution_cycle, SIGNAL_MAX_AGE_SECONDS


def _candle(high=1.0870, low=1.0840, close=1.0855, ts=None):
    ts = ts or int(time.time()) - 60
    return pd.DataFrame([{
        "id": 1, "pair": "EURUSD", "timeframe": "15m", "timestamp": ts,
        "open": 1.0850, "high": high, "low": low, "close": close, "volume": 1000.0,
    }])


def _signal(direction="BUY", sl=15.0, tp=30.0, ts=None):
    ts = ts or int(time.time()) - 60
    return pd.DataFrame([{
        "id": 1, "pair": "EURUSD", "timeframe": "15m", "timestamp": ts,
        "created_at": ts + 10, "direction": direction, "confidence": 0.75,
        "sl_pips": sl, "tp_pips": tp, "reasoning": "test",
        "claude_direction": direction, "claude_confidence": 0.75,
        "gemini_direction": direction, "gemini_confidence": 0.75,
    }])


def _open_trade(direction="BUY", sl_price=1.0835, tp_price=1.0880):
    return pd.DataFrame([{
        "id": 1, "pair": "EURUSD", "direction": direction,
        "entry_price": 1.0850, "sl_price": sl_price, "tp_price": tp_price,
        "lot_size": 0.67, "sl_pips": 15.0, "tp_pips": 30.0,
        "opened_at": int(time.time()) - 200, "status": "open",
    }])


def _mock_broker(balance=10000.0):
    broker = MagicMock()
    broker.get_balance.return_value = balance
    return broker


@patch("execution.executor.store")
def test_no_candles_skips_cycle(mock_store):
    mock_store.get_latest_candles.return_value = pd.DataFrame()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()
    broker.close_trade.assert_not_called()


@patch("execution.executor.store")
def test_no_signal_skips_open(mock_store):
    mock_store.get_latest_candles.return_value = _candle()
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = pd.DataFrame()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_stale_signal_skips_open(mock_store):
    stale_ts = int(time.time()) - SIGNAL_MAX_AGE_SECONDS - 100
    mock_store.get_latest_candles.return_value = _candle()
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(ts=stale_ts)
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_hold_signal_skips_open(mock_store):
    mock_store.get_latest_candles.return_value = _candle()
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="HOLD", sl=None, tp=None)
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_existing_open_trade_skips_new_open(mock_store):
    # Candle that does NOT trigger the open trade's SL or TP
    # open trade: sl_price=1.0835, tp_price=1.0880; candle: low=1.0840, high=1.0870 → no hit
    mock_store.get_latest_candles.return_value = _candle(high=1.0870, low=1.0840)
    mock_store.get_open_trades.return_value = _open_trade()
    mock_store.get_latest_signals.return_value = _signal()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_null_sl_pips_skips_open(mock_store):
    mock_store.get_latest_candles.return_value = _candle()
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="BUY", sl=None, tp=None)
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_not_called()


@patch("execution.executor.store")
def test_buy_signal_opens_trade_with_correct_prices(mock_store):
    mock_store.get_latest_candles.return_value = _candle(close=1.0855)
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="BUY", sl=15.0, tp=30.0)
    broker = _mock_broker(balance=10000.0)
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_called_once()
    trade = broker.open_trade.call_args[0][0]
    assert trade["direction"] == "BUY"
    assert trade["sl_price"] == pytest.approx(1.0855 - 15 * 0.0001, abs=1e-5)
    assert trade["tp_price"] == pytest.approx(1.0855 + 30 * 0.0001, abs=1e-5)
    assert trade["lot_size"] > 0


@patch("execution.executor.store")
def test_sell_signal_opens_trade_with_correct_prices(mock_store):
    mock_store.get_latest_candles.return_value = _candle(close=1.0855)
    mock_store.get_open_trades.return_value = pd.DataFrame()
    mock_store.get_latest_signals.return_value = _signal(direction="SELL", sl=15.0, tp=30.0)
    broker = _mock_broker(balance=10000.0)
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.open_trade.assert_called_once()
    trade = broker.open_trade.call_args[0][0]
    assert trade["direction"] == "SELL"
    assert trade["sl_price"] == pytest.approx(1.0855 + 15 * 0.0001, abs=1e-5)
    assert trade["tp_price"] == pytest.approx(1.0855 - 30 * 0.0001, abs=1e-5)


@patch("execution.executor.store")
def test_buy_sl_hit_closes_trade(mock_store):
    trade = _open_trade("BUY", sl_price=1.0835, tp_price=1.0880)
    # low=1.0830 goes below sl_price=1.0835 → SL hit
    mock_store.get_latest_candles.return_value = _candle(high=1.0845, low=1.0830, close=1.0832)
    mock_store.get_open_trades.side_effect = [trade, pd.DataFrame()]
    mock_store.get_latest_signals.return_value = pd.DataFrame()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.close_trade.assert_called_once()
    assert broker.close_trade.call_args[0][2] == "sl"


@patch("execution.executor.store")
def test_buy_tp_hit_closes_trade(mock_store):
    trade = _open_trade("BUY", sl_price=1.0835, tp_price=1.0880)
    # high=1.0885 goes above tp_price=1.0880 → TP hit
    mock_store.get_latest_candles.return_value = _candle(high=1.0885, low=1.0860, close=1.0882)
    mock_store.get_open_trades.side_effect = [trade, pd.DataFrame()]
    mock_store.get_latest_signals.return_value = pd.DataFrame()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.close_trade.assert_called_once()
    assert broker.close_trade.call_args[0][2] == "tp"


@patch("execution.executor.store")
def test_sl_takes_priority_over_tp_gap(mock_store):
    trade = _open_trade("BUY", sl_price=1.0835, tp_price=1.0880)
    # Both SL and TP hit in same candle (gap) — SL wins
    mock_store.get_latest_candles.return_value = _candle(high=1.0900, low=1.0820, close=1.0850)
    mock_store.get_open_trades.side_effect = [trade, pd.DataFrame()]
    mock_store.get_latest_signals.return_value = pd.DataFrame()
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    broker.close_trade.assert_called_once()
    assert broker.close_trade.call_args[0][2] == "sl"


@patch("execution.executor.store")
def test_exception_logs_to_fetch_log_and_does_not_raise(mock_store):
    mock_store.get_latest_candles.side_effect = Exception("DB error")
    broker = _mock_broker()
    run_execution_cycle("test.db", "EURUSD", "15m", broker)
    mock_store.write_fetch_log.assert_called_once_with(
        "test.db", "EURUSD", "15m", "executor", "error", "DB error", None
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```
py -m pytest tests/test_executor.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'execution.executor'`

- [ ] **Step 3: Implement executor.py**

Create `execution/executor.py`:

```python
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
) -> None:
    """
    Execute one full cycle: check SL/TP on open trades, then open a new trade if warranted.
    Never raises — all exceptions are logged to fetch_log with provider='executor'.
    """
    try:
        _cycle(db_path, pair, timeframe, broker, risk_pct)
    except Exception as exc:
        logger.error("Execution cycle failed for %s %s: %s", pair, timeframe, exc)
        store.write_fetch_log(db_path, pair, timeframe, "executor", "error", str(exc), None)


def _cycle(
    db_path: str, pair: str, timeframe: str, broker: Broker, risk_pct: float
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
        _check_sl_tp(trade, candle, broker)

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

    # Step 7: Validate sl_pips
    sl_pips = signal["sl_pips"]
    tp_pips = signal["tp_pips"]
    if pd.isna(sl_pips) or sl_pips <= 0:
        logger.warning("Signal for %s has no valid sl_pips — skipping open", pair)
        return

    # Step 8: Validate balance
    balance = broker.get_balance()
    if balance <= 0:
        logger.warning("Account balance is %.2f — skipping trade", balance)
        return

    # Step 9: Calculate position size
    lot_size = calculate_lot_size(balance, risk_pct, sl_pips)
    if lot_size == 0.0:
        logger.warning("Lot size rounds to 0 for %s (balance=%.2f, sl=%.1f) — skipping", pair, balance, sl_pips)
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


def _check_sl_tp(trade, candle, broker: Broker) -> None:
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
py -m pytest tests/test_executor.py -v
```

Expected: 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add execution/executor.py tests/test_executor.py
git commit -m "feat: add execution orchestrator with SL/TP monitoring and trade opening"
```

---

### Task 5: Wiring — config, main.py, scheduler

**Files:**
- Modify: `config.py`
- Modify: `main.py`
- Modify: `scheduler/jobs.py`
- Modify: `tests/test_analyzer.py` (update existing scheduler test)

- [ ] **Step 1: Update config.py**

Add to the end of `config.py`:

```python
PAPER_BALANCE: float = float(os.getenv("PAPER_BALANCE", "10000"))
RISK_PCT: float = float(os.getenv("RISK_PCT", "0.01"))
BROKER_MODE: str = os.getenv("BROKER_MODE", "paper")
```

- [ ] **Step 2: Update scheduler/jobs.py to accept broker and add execution job**

Replace the full contents of `scheduler/jobs.py` with:

```python
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from ai.analyzer import run_analysis_cycle
from data.fetcher import run_fetch_cycle
from execution.broker import Broker
from execution.executor import run_execution_cycle

logger = logging.getLogger(__name__)


def create_scheduler(broker: Broker) -> BlockingScheduler:
    scheduler = BlockingScheduler()

    for timeframe, interval_minutes in [("15m", 15), ("1H", 60)]:
        scheduler.add_job(
            run_fetch_cycle,
            trigger="interval",
            minutes=interval_minutes,
            id=f"fetch_{timeframe}",
            kwargs={
                "db_path": config.DB_PATH,
                "api_key": config.ALPHA_VANTAGE_API_KEY,
                "pair": config.PAIR,
                "timeframe": timeframe,
            },
            misfire_grace_time=interval_minutes * 30,
        )
        logger.info(
            "Scheduled %s %s fetch job every %d minutes",
            config.PAIR, timeframe, interval_minutes,
        )

    scheduler.add_job(
        run_analysis_cycle,
        trigger="interval",
        minutes=15,
        id="analyze_15m",
        kwargs={
            "db_path": config.DB_PATH,
            "pair": config.PAIR,
            "timeframe": "15m",
        },
        misfire_grace_time=15 * 30,
    )
    logger.info("Scheduled %s 15m analysis job every 15 minutes", config.PAIR)

    scheduler.add_job(
        run_execution_cycle,
        trigger="interval",
        minutes=15,
        id="execute_15m",
        kwargs={
            "db_path": config.DB_PATH,
            "pair": config.PAIR,
            "timeframe": "15m",
            "broker": broker,
            "risk_pct": config.RISK_PCT,
        },
        misfire_grace_time=15 * 30,
    )
    logger.info("Scheduled %s 15m execution job every 15 minutes", config.PAIR)

    return scheduler
```

- [ ] **Step 3: Update test_analyzer.py to pass mock broker to create_scheduler**

In `tests/test_analyzer.py`, replace the `test_scheduler_has_analysis_job` function:

```python
def test_scheduler_has_analysis_job():
    from scheduler.jobs import create_scheduler
    from unittest.mock import MagicMock
    broker = MagicMock()
    scheduler = create_scheduler(broker)
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert "analyze_15m" in job_ids
    analysis_job = next(j for j in scheduler.get_jobs() if j.id == "analyze_15m")
    assert analysis_job.trigger.interval.total_seconds() == 900  # 15 minutes
    assert analysis_job.kwargs["timeframe"] == "15m"
    assert "db_path" in analysis_job.kwargs
    assert "pair" in analysis_job.kwargs
    scheduler.remove_all_jobs()
```

- [ ] **Step 4: Run tests to verify the existing scheduler test still passes**

```
py -m pytest tests/test_analyzer.py::test_scheduler_has_analysis_job -v
```

Expected: PASS

- [ ] **Step 5: Update main.py**

Replace the full contents of `main.py` with:

```python
import logging
import sys

import config
from data.fetcher import backfill
from execution.paper_broker import PaperBroker
from scheduler.jobs import create_scheduler
from storage import store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("forex_ai.log"),
    ],
)

logger = logging.getLogger(__name__)


def main() -> None:
    if not config.ALPHA_VANTAGE_API_KEY:
        logger.error(
            "ALPHA_VANTAGE_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )
        sys.exit(1)
    if not config.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY is not set. Add it to .env")
        sys.exit(1)
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set. Add it to .env")
        sys.exit(1)
    if config.BROKER_MODE == "live":
        logger.error("BROKER_MODE=live is not yet implemented. Use BROKER_MODE=paper.")
        sys.exit(1)

    logger.info("Initialising database at %s", config.DB_PATH)
    store.init_db(config.DB_PATH)
    store.seed_account(config.DB_PATH, config.PAPER_BALANCE)
    logger.info("Paper account balance: $%.2f", store.get_account_balance(config.DB_PATH))

    logger.info("Backfilling history for %s...", config.PAIR)
    for timeframe in config.TIMEFRAMES:
        backfill(config.DB_PATH, config.ALPHA_VANTAGE_API_KEY, config.PAIR, timeframe)

    broker = PaperBroker(config.DB_PATH)
    logger.info("Starting scheduler. Press Ctrl+C to stop.")
    scheduler = create_scheduler(broker)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the full test suite**

```
py -m pytest tests/ -v
```

Expected: All tests PASS (previous 89 + new tests)

- [ ] **Step 7: Commit**

```bash
git add config.py main.py scheduler/jobs.py tests/test_analyzer.py
git commit -m "feat: wire execution job into scheduler with PaperBroker and account seeding"
```

---

## Self-Review

**Spec coverage check:**
- ✅ account table + seed_account (Task 1)
- ✅ trades table + all CRUD (Task 1)
- ✅ Fixed % risk, calculate_lot_size, min lot 0.01, EURUSD pip value $10 (Task 2)
- ✅ Broker Protocol (Task 3)
- ✅ PaperBroker delegates to store (Task 3)
- ✅ LiveBroker stub with NotImplementedError (Task 3)
- ✅ SL/TP monitoring with high/low (Task 4)
- ✅ SL priority on gap (Task 4)
- ✅ SIGNAL_MAX_AGE_SECONDS freshness guard (Task 4)
- ✅ One trade at a time (Task 4)
- ✅ All error paths: no candles, no signal, stale, HOLD, open trade, null sl, zero lot, exception→fetch_log (Task 4)
- ✅ PAPER_BALANCE, RISK_PCT, BROKER_MODE in config (Task 5)
- ✅ BROKER_MODE=live → sys.exit(1) in main.py (Task 5)
- ✅ seed_account on startup (Task 5)
- ✅ execution job every 15m in scheduler (Task 5)
- ✅ get_closed_trades for Phase 4 contract (Task 1)
