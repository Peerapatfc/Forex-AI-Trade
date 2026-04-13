import json
import pytest
import pandas as pd
from pathlib import Path
from indicators.engine import calculate, latest_indicators

FIXTURE = Path(__file__).parent / "fixtures" / "eurusd_15m.json"


@pytest.fixture
def eurusd_df():
    data = json.loads(FIXTURE.read_text())
    return pd.DataFrame(data)


def test_calculate_adds_all_indicator_columns(eurusd_df):
    result = calculate(eurusd_df)
    expected = [
        "ema20", "ema50", "ema200", "rsi14",
        "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_mid", "bb_lower",
        "atr14", "stoch_k", "stoch_d",
    ]
    for col in expected:
        assert col in result.columns, f"Missing column: {col}"


def test_ema200_valid_on_200_row_input(eurusd_df):
    result = calculate(eurusd_df)
    assert not pd.isna(result["ema200"].iloc[-1])


def test_ema200_all_nan_on_10_row_input(eurusd_df):
    result = calculate(eurusd_df.iloc[:10].copy())
    assert result["ema200"].isna().all()


def test_rsi_bounded_0_to_100(eurusd_df):
    result = calculate(eurusd_df)
    rsi = result["rsi14"].dropna()
    assert (rsi >= 0).all() and (rsi <= 100).all()


def test_bollinger_band_ordering(eurusd_df):
    result = calculate(eurusd_df)
    valid = result.dropna(subset=["bb_upper", "bb_mid", "bb_lower"])
    assert (valid["bb_upper"] >= valid["bb_mid"]).all()
    assert (valid["bb_mid"] >= valid["bb_lower"]).all()


def test_ema20_matches_pandas_ewm_reference(eurusd_df):
    """EMA20 verified independently: pandas ewm(span=20, adjust=False) is the standard formula."""
    result = calculate(eurusd_df)
    expected = float(eurusd_df["close"].ewm(span=20, adjust=False).mean().iloc[-1])
    actual = float(result["ema20"].iloc[-1])
    assert abs(actual - expected) < 1e-5


def test_latest_indicators_returns_dict_with_all_keys(eurusd_df):
    ind = latest_indicators(eurusd_df)
    expected_keys = [
        "ema20", "ema50", "ema200", "rsi14",
        "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_mid", "bb_lower",
        "atr14", "stoch_k", "stoch_d",
    ]
    for key in expected_keys:
        assert key in ind, f"Missing key: {key}"


def test_latest_indicators_none_for_nan_values(eurusd_df):
    """With only 10 rows, EMA200 cannot be computed — should return None, not NaN."""
    ind = latest_indicators(eurusd_df.iloc[:10].copy())
    assert ind["ema200"] is None


def test_latest_indicators_float_values_for_valid_row(eurusd_df):
    ind = latest_indicators(eurusd_df)
    assert isinstance(ind["ema20"], float)
    assert isinstance(ind["rsi14"], float)
    assert isinstance(ind["atr14"], float)
