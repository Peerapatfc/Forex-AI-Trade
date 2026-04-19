import sqlite3

from fastapi import APIRouter, Query
from fastapi.exceptions import HTTPException

from api.deps import get_db_path

router = APIRouter()


@router.get("/stats")
def get_stats(pair: str = Query("EURUSD")):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM stats WHERE pair = ?", (pair,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="No stats yet for this pair")

    return dict(row)
