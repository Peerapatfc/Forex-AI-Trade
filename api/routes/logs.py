import os
import psycopg2
import psycopg2.extras
from pathlib import Path

from fastapi import APIRouter, Query

from api.deps import get_db_url

router = APIRouter()

LOG_FILE = Path(os.getenv("LOG_FILE", str(Path(__file__).parents[2] / "forex_ai.log")))


@router.get("/logs")
def get_logs(lines: int = Query(default=200, ge=1, le=1000)):
    file_logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        file_logs = [{"line": ln.rstrip()} for ln in all_lines[-lines:]]

    conn = psycopg2.connect(get_db_url())
    db_errors = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            try:
                cur.execute(
                    "SELECT * FROM fetch_log WHERE status='error' ORDER BY timestamp DESC LIMIT 100"
                )
                db_errors = [dict(r) for r in cur.fetchall()]
            except psycopg2.Error:
                db_errors = []
    finally:
        conn.close()

    return {"file_logs": file_logs, "db_errors": db_errors}
