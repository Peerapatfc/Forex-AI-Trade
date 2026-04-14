import pytest
from ai.consensus import Signal, resolve

PAIR, TF, TS = "EURUSD", "15m", 1705334400


def _r(direction: str, confidence: float, sl: float = None, tp: float = None, reasoning: str = "test") -> dict:
    return {"direction": direction, "confidence": confidence,
            "sl_pips": sl, "tp_pips": tp, "reasoning": reasoning}


def test_both_buy_returns_buy_with_averaged_values():
    sig = resolve(_r("BUY", 0.78, 15.0, 30.0), _r("BUY", 0.72, 12.0, 28.0), PAIR, TF, TS)
    assert sig.direction == "BUY"
    assert sig.confidence == pytest.approx(0.75)
    assert sig.sl_pips == pytest.approx(13.5)
    assert sig.tp_pips == pytest.approx(29.0)


def test_both_sell_returns_sell_with_averaged_values():
    sig = resolve(_r("SELL", 0.80, 20.0, 40.0), _r("SELL", 0.60, 18.0, 36.0), PAIR, TF, TS)
    assert sig.direction == "SELL"
    assert sig.confidence == pytest.approx(0.70)
    assert sig.sl_pips == pytest.approx(19.0)
    assert sig.tp_pips == pytest.approx(38.0)


def test_both_hold_returns_hold_with_avg_confidence():
    sig = resolve(_r("HOLD", 0.4), _r("HOLD", 0.6), PAIR, TF, TS)
    assert sig.direction == "HOLD"
    assert sig.confidence == pytest.approx(0.5)
    assert sig.sl_pips is None
    assert sig.tp_pips is None


def test_buy_sell_returns_hold_zero_confidence():
    sig = resolve(_r("BUY", 0.8), _r("SELL", 0.7), PAIR, TF, TS)
    assert sig.direction == "HOLD"
    assert sig.confidence == 0.0
    assert "claude=BUY" in sig.reasoning
    assert "gemini=SELL" in sig.reasoning


def test_sell_buy_returns_hold():
    sig = resolve(_r("SELL", 0.7), _r("BUY", 0.8), PAIR, TF, TS)
    assert sig.direction == "HOLD" and sig.confidence == 0.0


def test_buy_hold_returns_hold():
    sig = resolve(_r("BUY", 0.8), _r("HOLD", 0.3), PAIR, TF, TS)
    assert sig.direction == "HOLD" and sig.confidence == 0.0


def test_hold_buy_returns_hold():
    sig = resolve(_r("HOLD", 0.3), _r("BUY", 0.8), PAIR, TF, TS)
    assert sig.direction == "HOLD" and sig.confidence == 0.0


def test_sell_hold_returns_hold():
    sig = resolve(_r("SELL", 0.7), _r("HOLD", 0.4), PAIR, TF, TS)
    assert sig.direction == "HOLD" and sig.confidence == 0.0


def test_hold_sell_returns_hold():
    sig = resolve(_r("HOLD", 0.4), _r("SELL", 0.7), PAIR, TF, TS)
    assert sig.direction == "HOLD" and sig.confidence == 0.0


def test_signal_stores_raw_model_outputs():
    sig = resolve(_r("BUY", 0.78), _r("BUY", 0.72), PAIR, TF, TS)
    assert sig.claude_direction == "BUY"
    assert sig.claude_confidence == pytest.approx(0.78)
    assert sig.gemini_direction == "BUY"
    assert sig.gemini_confidence == pytest.approx(0.72)


def test_agreed_buy_reasoning_comes_from_claude():
    sig = resolve(_r("BUY", 0.8, reasoning="Claude says buy"), _r("BUY", 0.7, reasoning="Gemini says buy"), PAIR, TF, TS)
    assert sig.reasoning == "Claude says buy"


def test_error_fallback_forces_hold():
    """Client error fallback (HOLD, confidence=0.0) + real BUY → HOLD."""
    error = _r("HOLD", 0.0, reasoning="parse error")
    sig = resolve(_r("BUY", 0.8, 15.0, 30.0), error, PAIR, TF, TS)
    assert sig.direction == "HOLD"
    assert sig.confidence == 0.0


def test_one_model_none_sl_tp_uses_other():
    """When only one model provides SL/TP, use that value."""
    sig = resolve(_r("BUY", 0.8, 15.0, 30.0), _r("BUY", 0.7, None, None), PAIR, TF, TS)
    assert sig.direction == "BUY"
    assert sig.sl_pips == pytest.approx(15.0)
    assert sig.tp_pips == pytest.approx(30.0)


def test_signal_is_dataclass():
    sig = resolve(_r("HOLD", 0.0), _r("HOLD", 0.0), PAIR, TF, TS)
    assert isinstance(sig, Signal)
    assert sig.pair == PAIR
    assert sig.timeframe == TF
    assert sig.timestamp == TS
