import json
import logging
import re

from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)

_HOLD_FALLBACK: dict = {
    "direction": "HOLD",
    "confidence": 0.0,
    "sl_pips": None,
    "tp_pips": None,
    "reasoning": "parse error",
}

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _parse_response(text: str) -> dict:
    """Strip markdown fences and parse JSON response. Returns HOLD fallback on any error."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return dict(_HOLD_FALLBACK)

    direction = data.get("direction", "")
    if direction not in {"BUY", "SELL", "HOLD"}:
        return dict(_HOLD_FALLBACK)

    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0

    def _to_float_or_none(val) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    return {
        "direction": direction,
        "confidence": confidence,
        "sl_pips": _to_float_or_none(data.get("sl_pips")),
        "tp_pips": _to_float_or_none(data.get("tp_pips")),
        "reasoning": str(data.get("reasoning", "")),
    }


async def analyze(prompt: str) -> dict:
    """Call Gemini API and return parsed signal dict. Never raises."""
    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=300,
            ),
        )
        return _parse_response(response.text)
    except Exception as exc:
        logger.warning("Gemini analysis failed: %s", exc)
        return {**_HOLD_FALLBACK, "reasoning": "api error"}
