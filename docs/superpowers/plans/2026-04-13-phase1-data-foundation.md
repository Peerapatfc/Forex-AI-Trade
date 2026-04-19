# Phase 1: Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a continuously-running Python service that fetches EUR/USD OHLCV candles from Alpha Vantage (with yfinance fallback), calculates 7 technical indicators, and persists everything to SQLite — ready for the Phase 2 AI pipeline to query.

**Architecture:** APScheduler fires two jobs (every 15m and every 60m). Each job calls `data/fetcher.py` which calls `data/providers.py` for OHLCV data, passes it to `indicators/engine.py` for TA calculations, and writes the result through `storage/store.py` to SQLite. `store.py` exposes a clean read interface that Phase 2 will consume without touching the pipeline internals.

**Tech Stack:** Python 3.11+, APScheduler 3.10, pandas 2.0, pandas-ta 0.3.14b, requests 2.31, yfinance 0.2.40, python-dotenv 1.0, pytest 8.0, SQLite (stdlib)

---

## File Map

| File | Responsibility |
|---|---|
| `config.py` | All settings; reads API keys from `.env` |
| `storage/schema.sql` | SQL `CREATE TABLE` statements |
| `storage/store.py` | All SQLite reads and writes; the Phase 2 contract |
| `indicators/engine.py` | pandas-ta wrapper; returns indicator dict for latest candle |
| `data/providers.py` | Alpha Vantage client, yfinance client, RateLimiter, fallback logic |
| `data/fetcher.py` | Orchestrates one fetch → indicators → store cycle |
| `scheduler/jobs.py` | APScheduler job definitions |
| `main.py` | Entry point: init DB, backfill, start scheduler |
| `tests/conftest.py` | Shared `db_path` fixture |
| `tests/fixtures/gen_fixture.py` | Script to generate `eurusd_15m.json` test fixture |
| `tests/fixtures/eurusd_15m.json` | 200 synthetic EUR/USD 15m candles (generated once, committed) |
| `tests/test_indicators.py` | Indicator engine unit tests (offline, fixture-based) |
| `tests/test_fetcher.py` | Provider and fetcher unit tests (mock HTTP) |
| `tests/test_pipeline.py` | End-to-end integration tests (in-memory SQLite, mock fetch) |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `forex-ai/requirements.txt`
- Create: `forex-ai/.env.example`
- Create: `forex-ai/config.py`
- Create: `forex-ai/storage/__init__.py` (empty)
- Create: `forex-ai/indicators/__init__.py` (empty)
- Create: `forex-ai/data/__init__.py` (empty)
- Create: `forex-ai/scheduler/__init__.py` (empty)
- Create: `forex-ai/tests/__init__.py` (empty)
- Create: `forex-ai/tests/fixtures/` (directory)

- [ ] **Step 1: Create the project root directory**

```bash
mkdir -p forex-ai/storage forex-ai/indicators forex-ai/data forex-ai/scheduler \
         forex-ai/tests/fixtures
touch forex-ai/storage/__init__.py forex-ai/indicators/__init__.py \
      forex-ai/data/__init__.py forex-ai/scheduler/__init__.py \
      forex-ai/tests/__init__.py
```

- [ ] **Step 2: Write `requirements.txt`**

```
apscheduler>=3.10,<4.0
pandas>=2.0,<3.0
pandas-ta>=0.3.14b
requests>=2.31,<3.0
yfinance>=0.2.40
python-dotenv>=1.0,<2.0
pytest>=8.0,<9.0
```

- [ ] **Step 3: Write `.env.example`**

```
ALPHA_VANTAGE_API_KEY=your_key_here
DB_PATH=forex.db
```

Get a free Alpha Vantage key at https://www.alphavantage.co/support/#api-key — takes 30 seconds.

- [ ] **Step 4: Write `config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
DB_PATH: str = os.getenv("DB_PATH", "forex.db")
PAIR: str = "EURUSD"
TIMEFRAMES: list[str] = ["15m", "1H"]
BACKFILL_CANDLES: int = 200
```

- [ ] **Step 5: Copy `.env.example` to `.env` and fill in your key**

```bash
cp forex-ai/.env.example forex-ai/.env
# Edit .env and replace 'your_key_here' with your actual Alpha Vantage key
```

- [ ] **Step 6: Install dependencies**

```bash
cd forex-ai && pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 7: Commit**

```bash
cd forex-ai
git init
git add requirements.txt .env.example config.py storage/__init__.py \
        indicators/__init__.py data/__init__.py scheduler/__init__.py \
        tests/__init__.py
git commit -m "feat: project scaffolding — directories, config, dependencies"
```

---

## Task 2: SQLite Schema

**Files:**
- Create: `forex-ai/storage/schema.sql`

- [ ] **Step 1: Write `storage/schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS candles (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pair      TEXT    NOT NULL,
    timeframe TEXT    NOT NULL,
    timestamp INTEGER NOT NULL,
    open      REAL    NOT NULL,
    high      REAL    NOT NULL,
    low       REAL    NOT NULL,
    close     REAL    NOT NULL,
    volume    REAL    NOT NULL,
    UNIQUE(pair, timeframe, timestamp)
);

CREATE TABLE IF NOT EXISTS indicators (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    candle_id   INTEGER NOT NULL REFERENCES candles(id),
    ema20       REAL,
    ema50       REAL,
    ema200      REAL,
    rsi14       REAL,
    macd        REAL,
    macd_signal REAL,
    macd_hist   REAL,
    bb_upper    REAL,
    bb_mid      REAL,
    bb_lower    REAL,
    atr14       REAL,
    stoch_k     REAL,
    stoch_d     REAL
);

