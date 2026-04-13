import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("data.providers.time.sleep", lambda s: None)


# --- Alpha Vantage mock responses ---

MOCK_AV_OK = {
    "Time Series FX (15min)": {
        "2024-01-15 16:00:00": {
            "1. open": "1.08500", "2. high": "1.08600",
            "3. low": "1.08450", "4. close": "1.08550", "5. volume": "1000",
        },
        "2024-01-15 15:45:00": {
            "1. open": "1.08400", "2. high": "1.08520",
            "3. low": "1.08380", "4. close": "1.08500", "5. volume": "900",
        },
    }
}

MOCK_AV_RATE_LIMIT = {
    "Note": "Thank you for using Alpha Vantage! Our standard API rate is 5 calls per minute."
}

MOCK_AV_ERROR = {
    "Error Message": "Invalid API call."
}


def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.raise_for_status.return_value = None
    mock.status_code = status_code
    return mock


# --- Alpha Vantage tests ---

@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_returns_dataframe(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_OK)

    df = fetch_alpha_vantage("fake_key", "EURUSD", "15m")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2


@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_column_names(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_OK)

    df = fetch_alpha_vantage("fake_key", "EURUSD", "15m")

    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_types(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_OK)

    df = fetch_alpha_vantage("fake_key", "EURUSD", "15m")

    assert df["timestamp"].dtype.kind == "i"  # integer
    assert df["open"].dtype.kind == "f"       # float


@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_sorted_ascending(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_OK)

    df = fetch_alpha_vantage("fake_key", "EURUSD", "15m")

    assert df["timestamp"].is_monotonic_increasing


@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_raises_on_rate_limit(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_RATE_LIMIT)

    with pytest.raises(ValueError, match="rate limit"):
        fetch_alpha_vantage("fake_key", "EURUSD", "15m")


@patch("data.providers.requests.get")
def test_fetch_alpha_vantage_raises_on_error_message(mock_get):
    from data.providers import fetch_alpha_vantage
    mock_get.return_value = _mock_response(MOCK_AV_ERROR)

    with pytest.raises(ValueError, match="Alpha Vantage error"):
        fetch_alpha_vantage("fake_key", "EURUSD", "15m")


# --- Rate limiter tests ---

def test_rate_limiter_records_calls():
    from data.providers import RateLimiter
    limiter = RateLimiter(calls_per_minute=5)
    limiter.wait_if_needed()
    limiter.wait_if_needed()
    assert len(limiter._call_times) == 2


# --- yfinance tests ---

@patch("data.providers.yf.Ticker")
def test_fetch_yfinance_returns_dataframe(mock_ticker_cls):
    from data.providers import fetch_yfinance
    index = pd.date_range("2024-01-15 09:00", periods=3, freq="15min", tz="UTC")
    mock_hist = pd.DataFrame({
        "Open": [1.085, 1.086, 1.087],
        "High": [1.086, 1.087, 1.088],
        "Low": [1.084, 1.085, 1.086],
        "Close": [1.0855, 1.0865, 1.0875],
        "Volume": [1000.0, 1100.0, 900.0],
    }, index=index)
    mock_ticker_cls.return_value.history.return_value = mock_hist

    df = fetch_yfinance("EURUSD", "15m")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


@patch("data.providers.yf.Ticker")
def test_fetch_yfinance_raises_on_empty_response(mock_ticker_cls):
    from data.providers import fetch_yfinance
    mock_ticker_cls.return_value.history.return_value = pd.DataFrame()

    with pytest.raises(ValueError, match="empty DataFrame"):
        fetch_yfinance("EURUSD", "15m")


# --- Fallback tests ---

@patch("data.providers.fetch_alpha_vantage")
@patch("data.providers.fetch_yfinance")
def test_fetch_candles_uses_alpha_vantage_first(mock_yf, mock_av):
    from data.providers import fetch_candles
    mock_av.return_value = pd.DataFrame([{
        "timestamp": 1705334400, "open": 1.085, "high": 1.086,
        "low": 1.084, "close": 1.0855, "volume": 1000.0,
    }])

    df, provider = fetch_candles("fake_key", "EURUSD", "15m")

    assert provider == "alpha_vantage"
    mock_yf.assert_not_called()


@patch("data.providers.fetch_alpha_vantage")
@patch("data.providers.fetch_yfinance")
def test_fetch_candles_falls_back_to_yfinance_on_av_failure(mock_yf, mock_av):
    from data.providers import fetch_candles
    mock_av.side_effect = ValueError("rate limit")
    mock_yf.return_value = pd.DataFrame([{
        "timestamp": 1705334400, "open": 1.085, "high": 1.086,
        "low": 1.084, "close": 1.0855, "volume": 1000.0,
    }])

    df, provider = fetch_candles("fake_key", "EURUSD", "15m")

    assert provider == "yfinance"
    assert len(df) == 1


@patch("data.providers.fetch_alpha_vantage")
@patch("data.providers.fetch_yfinance")
def test_fetch_candles_raises_when_both_fail(mock_yf, mock_av):
    from data.providers import fetch_candles
    mock_av.side_effect = ValueError("AV failed")
    mock_yf.side_effect = ValueError("yf failed")

    with pytest.raises(RuntimeError, match="Both providers failed"):
        fetch_candles("fake_key", "EURUSD", "15m")
