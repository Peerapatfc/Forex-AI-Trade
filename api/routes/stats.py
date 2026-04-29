import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Query
from fastapi.exceptions import HTTPException

from api.deps import get_db_url

router = APIRouter()


@router.get("/stats")
def get_stats(pair: str = Query("EURUSD")):
    conn = psycopg2.connect(get_db_url())
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM stats WHERE pair = %s", (pair,))
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="No stats yet for this pair")

    return dict(row)
