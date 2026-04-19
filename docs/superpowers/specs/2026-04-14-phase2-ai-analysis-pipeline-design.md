# Phase 2: AI Analysis Pipeline — Design Spec

**Date:** 2026-04-14
**Project:** Forex AI Trading System
**Phase:** 2 of 6 — AI Analysis Pipeline
**Status:** Approved

---

## Overview

Phase 2 adds an AI-powered signal generation layer on top of the Phase 1 data foundation. A dedicated APScheduler job reads the latest multi-timeframe candle and indicator data from the SQLite store, sends a structured prompt to both Claude (Opus 4.6) and Gemini (2.5 Pro) in parallel, applies a hard-veto consensus mechanism, and writes the resulting trading signal to a new `signals` table.

No trade execution. No frontend. Just a reliable, auditable signal record.

---

## Decisions

| Dimension | Decision | Rationale |
|---|---|---|
| AI models | Claude Opus 4.6 + Gemini 2.5 Pro | User has both Pro subscriptions; best reasoning quality available |
| Pipeline architecture | Decoupled parallel analyzer | AI failures never affect data fetching; `asyncio.gather` for speed |
| Consensus mechanism | Hard veto | Both must agree on direction or output is HOLD; conservative, auditable |
| Market context | Multi-timeframe (1H trend + 15m entry) | Higher TF for bias, lower TF for timing — standard professional practice |
| Context window | Last 20 candles per timeframe | 5h of 15m + ~20h of 1H; sufficient pattern context, token-efficient |
| Signal output | Full signal (direction, confidence, SL/TP pips, reasoning) | Needed for Phase 3 execution and Phase 4 performance tracking |
| Model config | Configurable via `.env` | Model names as env vars — upgrade without code changes |
| Retry policy | No retries within cycle | Log and skip; next cycle runs in 15m — avoids cascading delays |

---

## Architecture & Module Structure

```
forex-ai/
├── ai/
│   ├── __init__.py
│   ├── prompt.py          # builds prompt string from candle/indicator data
│   ├── claude_client.py   # calls Anthropic API → returns raw signal dict
│   ├── gemini_client.py   # calls Google GenAI API → returns raw signal dict
│   ├── consensus.py       # hard-veto logic → final Signal dataclass
│   └── analyzer.py        # orchestrates: read store → parallel calls → write signal
├── storage/
│   ├── schema.sql         # + signals table
│   └── store.py           # + write_signal(), get_latest_signals()
├── scheduler/
│   └── jobs.py            # + analysis job every 15m
└── config.py              # + ANTHROPIC_API_KEY, GEMINI_API_KEY, CLAUDE_MODEL, GEMINI_MODEL
```

### Data Flow

```
APScheduler (every 15m)
  → analyzer.run_analysis_cycle()
      → store.get_latest_candles(pair, "1H", 20)
      → store.get_latest_candles(pair, "15m", 20)
      → store.get_latest_indicators(pair, "15m", 1)
      → prompt.build(candles_1h, candles_15m, indicators)
      → asyncio.run(asyncio.gather(claude_client.analyze(prompt), gemini_client.analyze(prompt)))
      → consensus.resolve(claude_result, gemini_result)
      → store.write_signal(signal)

Note: APScheduler jobs are synchronous. `analyzer.run_analysis_cycle()` is a plain function
that calls `asyncio.run(...)` internally to execute parallel AI calls. No event loop
changes to the scheduler are needed.
```

---

## Storage: signals Table

```sql
CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pair        TEXT    NOT NULL,
    timeframe   TEXT    NOT NULL,
    timestamp   INTEGER NOT NULL,
    created_at  INTEGER NOT NULL,
    direction   TEXT    NOT NULL,
    confidence  REAL    NOT NULL,
    sl_pips     REAL,
    tp_pips     REAL,
    claude_direction   TEXT,
    claude_confidence  REAL,
    gemini_direction   TEXT,
    gemini_confidence  REAL,
    reasoning   TEXT,
    UNIQUE(pair, timeframe, timestamp)
);
```

- `timestamp` — the candle this signal is based on (links to `candles.timestamp`)
- `claude_direction` / `gemini_direction` — raw model outputs kept for audit
- `sl_pips` / `tp_pips` — NULL when direction is HOLD
- Duplicate signals silently ignored via `INSERT OR IGNORE`

---

## Prompt Design

Each model receives a single structured prompt built by `prompt.py`:

