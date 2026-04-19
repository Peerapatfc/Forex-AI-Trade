# Phase 2: AI Analysis Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dual-AI signal generation pipeline that reads candle/indicator data from SQLite, queries Claude Opus 4.6 and Gemini 2.5 Pro in parallel, applies hard-veto consensus, and writes trading signals to a new `signals` table.

**Architecture:** A new `ai/` package (prompt builder, two API clients, consensus engine, orchestrator) is wired into APScheduler as a standalone 15m job. The data pipeline (Phase 1) and AI pipeline are fully decoupled — failures in one never affect the other. AI calls use `asyncio.gather` for parallel execution, wrapped in `asyncio.run()` inside the synchronous scheduler job.

**Tech Stack:** Python 3.11+, anthropic SDK, google-generativeai SDK, asyncio, pytest, pytest-asyncio, unittest.mock

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `storage/schema.sql` | Add `signals` table |
| Modify | `config.py` | Add AI API keys + model name env vars |
| Modify | `requirements.txt` | Add anthropic, google-generativeai, pytest-asyncio |
| Modify | `storage/store.py` | Add `write_signal()`, `get_latest_signals()` |
| Create | `ai/__init__.py` | Package marker |
| Create | `ai/prompt.py` | Builds prompt string from candle/indicator data |
| Create | `ai/consensus.py` | `Signal` dataclass + `resolve()` hard-veto logic |
| Create | `ai/claude_client.py` | Anthropic API call + JSON parsing + fallback |
| Create | `ai/gemini_client.py` | Google GenAI API call + JSON parsing + fallback |
| Create | `ai/analyzer.py` | Orchestrator: read store → parallel calls → write signal |
| Modify | `scheduler/jobs.py` | Add analysis job every 15m |
| Create | `tests/test_signals_store.py` | Tests for write_signal / get_latest_signals |
| Create | `tests/test_prompt.py` | Tests for prompt.build() |
| Create | `tests/test_consensus.py` | Tests for all 9 direction combinations |
| Create | `tests/test_claude_client.py` | Tests for parsing + API mock |
| Create | `tests/test_gemini_client.py` | Tests for parsing + API mock |
| Create | `tests/test_analyzer.py` | Integration tests with mocked clients + store |

---

## Task 1: Schema, config, and dependencies

**Files:**
- Modify: `storage/schema.sql`
- Modify: `config.py`
- Modify: `requirements.txt`
- Modify: `tests/test_pipeline.py` (update table check)

- [ ] **Step 1: Write the failing test for signals table**

In `tests/test_pipeline.py`, update the existing `test_init_db_creates_tables` test:

```python
def test_init_db_creates_tables(db_path):
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert {"candles", "indicators", "fetch_log", "signals"} <= tables
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd forex-ai && python -m pytest tests/test_pipeline.py::test_init_db_creates_tables -v
```

Expected: FAIL — `signals` not in tables.

- [ ] **Step 3: Add signals table to schema.sql**

Append to `storage/schema.sql` (after the existing `fetch_log` table):

```sql
CREATE TABLE IF NOT EXISTS signals (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    pair              TEXT    NOT NULL,
    timeframe         TEXT    NOT NULL,
    timestamp         INTEGER NOT NULL,
    created_at        INTEGER NOT NULL,
    direction         TEXT    NOT NULL,
    confidence        REAL    NOT NULL,
    sl_pips           REAL,
    tp_pips           REAL,
    claude_direction  TEXT,
    claude_confidence REAL,
    gemini_direction  TEXT,
    gemini_confidence REAL,
    reasoning         TEXT,
    UNIQUE(pair, timeframe, timestamp)
);
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_pipeline.py::test_init_db_creates_tables -v
```

Expected: PASS.

- [ ] **Step 5: Update config.py**

Replace the entire `config.py` with:

```python
import os
from dotenv import load_dotenv

load_dotenv()

ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
DB_PATH: str = os.getenv("DB_PATH", "forex.db")
PAIR: str = "EURUSD"
TIMEFRAMES: list[str] = ["15m", "1H"]
BACKFILL_CANDLES: int = 200

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
```

- [ ] **Step 6: Update requirements.txt**

Add these lines to `requirements.txt`:

```
anthropic>=0.50,<1.0
google-generativeai>=0.8,<1.0
pytest-asyncio>=0.23,<1.0
```

- [ ] **Step 7: Install new dependencies**

```bash
pip install anthropic>=0.50 "google-generativeai>=0.8,<1.0" "pytest-asyncio>=0.23,<1.0"
```

Expected: installs without error.

- [ ] **Step 8: Run full test suite to confirm no regressions**

```bash
python -m pytest tests/ -v
```

Expected: all existing tests pass.

- [ ] **Step 9: Commit**

```bash
git add storage/schema.sql config.py requirements.txt tests/test_pipeline.py
git commit -m "feat: add signals table, AI config vars, and AI dependencies"
```

---

## Task 2: Store signal functions

**Files:**
- Modify: `storage/store.py`
- Create: `tests/test_signals_store.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_signals_store.py`:

```python
import pytest
import pandas as pd
from storage import store


_SIGNAL = {
    "pair": "EURUSD",
    "timeframe": "15m",
    "timestamp": 1705334400,
    "created_at": 1705334500,
    "direction": "BUY",
    "confidence": 0.75,
    "sl_pips": 15.0,
    "tp_pips": 30.0,
    "claude_direction": "BUY",
    "claude_confidence": 0.78,
    "gemini_direction": "BUY",
    "gemini_confidence": 0.72,
    "reasoning": "Strong upward momentum",
}


def test_write_signal_returns_row_id(db_path):
    row_id = store.write_signal(db_path, _SIGNAL)
    assert isinstance(row_id, int) and row_id > 0


def test_write_signal_duplicate_returns_none(db_path):
    store.write_signal(db_path, _SIGNAL)
    assert store.write_signal(db_path, _SIGNAL) is None


def test_write_signal_hold_allows_null_sl_tp(db_path):
    signal = {**_SIGNAL, "timestamp": 1705334401, "direction": "HOLD",
              "confidence": 0.0, "sl_pips": None, "tp_pips": None,
              "claude_direction": "BUY", "gemini_direction": "SELL",
              "reasoning": "Models disagreed: claude=BUY, gemini=SELL"}
    row_id = store.write_signal(db_path, signal)
    assert row_id is not None


def test_get_latest_signals_returns_dataframe(db_path):
    for i in range(3):
        store.write_signal(db_path, {**_SIGNAL, "timestamp": 1705334400 + i * 900,
                                      "created_at": 1705334500 + i * 900})
    df = store.get_latest_signals(db_path, "EURUSD", "15m", 2)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df["timestamp"].is_monotonic_increasing


def test_get_latest_signals_sorted_oldest_first(db_path):
    for i in range(5):
        store.write_signal(db_path, {**_SIGNAL, "timestamp": 1705334400 + i * 900,
                                      "created_at": 1705334500 + i * 900})
    df = store.get_latest_signals(db_path, "EURUSD", "15m", 5)
    assert list(df["timestamp"]) == sorted(df["timestamp"])


def test_get_latest_signals_respects_pair_and_timeframe(db_path):
    store.write_signal(db_path, {**_SIGNAL, "timeframe": "1H", "timestamp": 9999999})
    df = store.get_latest_signals(db_path, "EURUSD", "15m", 10)
    assert len(df) == 0


def test_write_signal_stores_all_fields(db_path):
    import sqlite3
    store.write_signal(db_path, _SIGNAL)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT * FROM signals WHERE timestamp=?",
                       (_SIGNAL["timestamp"],)).fetchone()
    conn.close()
    assert row is not None
    # direction is at index 5 (id, pair, timeframe, timestamp, created_at, direction)
    assert row[5] == "BUY"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_signals_store.py -v
```

Expected: FAIL — `store has no attribute 'write_signal'`.

- [ ] **Step 3: Add write_signal and get_latest_signals to store.py**

Append to `storage/store.py` (after the existing `get_candle_with_indicators` function):

```python
def write_signal(db_path: str, signal: dict) -> int | None:
    """Insert a signal. Returns new row id, or None if duplicate (same pair/timeframe/timestamp)."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO signals "
            "(pair, timeframe, timestamp, created_at, direction, confidence, "
            "sl_pips, tp_pips, claude_direction, claude_confidence, "
            "gemini_direction, gemini_confidence, reasoning) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                signal["pair"], signal["timeframe"], signal["timestamp"],
                signal["created_at"], signal["direction"], signal["confidence"],
                signal.get("sl_pips"), signal.get("tp_pips"),
                signal.get("claude_direction"), signal.get("claude_confidence"),
                signal.get("gemini_direction"), signal.get("gemini_confidence"),
                signal.get("reasoning"),
            ),
        )
        conn.commit()
        return cur.lastrowid if cur.rowcount > 0 else None
    finally:
        conn.close()


def get_latest_signals(db_path: str, pair: str, timeframe: str, n: int) -> pd.DataFrame:
    """Return the n most recent signals, sorted oldest-first."""
    conn = get_connection(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM signals WHERE pair=? AND timeframe=? "
            "ORDER BY timestamp DESC LIMIT ?",
            conn,
            params=(pair, timeframe, n),
        )
        return df.sort_values("timestamp").reset_index(drop=True)
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_signals_store.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Run full suite for regressions**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add storage/store.py tests/test_signals_store.py
git commit -m "feat: add write_signal and get_latest_signals to store"
```

---

## Task 3: Prompt builder

**Files:**
- Create: `ai/__init__.py`
- Create: `ai/prompt.py`
- Create: `tests/test_prompt.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_prompt.py`:

```python
import pandas as pd
from ai.prompt import build


def _make_candles(n: int, base_ts: int = 1705334400, interval: int = 900) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "timestamp": base_ts + i * interval,
            "open": round(1.0850 + i * 0.0001, 5),
            "high": round(1.0860 + i * 0.0001, 5),
            "low":  round(1.0840 + i * 0.0001, 5),
            "close": round(1.0855 + i * 0.0001, 5),
            "volume": 1000.0,
        }
        for i in range(n)
    ])


_INDICATORS = {
    "ema20": 1.0828, "ema50": 1.0819, "ema200": 1.0801,
    "rsi14": 58.3, "macd": 0.00042, "macd_signal": 0.00031, "macd_hist": 0.00011,
    "bb_upper": 1.0851, "bb_mid": 1.0828, "bb_lower": 1.0805,
    "atr14": 0.00089, "stoch_k": 64.2, "stoch_d": 61.8,
}


def test_build_returns_non_empty_string():
    result = build(_make_candles(20, interval=3600), _make_candles(20), _INDICATORS)
    assert isinstance(result, str) and len(result) > 200


def test_build_contains_required_sections():
    result = build(_make_candles(20, interval=3600), _make_candles(20), _INDICATORS)
    assert "1-Hour Context" in result
    assert "15-Minute Context" in result
    assert "Current Indicators" in result
    assert '"direction"' in result
    assert '"confidence"' in result
    assert '"sl_pips"' in result
    assert '"tp_pips"' in result
    assert '"reasoning"' in result


def test_build_shows_row_count_in_header():
    result = build(_make_candles(20, interval=3600), _make_candles(20), _INDICATORS)
    assert "last 20 candles" in result


def test_build_replaces_none_indicators_with_na():
    sparse = {k: None for k in _INDICATORS}
    result = build(_make_candles(5, interval=3600), _make_candles(5), sparse)
    assert "N/A" in result


def test_build_replaces_missing_indicators_with_na():
    result = build(_make_candles(5, interval=3600), _make_candles(5), {})
    assert "N/A" in result


def test_build_formats_indicator_values():
    result = build(_make_candles(5, interval=3600), _make_candles(5), _INDICATORS)
    assert "1.08280" in result  # ema20 formatted to 5 dp
    assert "58.3" in result     # rsi14 formatted to 1 dp
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_prompt.py -v
```

Expected: FAIL — `No module named 'ai'`.

- [ ] **Step 3: Create ai/__init__.py**

Create `ai/__init__.py` as an empty file:

```python
```

- [ ] **Step 4: Create ai/prompt.py**

```python
import pandas as pd


def build(
    candles_1h: pd.DataFrame,
    candles_15m: pd.DataFrame,
    indicators: dict,
) -> str:
    """Build the structured prompt string for AI model analysis."""

    def format_candles(df: pd.DataFrame) -> str:
        rows = []
        for _, row in df.iterrows():
            ts = pd.Timestamp(int(row["timestamp"]), unit="s", tz="UTC").strftime("%Y-%m-%d %H:%M")
            rows.append(
                f"{ts}, {float(row['open']):.5f}, {float(row['high']):.5f}, "
                f"{float(row['low']):.5f}, {float(row['close']):.5f}, {float(row['volume']):.0f}"
            )
        return "\n".join(rows)

    def fmt(val, decimals: int = 5) -> str:
        if val is None:
            return "N/A"
        try:
            f = float(val)
            if f != f:  # NaN check
                return "N/A"
            return f"{f:.{decimals}f}"
        except (TypeError, ValueError):
            return "N/A"

    ind = (
        f"EMA20: {fmt(indicators.get('ema20'))} | "
        f"EMA50: {fmt(indicators.get('ema50'))} | "
        f"EMA200: {fmt(indicators.get('ema200'))}\n"
        f"RSI14: {fmt(indicators.get('rsi14'), 1)} | "
        f"MACD: {fmt(indicators.get('macd'))} | "
        f"Signal: {fmt(indicators.get('macd_signal'))} | "
        f"Hist: {fmt(indicators.get('macd_hist'))}\n"
        f"BB Upper: {fmt(indicators.get('bb_upper'))} | "
        f"Mid: {fmt(indicators.get('bb_mid'))} | "
        f"Lower: {fmt(indicators.get('bb_lower'))}\n"
        f"ATR14: {fmt(indicators.get('atr14'))} | "
        f"Stoch K: {fmt(indicators.get('stoch_k'), 1)} | "
        f"Stoch D: {fmt(indicators.get('stoch_d'), 1)}"
    )

    return (
        "You are a professional Forex analyst. Analyze the following EUR/USD market data "
        "and return a trading signal as JSON.\n\n"
        f"## 1-Hour Context (last {len(candles_1h)} candles — trend/bias)\n"
        "timestamp, open, high, low, close, volume\n"
        f"{format_candles(candles_1h)}\n\n"
        f"## 15-Minute Context (last {len(candles_15m)} candles — entry timing)\n"
        "timestamp, open, high, low, close, volume\n"
        f"{format_candles(candles_15m)}\n\n"
        "## Current Indicators (15m)\n"
        f"{ind}\n\n"
        "## Instructions\n"
        "Return ONLY valid JSON, no markdown, no explanation outside the JSON:\n"
        "{\n"
        '  "direction": "BUY" | "SELL" | "HOLD",\n'
        '  "confidence": 0.0-1.0,\n'
        '  "sl_pips": <number or null>,\n'
        '  "tp_pips": <number or null>,\n'
        '  "reasoning": "<one sentence>"\n'
        "}\n"
        "Rules: sl_pips and tp_pips must be null when direction is HOLD.\n"
        "confidence reflects certainty (0.5 = uncertain, 1.0 = very confident)."
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_prompt.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add ai/__init__.py ai/prompt.py tests/test_prompt.py
git commit -m "feat: add AI prompt builder"
```

---

## Task 4: Consensus engine