CREATE TABLE IF NOT EXISTS fetch_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   INTEGER NOT NULL,
    pair        TEXT    NOT NULL,
    timeframe   TEXT    NOT NULL,
    provider    TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    error_msg   TEXT,
    duration_ms INTEGER
);
```

- [ ] **Step 2: Commit**

```bash
git add storage/schema.sql
git commit -m "feat: SQLite schema — candles, indicators, fetch_log tables"
```

---

## Task 3: Store Write Methods (TDD)

**Files:**
- Create: `forex-ai/tests/conftest.py`
- Create: `forex-ai/storage/store.py` (write methods only; read methods added in Task 4)

- [ ] **Step 1: Write `tests/conftest.py`**

```python
import pytest
from storage.store import init_db


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test_forex.db")
    init_db(path)
    return path
```

- [ ] **Step 2: Write failing tests for write methods in `tests/test_pipeline.py`**

Create the file with only these tests for now (more will be added in Task 8):

```python
import sqlite3
import pytest
from storage import store


def test_init_db_creates_tables(db_path):
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert {"candles", "indicators", "fetch_log"} == tables


def test_write_candle_returns_row_id(db_path):
    candle = {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
              "low": 1.084, "close": 1.0855, "volume": 1000.0}
    row_id = store.write_candle(db_path, "EURUSD", "15m", candle)
    assert isinstance(row_id, int)
    assert row_id > 0


def test_write_candle_duplicate_returns_none(db_path):
    candle = {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
              "low": 1.084, "close": 1.0855, "volume": 1000.0}
    store.write_candle(db_path, "EURUSD", "15m", candle)
    second = store.write_candle(db_path, "EURUSD", "15m", candle)
    assert second is None


def test_write_indicators_stores_all_fields(db_path):
    candle = {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
              "low": 1.084, "close": 1.0855, "volume": 1000.0}
    candle_id = store.write_candle(db_path, "EURUSD", "15m", candle)
    ind = {"ema20": 1.0850, "ema50": 1.0840, "ema200": 1.0830,
           "rsi14": 55.0, "macd": 0.0003, "macd_signal": 0.0002, "macd_hist": 0.0001,
           "bb_upper": 1.0870, "bb_mid": 1.0855, "bb_lower": 1.0840,
           "atr14": 0.0008, "stoch_k": 60.0, "stoch_d": 58.0}
    store.write_indicators(db_path, candle_id, ind)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT * FROM indicators WHERE candle_id=?", (candle_id,)).fetchone()
    conn.close()
    assert row is not None
    assert abs(row[2] - 1.0850) < 1e-6  # ema20 is column index 2


def test_write_fetch_log_stores_entry(db_path):
    store.write_fetch_log(db_path, "EURUSD", "15m", "alpha_vantage", "ok", None, 312)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT provider, status, duration_ms FROM fetch_log").fetchone()
    conn.close()
    assert row == ("alpha_vantage", "ok", 312)
```

- [ ] **Step 3: Run tests — verify they fail with `NameError` or `ImportError`**

```bash
cd forex-ai && pytest tests/test_pipeline.py -v
```

Expected: FAILED — `ModuleNotFoundError: No module named 'storage.store'`

- [ ] **Step 4: Implement `storage/store.py` write methods**

```python
import sqlite3
import time
from pathlib import Path

import pandas as pd

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    conn.close()


