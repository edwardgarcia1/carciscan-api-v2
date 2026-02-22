import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
import json

# Import the service and models we are testing
from app.services.parser import parse_ocr_text, ParsedLabelResult

# --- Mock Data ---
MOCK_OCR_INPUT = "SUPER KLEEN ... Liquid ... Ingredients: Water, Sod ium Hypochlorite."

MOCK_LLM_RESPONSE_SUCCESS = {
    "content": [
        {
            "text": '{\n  "category_id": 2,\n  "category_name": "Liquid Solution (Bleach, Detergent, Cleaner, Chemical)",\n  "ingredients": ["Water", "Sodium Hypochlorite"]\n}'
        }
    ]
}

MOCK_LLM_RESPONSE_MARKDOWN = {
    "content": [
        {
            "text": '```json\n{\n  "category_id": 1,\n  "category_name": "Aerosol / Spray (Disinfectant, Freshener, Cleaner)",\n  "ingredients": ["Butane", "Propane"]\n}\n```'
        }
    ]
}

MOCK_LLM_RESPONSE_INVALID_JSON = {
    "content": [
        {
            "text": "Sorry, I could not read the label."
        }
    ]
}


# --- Unit Tests ---

@pytest.mark.asyncio
async def test_parse_ocr_text_success():
    """
    Test that a valid JSON response from the LLM is parsed correctly into a Pydantic model.
    """
    # 1. Setup the Mock Client
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_LLM_RESPONSE_SUCCESS
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    # 2. Patch httpx.AsyncClient
    with patch("app.services.parser.httpx.AsyncClient", return_value=mock_client):
        result = await parse_ocr_text(MOCK_OCR_INPUT)

    # 3. Assertions
    assert result is not None
    assert isinstance(result, ParsedLabelResult)
    assert result.category_id == 2
    assert result.category_name == "Liquid Solution (Bleach, Detergent, Cleaner, Chemical)"
    assert result.ingredients == ["Water", "Sodium Hypochlorite"]

    # Verify the payload sent to the API
    call_args = mock_client.post.call_args
    sent_payload = call_args.kwargs['json']
    assert sent_payload['messages'][0]['content'] == MOCK_OCR_INPUT
    assert sent_payload['temperature'] == 0.1


@pytest.mark.asyncio
async def test_parse_ocr_text_strips_markdown():
    """
    Test that the parser handles markdown code blocks (```json ... ```) gracefully.
    """
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_LLM_RESPONSE_MARKDOWN
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    with patch("app.services.parser.httpx.AsyncClient", return_value=mock_client):
        result = await parse_ocr_text("Some OCR text")

    assert result is not None
    assert result.category_id == 1
    assert "Butane" in result.ingredients


@pytest.mark.asyncio
async def test_parse_ocr_text_handles_invalid_json():
    """
    Test that the parser returns None if the LLM returns non-JSON text.
    """
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_LLM_RESPONSE_INVALID_JSON
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    with patch("app.services.parser.httpx.AsyncClient", return_value=mock_client):
        result = await parse_ocr_text("Unreadable text")

    assert result is None


@pytest.mark.asyncio
async def test_parse_ocr_text_handles_http_error():
    """
    Test that the parser returns None on HTTP errors (e.g., 500 Server Error).
    """
    mock_response = MagicMock()
    # Simulate an HTTP error
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
    )

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    with patch("app.services.parser.httpx.AsyncClient", return_value=mock_client):
        result = await parse_ocr_text("Some text")

    assert result is None

# --- Integration Test (Requires Running Server) ---

@pytest.mark.asyncio
@pytest.mark.integration
async def test_real_llm_connectivity():
    """
    Performs a real HTTP request to the LLM server.
    Run this specifically with: pytest -m integration
    """
    # A small, simple OCR snippet to test connectability
    real_ocr_text = "Product: Bleach. Ingredients: Water, Sodium Hypochlorite."

    # Call the actual service function (no mocks)
    result = await parse_ocr_text(real_ocr_text)

    # 1. Check that we got a result (not None)
    assert result is not None, "The service returned None. Check if the server is running and parsing correctly."

    # 2. Check the structure of the data
    assert isinstance(result, ParsedLabelResult)
    assert isinstance(result.category_id, int)
    assert isinstance(result.ingredients, list)

    # 3. Sanity check the content (Bleach is usually a Liquid)
    # Note: LLMs can vary, but this is a reasonable assertion for a connectivity test
    assert result.category_id == 2
    assert len(result.ingredients) > 0

    print(f"\n[Integration Test Success] Category: {result.category_name}")
    print(f"[Integration Test Success] Ingredients: {result.ingredients}")