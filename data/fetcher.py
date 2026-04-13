import logging
import time

from data.providers import fetch_candles
from indicators.engine import latest_indicators
from storage import store

logger = logging.getLogger(__name__)

# Number of historical candles to load when computing indicators.
# Must be > 200 so EMA200 is valid for the new candle.
_INDICATOR_HISTORY = 210


def run_fetch_cycle(
    db_path: str, api_key: str, pair: str, timeframe: str, outputsize: str = "compact"
) -> None:
    """
    Execute one complete fetch -> indicators -> store cycle.
    Logs the outcome to fetch_log regardless of success or failure.
    Never raises -- exceptions are caught and recorded.
    """
    start = time.time()

    try:
        df, provider = fetch_candles(api_key, pair, timeframe, outputsize)
    except RuntimeError as exc:
        duration_ms = int((time.time() - start) * 1000)
        store.write_fetch_log(db_path, pair, timeframe, "none", "skipped", str(exc), duration_ms)
        logger.warning("Skipped cycle %s %s: %s", pair, timeframe, exc)
        return

    new_count = 0
    for _, row in df.iterrows():
        candle = {
            "timestamp": int(row["timestamp"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        }
        candle_id = store.write_candle(db_path, pair, timeframe, candle)
        if candle_id is None:
            continue  # duplicate -- already stored

        new_count += 1
        history = store.get_latest_candles(db_path, pair, timeframe, _INDICATOR_HISTORY)
        if len(history) >= 2:
            ind = latest_indicators(history)
            store.write_indicators(db_path, candle_id, ind)

    duration_ms = int((time.time() - start) * 1000)
    store.write_fetch_log(db_path, pair, timeframe, provider, "ok", None, duration_ms)
    logger.info(
        "Fetched %d new candles for %s %s via %s in %dms",
        new_count, pair, timeframe, provider, duration_ms,
    )


def backfill(db_path: str, api_key: str, pair: str, timeframe: str) -> None:
    """Pull the last ~500 candles on first run so indicator history is populated."""
    logger.info("Backfilling %s %s...", pair, timeframe)
    run_fetch_cycle(db_path, api_key, pair, timeframe, outputsize="full")