def write_candle(db_path: str, pair: str, timeframe: str, candle: dict) -> int | None:
    """Insert a candle. Returns new row id, or None if a duplicate (same pair/timeframe/timestamp)."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO candles "
            "(pair, timeframe, timestamp, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pair, timeframe, candle["timestamp"], candle["open"], candle["high"],
             candle["low"], candle["close"], candle["volume"]),
        )
        conn.commit()
        return cur.lastrowid if cur.rowcount > 0 else None
    finally:
        conn.close()


def write_indicators(db_path: str, candle_id: int, ind: dict) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO indicators "
            "(candle_id, ema20, ema50, ema200, rsi14, macd, macd_signal, macd_hist, "
            "bb_upper, bb_mid, bb_lower, atr14, stoch_k, stoch_d) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                candle_id,
                ind.get("ema20"), ind.get("ema50"), ind.get("ema200"),
                ind.get("rsi14"),
                ind.get("macd"), ind.get("macd_signal"), ind.get("macd_hist"),
                ind.get("bb_upper"), ind.get("bb_mid"), ind.get("bb_lower"),
                ind.get("atr14"),
                ind.get("stoch_k"), ind.get("stoch_d"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def write_fetch_log(
    db_path: str,
    pair: str,
    timeframe: str,
    provider: str,
    status: str,
    error_msg: str | None = None,
    duration_ms: int | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO fetch_log (timestamp, pair, timeframe, provider, status, error_msg, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (int(time.time()), pair, timeframe, provider, status, error_msg, duration_ms),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_pipeline.py -v
```

Expected:
```
test_pipeline.py::test_init_db_creates_tables PASSED
test_pipeline.py::test_write_candle_returns_row_id PASSED
test_pipeline.py::test_write_candle_duplicate_returns_none PASSED
test_pipeline.py::test_write_indicators_stores_all_fields PASSED
test_pipeline.py::test_write_fetch_log_stores_entry PASSED
```

- [ ] **Step 6: Commit**

```bash
git add storage/store.py tests/conftest.py tests/test_pipeline.py
git commit -m "feat: store write methods — candles, indicators, fetch_log with duplicate prevention"
```

---

## Task 4: Store Read Interface (TDD)

**Files:**
- Modify: `forex-ai/tests/test_pipeline.py` (append read tests)
- Modify: `forex-ai/storage/store.py` (append read methods)

- [ ] **Step 1: Append read tests to `tests/test_pipeline.py`**

Add these functions to the end of the existing file:

```python
def test_get_latest_candles_returns_dataframe(db_path):
    for i in range(5):
        store.write_candle(db_path, "EURUSD", "15m",
                           {"timestamp": 1705334400 + i * 900,
                            "open": 1.085, "high": 1.086, "low": 1.084,
                            "close": 1.0855, "volume": 1000.0})

    df = store.get_latest_candles(db_path, "EURUSD", "15m", 3)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert list(df.columns[:2]) == ["id", "pair"]
    assert df["timestamp"].is_monotonic_increasing


def test_get_latest_candles_respects_timeframe_filter(db_path):
    store.write_candle(db_path, "EURUSD", "15m",
                       {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
                        "low": 1.084, "close": 1.0855, "volume": 1000.0})
    store.write_candle(db_path, "EURUSD", "1H",
                       {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
                        "low": 1.084, "close": 1.0855, "volume": 1000.0})

    df_15m = store.get_latest_candles(db_path, "EURUSD", "15m", 10)
    df_1h = store.get_latest_candles(db_path, "EURUSD", "1H", 10)

    assert len(df_15m) == 1
    assert len(df_1h) == 1


def test_get_candle_with_indicators_returns_dict(db_path):
    candle = {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
              "low": 1.084, "close": 1.0855, "volume": 1000.0}
    candle_id = store.write_candle(db_path, "EURUSD", "15m", candle)
    store.write_indicators(db_path, candle_id,
                           {"ema20": 1.0850, "ema50": None, "ema200": None,
                            "rsi14": 55.0, "macd": None, "macd_signal": None, "macd_hist": None,
                            "bb_upper": None, "bb_mid": None, "bb_lower": None,
                            "atr14": 0.0008, "stoch_k": None, "stoch_d": None})

    result = store.get_candle_with_indicators(db_path, "EURUSD", "15m", 1705334400)

    assert isinstance(result, dict)
    assert result["pair"] == "EURUSD"
    assert result["close"] == pytest.approx(1.0855, abs=1e-6)
    assert result["ema20"] == pytest.approx(1.0850, abs=1e-6)


def test_get_latest_indicators_returns_dataframe(db_path):
    candle = {"timestamp": 1705334400, "open": 1.085, "high": 1.086,
              "low": 1.084, "close": 1.0855, "volume": 1000.0}
    candle_id = store.write_candle(db_path, "EURUSD", "15m", candle)
    store.write_indicators(db_path, candle_id,
                           {"ema20": 1.085, "ema50": None, "ema200": None,
                            "rsi14": 55.0, "macd": None, "macd_signal": None, "macd_hist": None,
                            "bb_upper": None, "bb_mid": None, "bb_lower": None,
                            "atr14": 0.0008, "stoch_k": None, "stoch_d": None})

    df = store.get_latest_indicators(db_path, "EURUSD", "15m", 5)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert "ema20" in df.columns
    assert df["ema20"].iloc[0] == pytest.approx(1.085, abs=1e-6)


def test_get_candle_with_indicators_returns_empty_dict_for_missing(db_path):
    result = store.get_candle_with_indicators(db_path, "EURUSD", "15m", 9999999999)
    assert result == {}
```

Also add `import pandas as pd` at the top of the file (after existing imports).

- [ ] **Step 2: Run new tests — verify they fail**

```bash
pytest tests/test_pipeline.py::test_get_latest_candles_returns_dataframe -v
```

Expected: FAILED — `AttributeError: module 'storage.store' has no attribute 'get_latest_candles'`

- [ ] **Step 3: Append read methods to `storage/store.py`**

Add these functions to the end of `storage/store.py`:

```python
def get_latest_candles(db_path: str, pair: str, timeframe: str, n: int) -> pd.DataFrame:
    """Return the n most recent candles, sorted oldest-first."""
    conn = get_connection(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM candles WHERE pair=? AND timeframe=? "
            "ORDER BY timestamp DESC LIMIT ?",
            conn,
            params=(pair, timeframe, n),
        )
        return df.sort_values("timestamp").reset_index(drop=True)
    finally:
        conn.close()


def get_latest_indicators(db_path: str, pair: str, timeframe: str, n: int) -> pd.DataFrame:
    """Return indicators for the n most recent candles, sorted oldest-first."""
    conn = get_connection(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT i.* FROM indicators i "
            "JOIN candles c ON i.candle_id = c.id "
            "WHERE c.pair=? AND c.timeframe=? "
            "ORDER BY c.timestamp DESC LIMIT ?",
            conn,
            params=(pair, timeframe, n),
        )
        return df.sort_values("id").reset_index(drop=True)
    finally:
        conn.close()


def get_candle_with_indicators(
    db_path: str, pair: str, timeframe: str, timestamp: int
) -> dict:
    """Return a single candle merged with its indicators as a flat dict. Empty dict if not found."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT c.id, c.pair, c.timeframe, c.timestamp, "
            "c.open, c.high, c.low, c.close, c.volume, "
            "i.ema20, i.ema50, i.ema200, i.rsi14, "
            "i.macd, i.macd_signal, i.macd_hist, "
            "i.bb_upper, i.bb_mid, i.bb_lower, "
            "i.atr14, i.stoch_k, i.stoch_d "
            "FROM candles c LEFT JOIN indicators i ON i.candle_id = c.id "
            "WHERE c.pair=? AND c.timeframe=? AND c.timestamp=?",
            (pair, timeframe, timestamp),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()
```

- [ ] **Step 4: Run all store tests**

```bash
pytest tests/test_pipeline.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add storage/store.py tests/test_pipeline.py
git commit -m "feat: store read interface — get_latest_candles, get_latest_indicators, get_candle_with_indicators"
```

---

## Task 5: Test Fixture + Indicator Engine (TDD)

**Files:**
- Create: `forex-ai/tests/fixtures/gen_fixture.py`
- Create: `forex-ai/tests/fixtures/eurusd_15m.json` (generated by the script)
- Create: `forex-ai/tests/test_indicators.py`
- Create: `forex-ai/indicators/engine.py`

- [ ] **Step 1: Write `tests/fixtures/gen_fixture.py`**

```python
"""
Run once to generate the test fixture:
    python tests/fixtures/gen_fixture.py
Produces tests/fixtures/eurusd_15m.json — 200 synthetic EUR/USD 15m candles.
Commit the output; the fixture is static input for offline tests.
"""
import json
import random
from pathlib import Path

random.seed(42)

BASE_PRICE = 1.0850
CANDLES = 200
INTERVAL_SECS = 900  # 15 minutes
START_TS = 1704067200  # 2024-01-01 00:00:00 UTC

