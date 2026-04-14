from dataclasses import dataclass


@dataclass
class Signal:
    pair: str
    timeframe: str
    timestamp: int
    direction: str
    confidence: float
    sl_pips: float | None
    tp_pips: float | None
    claude_direction: str
    claude_confidence: float
    gemini_direction: str
    gemini_confidence: float
    reasoning: str
    # Note: created_at is NOT included — it is set by the caller (ai/analyzer.py)
    # when converting this dataclass to a dict for store.write_signal().


def _avg_optional(a: float | None, b: float | None) -> float | None:
    """Average two optional floats. If one is None, return the other."""
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return (a + b) / 2


def resolve(
    claude: dict,
    gemini: dict,
    pair: str,
    timeframe: str,
    timestamp: int,
) -> Signal:
    """
    Apply hard-veto consensus: both models must agree on direction.
    Any disagreement → HOLD with confidence=0.0.

    Precondition: claude["direction"] and gemini["direction"] must each be
    one of {"BUY", "SELL", "HOLD"}. Input validation is the responsibility
    of the AI clients (claude_client.py, gemini_client.py) before calling
    this function. Invalid directions are treated as disagreements.

    When both agree on HOLD, confidence is averaged (non-zero confidence
    means "confident this is a non-trade" rather than "uncertain").
    """
    c_dir = claude["direction"]
    g_dir = gemini["direction"]
    c_conf = float(claude["confidence"])
    g_conf = float(gemini["confidence"])

    if c_dir == g_dir:
        direction = c_dir
        confidence = (c_conf + g_conf) / 2
        if direction == "HOLD":
            sl_pips = None
            tp_pips = None
        else:
            sl_pips = _avg_optional(claude.get("sl_pips"), gemini.get("sl_pips"))
            tp_pips = _avg_optional(claude.get("tp_pips"), gemini.get("tp_pips"))
        reasoning = claude.get("reasoning", "")
    else:
        direction = "HOLD"
        confidence = 0.0
        sl_pips = None
        tp_pips = None
        reasoning = f"Models disagreed: claude={c_dir}, gemini={g_dir}"

    return Signal(
        pair=pair,
        timeframe=timeframe,
        timestamp=timestamp,
        direction=direction,
        confidence=confidence,
        sl_pips=sl_pips,
        tp_pips=tp_pips,
        claude_direction=c_dir,
        claude_confidence=c_conf,
        gemini_direction=g_dir,
        gemini_confidence=g_conf,
        reasoning=reasoning,
    )
