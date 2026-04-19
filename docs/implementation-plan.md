# Forex AI Trading System — Full Implementation Plan

**Last updated:** 2026-04-19  
**Test status:** 141/141 passing  
**Backend status:** Fully functional in paper mode

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

## Known Bugs (pre-Phase 5 blockers) ⚠️

| # | Issue | Status |
|---|-------|--------|
| B1 | `config.py` missing `BROKER_MODE` + `PAPER_BALANCE` — `main.py` crashes on those attributes | ❌ BUG |
| B2 | `requirements.txt` missing `anthropic`, `google-genai`, `pytest-asyncio` | ❌ BUG |

---

## Phase 5: Frontend Dashboard (Vercel) ❌ NOT STARTED

| # | Task | Status |
|---|------|--------|
| 5.1 | API layer — FastAPI endpoints (candles, signals, trades, stats) | ❌ |
| 5.2 | `/api/status` — current signal + account balance | ❌ |
| 5.3 | `/api/signals` — signal history with direction/confidence | ❌ |
| 5.4 | `/api/trades` — open/closed trades with P&L | ❌ |
| 5.5 | `/api/stats` — win rate, drawdown, total P&L | ❌ |
| 5.6 | Frontend UI (Next.js) — dashboard layout | ❌ |
| 5.7 | Charts — price + EMA overlay, equity curve | ❌ |
| 5.8 | Signal feed — live direction badges (BUY/SELL/HOLD) + AI reasoning | ❌ |
| 5.9 | Trade log table — entry/exit, SL/TP, P&L per trade | ❌ |
| 5.10 | Stats panel — win rate %, drawdown %, total P&L | ❌ |
| 5.11 | Vercel deployment config (`vercel.json`) | ❌ |
| 5.12 | Environment vars on Vercel (read-only DB via API) | ❌ |

---

## Phase 6: Live Deployment & Monitoring ❌ NOT STARTED

| # | Task | Status |
|---|------|--------|
| 6.1 | LiveBroker full implementation (MT5 via MetaApi or direct) | ❌ |
| 6.2 | `BROKER_MODE=live` guard lifted + integration tests | ❌ |
| 6.3 | Production environment setup (VPS/cloud, systemd service) | ❌ |
| 6.4 | Alerting — email/Telegram on trade open/close/error | ❌ |
| 6.5 | Go-live criteria checklist (min backtest P&L, max drawdown threshold) | ❌ |
| 6.6 | Monitoring dashboard (Grafana or built-in log viewer) | ❌ |

---

## Summary

| Phase | Status | Tests |
|-------|--------|-------|
| 1 — Data Foundation | ✅ Complete | ✅ |
| 2 — AI Analysis | ✅ Complete | ✅ |
| 3 — Trade Execution | ✅ Complete | ✅ |
| 4 — Performance Tracking | ✅ Complete | ✅ |
| Pre-5 bugs (B1, B2) | ❌ 2 bugs to fix | — |
| 5 — Frontend (Vercel) | ❌ Not started | — |
| 6 — Live Deployment | ❌ Not started | — |

## Recommended Next Steps

1. Fix B1: add `BROKER_MODE` and `PAPER_BALANCE` to `config.py` and `.env.example`
2. Fix B2: add missing deps to `requirements.txt`
3. Push 2 pending commits to GitHub
4. Start Phase 5 (frontend dashboard on Vercel)
5. Start Phase 6 (live deployment) after Phase 5 ships