**Files:**
- Create: `ai/consensus.py`
- Create: `tests/test_consensus.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_consensus.py`:

```python
import pytest
from ai.consensus import Signal, resolve

PAIR, TF, TS = "EURUSD", "15m", 1705334400


def _r(direction: str, confidence: float, sl: float = None, tp: float = None, reasoning: str = "test") -> dict:
    return {"direction": direction, "confidence": confidence,
            "sl_pips": sl, "tp_pips": tp, "reasoning": reasoning}


def test_both_buy_returns_buy_with_averaged_values():
    sig = resolve(_r("BUY", 0.78, 15.0, 30.0), _r("BUY", 0.72, 12.0, 28.0), PAIR, TF, TS)
    assert sig.direction == "BUY"
    assert sig.confidence == pytest.approx(0.75)
    assert sig.sl_pips == pytest.approx(13.5)
    assert sig.tp_pips == pytest.approx(29.0)


def test_both_sell_returns_sell_with_averaged_values():
    sig = resolve(_r("SELL", 0.80, 20.0, 40.0), _r("SELL", 0.60, 18.0, 36.0), PAIR, TF, TS)
    assert sig.direction == "SELL"
    assert sig.confidence == pytest.approx(0.70)
    assert sig.sl_pips == pytest.approx(19.0)
    assert sig.tp_pips == pytest.approx(38.0)


def test_both_hold_returns_hold_with_avg_confidence():
    sig = resolve(_r("HOLD", 0.4), _r("HOLD", 0.6), PAIR, TF, TS)
    assert sig.direction == "HOLD"
    assert sig.confidence == pytest.approx(0.5)
    assert sig.sl_pips is None
    assert sig.tp_pips is None


def test_buy_sell_returns_hold_zero_confidence():
    sig = resolve(_r("BUY", 0.8), _r("SELL", 0.7), PAIR, TF, TS)
    assert sig.direction == "HOLD"
    assert sig.confidence == 0.0
    assert "claude=BUY" in sig.reasoning
    assert "gemini=SELL" in sig.reasoning


def test_sell_buy_returns_hold():
    sig = resolve(_r("SELL", 0.7), _r("BUY", 0.8), PAIR, TF, TS)
    assert sig.direction == "HOLD" and sig.confidence == 0.0


def test_buy_hold_returns_hold():
    sig = resolve(_r("BUY", 0.8), _r("HOLD", 0.3), PAIR, TF, TS)
    assert sig.direction == "HOLD" and sig.confidence == 0.0


def test_hold_buy_returns_hold():
    sig = resolve(_r("HOLD", 0.3), _r("BUY", 0.8), PAIR, TF, TS)
    assert sig.direction == "HOLD" and sig.confidence == 0.0


def test_sell_hold_returns_hold():
    sig = resolve(_r("SELL", 0.7), _r("HOLD", 0.4), PAIR, TF, TS)
    assert sig.direction == "HOLD" and sig.confidence == 0.0


def test_hold_sell_returns_hold():
    sig = resolve(_r("HOLD", 0.4), _r("SELL", 0.7), PAIR, TF, TS)
    assert sig.direction == "HOLD" and sig.confidence == 0.0


def test_signal_stores_raw_model_outputs():
    sig = resolve(_r("BUY", 0.78), _r("BUY", 0.72), PAIR, TF, TS)
    assert sig.claude_direction == "BUY"
    assert sig.claude_confidence == pytest.approx(0.78)
    assert sig.gemini_direction == "BUY"
    assert sig.gemini_confidence == pytest.approx(0.72)


def test_agreed_buy_reasoning_comes_from_claude():
    sig = resolve(_r("BUY", 0.8, reasoning="Claude says buy"), _r("BUY", 0.7, reasoning="Gemini says buy"), PAIR, TF, TS)
    assert sig.reasoning == "Claude says buy"


def test_error_fallback_forces_hold():
    """Client error fallback (HOLD, confidence=0.0) + real BUY → HOLD."""
    error = _r("HOLD", 0.0, reasoning="parse error")
    sig = resolve(_r("BUY", 0.8, 15.0, 30.0), error, PAIR, TF, TS)
    assert sig.direction == "HOLD"
    assert sig.confidence == 0.0


def test_one_model_none_sl_tp_uses_other():
    """When only one model provides SL/TP, use that value."""
    sig = resolve(_r("BUY", 0.8, 15.0, 30.0), _r("BUY", 0.7, None, None), PAIR, TF, TS)
    assert sig.direction == "BUY"
    assert sig.sl_pips == pytest.approx(15.0)
    assert sig.tp_pips == pytest.approx(30.0)


def test_signal_is_dataclass():
    sig = resolve(_r("HOLD", 0.0), _r("HOLD", 0.0), PAIR, TF, TS)
    assert isinstance(sig, Signal)
    assert sig.pair == PAIR
    assert sig.timeframe == TF
    assert sig.timestamp == TS
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_consensus.py -v
```

Expected: FAIL — `No module named 'ai.consensus'`.

- [ ] **Step 3: Create ai/consensus.py**