```
You are a professional Forex analyst. Analyze the following EUR/USD market data
and return a trading signal as JSON.

## 1-Hour Context (last 20 candles — trend/bias)
timestamp, open, high, low, close, volume
<20 rows of 1H OHLCV data>

## 15-Minute Context (last 20 candles — entry timing)
timestamp, open, high, low, close, volume
<20 rows of 15m OHLCV data>

## Current Indicators (15m)
EMA20: x | EMA50: x | EMA200: x
RSI14: x | MACD: x | Signal: x | Hist: x
BB Upper: x | Mid: x | Lower: x
ATR14: x | Stoch K: x | Stoch D: x

## Instructions
Return ONLY valid JSON, no markdown, no explanation outside the JSON:
{
  "direction": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0–1.0,
  "sl_pips": <number or null>,
  "tp_pips": <number or null>,
  "reasoning": "<one sentence>"
}
Rules: sl_pips and tp_pips must be null when direction is HOLD.
confidence reflects certainty (0.5 = uncertain, 1.0 = very confident).
```

**Model configuration:**
- Claude: `claude-opus-4-6` (env: `CLAUDE_MODEL`)
- Gemini: `gemini-2.5-pro` (env: `GEMINI_MODEL`)
- Temperature: `0.2` for both
- Max tokens: `300`

**Response parsing (each client):**
1. Strip markdown fences if present
2. Parse JSON
3. Validate `direction` ∈ {BUY, SELL, HOLD}
4. Clamp `confidence` to [0.0, 1.0]
5. On any error → return `{direction: "HOLD", confidence: 0.0, sl_pips: null, tp_pips: null, reasoning: "parse error"}`

---

## Consensus Engine

| Claude | Gemini | Output direction | Confidence | SL/TP |
|--------|--------|-----------------|------------|-------|
| BUY | BUY | BUY | avg(c, g) | avg(c, g) |
| SELL | SELL | SELL | avg(c, g) | avg(c, g) |
| HOLD | HOLD | HOLD | avg(c, g) | null |
| BUY | SELL | HOLD | 0.0 | null |
| SELL | BUY | HOLD | 0.0 | null |
| BUY | HOLD | HOLD | 0.0 | null |
| HOLD | BUY | HOLD | 0.0 | null |
| SELL | HOLD | HOLD | 0.0 | null |
| HOLD | SELL | HOLD | 0.0 | null |

When models agree: `reasoning` = Claude's reasoning string.
When models disagree: `reasoning` = `"Models disagreed: claude={X}, gemini={Y}"`.

---

## Error Handling

| Failure mode | Behaviour |
|---|---|
| One model times out (>30s) | Treat response as `HOLD, confidence=0.0` |
| One model returns malformed JSON | Parse error → HOLD fallback, no exception |
| Both models fail | Log error, skip `write_signal`, continue |
| `write_signal` fails | Log error, never crash scheduler |
| `get_latest_candles` returns empty DataFrame | Skip analysis cycle, log warning |

No retries within a cycle. Failed cycles are logged to the existing `fetch_log` table using a new provider value of `"ai_analyzer"`.

---

## Testing Strategy

```
forex-ai/tests/
├── test_prompt.py         # prompt builder output — no API calls
├── test_consensus.py      # all agree/disagree/error combinations — pure logic
├── test_claude_client.py  # mock Anthropic SDK → test parsing & fallback
├── test_gemini_client.py  # mock Google GenAI SDK → test parsing & fallback
└── test_analyzer.py       # integration: mock both clients + store → full cycle
```

**Coverage requirements:**
- `test_consensus.py`: all 7 direction combinations + error sentinel input
- `test_claude_client.py` / `test_gemini_client.py`: valid JSON, markdown-wrapped JSON, malformed JSON, timeout/API error
- `test_analyzer.py`: happy path (signal written), both-fail path (no write), empty-candles path (skip)

No real API calls in tests. All network calls mocked with `unittest.mock.patch`.

---

## New Dependencies

```
anthropic>=0.50,<1.0
google-generativeai>=0.8,<1.0
```

Both added to `requirements.txt`.

---

## Phase 2 Contract for Phase 3

Phase 3 (Trading Execution) reads signals via:
```python
store.get_latest_signals(db_path, pair, timeframe, n) -> pd.DataFrame
```

The `signals` table schema is the stable interface. Phase 3 must not depend on `ai/` internals.
