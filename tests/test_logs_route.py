import sqlite3
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app
from storage.store import init_db

client = TestClient(app)


@pytest.fixture
def db_with_logs(tmp_path):
    """Create a temp DB with a mix of ok and error fetch_log rows."""
    path = str(tmp_path / "test_logs.db")
    init_db(path)
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO fetch_log (timestamp, pair, timeframe, provider, status, error_msg, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1705314225, "EURUSD", "15m", "alpha_vantage", "error", "Rate limit exceeded", None),
    )
    conn.execute(
        "INSERT INTO fetch_log (timestamp, pair, timeframe, provider, status, error_msg, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1705314300, "GBPUSD", "1H", "twelve_data", "ok", None, 312),
    )
    conn.execute(
        "INSERT INTO fetch_log (timestamp, pair, timeframe, provider, status, error_msg, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1705314400, "EURUSD", "15m", "twelve_data", "error", "Connection timeout", 0),
    )
    conn.commit()
    conn.close()
    return path


def test_get_logs_returns_200_with_expected_keys(tmp_path, db_with_logs):
    """GET /api/logs returns 200 and response has file_logs and db_errors keys."""
    with patch("api.routes.logs.get_db_path", return_value=db_with_logs):
        response = client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert "file_logs" in data
    assert "db_errors" in data



def test_get_logs_no_log_file_returns_empty_file_logs(db_with_logs):
    """When log file doesn't exist, file_logs is an empty list."""
    with patch("api.routes.logs.get_db_path", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE") as mock_path:
            mock_path.exists.return_value = False
            response = client.get("/api/logs")
    assert response.status_code == 200
    assert response.json()["file_logs"] == []


def test_get_logs_lines_param_limits_output(tmp_path, db_with_logs):
    """?lines=N limits file_logs to at most N lines."""
    log_file = tmp_path / "test.log"
    # Write 10 lines
    log_file.write_text("\n".join(f"line {i}" for i in range(10)), encoding="utf-8")

    from pathlib import Path
    with patch("api.routes.logs.get_db_path", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE", new=log_file):
            response = client.get("/api/logs?lines=3")

    assert response.status_code == 200
    data = response.json()
    assert len(data["file_logs"]) == 3
    # Should be the LAST 3 lines
    assert data["file_logs"][0]["line"] == "line 7"
    assert data["file_logs"][2]["line"] == "line 9"


def test_get_logs_default_lines_up_to_200(tmp_path, db_with_logs):
    """Default lines=200 returns all lines when file has fewer than 200."""
    log_file = tmp_path / "test.log"
    log_file.write_text("\n".join(f"entry {i}" for i in range(50)), encoding="utf-8")

    with patch("api.routes.logs.get_db_path", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE", new=log_file):
            response = client.get("/api/logs")

    assert response.status_code == 200
    assert len(response.json()["file_logs"]) == 50


def test_get_logs_db_errors_only_error_status(db_with_logs):
    """db_errors only contains rows where status='error', not 'ok' rows."""
    with patch("api.routes.logs.get_db_path", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE") as mock_path:
            mock_path.exists.return_value = False
            response = client.get("/api/logs")

    data = response.json()
    db_errors = data["db_errors"]
    assert len(db_errors) == 2
    for row in db_errors:
        assert row["status"] == "error"


def test_get_logs_db_errors_excludes_ok_rows(db_with_logs):
    """Verify the 'ok' row from the DB is not present in db_errors."""
    with patch("api.routes.logs.get_db_path", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE") as mock_path:
            mock_path.exists.return_value = False
            response = client.get("/api/logs")

    db_errors = response.json()["db_errors"]
    providers = [r["provider"] for r in db_errors]
    # "twelve_data" ok row should not appear
    assert providers.count("twelve_data") == 1  # only the error row
    # check the ok row's pair+provider combo is absent
    ok_combos = [(r["pair"], r["provider"]) for r in db_errors if r["status"] == "ok"]
    assert ok_combos == []


def test_get_logs_file_log_line_structure(tmp_path, db_with_logs):
    """Each file_logs entry has a 'line' key."""
    log_file = tmp_path / "test.log"
    log_file.write_text("INFO startup\nWARN something\n", encoding="utf-8")

    with patch("api.routes.logs.get_db_path", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE", new=log_file):
            response = client.get("/api/logs")

    data = response.json()
    assert len(data["file_logs"]) == 2
    for entry in data["file_logs"]:
        assert "line" in entry
        assert isinstance(entry["line"], str)


def test_get_logs_lines_param_validation_too_low():
    """lines=0 should return 422 (ge=1 constraint)."""
    response = client.get("/api/logs?lines=0")
    assert response.status_code == 422


def test_get_logs_lines_param_validation_too_high():
    """lines=1001 should return 422 (le=1000 constraint)."""
    response = client.get("/api/logs?lines=1001")
    assert response.status_code == 422


def test_get_logs_db_errors_empty_on_missing_table(tmp_path):
    """When DB has no fetch_log table, db_errors returns [] not 500."""
    # Create an empty DB without running init_db (no tables)
    empty_db = str(tmp_path / "empty.db")
    conn = sqlite3.connect(empty_db)
    conn.close()

    with patch("api.routes.logs.get_db_path", return_value=empty_db):
        with patch("api.routes.logs.LOG_FILE") as mock_path:
            mock_path.exists.return_value = False
            response = client.get("/api/logs")

    assert response.status_code == 200
    data = response.json()
    assert data["db_errors"] == []
