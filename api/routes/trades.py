import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Query

from api.deps import get_db_url, get_paper_balance

router = APIRouter()


@router.get("/trades")
def get_trades(pair: str = Query("EURUSD")):
    conn = psycopg2.connect(get_db_url())
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM trades WHERE pair = %s AND status = 'open' ORDER BY opened_at",
                (pair,),
            )
            open_rows = cur.fetchall()

            cur.execute(
                "SELECT * FROM trades WHERE pair = %s AND status = 'closed' ORDER BY closed_at",
                (pair,),
            )
            closed_rows = cur.fetchall()
    finally:
        conn.close()

    open_trades = [dict(r) for r in open_rows]
    closed_trades = [dict(r) for r in closed_rows]

    initial = get_paper_balance()
    equity_curve = []
    running = initial
    for t in closed_trades:
        if t.get("closed_at") and t.get("pnl_usd") is not None:
            running += t["pnl_usd"]
            equity_curve.append({"time": t["closed_at"], "value": round(running, 2)})

    return {"open": open_trades, "closed": closed_trades, "equity_curve": equity_curve}
