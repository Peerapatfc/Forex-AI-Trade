import psycopg2
import psycopg2.extras
from fastapi import APIRouter

from api.deps import get_db_url

router = APIRouter()

_PAIR = "EURUSD"
_TIMEFRAME = "15m"


@router.get("/status")
def get_status():
    conn = psycopg2.connect(get_db_url())
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT balance FROM account WHERE id = 1")
            balance_row = cur.fetchone()
            balance = float(balance_row["balance"]) if balance_row else 0.0

            cur.execute(
                """
                SELECT direction, confidence, reasoning, timestamp
                FROM signals
                WHERE pair = %s AND timeframe = %s
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (_PAIR, _TIMEFRAME),
            )
            signal_row = cur.fetchone()
            signal = dict(signal_row) if signal_row else None
    finally:
        conn.close()

    return {"pair": _PAIR, "balance": balance, "signal": signal}
