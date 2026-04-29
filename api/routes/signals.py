import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Query

from api.deps import get_db_url

router = APIRouter()


@router.get("/signals")
def get_signals(
    pair: str = Query("EURUSD"),
    timeframe: str = Query("15m"),
    n: int = Query(50, ge=1, le=500),
):
    conn = psycopg2.connect(get_db_url())
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, timestamp, direction, confidence,
                       claude_direction, claude_confidence,
                       gemini_direction, gemini_confidence,
                       reasoning, sl_pips, tp_pips, created_at
                FROM signals
                WHERE pair = %s AND timeframe = %s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (pair, timeframe, n),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [dict(r) for r in reversed(rows)]
