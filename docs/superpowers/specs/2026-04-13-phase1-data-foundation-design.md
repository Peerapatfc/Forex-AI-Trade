# Phase 1: Data Foundation — Design Spec

**Date:** 2026-04-13
**Project:** Forex AI Trading System
**Phase:** 1 of 6 — Data Foundation
**Status:** Approved

---

## Overview

Phase 1 builds the market data ingestion and technical indicator calculation layer. It is the foundation all subsequent phases depend on. The output is a continuously-updated SQLite database containing OHLCV candles and pre-computed indicators for EUR/USD at 15-minute and 1-hour timeframes.

No AI, no trading execution, no frontend. Just reliable data in a queryable store.

---

## Decisions

| Dimension | Decision | Rationale |
|---|---|---|
| Language | Python 3.11+ | Dominant ecosystem for trading/TA libraries |
| Timeframes | 15m, 1H | Free-tier API friendly; enough signal for AI analysis |
| Currency pairs | EUR/USD only | Validate pipeline before scaling to multiple pairs |
| Storage | SQLite | Zero infrastructure; sufficient for single-pair load |
| Scheduler | APScheduler | Lightweight in-process scheduler; no separate service |
| Primary data provider | Alpha Vantage (free tier) | Reliable OHLCV history + recent candles |
| Fallback provider | Yahoo Finance (yfinance) | Free, no API key required; covers rate-limit failures |
| Indicator library | pandas-ta | Comprehensive, pandas-native, well-maintained |

---

## Architecture

```
APScheduler
  ├── every 15 min → fetch 15m candles → calculate indicators → store
  └── every 60 min → fetch 1H candles  → calculate indicators → store

fetcher.py → providers.py (Alpha Vantage → yfinance fallback)
          → indicators/engine.py (pandas-ta)
          → storage/store.py (SQLite)
```

The data pipeline is a straight sequential flow with no concurrency. Each scheduler job runs fetch → indicators → store as a single transaction. The `store.py` module exposes a clean read interface that Phase 2 (AI pipeline) will consume without touching the pipeline internals.

---

## Project Structure

```
forex-ai/
├── data/
│   ├── fetcher.py        # Orchestrates fetch → indicators → store
│   └── providers.py      # Alpha Vantage + yfinance clients, rate limiter, fallback
├── indicators/
│   └── engine.py         # pandas-ta wrapper; all indicator calculations
├── storage/
│   ├── store.py          # Read/write interface (the contract Phase 2 depends on)
│   └── schema.sql        # Table definitions and migrations
├── scheduler/
│   └── jobs.py           # APScheduler job definitions and startup
├── tests/
│   ├── test_fetcher.py   # Fetcher unit tests (mock HTTP)
│   ├── test_indicators.py # Indicator unit tests (fixture OHLCV data)
│   ├── test_pipeline.py  # Integration test (in-memory SQLite, mock HTTP)
│   └── fixtures/         # Saved EUR/USD OHLCV snapshots for offline tests
├── config.py             # All settings; API keys loaded from .env
├── main.py               # Entry point: `python main.py`
└── requirements.txt
```

---

## SQLite Schema

### `candles`
```sql
CREATE TABLE candles (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pair      TEXT    NOT NULL,          -- e.g. 'EURUSD'
    timeframe TEXT    NOT NULL,          -- '15m' or '1H'
    timestamp INTEGER NOT NULL,         -- Unix timestamp UTC
    open      REAL    NOT NULL,
    high      REAL    NOT NULL,
    low       REAL    NOT NULL,
    close     REAL    NOT NULL,
    volume    REAL    NOT NULL,
    UNIQUE(pair, timeframe, timestamp)  -- prevents duplicates on re-fetch
);
```

### `indicators`
```sql
CREATE TABLE indicators (
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
```

### `fetch_log`
```sql
CREATE TABLE fetch_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   INTEGER NOT NULL,        -- Unix timestamp UTC
    pair        TEXT    NOT NULL,
    timeframe   TEXT    NOT NULL,
    provider    TEXT    NOT NULL,        -- 'alpha_vantage' or 'yfinance'
    status      TEXT    NOT NULL,        -- 'ok' | 'rate_limit' | 'error' | 'skipped'
    error_msg   TEXT,
    duration_ms INTEGER
);
```

---

## Technical Indicators

All indicators computed by `indicators/engine.py` using `pandas-ta` on a DataFrame of the last N candles retrieved from the store:

| Indicator | Parameters | Purpose |
|---|---|---|
| EMA | 20, 50, 200 periods | Trend direction and strength |
| RSI | 14 periods | Momentum; overbought/oversold |
| MACD | 12, 26, 9 | Trend momentum and divergence |
| Bollinger Bands | 20 periods, 2 std dev | Volatility and mean-reversion context |
| ATR | 14 periods | Volatility; used for position sizing in later phases |
| Stochastic | 14, 3, 3 | Short-term momentum confirmation |

**Minimum history requirement:** 200 candles needed before EMA200 is valid. On first run, the fetcher backfills the last 200 candles before starting the live scheduler loop.

---

## Data Providers

### Alpha Vantage (primary)
- Endpoint: `TIME_SERIES_INTRADAY` with `interval=15min` and `interval=60min`
- Free tier: 5 requests/minute, 500 requests/day
- With 1 pair: 15m = 96 cycles/day + 1H = 24 cycles/day = 120 requests/day — well within limits
- API key loaded from `ALPHA_VANTAGE_API_KEY` environment variable

### Yahoo Finance / yfinance (fallback)
- No API key required
- Used automatically when Alpha Vantage returns a rate-limit error or HTTP failure
- If both providers fail: log to `fetch_log` with `status='skipped'` and wait for next cycle

### Rate Limiter
`providers.py` implements a token-bucket rate limiter tracking Alpha Vantage call timestamps. If a call would exceed 5/minute, it sleeps for the remainder of the window before proceeding. This prevents avoidable 429 errors.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Alpha Vantage rate limit (429) | Immediate fallback to yfinance |
| Alpha Vantage network error | Immediate fallback to yfinance |
| yfinance failure | Log `status='skipped'`, skip cycle, continue |
| Duplicate candle on insert | `INSERT OR IGNORE` — silent skip, no error |
| Indicator calc on insufficient history | Returns `None` for affected indicators; stored as NULL |
| Scheduler job exception | Caught at job level; logs error, does not crash scheduler |

---

## Testing

All tests run offline — no API keys, no network access.

### `test_indicators.py`
- Loads EUR/USD OHLCV fixture (200 real candles saved to `tests/fixtures/eurusd_15m.json`)
- Runs through `engine.py`
- Asserts output values match reference values computed directly with pandas (no pandas-ta), verified manually (±0.00001 tolerance)
- Covers: all 7 indicators, edge case of <200 bars (NaN handling)

### `test_fetcher.py`
- Mock HTTP client returns pre-recorded Alpha Vantage JSON responses
- Asserts correct parsing, UTC normalization, float conversion
- Simulates 429 response → asserts yfinance fallback is invoked
- Simulates both providers failing → asserts `fetch_log` records `status='skipped'`

### `test_pipeline.py`
- Full integration: mock HTTP → fetcher → indicators → in-memory SQLite
- Asserts correct row counts in `candles` and `indicators`
- Asserts foreign key integrity
- Asserts `fetch_log` contains one entry per cycle with correct provider and status

---

## Store Interface (Phase 2 Contract)

`storage/store.py` exposes these methods only — Phase 2 AI pipeline is permitted to call these and nothing else:

```python
def get_latest_candles(pair: str, timeframe: str, n: int) -> pd.DataFrame
def get_latest_indicators(pair: str, timeframe: str, n: int) -> pd.DataFrame
def get_candle_with_indicators(pair: str, timeframe: str, timestamp: int) -> dict
```

This interface is stable. Changes to the internal schema do not break Phase 2 as long as these signatures hold.

---

## Dependencies

```
apscheduler>=3.10
pandas>=2.0
pandas-ta>=0.3.14b
requests>=2.31
yfinance>=0.2.40
python-dotenv>=1.0
pytest>=8.0
```

---

## Deliverables (Definition of Done)

Phase 1 is complete when:

1. `python main.py` runs without error and populates SQLite with candles + indicators
2. `fetch_log` shows successful fetches from Alpha Vantage (or yfinance fallback)
3. All three test files pass with `pytest tests/`
4. The store interface returns correct DataFrames for the last 50 candles at both timeframes
5. System runs stably for 24 hours in background with no crashes

---

## Out of Scope for Phase 1

- Any AI model integration (Phase 2)
- MetaTrader connectivity (Phase 3)
- Trade execution or order management (Phase 3)
- Frontend or dashboard (Phase 5)
- Additional currency pairs (Phase 2+)
- Additional timeframes (Phase 2+)
