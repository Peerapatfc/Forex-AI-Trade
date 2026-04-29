import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Query

from api.deps import get_db_url

router = APIRouter()


@router.get("/candles")
def get_candles(
    pair: str = Query("EURUSD"),
    timeframe: str = Query("15m"),
    n: int = Query(200, ge=1, le=1000),
):
    conn = psycopg2.connect(get_db_url())
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.timestamp AS time,
                       c.open, c.high, c.low, c.close, c.volume,
                       i.ema20, i.ema50, i.ema200
                FROM candles c
                LEFT JOIN indicators i ON i.candle_id = c.id
                WHERE c.pair = %s AND c.timeframe = %s
                ORDER BY c.timestamp DESC
                LIMIT %s
                """,
                (pair, timeframe, n),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [dict(r) for r in reversed(rows)]
