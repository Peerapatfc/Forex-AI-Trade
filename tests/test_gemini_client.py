import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ai.gemini_client import _parse_response, analyze
import ai.gemini_client as _gemini_module


@pytest.fixture(autouse=True)
def reset_gemini_client():
    """Reset the module-level cached client before each test."""
    _gemini_module._client = None
    yield
    _gemini_module._client = None


def test_parse_valid_json():
    text = '{"direction": "SELL", "confidence": 0.65, "sl_pips": 12.0, "tp_pips": 24.0, "reasoning": "Bearish trend"}'
    r = _parse_response(text)
    assert r["direction"] == "SELL"
    assert r["confidence"] == pytest.approx(0.65)
    assert r["sl_pips"] == pytest.approx(12.0)


def test_parse_markdown_code_fence_stripped():
    text = '```json\n{"direction": "BUY", "confidence": 0.8, "sl_pips": 10.0, "tp_pips": 20.0, "reasoning": "bull"}\n```'
    r = _parse_response(text)
    assert r["direction"] == "BUY"


def test_parse_malformed_json_returns_hold_fallback():
    r = _parse_response("sorry I cannot help")
    assert r["direction"] == "HOLD"
    assert r["confidence"] == 0.0
    assert r["sl_pips"] is None


def test_parse_invalid_direction_returns_hold():
    r = _parse_response('{"direction": "UNKNOWN", "confidence": 0.5, "sl_pips": null, "tp_pips": null, "reasoning": "x"}')
    assert r["direction"] == "HOLD"


def test_parse_confidence_clamped():
    r = _parse_response('{"direction": "BUY", "confidence": 99.0, "sl_pips": null, "tp_pips": null, "reasoning": "x"}')
    assert r["confidence"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_analyze_returns_parsed_signal():
    mock_response = MagicMock()
    mock_response.text = '{"direction": "BUY", "confidence": 0.75, "sl_pips": 15.0, "tp_pips": 30.0, "reasoning": "test"}'

    mock_aio_models = MagicMock()
    mock_aio_models.generate_content = AsyncMock(return_value=mock_response)

    mock_aio = MagicMock()
    mock_aio.models = mock_aio_models

    mock_client = MagicMock()
    mock_client.aio = mock_aio

    with patch("ai.gemini_client.genai.Client", return_value=mock_client):
        result = await analyze("test prompt")

    assert result["direction"] == "BUY"
    assert result["confidence"] == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_analyze_returns_hold_on_api_exception():
    with patch("ai.gemini_client.genai.Client", side_effect=Exception("quota exceeded")):
        result = await analyze("test prompt")

    assert result["direction"] == "HOLD"
    assert result["confidence"] == 0.0


@pytest.mark.asyncio
async def test_analyze_returns_hold_on_malformed_response():
    mock_response = MagicMock()
    mock_response.text = "I am unable to provide financial advice."

    mock_aio_models = MagicMock()
    mock_aio_models.generate_content = AsyncMock(return_value=mock_response)

    mock_aio = MagicMock()
    mock_aio.models = mock_aio_models

    mock_client = MagicMock()
    mock_client.aio = mock_aio

    with patch("ai.gemini_client.genai.Client", return_value=mock_client):
        result = await analyze("test prompt")

    assert result["direction"] == "HOLD"
