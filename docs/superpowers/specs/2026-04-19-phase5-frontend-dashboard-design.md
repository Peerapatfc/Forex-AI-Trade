# Phase 5: Frontend Dashboard — Design Spec

**Date:** 2026-04-19  
**Status:** Approved

---

## Architecture

Option A selected: FastAPI on same server as trading bot, Next.js on Vercel.

```
forex-ai/
  api/                        ← FastAPI (new)
    main.py                   ← app + CORS + routers
    deps.py                   ← DB path from env
    routes/
      candles.py              ← GET /api/candles
      signals.py              ← GET /api/signals
      status.py               ← GET /api/status
      trades.py               ← GET /api/trades
      stats.py                ← GET /api/stats
  frontend/                   ← Next.js 16 (new)
    src/app/page.tsx          ← dashboard page
    src/components/           ← 6 UI components
    src/lib/api.ts            ← typed fetch client
    src/lib/types.ts          ← TypeScript interfaces
    vercel.json               ← framework: nextjs
    .env.local.example        ← NEXT_PUBLIC_API_URL=http://localhost:8000
```

**FastAPI** reads `forex.db` (read-only SQL queries, no writes). CORS open (`allow_origins=["*"]`).  
**Run:** `uvicorn api.main:app --host 0.0.0.0 --port 8000` from project root.

---

## API Endpoints

| Method | Path | Query Params | Response |
|--------|------|--------------|----------|
| GET | `/api/status` | — | `{ pair, balance, signal: {direction, confidence, reasoning, timestamp} }` |
| GET | `/api/candles` | `pair`, `timeframe`, `n=200` | `[{time, open, high, low, close, volume, ema20, ema50, ema200}]` |
| GET | `/api/signals` | `pair`, `timeframe`, `n=50` | `[{id, timestamp, direction, confidence, claude_direction, gemini_direction, reasoning}]` |
| GET | `/api/trades` | `pair` | `{ open: [...], closed: [...], equity_curve: [{time, value}] }` |
| GET | `/api/stats` | `pair` | `{win_rate, total_pnl_usd, max_drawdown_usd, trade_count, win_count, loss_count, ...}` |

Equity curve computed server-side: `PAPER_BALANCE` + cumulative `pnl_usd` from closed trades sorted by `closed_at`.

---

## Frontend Components

| Component | Purpose |
|-----------|---------|
| `StatusBar` | Pair name, direction badge (BUY=green / SELL=red / HOLD=gray), confidence %, account balance |
| `PriceChart` | Candlestick + EMA20 (amber) / EMA50 (blue) / EMA200 (purple) overlays |
| `EquityChart` | Line chart of account equity over time |
| `SignalFeed` | Last 20 signals — direction badge + expandable AI reasoning |
| `TradeLog` | Open + closed trades table — entry/exit price, SL/TP, P&L pips/USD |
| `StatsPanel` | Win rate %, total P&L USD, max drawdown USD, trade count |

---

## Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Backend | FastAPI + uvicorn | Async, typed, integrates with existing Python store |
| Frontend | Next.js 16, React 19 | Latest stable, Turbopack, App Router |
| Styling | Tailwind CSS | Dark theme, utility-first |
| Charts | lightweight-charts v5 | TradingView library, candlestick + line, browser-only |
| Data fetching | SWR | 30s poll interval, auto-revalidation |
| Language | TypeScript | Type-safe API client |

---

## Data Flow

```
forex.db (SQLite)
  ↓ read-only SQL queries
FastAPI (port 8000, same server)
  ↓ JSON over HTTP, CORS enabled
Next.js (Vercel) — SWR polling every 30s
  ↓ rendered in browser
Dashboard components
```

---

## Deployment

- FastAPI: run alongside trading bot on VPS (`systemd` service or `tmux`)
- Next.js: `vercel deploy` from `frontend/` directory
- Vercel env var: `NEXT_PUBLIC_API_URL=https://your-server.com`
- requirements.txt: add `fastapi>=0.115`, `uvicorn>=0.30`
