import pytest
import pandas as pd
from unittest.mock import patch, AsyncMock
from ai.analyzer import run_analysis_cycle


def _candles(n: int, base_ts: int = 1705334400, interval: int = 900) -> pd.DataFrame:
    return pd.DataFrame([
        {"id": i + 1, "pair": "EURUSD", "timeframe": "15m",
         "timestamp": base_ts + i * interval,
         "open": 1.0850, "high": 1.0860, "low": 1.0840, "close": 1.0855, "volume": 1000.0}
        for i in range(n)
    ])


def _indicators() -> pd.DataFrame:
    return pd.DataFrame([{
        "id": 1, "candle_id": 20,
        "ema20": 1.0828, "ema50": 1.0819, "ema200": 1.0801,
        "rsi14": 58.3, "macd": 0.00042, "macd_signal": 0.00031, "macd_hist": 0.00011,
        "bb_upper": 1.0851, "bb_mid": 1.0828, "bb_lower": 1.0805,
        "atr14": 0.00089, "stoch_k": 64.2, "stoch_d": 61.8,
    }])


_BUY = {"direction": "BUY", "confidence": 0.75, "sl_pips": 15.0, "tp_pips": 30.0, "reasoning": "bull"}
_SELL = {"direction": "SELL", "confidence": 0.70, "sl_pips": 12.0, "tp_pips": 24.0, "reasoning": "bear"}


@patch("ai.analyzer.store.write_signal")
@patch("ai.analyzer.store.get_latest_indicators")
@patch("ai.analyzer.store.get_latest_candles")
@patch("ai.analyzer.gemini_client.analyze", new_callable=AsyncMock)
@patch("ai.analyzer.claude_client.analyze", new_callable=AsyncMock)
def test_both_agree_buy_writes_buy_signal(mock_claude, mock_gemini, mock_candles, mock_ind, mock_write):
    mock_claude.return_value = _BUY
    mock_gemini.return_value = _BUY
    mock_candles.return_value = _candles(20)
    mock_ind.return_value = _indicators()

    run_analysis_cycle("test.db", "EURUSD", "15m")

    mock_write.assert_called_once()
    sig = mock_write.call_args[0][1]
    assert sig["direction"] == "BUY"
    assert sig["pair"] == "EURUSD"
    assert sig["timeframe"] == "15m"
    assert sig["confidence"] == pytest.approx(0.75)


@patch("ai.analyzer.store.write_signal")
@patch("ai.analyzer.store.get_latest_indicators")
@patch("ai.analyzer.store.get_latest_candles")
@patch("ai.analyzer.gemini_client.analyze", new_callable=AsyncMock)
@patch("ai.analyzer.claude_client.analyze", new_callable=AsyncMock)
def test_disagreement_writes_hold(mock_claude, mock_gemini, mock_candles, mock_ind, mock_write):
    mock_claude.return_value = _BUY
    mock_gemini.return_value = _SELL
    mock_candles.return_value = _candles(20)
    mock_ind.return_value = _indicators()

    run_analysis_cycle("test.db", "EURUSD", "15m")

    sig = mock_write.call_args[0][1]
    assert sig["direction"] == "HOLD"
    assert sig["confidence"] == 0.0


@patch("ai.analyzer.store.write_signal")
@patch("ai.analyzer.store.get_latest_candles")
def test_empty_15m_candles_skips_analysis(mock_candles, mock_write):
    # First call is 1H (returns full data), second call is 15m (returns empty)
    mock_candles.side_effect = [_candles(20, interval=3600), pd.DataFrame()]

    run_analysis_cycle("test.db", "EURUSD", "15m")

    mock_write.assert_not_called()


@patch("ai.analyzer.store.write_signal")
@patch("ai.analyzer.store.get_latest_indicators")
@patch("ai.analyzer.store.get_latest_candles")
@patch("ai.analyzer.gemini_client.analyze", new_callable=AsyncMock)
@patch("ai.analyzer.claude_client.analyze", new_callable=AsyncMock)
def test_signal_timestamp_matches_latest_candle(mock_claude, mock_gemini, mock_candles, mock_ind, mock_write):
    mock_claude.return_value = _BUY
    mock_gemini.return_value = _BUY
    candles = _candles(20)
    mock_candles.return_value = candles
    mock_ind.return_value = _indicators()

    run_analysis_cycle("test.db", "EURUSD", "15m")

    sig = mock_write.call_args[0][1]
    expected_ts = int(candles["timestamp"].iloc[-1])
    assert sig["timestamp"] == expected_ts


@patch("ai.analyzer.store.write_fetch_log")
@patch("ai.analyzer.store.write_signal", side_effect=Exception("DB write failed"))
@patch("ai.analyzer.store.get_latest_indicators")
@patch("ai.analyzer.store.get_latest_candles")
@patch("ai.analyzer.gemini_client.analyze", new_callable=AsyncMock)
@patch("ai.analyzer.claude_client.analyze", new_callable=AsyncMock)
def test_write_signal_failure_logs_and_does_not_crash(mock_claude, mock_gemini, mock_candles, mock_ind, mock_write, mock_log):
    mock_claude.return_value = _BUY
    mock_gemini.return_value = _BUY
    mock_candles.return_value = _candles(20)
    mock_ind.return_value = _indicators()

    # Should not raise
    run_analysis_cycle("test.db", "EURUSD", "15m")

    mock_log.assert_called_once_with(
        "test.db", "EURUSD", "15m", "ai_analyzer", "error", "DB write failed", None
    )


def test_scheduler_has_analysis_job():
    from scheduler.jobs import create_scheduler
    from unittest.mock import MagicMock
    broker = MagicMock()
    scheduler = create_scheduler(broker)
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert "analyze_15m" in job_ids
    analysis_job = next(j for j in scheduler.get_jobs() if j.id == "analyze_15m")
    assert analysis_job.trigger.interval.total_seconds() == 900  # 15 minutes
    assert analysis_job.kwargs["timeframe"] == "15m"
    assert "db_path" in analysis_job.kwargs
    assert "pair" in analysis_job.kwargs
    scheduler.remove_all_jobs()
