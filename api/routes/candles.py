import sqlite3

from fastapi import APIRouter, Query

from api.deps import get_db_path

router = APIRouter()


@router.get("/candles")
def get_candles(
    pair: str = Query("EURUSD"),
    timeframe: str = Query("15m"),
    n: int = Query(200, ge=1, le=1000),
):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT c.timestamp AS time,
                   c.open, c.high, c.low, c.close, c.volume,
                   i.ema20, i.ema50, i.ema200
            FROM candles c
            LEFT JOIN indicators i ON i.candle_id = c.id
            WHERE c.pair = ? AND c.timeframe = ?
            ORDER BY c.timestamp DESC
            LIMIT ?
            """,
            (pair, timeframe, n),
        ).fetchall()
    finally:
        conn.close()

    return [dict(r) for r in reversed(rows)]