```python
from dataclasses import dataclass


@dataclass
class Signal:
    pair: str
    timeframe: str
    timestamp: int
    direction: str
    confidence: float
    sl_pips: float | None
    tp_pips: float | None
    claude_direction: str
    claude_confidence: float
    gemini_direction: str
    gemini_confidence: float
    reasoning: str


def _avg_optional(a: float | None, b: float | None) -> float | None:
    """Average two optional floats. If one is None, return the other."""
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return (a + b) / 2


def resolve(
    claude: dict,
    gemini: dict,
    pair: str,
    timeframe: str,
    timestamp: int,
) -> Signal:
    """
    Apply hard-veto consensus: both models must agree on direction.
    Any disagreement → HOLD with confidence=0.0.
    """
    c_dir = claude["direction"]
    g_dir = gemini["direction"]
    c_conf = float(claude["confidence"])
    g_conf = float(gemini["confidence"])

    if c_dir == g_dir:
        direction = c_dir
        confidence = (c_conf + g_conf) / 2
        if direction == "HOLD":
            sl_pips = None
            tp_pips = None
        else:
            sl_pips = _avg_optional(claude.get("sl_pips"), gemini.get("sl_pips"))
            tp_pips = _avg_optional(claude.get("tp_pips"), gemini.get("tp_pips"))
        reasoning = claude.get("reasoning", "")
    else:
        direction = "HOLD"
        confidence = 0.0
        sl_pips = None
        tp_pips = None
        reasoning = f"Models disagreed: claude={c_dir}, gemini={g_dir}"

    return Signal(
        pair=pair,
        timeframe=timeframe,
        timestamp=timestamp,
        direction=direction,
        confidence=confidence,
        sl_pips=sl_pips,
        tp_pips=tp_pips,
        claude_direction=c_dir,
        claude_confidence=c_conf,
        gemini_direction=g_dir,
        gemini_confidence=g_conf,
        reasoning=reasoning,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_consensus.py -v
```

Expected: all 14 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ai/consensus.py tests/test_consensus.py
git commit -m "feat: add consensus engine with hard-veto logic"
```

---

## Task 5: Claude client

**Files:**
- Create: `ai/claude_client.py`
- Create: `tests/test_claude_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_claude_client.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ai.claude_client import _parse_response, analyze


def test_parse_valid_json():
    text = '{"direction": "BUY", "confidence": 0.78, "sl_pips": 15.0, "tp_pips": 30.0, "reasoning": "Strong momentum"}'
    r = _parse_response(text)
    assert r["direction"] == "BUY"
    assert r["confidence"] == pytest.approx(0.78)
    assert r["sl_pips"] == pytest.approx(15.0)
    assert r["tp_pips"] == pytest.approx(30.0)
    assert r["reasoning"] == "Strong momentum"


def test_parse_hold_with_null_sl_tp():
    text = '{"direction": "HOLD", "confidence": 0.3, "sl_pips": null, "tp_pips": null, "reasoning": "uncertain"}'
    r = _parse_response(text)
    assert r["direction"] == "HOLD"
    assert r["sl_pips"] is None
    assert r["tp_pips"] is None


def test_parse_markdown_code_fence_stripped():
    text = '```json\n{"direction": "SELL", "confidence": 0.65, "sl_pips": 12.0, "tp_pips": 24.0, "reasoning": "Bearish"}\n```'
    r = _parse_response(text)
    assert r["direction"] == "SELL"
    assert r["confidence"] == pytest.approx(0.65)


def test_parse_plain_code_fence_stripped():
    text = '```\n{"direction": "BUY", "confidence": 0.7, "sl_pips": 10.0, "tp_pips": 20.0, "reasoning": "x"}\n```'
    r = _parse_response(text)
    assert r["direction"] == "BUY"


def test_parse_malformed_json_returns_hold_fallback():
    r = _parse_response("not valid json at all")
    assert r["direction"] == "HOLD"
    assert r["confidence"] == 0.0
    assert r["sl_pips"] is None
    assert r["tp_pips"] is None


def test_parse_invalid_direction_returns_hold_fallback():
    r = _parse_response('{"direction": "MAYBE", "confidence": 0.5, "sl_pips": null, "tp_pips": null, "reasoning": "x"}')
    assert r["direction"] == "HOLD"


def test_parse_confidence_clamped_above_one():
    r = _parse_response('{"direction": "BUY", "confidence": 2.5, "sl_pips": null, "tp_pips": null, "reasoning": "x"}')
    assert r["confidence"] == pytest.approx(1.0)


