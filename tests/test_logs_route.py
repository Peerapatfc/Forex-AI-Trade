import os
import pytest
import psycopg2
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app
from storage.store import init_db

client = TestClient(app)

_FETCH_LOG_INSERT = (
    "INSERT INTO fetch_log (timestamp, pair, timeframe, provider, status, error_msg, duration_ms) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
)


@pytest.fixture
def db_with_logs(db_path):
    """Seed fetch_log with a mix of ok and error rows. db_path is the DATABASE_URL."""
    conn = psycopg2.connect(db_path)
    try:
        with conn.cursor() as cur:
            cur.execute(_FETCH_LOG_INSERT, (1705314225, "EURUSD", "15m", "alpha_vantage", "error", "Rate limit exceeded", None))
            cur.execute(_FETCH_LOG_INSERT, (1705314300, "GBPUSD", "1H", "twelve_data", "ok", None, 312))
            cur.execute(_FETCH_LOG_INSERT, (1705314400, "EURUSD", "15m", "twelve_data", "error", "Connection timeout", 0))
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_get_logs_returns_200_with_expected_keys(db_with_logs):
    with patch("api.routes.logs.get_db_url", return_value=db_with_logs):
        response = client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert "file_logs" in data
    assert "db_errors" in data


def test_get_logs_no_log_file_returns_empty_file_logs(db_with_logs):
    with patch("api.routes.logs.get_db_url", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE") as mock_path:
            mock_path.exists.return_value = False
            response = client.get("/api/logs")
    assert response.status_code == 200
    assert response.json()["file_logs"] == []


def test_get_logs_lines_param_limits_output(tmp_path, db_with_logs):
    log_file = tmp_path / "test.log"
    log_file.write_text("\n".join(f"line {i}" for i in range(10)), encoding="utf-8")

    with patch("api.routes.logs.get_db_url", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE", new=log_file):
            response = client.get("/api/logs?lines=3")

    assert response.status_code == 200
    data = response.json()
    assert len(data["file_logs"]) == 3
    assert data["file_logs"][0]["line"] == "line 7"
    assert data["file_logs"][2]["line"] == "line 9"


def test_get_logs_default_lines_up_to_200(tmp_path, db_with_logs):
    log_file = tmp_path / "test.log"
    log_file.write_text("\n".join(f"entry {i}" for i in range(50)), encoding="utf-8")

    with patch("api.routes.logs.get_db_url", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE", new=log_file):
            response = client.get("/api/logs")

    assert response.status_code == 200
    assert len(response.json()["file_logs"]) == 50


def test_get_logs_db_errors_only_error_status(db_with_logs):
    with patch("api.routes.logs.get_db_url", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE") as mock_path:
            mock_path.exists.return_value = False
            response = client.get("/api/logs")

    db_errors = response.json()["db_errors"]
    assert len(db_errors) == 2
    for row in db_errors:
        assert row["status"] == "error"


def test_get_logs_db_errors_excludes_ok_rows(db_with_logs):
    with patch("api.routes.logs.get_db_url", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE") as mock_path:
            mock_path.exists.return_value = False
            response = client.get("/api/logs")

    db_errors = response.json()["db_errors"]
    ok_combos = [(r["pair"], r["provider"]) for r in db_errors if r["status"] == "ok"]
    assert ok_combos == []


def test_get_logs_file_log_line_structure(tmp_path, db_with_logs):
    log_file = tmp_path / "test.log"
    log_file.write_text("INFO startup\nWARN something\n", encoding="utf-8")

    with patch("api.routes.logs.get_db_url", return_value=db_with_logs):
        with patch("api.routes.logs.LOG_FILE", new=log_file):
            response = client.get("/api/logs")

    data = response.json()
    assert len(data["file_logs"]) == 2
    for entry in data["file_logs"]:
        assert "line" in entry
        assert isinstance(entry["line"], str)


def test_get_logs_lines_param_validation_too_low():
    response = client.get("/api/logs?lines=0")
    assert response.status_code == 422


def test_get_logs_lines_param_validation_too_high():
    response = client.get("/api/logs?lines=1001")
    assert response.status_code == 422


def test_get_logs_db_errors_empty_on_db_error(db_with_logs):
    """When DB raises an error, db_errors returns [] not 500."""
    with patch("api.routes.logs.psycopg2.connect") as mock_connect:
        mock_connect.side_effect = psycopg2.OperationalError("connection failed")
        with patch("api.routes.logs.LOG_FILE") as mock_path:
            mock_path.exists.return_value = False
            response = client.get("/api/logs")

    assert response.status_code == 200
    assert response.json()["db_errors"] == []
