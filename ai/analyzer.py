import asyncio
import dataclasses
import logging
import time

from ai import claude_client, gemini_client
from ai.consensus import resolve
from ai.prompt import build
from storage import store

logger = logging.getLogger(__name__)


async def _parallel_analyze(prompt: str) -> tuple[dict, dict]:
    return await asyncio.wait_for(
        asyncio.gather(
            claude_client.analyze(prompt),
            gemini_client.analyze(prompt),
        ),
        timeout=30.0,
    )


def run_analysis_cycle(db_path: str, pair: str, timeframe: str) -> None:
    """
    Execute one complete analysis cycle. Never raises.

    Reads latest candles + indicators from store, builds a prompt,
    calls both AI models in parallel, applies consensus, and writes
    the resulting signal.

    Note: Uses asyncio.run() internally. Must not be called from within
    an already-running event loop (e.g., from an AsyncIOScheduler job).
    Currently safe because BlockingScheduler is used.
    """
    try:
        candles_1h = store.get_latest_candles(db_path, pair, "1H", 20)
        candles_15m = store.get_latest_candles(db_path, pair, timeframe, 20)

        if candles_15m.empty or candles_1h.empty:
            logger.warning(
                "Insufficient candle data for %s %s — skipping analysis", pair, timeframe
            )
            return

        indicators_df = store.get_latest_indicators(db_path, pair, timeframe, 1)
        indicators = indicators_df.iloc[-1].to_dict() if not indicators_df.empty else {}

        prompt = build(candles_1h, candles_15m, indicators, pair=pair)

        claude_result, gemini_result = asyncio.run(_parallel_analyze(prompt))

        timestamp = int(candles_15m["timestamp"].iloc[-1])
        signal = resolve(claude_result, gemini_result, pair, timeframe, timestamp)

        signal_dict = {**dataclasses.asdict(signal), "created_at": int(time.time())}
        store.write_signal(db_path, signal_dict)

        logger.info(
            "Signal for %s %s: %s (confidence=%.2f, claude=%s, gemini=%s)",
            pair, timeframe, signal.direction, signal.confidence,
            signal.claude_direction, signal.gemini_direction,
        )

    except Exception as exc:
        store.write_fetch_log(
            db_path, pair, timeframe, "ai_analyzer", "error", str(exc), None
        )
        logger.error("Analysis cycle failed for %s %s: %s", pair, timeframe, exc)
