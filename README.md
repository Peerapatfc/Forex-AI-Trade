# Forex AI

Algorithmic forex trading bot using multi-LLM consensus analysis (Claude + Gemini) with automated execution and a real-time Next.js dashboard.

## Features

- **Dual-LLM consensus** — Claude and Gemini must agree on direction (BUY/SELL) or the bot holds. Conflicting signals → HOLD.
- **Technical analysis** — EMA 20/50/200, RSI, MACD, Bollinger Bands, ATR, Stochastic computed every 15 minutes.
- **Paper & live trading** — Paper mode (default) simulates execution with full SL/TP tracking. Live mode connects to MetaTrader5.
- **REST API** — FastAPI backend exposes candles, signals, trades, stats, and logs.
- **Real-time dashboard** — Next.js frontend with TradingView-style candle charts, equity curve, signal feed, and trade log.
- **Deployment-ready** — systemd service (VPS), Render.com config, and GitHub Actions CI included.

## Architecture

```
Data Layer      Alpha Vantage → yfinance fallback → PostgreSQL / SQLite
                Rate-limited token bucket (5 req/min for free tier)

Analysis Layer  Candles + Indicators → Prompt Builder → Claude + Gemini (parallel)
                Consensus Engine: hard-veto (both agree or HOLD)

Execution Layer Signal → Position Sizer (1% risk) → PaperBroker / LiveBroker (MT5)
                SL/TP check on every cycle, closes at candle price

Scheduler       APScheduler: fetch_15m, analyze_15m, execute_15m, stats_15m
                All jobs wrapped in try/except — scheduler never crashes

API Layer       FastAPI: /api/status /api/candles /api/signals /api/trades /api/stats /api/logs

Frontend        Next.js 16 + SWR polling (30s) + lightweight-charts + Tailwind CSS
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (frontend only)
- Alpha Vantage API key (free tier works)
- Anthropic API key (Claude)
- Google AI API key (Gemini)

### Setup

```bash
git clone <repo>
cd forex-ai

# Backend
cp .env.example .env
# Edit .env — add API keys at minimum
pip install -r requirements.txt
python main.py &                          # Scheduler + data pipeline
uvicorn api.main:app --reload             # API on :8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                               # Dashboard on :3000
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALPHA_VANTAGE_API_KEY` | Yes | Market data provider |
| `ANTHROPIC_API_KEY` | Yes | Claude API |
| `GEMINI_API_KEY` | Yes | Gemini API |
| `DATABASE_URL` | No | PostgreSQL URL — falls back to SQLite |
| `BROKER_MODE` | No | `paper` (default) or `live` |
| `PAPER_BALANCE` | No | Starting balance for paper mode (default: 10000) |
| `RISK_PCT` | No | Risk per trade as decimal (default: 0.01 = 1%) |
| `CLAUDE_MODEL` | No | Claude model ID (default: claude-haiku-4-5-20251001) |
| `GEMINI_MODEL` | No | Gemini model ID (default: gemini-1.5-flash) |
| `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` | Live only | MetaTrader5 credentials |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | No | Alert notifications |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Current balance + latest signal |
| GET | `/api/candles` | OHLCV history + EMA 20/50/200 |
| GET | `/api/signals` | Signal history (direction, confidence, reasoning) |
| GET | `/api/trades` | Open/closed trades + equity curve |
| GET | `/api/stats` | Win rate, drawdown, profit factor |
| GET | `/api/logs` | File logs + database error logs |

## Testing

```bash
pytest                                          # All tests (205)
pytest tests/test_executor.py -v               # Single file
pytest --ignore=tests/test_live_broker.py      # Skip live broker (CI mode)
```

Tests require a PostgreSQL instance. The `conftest.py` fixture handles table setup and teardown. CI spins up PostgreSQL as a service.

## Deployment

### VPS (systemd)

```bash
sudo bash deploy/install.sh    # First-time setup (creates forex system user, venv, service)
sudo bash deploy/update.sh     # Update: git pull + pip upgrade + restart
sudo systemctl status forex-ai
sudo journalctl -u forex-ai -f
```

### Render.com

Uses `render.yaml`. Set environment variables in the Render dashboard. Build command: `pip install -r requirements-server.txt`. Start command: `bash start.sh`.

### Frontend (Vercel)

Deploy the `frontend/` directory. Set `NEXT_PUBLIC_API_URL` to your backend URL.

## Database Schema

PostgreSQL (or SQLite fallback). Schema applied via `storage/schema.sql` on `init_db()`.

| Table | Contents |
|-------|----------|
| `candles` | OHLCV data indexed by pair/timeframe/timestamp |
| `indicators` | EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic |
| `signals` | AI-generated direction, confidence, SL/TP pips, reasoning |
| `trades` | Open/closed positions with entry price, SL, TP, P&L |
| `account` | Current account balance |
| `stats` | Win rate, max drawdown, profit factor, trade count |
| `fetch_log` | Data provider calls for debugging |

## Go-Live Checklist

```bash
python scripts/check_golive.py    # Validates all go-live criteria
```
