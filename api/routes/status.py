import sqlite3

from fastapi import APIRouter

from api.deps import get_db_path

router = APIRouter()

_PAIR = "EURUSD"
_TIMEFRAME = "15m"


@router.get("/status")
def get_status():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        balance_row = conn.execute(
            "SELECT balance FROM account WHERE id = 1"
        ).fetchone()
        balance = float(balance_row["balance"]) if balance_row else 0.0

        signal_row = conn.execute(
            """
            SELECT direction, confidence, reasoning, timestamp
            FROM signals
            WHERE pair = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (_PAIR, _TIMEFRAME),
        ).fetchone()
        signal = dict(signal_row) if signal_row else None
    finally:
        conn.close()

    return {"pair": _PAIR, "balance": balance, "signal": signal}