def test_parse_confidence_clamped_below_zero():
    r = _parse_response('{"direction": "HOLD", "confidence": -0.5, "sl_pips": null, "tp_pips": null, "reasoning": "x"}')
    assert r["confidence"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_analyze_returns_parsed_signal():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text='{"direction": "BUY", "confidence": 0.7, "sl_pips": 15.0, "tp_pips": 30.0, "reasoning": "test"}')]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("ai.claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await analyze("test prompt")

    assert result["direction"] == "BUY"
    assert result["confidence"] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_analyze_returns_hold_on_api_exception():
    with patch("ai.claude_client.anthropic.AsyncAnthropic", side_effect=Exception("API down")):
        result = await analyze("test prompt")

    assert result["direction"] == "HOLD"
    assert result["confidence"] == 0.0


@pytest.mark.asyncio
async def test_analyze_returns_hold_on_malformed_response():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="I cannot provide trading advice.")]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("ai.claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await analyze("test prompt")

    assert result["direction"] == "HOLD"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_claude_client.py -v
```

Expected: FAIL — `No module named 'ai.claude_client'`.

- [ ] **Step 3: Create ai/claude_client.py**

```python
import json
import logging
import re

import anthropic

import config

logger = logging.getLogger(__name__)

_HOLD_FALLBACK: dict = {
    "direction": "HOLD",
    "confidence": 0.0,
    "sl_pips": None,
    "tp_pips": None,
    "reasoning": "parse error",
}


def _parse_response(text: str) -> dict:
    """Strip markdown fences and parse JSON response. Returns HOLD fallback on any error."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return dict(_HOLD_FALLBACK)

    direction = data.get("direction", "")
    if direction not in {"BUY", "SELL", "HOLD"}:
        return dict(_HOLD_FALLBACK)

    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0

    def _to_float_or_none(val) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    return {
        "direction": direction,
        "confidence": confidence,
        "sl_pips": _to_float_or_none(data.get("sl_pips")),
        "tp_pips": _to_float_or_none(data.get("tp_pips")),
        "reasoning": str(data.get("reasoning", "")),
    }


async def analyze(prompt: str) -> dict:
    """Call Claude API and return parsed signal dict. Never raises."""
    try:
        client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=300,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_response(message.content[0].text)
    except Exception as exc:
        logger.warning("Claude analysis failed: %s", exc)
        return dict(_HOLD_FALLBACK)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_claude_client.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ai/claude_client.py tests/test_claude_client.py
git commit -m "feat: add Claude API client with JSON parsing and fallback"
```

---

## Task 6: Gemini client

**Files:**
- Create: `ai/gemini_client.py`
- Create: `tests/test_gemini_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gemini_client.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ai.gemini_client import _parse_response, analyze


def test_parse_valid_json():
    text = '{"direction": "SELL", "confidence": 0.65, "sl_pips": 12.0, "tp_pips": 24.0, "reasoning": "Bearish trend"}'
    r = _parse_response(text)
    assert r["direction"] == "SELL"
    assert r["confidence"] == pytest.approx(0.65)
    assert r["sl_pips"] == pytest.approx(12.0)


def test_parse_markdown_code_fence_stripped():
    text = '```json\n{"direction": "BUY", "confidence": 0.8, "sl_pips": 10.0, "tp_pips": 20.0, "reasoning": "bull"}\n```'
    r = _parse_response(text)
    assert r["direction"] == "BUY"


def test_parse_malformed_json_returns_hold_fallback():
    r = _parse_response("sorry I cannot help")
    assert r["direction"] == "HOLD"
    assert r["confidence"] == 0.0
    assert r["sl_pips"] is None


def test_parse_invalid_direction_returns_hold():
    r = _parse_response('{"direction": "UNKNOWN", "confidence": 0.5, "sl_pips": null, "tp_pips": null, "reasoning": "x"}')
    assert r["direction"] == "HOLD"


def test_parse_confidence_clamped():
    r = _parse_response('{"direction": "BUY", "confidence": 99.0, "sl_pips": null, "tp_pips": null, "reasoning": "x"}')
    assert r["confidence"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_analyze_returns_parsed_signal():
    mock_response = MagicMock()
    mock_response.text = '{"direction": "BUY", "confidence": 0.75, "sl_pips": 15.0, "tp_pips": 30.0, "reasoning": "test"}'
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    with patch("ai.gemini_client.genai.configure"), \
         patch("ai.gemini_client.genai.GenerativeModel", return_value=mock_model):
        result = await analyze("test prompt")

    assert result["direction"] == "BUY"
    assert result["confidence"] == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_analyze_returns_hold_on_api_exception():
    with patch("ai.gemini_client.genai.configure"), \
         patch("ai.gemini_client.genai.GenerativeModel", side_effect=Exception("quota exceeded")):
        result = await analyze("test prompt")

    assert result["direction"] == "HOLD"
    assert result["confidence"] == 0.0


@pytest.mark.asyncio
async def test_analyze_returns_hold_on_malformed_response():
    mock_response = MagicMock()
    mock_response.text = "I am unable to provide financial advice."
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    with patch("ai.gemini_client.genai.configure"), \
         patch("ai.gemini_client.genai.GenerativeModel", return_value=mock_model):
        result = await analyze("test prompt")

    assert result["direction"] == "HOLD"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_gemini_client.py -v
```

Expected: FAIL — `No module named 'ai.gemini_client'`.

- [ ] **Step 3: Create ai/gemini_client.py**

```python
import json
import logging
import re

import google.generativeai as genai

import config

logger = logging.getLogger(__name__)

_HOLD_FALLBACK: dict = {
    "direction": "HOLD",
    "confidence": 0.0,
    "sl_pips": None,
    "tp_pips": None,
    "reasoning": "parse error",
}


def _parse_response(text: str) -> dict:
    """Strip markdown fences and parse JSON response. Returns HOLD fallback on any error."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return dict(_HOLD_FALLBACK)

    direction = data.get("direction", "")
    if direction not in {"BUY", "SELL", "HOLD"}:
        return dict(_HOLD_FALLBACK)

    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0

    def _to_float_or_none(val) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    return {
        "direction": direction,
        "confidence": confidence,
        "sl_pips": _to_float_or_none(data.get("sl_pips")),
        "tp_pips": _to_float_or_none(data.get("tp_pips")),
        "reasoning": str(data.get("reasoning", "")),
    }


async def analyze(prompt: str) -> dict:
    """Call Gemini API and return parsed signal dict. Never raises."""
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                max_output_tokens=300,
            ),
        )
        response = await model.generate_content_async(prompt)
        return _parse_response(response.text)
    except Exception as exc:
        logger.warning("Gemini analysis failed: %s", exc)
        return dict(_HOLD_FALLBACK)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_gemini_client.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ai/gemini_client.py tests/test_gemini_client.py
