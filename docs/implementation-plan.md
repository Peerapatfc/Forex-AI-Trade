# Forex AI Trading System — Full Implementation Plan

**Last updated:** 2026-04-22  
**Test status:** 205/205 passing  
**Backend status:** Fully functional — paper + live mode implemented  
**API:** FastAPI in `api/` — run with `uvicorn api.main:app --host 0.0.0.0 --port 8000`  
**Frontend:** Next.js 16 in `frontend/` — deploy to Vercel, set `NEXT_PUBLIC_API_URL`

---

## Phase 1: Data Foundation ✅ COMPLETE

| # | Task | Status |
|---|------|--------|
| 1.1 | Project scaffolding (dirs, config, deps) | ✅ |
| 1.2 | SQLite schema — candles, indicators, fetch_log | ✅ |
| 1.3 | Store write methods (candles, indicators, fetch_log) | ✅ |
| 1.4 | Store read methods (get_latest_candles, indicators) | ✅ |
| 1.5 | Indicator engine — EMA 20/50/200, RSI 14, MACD, BB, ATR 14, Stoch | ✅ |
| 1.6 | Alpha Vantage provider + token-bucket rate limiter | ✅ |
| 1.7 | yfinance fallback provider | ✅ |
| 1.8 | Fetcher orchestrator (primary + fallback + duplicate prevention) | ✅ |
| 1.9 | APScheduler jobs (15m + 1H fetch) + main entry point + backfill | ✅ |

---

## Phase 2: AI Analysis Pipeline ✅ COMPLETE

| # | Task | Status |
|---|------|--------|
| 2.1 | Signals table + store functions (write_signal, get_latest_signals) | ✅ |
| 2.2 | AI prompt builder (candles + indicators → structured prompt) | ✅ |
| 2.3 | Consensus engine (hard-veto: both must agree or HOLD) | ✅ |
| 2.4 | Claude API client (Anthropic async, JSON parse, fallback) | ✅ |
| 2.5 | Gemini API client (google.genai async, JSON parse, fallback) | ✅ (migrated from deprecated SDK) |
| 2.6 | Analyzer orchestrator (parallel AI calls → consensus → write signal) | ✅ |
| 2.7 | Analysis scheduler job (every 15m) | ✅ |

---

## Phase 3: Trade Execution ✅ COMPLETE

| # | Task | Status |
|---|------|--------|
| 3.1 | Position sizer (fixed-percent risk, min lot 0.01) | ✅ |
| 3.2 | Broker protocol (abstract interface) | ✅ |
| 3.3 | PaperBroker (simulated SL/TP, account tracking) | ✅ |
| 3.4 | LiveBroker stub (MT5 placeholder, blocks on startup) | ✅ |
| 3.5 | Account + trades tables + store functions | ✅ |
| 3.6 | Execution orchestrator (signal → open trade → SL/TP monitor) | ✅ |
| 3.7 | Execution scheduler job (every 15m) | ✅ |

---

## Phase 4: Performance Tracking ✅ COMPLETE

| # | Task | Status |
|---|------|--------|
| 4.1 | Stats table + write_stats/get_stats | ✅ |
| 4.2 | compute_stats (win rate, P&L, drawdown, trade count) | ✅ |
| 4.3 | run_stats_cycle orchestrator | ✅ |
| 4.4 | Stats scheduler job (every 15m) | ✅ |

---

## Bugs ✅ ALL FIXED

| # | Issue | Status |
|---|-------|--------|
| B1 | `config.py` missing `BROKER_MODE` + `PAPER_BALANCE` — `main.py` crashed on those attributes | ✅ Fixed |
| B2 | `requirements.txt` missing `anthropic`, `google-genai`, `pytest-asyncio` | ✅ Fixed |

---

## Phase 5: Frontend Dashboard (Vercel) ✅ COMPLETE

| # | Task | Status |
|---|------|--------|
| 5.1 | API layer — FastAPI endpoints (candles, signals, trades, stats) | ✅ |
| 5.2 | `/api/status` — current signal + account balance | ✅ |
| 5.3 | `/api/signals` — signal history with direction/confidence | ✅ |
| 5.4 | `/api/trades` — open/closed trades with P&L | ✅ |
| 5.5 | `/api/stats` — win rate, drawdown, total P&L | ✅ |
| 5.6 | Frontend UI (Next.js 16) — dashboard layout | ✅ |
| 5.7 | Charts — price + EMA overlay (lightweight-charts), equity curve | ✅ |
| 5.8 | Signal feed — live direction badges (BUY/SELL/HOLD) + AI reasoning | ✅ |
| 5.9 | Trade log table — entry/exit, SL/TP, P&L per trade | ✅ |
| 5.10 | Stats panel — win rate %, drawdown %, total P&L | ✅ |
| 5.11 | Vercel deployment config (`vercel.json`) | ✅ |
| 5.12 | Environment vars on Vercel (read-only DB via API) | ✅ |

---

## Phase 6: Live Deployment & Monitoring ✅ COMPLETE

| # | Task | Status |
|---|------|--------|
| 6.1 | LiveBroker full implementation (MT5 direct via MetaTrader5 library) | ✅ |
| 6.2 | `BROKER_MODE=live` guard lifted + integration tests | ✅ |
| 6.3 | Production environment setup (systemd service, install/update scripts) | ✅ |
| 6.4 | Alerting — email/Telegram on trade open/close/error | ✅ |
| 6.5 | Go-live criteria checklist (`scripts/check_golive.py`) | ✅ |
| 6.6 | Monitoring dashboard — built-in log viewer (`GET /api/logs` + LogViewer tab) | ✅ |

---

## Summary

| Phase | Status | Tests |
|-------|--------|-------|
| 1 — Data Foundation | ✅ Complete | ✅ |
| 2 — AI Analysis | ✅ Complete | ✅ |
| 3 — Trade Execution | ✅ Complete | ✅ |
| 4 — Performance Tracking | ✅ Complete | ✅ |
| Pre-5 bugs (B1, B2) | ✅ Fixed | — |
| 5 — Frontend (Vercel) | ✅ Complete | — |
| 6 — Live Deployment | ✅ Complete | ✅ (205/205) |

## Recommended Next Steps

1. Run `python scripts/check_golive.py` after paper trading to verify go-live criteria
2. Configure `.env` with MT5 credentials, Telegram/email alerts
3. Deploy to VPS: `sudo bash deploy/install.sh`
4. Switch to live: set `BROKER_MODE=live` in `.env`, restart service
