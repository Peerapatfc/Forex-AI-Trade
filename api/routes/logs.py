import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Query

from api.deps import get_db_path

router = APIRouter()

LOG_FILE = Path(os.getenv("LOG_FILE", str(Path(__file__).parents[2] / "forex_ai.log")))


@router.get("/logs")
def get_logs(lines: int = Query(default=200, ge=1, le=1000)):
    # File logs
    file_logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        file_logs = [{"line": ln.rstrip()} for ln in all_lines[-lines:]]

    # DB error logs
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    db_errors = []
    try:
        rows = conn.execute(
            "SELECT * FROM fetch_log WHERE status='error' ORDER BY timestamp DESC LIMIT 100"
        ).fetchall()
        db_errors = [dict(row) for row in rows]
    except sqlite3.OperationalError:
        db_errors = []
    finally:
        conn.close()

    return {"file_logs": file_logs, "db_errors": db_errors}
