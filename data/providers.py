import logging
import time
from datetime import datetime, timezone

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

AV_INTERVAL_MAP = {"15m": "15min", "1H": "60min"}
YF_INTERVAL_MAP = {"15m": "15m", "1H": "1h"}
YF_PERIOD_MAP = {"15m": "5d", "1H": "15d"}
YF_TICKER_MAP = {"EURUSD": "EURUSD=X"}


class RateLimiter:
    """Token-bucket rate limiter; default matches Alpha Vantage free tier (5 calls/minute)."""

    def __init__(self, calls_per_minute: int = 5):
        self.calls_per_minute = calls_per_minute
        self._call_times: list[float] = []

    def wait_if_needed(self) -> None:
        now = time.time()
        self._call_times = [t for t in self._call_times if now - t < 60]
        if len(self._call_times) >= self.calls_per_minute:
            sleep_for = 60 - (now - self._call_times[0])
            if sleep_for > 0:
                logger.debug("Rate limit: sleeping %.1fs", sleep_for)
                time.sleep(sleep_for)
        self._call_times.append(time.time())


_rate_limiter = RateLimiter()


def fetch_alpha_vantage(
    api_key: str, pair: str, timeframe: str, outputsize: str = "compact"
) -> pd.DataFrame:
    """
    Fetch OHLCV candles from Alpha Vantage FX_INTRADAY endpoint.

    Returns DataFrame with columns: timestamp (int UTC), open, high, low, close, volume.
    Raises ValueError on rate-limit notes or error messages in the JSON response.
    Raises requests.HTTPError on non-2xx HTTP responses.
    """
    interval = AV_INTERVAL_MAP[timeframe]
    from_symbol, to_symbol = pair[:3], pair[3:]

    _rate_limiter.wait_if_needed()

    resp = requests.get(
        "https://www.alphavantage.co/query",
        params={
            "function": "FX_INTRADAY",
            "from_symbol": from_symbol,
            "to_symbol": to_symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": api_key,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if "Note" in data:
        raise ValueError(f"Alpha Vantage rate limit: {data['Note']}")
    if "Error Message" in data:
        raise ValueError(f"Alpha Vantage error: {data['Error Message']}")

    key = f"Time Series FX ({interval})"
    if key not in data:
        raise ValueError(f"Unexpected response keys: {list(data.keys())}")

    rows = []
    for ts_str, ohlcv in data[key].items():
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        rows.append({
            "timestamp": int(dt.timestamp()),
            "open": float(ohlcv["1. open"]),
            "high": float(ohlcv["2. high"]),
            "low": float(ohlcv["3. low"]),
            "close": float(ohlcv["4. close"]),
            "volume": float(ohlcv["5. volume"]),
        })

    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


def fetch_yfinance(pair: str, timeframe: str) -> pd.DataFrame:
    """
    Fetch OHLCV candles from Yahoo Finance.

    Returns DataFrame with columns: timestamp (int UTC), open, high, low, close, volume.
    Raises ValueError if the response is empty.
    """
    ticker_sym = YF_TICKER_MAP.get(pair, f"{pair[:3]}{pair[3:]}=X")
    ticker = yf.Ticker(ticker_sym)
    hist = ticker.history(interval=YF_INTERVAL_MAP[timeframe], period=YF_PERIOD_MAP[timeframe])

    if hist.empty:
        raise ValueError(f"yfinance returned empty DataFrame for {pair} {timeframe}")

    rows = []
    for idx, row in hist.iterrows():
        rows.append({
            "timestamp": int(idx.timestamp()),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row.get("Volume", 0.0)),
        })

    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


def fetch_candles(
    api_key: str, pair: str, timeframe: str, outputsize: str = "compact"
) -> tuple[pd.DataFrame, str]:
    """
    Fetch candles with automatic fallback: Alpha Vantage -> yfinance.

    Returns (DataFrame, provider_name).
    Raises RuntimeError if both providers fail.
    """
    try:
        df = fetch_alpha_vantage(api_key, pair, timeframe, outputsize)
        return df, "alpha_vantage"
    except Exception as exc:
        logger.warning("Alpha Vantage failed (%s), trying yfinance", exc)

    try:
        df = fetch_yfinance(pair, timeframe)
        return df, "yfinance"
    except Exception as exc:
        raise RuntimeError(f"Both providers failed for {pair} {timeframe}: {exc}") from exc
