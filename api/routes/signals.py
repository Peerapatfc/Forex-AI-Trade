import sqlite3

from fastapi import APIRouter, Query

from api.deps import get_db_path

router = APIRouter()


@router.get("/signals")
def get_signals(
    pair: str = Query("EURUSD"),
    timeframe: str = Query("15m"),
    n: int = Query(50, ge=1, le=500),
):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, timestamp, direction, confidence,
                   claude_direction, claude_confidence,
                   gemini_direction, gemini_confidence,
                   reasoning, sl_pips, tp_pips, created_at
            FROM signals
            WHERE pair = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (pair, timeframe, n),
        ).fetchall()
    finally:
        conn.close()

    return [dict(r) for r in reversed(rows)]