rows = []
price = BASE_PRICE
for i in range(CANDLES):
    change = random.gauss(0, 0.0004)
    open_ = round(price, 5)
    close = round(price + change, 5)
    high = round(max(open_, close) + abs(random.gauss(0, 0.0002)), 5)
    low = round(min(open_, close) - abs(random.gauss(0, 0.0002)), 5)
    volume = round(random.uniform(500, 2000), 1)
    rows.append({
        "timestamp": START_TS + i * INTERVAL_SECS,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
    price = close

out = Path(__file__).parent / "eurusd_15m.json"
out.write_text(json.dumps(rows, indent=2))
print(f"Written {len(rows)} candles to {out}")
```

- [ ] **Step 2: Generate the fixture file**

```bash
cd forex-ai && python tests/fixtures/gen_fixture.py
```

Expected: `Written 200 candles to tests/fixtures/eurusd_15m.json`

- [ ] **Step 3: Write `tests/test_indicators.py`**

```python
import json
import pytest
import pandas as pd
from pathlib import Path
from indicators.engine import calculate, latest_indicators

FIXTURE = Path(__file__).parent / "fixtures" / "eurusd_15m.json"


@pytest.fixture
def eurusd_df():
    data = json.loads(FIXTURE.read_text())
    return pd.DataFrame(data)


def test_calculate_adds_all_indicator_columns(eurusd_df):
    result = calculate(eurusd_df)
    expected = [
        "ema20", "ema50", "ema200", "rsi14",
        "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_mid", "bb_lower",
        "atr14", "stoch_k", "stoch_d",
    ]
    for col in expected:
        assert col in result.columns, f"Missing column: {col}"


def test_ema200_valid_on_200_row_input(eurusd_df):
    result = calculate(eurusd_df)
    assert not pd.isna(result["ema200"].iloc[-1])


def test_ema200_all_nan_on_10_row_input(eurusd_df):
    result = calculate(eurusd_df.iloc[:10].copy())
    assert result["ema200"].isna().all()


def test_rsi_bounded_0_to_100(eurusd_df):
    result = calculate(eurusd_df)
    rsi = result["rsi14"].dropna()
    assert (rsi >= 0).all() and (rsi <= 100).all()


def test_bollinger_band_ordering(eurusd_df):
    result = calculate(eurusd_df)
    valid = result.dropna(subset=["bb_upper", "bb_mid", "bb_lower"])
    assert (valid["bb_upper"] >= valid["bb_mid"]).all()
    assert (valid["bb_mid"] >= valid["bb_lower"]).all()


def test_ema20_matches_pandas_ewm_reference(eurusd_df):
    """EMA20 verified independently: pandas ewm(span=20, adjust=False) is the standard formula."""
    result = calculate(eurusd_df)
    expected = float(eurusd_df["close"].ewm(span=20, adjust=False).mean().iloc[-1])
    actual = float(result["ema20"].iloc[-1])
    assert abs(actual - expected) < 1e-5


def test_latest_indicators_returns_dict_with_all_keys(eurusd_df):
    ind = latest_indicators(eurusd_df)
    expected_keys = [
        "ema20", "ema50", "ema200", "rsi14",
        "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_mid", "bb_lower",
        "atr14", "stoch_k", "stoch_d",
    ]
    for key in expected_keys:
        assert key in ind, f"Missing key: {key}"


def test_latest_indicators_none_for_nan_values(eurusd_df):
    """With only 10 rows, EMA200 cannot be computed — should return None, not NaN."""
    ind = latest_indicators(eurusd_df.iloc[:10].copy())
    assert ind["ema200"] is None


def test_latest_indicators_float_values_for_valid_row(eurusd_df):
    ind = latest_indicators(eurusd_df)
    assert isinstance(ind["ema20"], float)
    assert isinstance(ind["rsi14"], float)
    assert isinstance(ind["atr14"], float)
```

- [ ] **Step 4: Run tests — verify they fail**

```bash
pytest tests/test_indicators.py -v
```

Expected: FAILED — `ModuleNotFoundError: No module named 'indicators.engine'`

- [ ] **Step 5: Implement `indicators/engine.py`**

```python
import pandas as pd
import pandas_ta as ta


def calculate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all indicators on an OHLCV DataFrame.

    Input must have lowercase columns: open, high, low, close, volume.
    Returns a copy of df with indicator columns appended.
    Columns requiring more history than available will contain NaN.
    """
    df = df.copy()

    # Trend
    df["ema20"] = ta.ema(df["close"], length=20)
    df["ema50"] = ta.ema(df["close"], length=50)
    df["ema200"] = ta.ema(df["close"], length=200)

    # Momentum
    df["rsi14"] = ta.rsi(df["close"], length=14)

    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    if macd is not None and not macd.empty:
        df["macd"] = macd["MACD_12_26_9"]
        df["macd_signal"] = macd["MACDs_12_26_9"]
        df["macd_hist"] = macd["MACDh_12_26_9"]
    else:
        df["macd"] = df["macd_signal"] = df["macd_hist"] = float("nan")

    stoch = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
    if stoch is not None and not stoch.empty:
        df["stoch_k"] = stoch["STOCHk_14_3_3"]
        df["stoch_d"] = stoch["STOCHd_14_3_3"]
    else:
        df["stoch_k"] = df["stoch_d"] = float("nan")

    # Volatility
    bb = ta.bbands(df["close"], length=20, std=2)
    if bb is not None and not bb.empty:
        df["bb_upper"] = bb["BBU_20_2.0"]
        df["bb_mid"] = bb["BBM_20_2.0"]
        df["bb_lower"] = bb["BBL_20_2.0"]
    else:
        df["bb_upper"] = df["bb_mid"] = df["bb_lower"] = float("nan")

    df["atr14"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    return df


def latest_indicators(df: pd.DataFrame) -> dict:
    """
    Return indicator values for the most recent candle as a plain dict.
    Values that could not be computed (NaN) are returned as None.
    """
    result = calculate(df)
    last = result.iloc[-1]

    def safe(val):
        try:
            return None if pd.isna(val) else float(val)
        except (TypeError, ValueError):
            return None

    return {
        "ema20": safe(last.get("ema20")),
        "ema50": safe(last.get("ema50")),
        "ema200": safe(last.get("ema200")),
        "rsi14": safe(last.get("rsi14")),
        "macd": safe(last.get("macd")),
        "macd_signal": safe(last.get("macd_signal")),
        "macd_hist": safe(last.get("macd_hist")),
        "bb_upper": safe(last.get("bb_upper")),
        "bb_mid": safe(last.get("bb_mid")),
        "bb_lower": safe(last.get("bb_lower")),
        "atr14": safe(last.get("atr14")),
        "stoch_k": safe(last.get("stoch_k")),
        "stoch_d": safe(last.get("stoch_d")),
    }
```

- [ ] **Step 6: Run indicator tests**

```bash
pytest tests/test_indicators.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add indicators/engine.py tests/test_indicators.py \
        tests/fixtures/gen_fixture.py tests/fixtures/eurusd_15m.json
git commit -m "feat: indicator engine — EMA/RSI/MACD/BB/ATR/Stoch with fixture-based tests"
```

---

## Task 6: Alpha Vantage Provider (TDD)

**Files:**
- Create: `forex-ai/tests/test_fetcher.py`
- Create: `forex-ai/data/providers.py` (Alpha Vantage portion only; yfinance and fallback added in Task 7)

- [ ] **Step 1: Write failing tests in `tests/test_fetcher.py`**

```python
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# --- Alpha Vantage mock response ---

MOCK_AV_OK = {
    "Time Series FX (15min)": {
        "2024-01-15 16:00:00": {
            "1. open": "1.08500", "2. high": "1.08600",
            "3. low": "1.08450", "4. close": "1.08550", "5. volume": "1000",
        },
        "2024-01-15 15:45:00": {
            "1. open": "1.08400", "2. high": "1.08520",
            "3. low": "1.08380", "4. close": "1.08500", "5. volume": "900",
        },
    }
}

MOCK_AV_RATE_LIMIT = {
    "Note": "Thank you for using Alpha Vantage! Our standard API rate is 5 calls per minute."
}

MOCK_AV_ERROR = {
    "Error Message": "Invalid API call."
}


def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.raise_for_status.return_value = None
    mock.status_code = status_code
    return mock


@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_returns_dataframe(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_OK)

    df = fetch_alpha_vantage("fake_key", "EURUSD", "15m")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2


@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_column_names(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_OK)

    df = fetch_alpha_vantage("fake_key", "EURUSD", "15m")

    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_types(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_OK)

    df = fetch_alpha_vantage("fake_key", "EURUSD", "15m")

    assert df["timestamp"].dtype.kind == "i"  # integer
    assert df["open"].dtype.kind == "f"       # float


@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_sorted_ascending(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_OK)

    df = fetch_alpha_vantage("fake_key", "EURUSD", "15m")

    assert df["timestamp"].is_monotonic_increasing


@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_raises_on_rate_limit(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_RATE_LIMIT)

    with pytest.raises(ValueError, match="rate limit"):
        fetch_alpha_vantage("fake_key", "EURUSD", "15m")


@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_raises_on_error_message(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_ERROR)

    with pytest.raises(ValueError, match="Alpha Vantage error"):
        fetch_alpha_vantage("fake_key", "EURUSD", "15m")
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_fetcher.py -v
```

Expected: FAILED — `ModuleNotFoundError: No module named 'data.providers'`

- [ ] **Step 3: Write `data/providers.py` (Alpha Vantage only)**

```python
import logging
import time
from datetime import datetime, timezone

import pandas as pd
import requests

logger = logging.getLogger(__name__)

AV_INTERVAL_MAP = {"15m": "15min", "1H": "60min"}
YF_INTERVAL_MAP = {"15m": "15m", "1H": "1h"}
YF_PERIOD_MAP = {"15m": "5d", "1H": "15d"}
YF_TICKER_MAP = {"EURUSD": "EURUSD=X"}


class RateLimiter:
    """Token-bucket rate limiter; default matches Alpha Vantage free tier (5 calls/minute)."""

    def __init__(self, calls_per_minute: int = 5):
        self.calls_per_minute = calls_per_minute
        self._call_times: list[float] = []

    def wait_if_needed(self) -> None:
        now = time.time()
        self._call_times = [t for t in self._call_times if now - t < 60]
        if len(self._call_times) >= self.calls_per_minute:
            sleep_for = 60 - (now - self._call_times[0])
            if sleep_for > 0:
                logger.debug("Rate limit: sleeping %.1fs", sleep_for)
                time.sleep(sleep_for)
        self._call_times.append(time.time())


_rate_limiter = RateLimiter()


def fetch_alpha_vantage(
    api_key: str, pair: str, timeframe: str, outputsize: str = "compact"
) -> pd.DataFrame:
    """
    Fetch OHLCV candles from Alpha Vantage FX_INTRADAY endpoint.

    Returns DataFrame with columns: timestamp (int UTC), open, high, low, close, volume.
    Raises ValueError on rate-limit notes or error messages in the JSON response.
    Raises requests.HTTPError on non-2xx HTTP responses.
    """
    interval = AV_INTERVAL_MAP[timeframe]
    from_symbol, to_symbol = pair[:3], pair[3:]

    _rate_limiter.wait_if_needed()

    resp = requests.get(
        "https://www.alphavantage.co/query",
        params={
            "function": "FX_INTRADAY",
            "from_symbol": from_symbol,
            "to_symbol": to_symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": api_key,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if "Note" in data:
        raise ValueError(f"Alpha Vantage rate limit: {data['Note']}")
    if "Error Message" in data:
        raise ValueError(f"Alpha Vantage error: {data['Error Message']}")

    key = f"Time Series FX ({interval})"
    if key not in data:
        raise ValueError(f"Unexpected response keys: {list(data.keys())}")

    rows = []
    for ts_str, ohlcv in data[key].items():
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        rows.append({
            "timestamp": int(dt.timestamp()),
            "open": float(ohlcv["1. open"]),
            "high": float(ohlcv["2. high"]),
            "low": float(ohlcv["3. low"]),
            "close": float(ohlcv["4. close"]),
            "volume": float(ohlcv["5. volume"]),
        })

    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
```

- [ ] **Step 4: Run Alpha Vantage tests**

```bash
pytest tests/test_fetcher.py -v
```

Expected: 6 tests PASS (yfinance and fallback tests not yet written).

- [ ] **Step 5: Commit**

```bash
git add data/providers.py tests/test_fetcher.py
git commit -m "feat: Alpha Vantage provider with rate limiter and mock-based tests"
```

---

## Task 7: yfinance Provider + Fallback (TDD)

**Files:**
- Modify: `forex-ai/tests/test_fetcher.py` (append yfinance and fallback tests)
- Modify: `forex-ai/data/providers.py` (append yfinance client and `fetch_candles`)

- [ ] **Step 1: Append yfinance and fallback tests to `tests/test_fetcher.py`**

```python
# --- Rate limiter tests ---

def test_rate_limiter_records_calls():
    from data.providers import RateLimiter
    limiter = RateLimiter(calls_per_minute=5)
    limiter.wait_if_needed()
    limiter.wait_if_needed()
    assert len(limiter._call_times) == 2


# --- yfinance tests ---

@patch("data.providers.yf.Ticker")
def test_fetch_yfinance_returns_dataframe(mock_ticker_cls):
    from data.providers import fetch_yfinance

    index = pd.date_range("2024-01-15 09:00", periods=3, freq="15min", tz="UTC")
    mock_hist = pd.DataFrame({
        "Open": [1.085, 1.086, 1.087],
        "High": [1.086, 1.087, 1.088],
        "Low": [1.084, 1.085, 1.086],
        "Close": [1.0855, 1.0865, 1.0875],
        "Volume": [1000.0, 1100.0, 900.0],
    }, index=index)
    mock_ticker_cls.return_value.history.return_value = mock_hist

    df = fetch_yfinance("EURUSD", "15m")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


@patch("data.providers.yf.Ticker")
def test_fetch_yfinance_raises_on_empty_response(mock_ticker_cls):
    from data.providers import fetch_yfinance
    mock_ticker_cls.return_value.history.return_value = pd.DataFrame()

    with pytest.raises(ValueError, match="empty DataFrame"):
        fetch_yfinance("EURUSD", "15m")


# --- Fallback tests ---

@patch("data.providers.fetch_alpha_vantage")
@patch("data.providers.fetch_yfinance")
def test_fetch_candles_uses_alpha_vantage_first(mock_yf, mock_av):
    from data.providers import fetch_candles
    mock_av.return_value = pd.DataFrame([{
        "timestamp": 1705334400, "open": 1.085, "high": 1.086,
        "low": 1.084, "close": 1.0855, "volume": 1000.0,
    }])

    df, provider = fetch_candles("fake_key", "EURUSD", "15m")

    assert provider == "alpha_vantage"
    mock_yf.assert_not_called()


@patch("data.providers.fetch_alpha_vantage")
@patch("data.providers.fetch_yfinance")
def test_fetch_candles_falls_back_to_yfinance_on_av_failure(mock_yf, mock_av):
    from data.providers import fetch_candles
    mock_av.side_effect = ValueError("rate limit")
    mock_yf.return_value = pd.DataFrame([{
        "timestamp": 1705334400, "open": 1.085, "high": 1.086,
        "low": 1.084, "close": 1.0855, "volume": 1000.0,
    }])

    df, provider = fetch_candles("fake_key", "EURUSD", "15m")

    assert provider == "yfinance"
    assert len(df) == 1


@patch("data.providers.fetch_alpha_vantage")
@patch("data.providers.fetch_yfinance")
def test_fetch_candles_raises_when_both_fail(mock_yf, mock_av):
    from data.providers import fetch_candles
    mock_av.side_effect = ValueError("AV failed")
    mock_yf.side_effect = ValueError("yf failed")

    with pytest.raises(RuntimeError, match="Both providers failed"):
        fetch_candles("fake_key", "EURUSD", "15m")
```

- [ ] **Step 2: Run new tests — verify they fail**

```bash
pytest tests/test_fetcher.py::test_fetch_yfinance_returns_dataframe -v
```

Expected: FAILED — `ImportError` or `AttributeError` (yfinance functions not yet in providers.py)

- [ ] **Step 3: Append yfinance client and `fetch_candles` to `data/providers.py`**

```python
import yfinance as yf


def fetch_yfinance(pair: str, timeframe: str) -> pd.DataFrame:
    """
    Fetch OHLCV candles from Yahoo Finance.

    Returns DataFrame with columns: timestamp (int UTC), open, high, low, close, volume.
    Raises ValueError if the response is empty.
    """
    ticker_sym = YF_TICKER_MAP.get(pair, f"{pair[:3]}{pair[3:]}=X")
    ticker = yf.Ticker(ticker_sym)
    hist = ticker.history(interval=YF_INTERVAL_MAP[timeframe], period=YF_PERIOD_MAP[timeframe])

    if hist.empty:
        raise ValueError(f"yfinance returned empty DataFrame for {pair} {timeframe}")

    rows = []
    for idx, row in hist.iterrows():
        rows.append({
            "timestamp": int(idx.timestamp()),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row.get("Volume", 0.0)),
        })

    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


def fetch_candles(
    api_key: str, pair: str, timeframe: str, outputsize: str = "compact"
) -> tuple[pd.DataFrame, str]:
    """
    Fetch candles with automatic fallback: Alpha Vantage → yfinance.

    Returns (DataFrame, provider_name).
    Raises RuntimeError if both providers fail.
    """
    try:
        df = fetch_alpha_vantage(api_key, pair, timeframe, outputsize)
        return df, "alpha_vantage"
    except Exception as exc:
        logger.warning("Alpha Vantage failed (%s), trying yfinance", exc)

    try:
        df = fetch_yfinance(pair, timeframe)
        return df, "yfinance"
    except Exception as exc:
        raise RuntimeError(f"Both providers failed for {pair} {timeframe}: {exc}") from exc
```

Also add `import yfinance as yf` near the top of `data/providers.py` (after the existing imports).

- [ ] **Step 4: Run all fetcher tests**

```bash
pytest tests/test_fetcher.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add data/providers.py tests/test_fetcher.py
git commit -m "feat: yfinance provider and fallback chain — both providers tested with mocks"
```

---

## Task 8: Fetcher Orchestrator + Integration Tests (TDD)

**Files:**
- Modify: `forex-ai/tests/test_pipeline.py` (append integration tests)
- Create: `forex-ai/data/fetcher.py`

- [ ] **Step 1: Append integration tests to `tests/test_pipeline.py`**

Add `from unittest.mock import patch` to the imports at the top of the file if not already present.
Then append the following after the existing test functions:

```python
# -- add to top of file if not present --
# from unittest.mock import patch
# import pandas as pd  (already added in Task 4)

_MOCK_5_CANDLES = pd.DataFrame([
    {
        "timestamp": 1705334400 + i * 900,
        "open": round(1.0850 + i * 0.0001, 5),
        "high": round(1.0860 + i * 0.0001, 5),
        "low": round(1.0840 + i * 0.0001, 5),
        "close": round(1.0855 + i * 0.0001, 5),
        "volume": 1000.0,
    }
    for i in range(5)
])


@patch("data.fetcher.fetch_candles")
def test_run_fetch_cycle_writes_candles(mock_fetch, db_path):
    from data.fetcher import run_fetch_cycle
    mock_fetch.return_value = (_MOCK_5_CANDLES, "alpha_vantage")

    run_fetch_cycle(db_path, "fake_key", "EURUSD", "15m")

    candles = store.get_latest_candles(db_path, "EURUSD", "15m", 10)
    assert len(candles) == 5


@patch("data.fetcher.fetch_candles")
def test_run_fetch_cycle_writes_fetch_log_ok(mock_fetch, db_path):
    import sqlite3
    from data.fetcher import run_fetch_cycle
    mock_fetch.return_value = (_MOCK_5_CANDLES, "alpha_vantage")

    run_fetch_cycle(db_path, "fake_key", "EURUSD", "15m")

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT provider, status FROM fetch_log").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0] == ("alpha_vantage", "ok")


@patch("data.fetcher.fetch_candles")
def test_run_fetch_cycle_logs_skipped_when_both_fail(mock_fetch, db_path):
    import sqlite3
    from data.fetcher import run_fetch_cycle
    mock_fetch.side_effect = RuntimeError("Both providers failed")

    run_fetch_cycle(db_path, "fake_key", "EURUSD", "15m")

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM fetch_log").fetchone()
    conn.close()
    assert row[0] == "skipped"


@patch("data.fetcher.fetch_candles")
def test_run_fetch_cycle_no_duplicate_candles(mock_fetch, db_path):
    from data.fetcher import run_fetch_cycle
    mock_fetch.return_value = (_MOCK_5_CANDLES, "alpha_vantage")

    run_fetch_cycle(db_path, "fake_key", "EURUSD", "15m")
    run_fetch_cycle(db_path, "fake_key", "EURUSD", "15m")  # identical data, second call

    candles = store.get_latest_candles(db_path, "EURUSD", "15m", 100)
    assert len(candles) == 5  # not 10


@patch("data.fetcher.fetch_candles")
def test_run_fetch_cycle_store_interface_returns_correct_data(mock_fetch, db_path):
    from data.fetcher import run_fetch_cycle
    mock_fetch.return_value = (_MOCK_5_CANDLES, "alpha_vantage")

    run_fetch_cycle(db_path, "fake_key", "EURUSD", "15m")

    df = store.get_latest_candles(db_path, "EURUSD", "15m", 3)
    assert len(df) == 3
    assert "close" in df.columns

    ts = int(_MOCK_5_CANDLES["timestamp"].iloc[-1])
    result = store.get_candle_with_indicators(db_path, "EURUSD", "15m", ts)
    assert result["pair"] == "EURUSD"
    assert "close" in result
```

- [ ] **Step 2: Run new tests — verify they fail**

```bash
pytest tests/test_pipeline.py::test_run_fetch_cycle_writes_candles -v
```

Expected: FAILED — `ModuleNotFoundError: No module named 'data.fetcher'`

- [ ] **Step 3: Implement `data/fetcher.py`**

```python
import logging
import time

from data.providers import fetch_candles
from indicators.engine import latest_indicators
from storage import store

logger = logging.getLogger(__name__)

# Number of historical candles to load when computing indicators.
# Must be > 200 so EMA200 is valid for the new candle.
_INDICATOR_HISTORY = 210


def run_fetch_cycle(
    db_path: str, api_key: str, pair: str, timeframe: str, outputsize: str = "compact"
) -> None:
    """
    Execute one complete fetch → indicators → store cycle.
    Logs the outcome to fetch_log regardless of success or failure.
    Never raises — exceptions are caught and recorded.
    """
    start = time.time()

    try:
        df, provider = fetch_candles(api_key, pair, timeframe, outputsize)
    except RuntimeError as exc:
        duration_ms = int((time.time() - start) * 1000)
        store.write_fetch_log(db_path, pair, timeframe, "none", "skipped", str(exc), duration_ms)
        logger.warning("Skipped cycle %s %s: %s", pair, timeframe, exc)
        return

    new_count = 0
    for _, row in df.iterrows():
        candle = {
            "timestamp": int(row["timestamp"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        }
        candle_id = store.write_candle(db_path, pair, timeframe, candle)
        if candle_id is None:
            continue  # duplicate — already stored

        new_count += 1
        history = store.get_latest_candles(db_path, pair, timeframe, _INDICATOR_HISTORY)
        if len(history) >= 2:
            ind = latest_indicators(history)
            store.write_indicators(db_path, candle_id, ind)

    duration_ms = int((time.time() - start) * 1000)
    store.write_fetch_log(db_path, pair, timeframe, provider, "ok", None, duration_ms)
    logger.info("Fetched %d new candles for %s %s via %s in %dms",
                new_count, pair, timeframe, provider, duration_ms)


def backfill(db_path: str, api_key: str, pair: str, timeframe: str) -> None:
    """Pull last ~500 candles on first run so indicator history is populated."""
    logger.info("Backfilling %s %s...", pair, timeframe)
    run_fetch_cycle(db_path, api_key, pair, timeframe, outputsize="full")
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS (test_indicators, test_fetcher, test_pipeline).

- [ ] **Step 5: Commit**

```bash
git add data/fetcher.py tests/test_pipeline.py
git commit -m "feat: fetcher orchestrator and full pipeline integration tests"
```

---

## Task 9: Scheduler + Main Entry Point

**Files:**
- Create: `forex-ai/scheduler/jobs.py`
- Create: `forex-ai/main.py`

No automated tests for this task — verified manually by running the process.

- [ ] **Step 1: Write `scheduler/jobs.py`**

```python
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from data.fetcher import run_fetch_cycle

logger = logging.getLogger(__name__)


def create_scheduler() -> BlockingScheduler:
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
        logger.info("Scheduled %s %s job every %d minutes", config.PAIR, timeframe, interval_minutes)

    return scheduler
```

- [ ] **Step 2: Write `main.py`**

```python
import logging
import sys

import config
from data.fetcher import backfill
from scheduler.jobs import create_scheduler
from storage.store import init_db

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
        logger.error("ALPHA_VANTAGE_API_KEY is not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    logger.info("Initialising database at %s", config.DB_PATH)
    init_db(config.DB_PATH)

    logger.info("Backfilling history for %s...", config.PAIR)
    for timeframe in config.TIMEFRAMES:
        backfill(config.DB_PATH, config.ALPHA_VANTAGE_API_KEY, config.PAIR, timeframe)

    logger.info("Starting scheduler. Press Ctrl+C to stop.")
    scheduler = create_scheduler()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the full test suite one last time**

```bash
pytest tests/ -v
```

Expected: all tests PASS — no regressions from new files.

- [ ] **Step 4: Commit**

```bash
git add scheduler/jobs.py main.py
git commit -m "feat: APScheduler jobs and main entry point with startup backfill"
```

---

## Task 10: Verify Definition of Done

- [ ] **Step 1: Start the service**

```bash
cd forex-ai && python main.py
```

Expected output (first run, with a valid API key):
```
2026-04-13 ... INFO     __main__ — Initialising database at forex.db
2026-04-13 ... INFO     __main__ — Backfilling history for EURUSD...
2026-04-13 ... INFO     data.fetcher — Backfilling EURUSD 15m...
2026-04-13 ... INFO     data.fetcher — Fetched N new candles for EURUSD 15m via alpha_vantage in Xms
2026-04-13 ... INFO     data.fetcher — Backfilling EURUSD 1H...
2026-04-13 ... INFO     data.fetcher — Fetched N new candles for EURUSD 1H via alpha_vantage in Xms
2026-04-13 ... INFO     __main__ — Starting scheduler. Press Ctrl+C to stop.
```

- [ ] **Step 2: Verify the store interface in a Python shell**

Open a second terminal while `main.py` is running:

```bash
cd forex-ai && python -c "
from storage.store import get_latest_candles, get_latest_indicators
import config

df = get_latest_candles(config.DB_PATH, 'EURUSD', '15m', 50)
print(f'15m candles: {len(df)} rows')
print(df[['timestamp','close','volume']].tail(3).to_string())

ind = get_latest_indicators(config.DB_PATH, 'EURUSD', '15m', 50)
print(f'\nIndicators: {len(ind)} rows')
print(ind[['ema20','rsi14','atr14']].tail(3).to_string())
"
```

Expected: 50 rows of candle data and indicator data print without error. `ema20`, `rsi14`, `atr14` should be non-null floats.

- [ ] **Step 3: Verify `fetch_log` shows successful fetches**

```bash
cd forex-ai && python -c "
import sqlite3, config
conn = sqlite3.connect(config.DB_PATH)
rows = conn.execute(
    'SELECT pair, timeframe, provider, status, duration_ms FROM fetch_log ORDER BY id DESC LIMIT 5'
).fetchall()
for r in rows: print(r)
conn.close()
"
```

Expected: rows like `('EURUSD', '15m', 'alpha_vantage', 'ok', 312)` — no `'skipped'` or `'error'` statuses.

- [ ] **Step 4: Leave running for 24 hours**

Let `main.py` run in a terminal (or `nohup python main.py &`) for 24 hours without restart. After 24 hours, confirm:

```bash
cd forex-ai && python -c "
import sqlite3, config
conn = sqlite3.connect(config.DB_PATH)
count = conn.execute(
    'SELECT COUNT(*) FROM candles WHERE pair=\"EURUSD\"'
).fetchone()[0]
errors = conn.execute(
    'SELECT COUNT(*) FROM fetch_log WHERE status != \"ok\"'
).fetchone()[0]
print(f'Total candles: {count}')
print(f'Non-ok fetch log entries: {errors}')
conn.close()
"
```

Expected: `Total candles` > 150 (96 × 15m + some 1H), `Non-ok entries` = 0 or very low (≤5 from transient network issues).

- [ ] **Step 5: Final commit**

```bash
git add forex_ai.log  # optional — .gitignore it if preferred
git commit -m "chore: phase 1 complete — data foundation verified stable over 24h"
```

---

## Appendix: Free Alpha Vantage API Key

1. Visit https://www.alphavantage.co/support/#api-key
2. Enter your email and claim a free key (instant, no credit card)
3. Free tier: 5 requests/minute, 500 requests/day — this system uses 120/day

## Appendix: Running Tests in CI (No API Key Needed)

All tests use mocks or fixture files. They pass with no `.env` file:

```bash
pytest tests/ -v --tb=short
```

GitHub Actions free tier works fine. No secrets needed.