git commit -m "feat: add Gemini API client with JSON parsing and fallback"
```

---

## Task 7: Analyzer orchestrator

**Files:**
- Create: `ai/analyzer.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_analyzer.py`:

```python
import pytest
import pandas as pd
from unittest.mock import patch, AsyncMock, MagicMock, call
from ai.analyzer import run_analysis_cycle


def _candles(n: int, base_ts: int = 1705334400, interval: int = 900) -> pd.DataFrame:
    return pd.DataFrame([
        {"id": i + 1, "pair": "EURUSD", "timeframe": "15m",
         "timestamp": base_ts + i * interval,
         "open": 1.0850, "high": 1.0860, "low": 1.0840, "close": 1.0855, "volume": 1000.0}
        for i in range(n)
    ])


def _indicators() -> pd.DataFrame:
    return pd.DataFrame([{
        "id": 1, "candle_id": 20,
        "ema20": 1.0828, "ema50": 1.0819, "ema200": 1.0801,
        "rsi14": 58.3, "macd": 0.00042, "macd_signal": 0.00031, "macd_hist": 0.00011,
        "bb_upper": 1.0851, "bb_mid": 1.0828, "bb_lower": 1.0805,
        "atr14": 0.00089, "stoch_k": 64.2, "stoch_d": 61.8,
    }])


_BUY = {"direction": "BUY", "confidence": 0.75, "sl_pips": 15.0, "tp_pips": 30.0, "reasoning": "bull"}
_SELL = {"direction": "SELL", "confidence": 0.70, "sl_pips": 12.0, "tp_pips": 24.0, "reasoning": "bear"}


@patch("ai.analyzer.store.write_signal")
@patch("ai.analyzer.store.get_latest_indicators")
@patch("ai.analyzer.store.get_latest_candles")
@patch("ai.analyzer.gemini_client.analyze", new_callable=AsyncMock)
@patch("ai.analyzer.claude_client.analyze", new_callable=AsyncMock)
def test_both_agree_buy_writes_buy_signal(mock_claude, mock_gemini, mock_candles, mock_ind, mock_write):
    mock_claude.return_value = _BUY
    mock_gemini.return_value = _BUY
    mock_candles.return_value = _candles(20)
    mock_ind.return_value = _indicators()

    run_analysis_cycle("test.db", "EURUSD", "15m")

    mock_write.assert_called_once()
    sig = mock_write.call_args[0][1]
    assert sig["direction"] == "BUY"
    assert sig["pair"] == "EURUSD"
    assert sig["timeframe"] == "15m"
    assert sig["confidence"] == pytest.approx(0.75)


@patch("ai.analyzer.store.write_signal")
@patch("ai.analyzer.store.get_latest_indicators")
@patch("ai.analyzer.store.get_latest_candles")
@patch("ai.analyzer.gemini_client.analyze", new_callable=AsyncMock)
@patch("ai.analyzer.claude_client.analyze", new_callable=AsyncMock)
def test_disagreement_writes_hold(mock_claude, mock_gemini, mock_candles, mock_ind, mock_write):
    mock_claude.return_value = _BUY
    mock_gemini.return_value = _SELL
    mock_candles.return_value = _candles(20)
    mock_ind.return_value = _indicators()

    run_analysis_cycle("test.db", "EURUSD", "15m")

    sig = mock_write.call_args[0][1]
    assert sig["direction"] == "HOLD"
    assert sig["confidence"] == 0.0


@patch("ai.analyzer.store.write_signal")
@patch("ai.analyzer.store.get_latest_candles")
def test_empty_15m_candles_skips_analysis(mock_candles, mock_write):
    mock_candles.return_value = pd.DataFrame()

    run_analysis_cycle("test.db", "EURUSD", "15m")

    mock_write.assert_not_called()


@patch("ai.analyzer.store.write_signal")
@patch("ai.analyzer.store.get_latest_indicators")
@patch("ai.analyzer.store.get_latest_candles")
@patch("ai.analyzer.gemini_client.analyze", new_callable=AsyncMock)
@patch("ai.analyzer.claude_client.analyze", new_callable=AsyncMock)
def test_signal_timestamp_matches_latest_candle(mock_claude, mock_gemini, mock_candles, mock_ind, mock_write):
    mock_claude.return_value = _BUY
    mock_gemini.return_value = _BUY
    candles = _candles(20)
    mock_candles.return_value = candles
    mock_ind.return_value = _indicators()

    run_analysis_cycle("test.db", "EURUSD", "15m")

    sig = mock_write.call_args[0][1]
    expected_ts = int(candles["timestamp"].iloc[-1])
    assert sig["timestamp"] == expected_ts


