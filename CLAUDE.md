# CLAUDE.md

## Project

Algorithmic forex trading bot. Python backend (FastAPI + APScheduler) + Next.js frontend. Multi-LLM consensus (Claude + Gemini) drives trade signals every 15 minutes.

## Commands

```bash
# Backend
python main.py                              # Start scheduler + data pipeline
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload  # API server
bash start.sh                               # Production: both together

# Frontend
cd frontend && npm run dev                  # Dev on :3000
cd frontend && npm run build && npm start   # Prod build

# Tests
pytest                                      # All 205 tests
pytest tests/test_executor.py -v           # Single file
pytest --ignore=tests/test_live_broker.py  # CI mode (skips MT5)

# Deployment
sudo bash deploy/install.sh                # First-time VPS setup
sudo bash deploy/update.sh                 # git pull + pip + restart
python scripts/check_golive.py             # Go-live validation
```

## Architecture

```
config.py               Environment (API keys, DB URL, broker mode, risk %)
main.py                 Entry: init_db → backfill → scheduler.start()
scheduler/jobs.py       4 APScheduler jobs at 15m intervals
data/fetcher.py         Alpha Vantage → yfinance fallback → indicators → store
indicators/engine.py    EMA 20/50/200, RSI, MACD, BB, ATR, Stochastic
ai/analyzer.py          Candles → prompt → parallel LLM calls → consensus → store signal
ai/prompt.py            Formats market data into structured LLM prompt
ai/consensus.py         Hard-veto: both models agree or HOLD (confidence=0)
ai/claude_client.py     Async Anthropic call, JSON parse, fallback to HOLD
ai/gemini_client.py     Async google-genai call, JSON parse, fallback to HOLD
execution/executor.py   Check SL/TP on open trades → size position → open trade
execution/paper.py      PaperBroker: simulated execution
execution/live.py       LiveBroker: MetaTrader5 API (requires MT5 terminal)
storage/store.py        All DB ops (30+ functions)
storage/schema.sql      PostgreSQL table definitions
api/main.py             FastAPI app + CORS
api/routes/             candles, signals, trades, stats, status, logs
frontend/               Next.js 16 + SWR + lightweight-charts + Tailwind
```

## Key Patterns

**Consensus logic** (`ai/consensus.py`): Both LLMs return `{direction, confidence, sl_pips, tp_pips}`. If directions match → average confidence and pips. If they disagree → direction=HOLD, confidence=0. Changing this is the most impactful architectural change.

**Scheduler jobs** (`scheduler/jobs.py`): All 4 jobs are `try/except`-wrapped so exceptions never crash APScheduler. Errors are logged, not raised.

**Broker protocol** (`execution/base.py`): `open_trade`, `close_trade`, `get_balance` abstract methods. PaperBroker and LiveBroker both implement this. Executor only talks to the protocol.

**Position sizing** (`execution/executor.py`): `lot_size = (balance * RISK_PCT) / (sl_pips * pip_value)`, min 0.01 lots.

**Rate limiting** (`data/fetcher.py`): Token-bucket limiter for Alpha Vantage free tier (5 calls/min). Do not remove — free tier blocks IPs on excess.

**DB fallback** (`config.py`): `DATABASE_URL` empty → SQLite at `data/forex.db`. PostgreSQL for production.

## Environment

Minimum `.env` for local dev:
```
ALPHA_VANTAGE_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
BROKER_MODE=paper
```

`CLAUDE_MODEL` defaults to `claude-haiku-4-5-20251001` (latest Haiku). `GEMINI_MODEL` defaults to `gemini-2.5-flash`.

## Tests

- `conftest.py` — PostgreSQL test DB fixture, creates/drops all tables per session
- `pytest.ini` — `asyncio_mode=auto`, `testpaths=tests`
- `test_live_broker.py` — skipped in CI (requires MT5 terminal)
- 22 test files covering: fetcher, indicators, consensus, paper broker, executor, API routes, stats

## Database Tables

`candles`, `indicators`, `signals`, `trades`, `account`, `stats`, `fetch_log`

Schema applied via `storage/store.py:init_db()` which runs `storage/schema.sql`. No migration system — drop and recreate for schema changes.

## Deployment

- **Render.com**: `render.yaml` + env vars in dashboard
- **VPS**: `deploy/install.sh` creates `forex` system user + venv + systemd service at `/etc/systemd/system/forex-ai.service`
- **Frontend**: Vercel. Set `NEXT_PUBLIC_API_URL` to backend URL.
- **CI**: `.github/workflows/ci.yml` — pytest on push/PR to master with PostgreSQL service

## Gotchas

- Live broker (`BROKER_MODE=live`) requires MetaTrader5 terminal running on the **same machine** — MT5 SDK is Windows-only.
- Alpha Vantage free tier: 5 req/min, 500 req/day. Changing fetch intervals risks hitting the daily cap.
- Frontend polls every 30s via SWR — no websockets.
- `start.sh` runs scheduler in background, API in foreground. Render expects a foreground process.
