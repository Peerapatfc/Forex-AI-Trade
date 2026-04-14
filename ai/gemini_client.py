import json
import logging
import re

import google.generativeai as genai

import config

logger = logging.getLogger(__name__)

_HOLD_FALLBACK: dict = {
    "direction": "HOLD",
    "confidence": 0.0,
    "sl_pips": None,
    "tp_pips": None,
    "reasoning": "parse error",
}

_model: genai.GenerativeModel | None = None


def _get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        genai.configure(api_key=config.GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                max_output_tokens=300,
            ),
        )
    return _model


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
        response = await _get_model().generate_content_async(prompt)
        return _parse_response(response.text)
    except Exception as exc:
        logger.warning("Gemini analysis failed: %s", exc)
        return {**_HOLD_FALLBACK, "reasoning": "api error"}