@patch("ai.analyzer.store.write_fetch_log")
@patch("ai.analyzer.store.write_signal", side_effect=Exception("DB write failed"))
@patch("ai.analyzer.store.get_latest_indicators")
@patch("ai.analyzer.store.get_latest_candles")
@patch("ai.analyzer.gemini_client.analyze", new_callable=AsyncMock)
@patch("ai.analyzer.claude_client.analyze", new_callable=AsyncMock)
def test_write_signal_failure_logs_and_does_not_crash(mock_claude, mock_gemini, mock_candles, mock_ind, mock_write, mock_log):
    mock_claude.return_value = _BUY
    mock_gemini.return_value = _BUY
    mock_candles.return_value = _candles(20)
    mock_ind.return_value = _indicators()

    # Should not raise
    run_analysis_cycle("test.db", "EURUSD", "15m")

    mock_log.assert_called_once()
    args = mock_log.call_args[0]
    assert args[4] == "error"  # status argument
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_analyzer.py -v
```

Expected: FAIL — `No module named 'ai.analyzer'`.

- [ ] **Step 3: Create ai/analyzer.py**

```python
import asyncio
import logging
import time

from ai import claude_client, gemini_client
from ai.consensus import resolve
from ai.prompt import build
from storage import store

logger = logging.getLogger(__name__)


async def _parallel_analyze(prompt: str) -> tuple[dict, dict]:
    return await asyncio.gather(
        claude_client.analyze(prompt),
        gemini_client.analyze(prompt),
    )


def run_analysis_cycle(db_path: str, pair: str, timeframe: str) -> None:
    """
    Execute one complete analysis cycle. Never raises.

    Reads latest candles + indicators from store, builds a prompt,
    calls both AI models in parallel, applies consensus, and writes
    the resulting signal.
    """
    try:
        candles_1h = store.get_latest_candles(db_path, pair, "1H", 20)
        candles_15m = store.get_latest_candles(db_path, pair, timeframe, 20)

        if candles_15m.empty or candles_1h.empty:
            logger.warning(
                "Insufficient candle data for %s %s — skipping analysis", pair, timeframe
            )
            return

        indicators_df = store.get_latest_indicators(db_path, pair, timeframe, 1)
        indicators = indicators_df.iloc[-1].to_dict() if not indicators_df.empty else {}

        prompt = build(candles_1h, candles_15m, indicators)

        claude_result, gemini_result = asyncio.run(_parallel_analyze(prompt))

        timestamp = int(candles_15m["timestamp"].iloc[-1])
        signal = resolve(claude_result, gemini_result, pair, timeframe, timestamp)

        store.write_signal(db_path, {
            "pair": signal.pair,
            "timeframe": signal.timeframe,
            "timestamp": signal.timestamp,
            "created_at": int(time.time()),
            "direction": signal.direction,
            "confidence": signal.confidence,
            "sl_pips": signal.sl_pips,
            "tp_pips": signal.tp_pips,
            "claude_direction": signal.claude_direction,
            "claude_confidence": signal.claude_confidence,
            "gemini_direction": signal.gemini_direction,
            "gemini_confidence": signal.gemini_confidence,
            "reasoning": signal.reasoning,
        })

        logger.info(
            "Signal for %s %s: %s (confidence=%.2f, claude=%s, gemini=%s)",
            pair, timeframe, signal.direction, signal.confidence,
            signal.claude_direction, signal.gemini_direction,
        )

    except Exception as exc:
        store.write_fetch_log(
            db_path, pair, timeframe, "ai_analyzer", "error", str(exc), None
        )
        logger.error("Analysis cycle failed for %s %s: %s", pair, timeframe, exc)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_analyzer.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add ai/analyzer.py tests/test_analyzer.py
git commit -m "feat: add analyzer orchestrator with parallel AI calls"
```

---

## Task 8: Wire analysis job into scheduler

**Files:**
- Modify: `scheduler/jobs.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_analyzer.py` (append to the end of the file):

```python
def test_scheduler_has_analysis_job():
    from scheduler.jobs import create_scheduler
    scheduler = create_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert "analyze_15m" in job_ids
    scheduler.shutdown(wait=False)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_analyzer.py::test_scheduler_has_analysis_job -v
```

Expected: FAIL — `analyze_15m` not in job ids.

- [ ] **Step 3: Update scheduler/jobs.py**

Replace the entire `scheduler/jobs.py` with:

```python
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from ai.analyzer import run_analysis_cycle
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

    return scheduler
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_analyzer.py::test_scheduler_has_analysis_job -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scheduler/jobs.py tests/test_analyzer.py
git commit -m "feat: wire AI analysis job into scheduler every 15m"
```

---

## Completion Checklist

- [ ] `python -m pytest tests/ -v` — all tests green
- [ ] `signals` table present in schema.sql
- [ ] All 5 `ai/` modules exist with correct interfaces
- [ ] `store.write_signal` and `store.get_latest_signals` working
- [ ] Scheduler has `analyze_15m` job
- [ ] No real API calls in any test
- [ ] `.env` contains `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`
