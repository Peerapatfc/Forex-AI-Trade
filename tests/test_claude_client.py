import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import ai.claude_client as claude_client_module
from ai.claude_client import _parse_response, analyze


@pytest.fixture(autouse=True)
def reset_claude_client():
    """Reset the module-level cached client before each test."""
    claude_client_module._client = None
    yield
    claude_client_module._client = None


def test_parse_valid_json():
    text = '{"direction": "BUY", "confidence": 0.78, "sl_pips": 15.0, "tp_pips": 30.0, "reasoning": "Strong momentum"}'
    r = _parse_response(text)
    assert r["direction"] == "BUY"
    assert r["confidence"] == pytest.approx(0.78)
    assert r["sl_pips"] == pytest.approx(15.0)
    assert r["tp_pips"] == pytest.approx(30.0)
    assert r["reasoning"] == "Strong momentum"


def test_parse_hold_with_null_sl_tp():
    text = '{"direction": "HOLD", "confidence": 0.3, "sl_pips": null, "tp_pips": null, "reasoning": "uncertain"}'
    r = _parse_response(text)
    assert r["direction"] == "HOLD"
    assert r["sl_pips"] is None
    assert r["tp_pips"] is None


def test_parse_markdown_code_fence_stripped():
    text = '```json\n{"direction": "SELL", "confidence": 0.65, "sl_pips": 12.0, "tp_pips": 24.0, "reasoning": "Bearish"}\n```'
    r = _parse_response(text)
    assert r["direction"] == "SELL"
    assert r["confidence"] == pytest.approx(0.65)


def test_parse_plain_code_fence_stripped():
    text = '```\n{"direction": "BUY", "confidence": 0.7, "sl_pips": 10.0, "tp_pips": 20.0, "reasoning": "x"}\n```'
    r = _parse_response(text)
    assert r["direction"] == "BUY"


def test_parse_malformed_json_returns_hold_fallback():
    r = _parse_response("not valid json at all")
    assert r["direction"] == "HOLD"
    assert r["confidence"] == 0.0
    assert r["sl_pips"] is None
    assert r["tp_pips"] is None


def test_parse_invalid_direction_returns_hold_fallback():
    r = _parse_response('{"direction": "MAYBE", "confidence": 0.5, "sl_pips": null, "tp_pips": null, "reasoning": "x"}')
    assert r["direction"] == "HOLD"


def test_parse_confidence_clamped_above_one():
    r = _parse_response('{"direction": "BUY", "confidence": 2.5, "sl_pips": null, "tp_pips": null, "reasoning": "x"}')
    assert r["confidence"] == pytest.approx(1.0)


def test_parse_confidence_clamped_below_zero():
    r = _parse_response('{"direction": "HOLD", "confidence": -0.5, "sl_pips": null, "tp_pips": null, "reasoning": "x"}')
    assert r["confidence"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_analyze_returns_parsed_signal():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text='{"direction": "BUY", "confidence": 0.7, "sl_pips": 15.0, "tp_pips": 30.0, "reasoning": "test"}')]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("ai.claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await analyze("test prompt")

    assert result["direction"] == "BUY"
    assert result["confidence"] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_analyze_returns_hold_on_api_exception():
    with patch("ai.claude_client.anthropic.AsyncAnthropic", side_effect=Exception("API down")):
        result = await analyze("test prompt")

    assert result["direction"] == "HOLD"
    assert result["confidence"] == 0.0


@pytest.mark.asyncio
async def test_analyze_returns_hold_on_malformed_response():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="I cannot provide trading advice.")]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("ai.claude_client.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await analyze("test prompt")

    assert result["direction"] == "HOLD"
