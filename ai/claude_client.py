import json
import logging
import re

import anthropic

import config

logger = logging.getLogger(__name__)

_HOLD_FALLBACK: dict = {
    "direction": "HOLD",
    "confidence": 0.0,
    "sl_pips": None,
    "tp_pips": None,
    "reasoning": "parse error",
}


def _parse_response(text: str) -> dict:
    """Strip markdown fences and parse JSON response. Returns HOLD fallback on any error."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
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
    """Call Claude API and return parsed signal dict. Never raises."""
    try:
        client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=300,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_response(message.content[0].text)
    except Exception as exc:
        logger.warning("Claude analysis failed: %s", exc)
        return dict(_HOLD_FALLBACK)
