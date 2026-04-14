import pandas as pd
from ai.prompt import build


def _make_candles(n: int, base_ts: int = 1705334400, interval: int = 900) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "timestamp": base_ts + i * interval,
            "open": round(1.0850 + i * 0.0001, 5),
            "high": round(1.0860 + i * 0.0001, 5),
            "low":  round(1.0840 + i * 0.0001, 5),
            "close": round(1.0855 + i * 0.0001, 5),
            "volume": 1000.0,
        }
        for i in range(n)
    ])


_INDICATORS = {
    "ema20": 1.0828, "ema50": 1.0819, "ema200": 1.0801,
    "rsi14": 58.3, "macd": 0.00042, "macd_signal": 0.00031, "macd_hist": 0.00011,
    "bb_upper": 1.0851, "bb_mid": 1.0828, "bb_lower": 1.0805,
    "atr14": 0.00089, "stoch_k": 64.2, "stoch_d": 61.8,
}


def test_build_returns_non_empty_string():
    result = build(_make_candles(20, interval=3600), _make_candles(20), _INDICATORS)
    assert isinstance(result, str) and len(result) > 200


def test_build_contains_required_sections():
    result = build(_make_candles(20, interval=3600), _make_candles(20), _INDICATORS)
    assert "1-Hour Context" in result
    assert "15-Minute Context" in result
    assert "Current Indicators" in result
    assert '"direction"' in result
    assert '"confidence"' in result
    assert '"sl_pips"' in result
    assert '"tp_pips"' in result
    assert '"reasoning"' in result


def test_build_shows_row_count_in_header():
    result = build(_make_candles(20, interval=3600), _make_candles(20), _INDICATORS)
    assert "last 20 candles" in result


def test_build_replaces_none_indicators_with_na():
    sparse = {k: None for k in _INDICATORS}
    result = build(_make_candles(5, interval=3600), _make_candles(5), sparse)
    assert "N/A" in result


def test_build_replaces_missing_indicators_with_na():
    result = build(_make_candles(5, interval=3600), _make_candles(5), {})
    assert "N/A" in result


def test_build_formats_indicator_values():
    result = build(_make_candles(5, interval=3600), _make_candles(5), _INDICATORS)
    assert "1.08280" in result  # ema20 formatted to 5 dp
    assert "58.3" in result     # rsi14 formatted to 1 dp
