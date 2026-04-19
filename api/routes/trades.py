import sqlite3

from fastapi import APIRouter, Query

from api.deps import get_db_path, get_paper_balance

router = APIRouter()


@router.get("/trades")
def get_trades(pair: str = Query("EURUSD")):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        open_rows = conn.execute(
            "SELECT * FROM trades WHERE pair = ? AND status = 'open' ORDER BY opened_at",
            (pair,),
        ).fetchall()

        closed_rows = conn.execute(
            "SELECT * FROM trades WHERE pair = ? AND status = 'closed' ORDER BY closed_at",
            (pair,),
        ).fetchall()
    finally:
        conn.close()

    open_trades = [dict(r) for r in open_rows]
    closed_trades = [dict(r) for r in closed_rows]

    # Equity curve: start from paper balance, accumulate pnl_usd per closed trade
    initial = get_paper_balance()
    equity_curve = []
    running = initial
    for t in closed_trades:
        if t.get("closed_at") and t.get("pnl_usd") is not None:
            running += t["pnl_usd"]
            equity_curve.append({"time": t["closed_at"], "value": round(running, 2)})

    return {"open": open_trades, "closed": closed_trades, "equity_curve": equity_curve}
