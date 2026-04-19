"""Integration tests for main.py broker-selection logic (task 6.2)."""

import sys
from unittest.mock import MagicMock, patch

import pytest

import main as main_module


def _run(config_attrs: dict):
    """
    Directly test main.main() with fully patched config and dependencies.
    Returns (paper_mock, live_mock).
    """
    mock_paper = MagicMock()
    mock_paper.return_value = MagicMock()
    mock_live = MagicMock()
    mock_live.return_value = MagicMock()

    mock_scheduler = MagicMock()
    mock_scheduler.start.side_effect = KeyboardInterrupt

    fake_lb_module = MagicMock()
    fake_lb_module.LiveBroker = mock_live

    cfg = MagicMock()
    cfg.ALPHA_VANTAGE_API_KEY = "key"
    cfg.ANTHROPIC_API_KEY = "key"
    cfg.GEMINI_API_KEY = "key"
    cfg.DB_PATH = ":memory:"
    cfg.PAPER_BALANCE = 10000.0
    cfg.PAIR = "EURUSD"
    cfg.TIMEFRAMES = ["15m"]
    cfg.BROKER_MODE = "paper"
    cfg.MT5_LOGIN = None
    cfg.MT5_PASSWORD = ""
    cfg.MT5_SERVER = ""

    for k, v in config_attrs.items():
        setattr(cfg, k, v)

    with (
        patch.object(main_module, "config", cfg),
        patch.object(main_module, "store") as ms,
        patch.object(main_module, "backfill"),
        patch.object(main_module, "create_scheduler", return_value=mock_scheduler),
        patch.object(main_module, "PaperBroker", mock_paper),
        patch.dict("sys.modules", {"execution.live_broker": fake_lb_module}),
    ):
        ms.init_db = MagicMock()
        ms.seed_account = MagicMock()
        ms.get_account_balance = MagicMock(return_value=10000.0)

        main_module.main()

    return mock_paper, mock_live


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBrokerModeSelection:
    def test_paper_mode_creates_paper_broker(self):
        """BROKER_MODE=paper should instantiate PaperBroker, not LiveBroker."""
        paper, live = _run({"BROKER_MODE": "paper"})
        assert paper.called, "PaperBroker constructor should have been called"
        assert not live.called, "LiveBroker constructor should NOT have been called"

    def test_live_mode_creates_live_broker(self):
        """BROKER_MODE=live with all credentials should instantiate LiveBroker."""
        paper, live = _run(
            {
                "BROKER_MODE": "live",
                "MT5_LOGIN": 12345,
                "MT5_PASSWORD": "secret",
                "MT5_SERVER": "Broker-Demo",
            }
        )
        assert live.called, "LiveBroker constructor should have been called"
        assert not paper.called, "PaperBroker constructor should NOT have been called"

    def test_live_mode_missing_login_exits(self):
        """BROKER_MODE=live with unset MT5_LOGIN exits."""
        with pytest.raises(SystemExit) as exc_info:
            _run(
                {
                    "BROKER_MODE": "live",
                    "MT5_LOGIN": None,
                    "MT5_PASSWORD": "secret",
                    "MT5_SERVER": "Broker-Demo",
                }
            )
        assert exc_info.value.code == 1

    def test_live_mode_missing_password_exits(self):
        """BROKER_MODE=live with empty MT5_PASSWORD should call sys.exit(1)."""
        with pytest.raises(SystemExit) as exc_info:
            _run(
                {
                    "BROKER_MODE": "live",
                    "MT5_LOGIN": 12345,
                    "MT5_PASSWORD": "",
                    "MT5_SERVER": "Broker-Demo",
                }
            )
        assert exc_info.value.code == 1

    def test_live_mode_missing_server_exits(self):
        """BROKER_MODE=live with empty MT5_SERVER should call sys.exit(1)."""
        with pytest.raises(SystemExit) as exc_info:
            _run(
                {
                    "BROKER_MODE": "live",
                    "MT5_LOGIN": 12345,
                    "MT5_PASSWORD": "secret",
                    "MT5_SERVER": "",
                }
            )
        assert exc_info.value.code == 1

    def test_unknown_broker_mode_exits(self):
        """Unknown BROKER_MODE value should call sys.exit(1)."""
        with pytest.raises(SystemExit) as exc_info:
            _run({"BROKER_MODE": "invalid"})
        assert exc_info.value.code == 1
