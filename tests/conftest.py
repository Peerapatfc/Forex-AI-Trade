import pytest
from storage.store import init_db


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test_forex.db")
    init_db(path)
    return path
