import base64
import httpx
import json
from typing import Optional, List

from app.core.config import settings
from app.services.parser import ParsedLabelResult

# --- Configuration ---
LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions"

VLM_SYSTEM_PROMPT = """/no_think You are an expert hazardous product label analyst.

Your task is to visually read the provided product label image and extract specific information.

### Instructions

1. **Visual Scanning**:
   - Read all visible text: front panel, ingredient list, back panel, and side panels.
   - Handle rotated text, small print, and stylized fonts.
   - Do not guess ingredients that are not visible.

2. **Product Categorization**:
   - Determine the product's physical form.
   - Select the single best fitting category ID:
     1: "Aerosol / Spray"
     2: "Liquid Solution"
     3: "Powder / Granular"
     4: "Cream / Gel / Paste"
     5: "Solid / Tablet / Block"
     6: "Vapor / Strong Fumes"

3. **Ingredient Extraction**:
   - Extract only chemical ingredients or active/inactive components.
   - Exclude: usage instructions, warnings, marketing claims, brand names.
   - Normalize to lowercase. Merge line-break fragments (e.g. "so-\\ndium" → "sodium").

### Output Format
You MUST respond in strict JSON format matching the schema: 
{ "category_id": int, "category_name": str, "ingredients": [str] }
"""


def _get_model_queue() -> List[str]:
    """
    Parses the primary model and fallback models into an ordered list.
    """
    # Start with the primary model
    models = [settings.MODEL_ID]

    # Add fallbacks if defined in settings (comma-separated string)
    if hasattr(settings, "FALLBACK_MODEL_IDS") and settings.FALLBACK_MODEL_IDS:
        # Split by comma and strip whitespace
        fallbacks = [m.strip() for m in settings.FALLBACK_MODEL_IDS.split(",") if m.strip()]
        models.extend(fallbacks)

    return models


async def parse_image_with_vlm(image_bytes: bytes) -> Optional[ParsedLabelResult]:
    """
    Sends preprocessed JPEG bytes to OpenRouter with automatic model fallback.
    """
    # 1. Prepare Image Data
    b64_data = base64.standard_b64encode(image_bytes).decode("utf-8")
    image_data_uri = f"data:image/jpeg;base64,{b64_data}"

    # 2. Prepare Model Queue
    models_to_try = _get_model_queue()

    # 3. Initialize Headers (static for all requests)
    request_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "HTTP-Referer": "https://carciscan.edwardgarcia.site",
        "X-Title": "Hazardous Label Analyzer"
    }

    # 4. Iterate through models
    async with httpx.AsyncClient(timeout=90.0) as client:
        for model_id in models_to_try:
            print(f"Attempting model: {model_id}")  # Optional: Logging for debugging

            payload = {
                "model": model_id,
                "temperature": 0.0,
                "max_tokens": 1024,
                "stream": False,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": VLM_SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": image_data_uri}
                            },
                            {
                                "type": "text",
                                "text": "Analyze this label and extract the data."
                            }
                        ]
                    }
                ]
            }

            raw_content = None
            try:
                response = await client.post(
                    LLM_API_URL,
                    json=payload,
                    headers=request_headers,
                )

                # Handle HTTP errors (e.g., 429 Rate Limit, 500 Server Error)
                if response.status_code >= 400:
                    print(f"Model {model_id} failed with status {response.status_code}: {response.text}")
                    continue  # Try next model

                data = response.json()
                choices = data.get("choices", [])

                if not choices:
                    print(f"Model {model_id} returned no choices.")
                    continue

                message = choices[0].get("message", {})
                raw_content = message.get("content", "")

                if not raw_content:
                    print(f"Model {model_id} returned empty content.")
                    continue

                # Clean potential markdown fences
                cleaned_json = raw_content.strip()
                if cleaned_json.startswith("```json"):
                    cleaned_json = cleaned_json[7:]
                if cleaned_json.startswith("```"):
                    cleaned_json = cleaned_json[3:]
                if cleaned_json.endswith("```"):
                    cleaned_json = cleaned_json[:-3]

                parsed_data = json.loads(cleaned_json.strip())

                # Success! Return and break loop
                return ParsedLabelResult(**parsed_data)

            except json.JSONDecodeError as e:
                print(f"JSON Decode Error with model {model_id}: {e}")
                continue
            except Exception as e:
                print(f"Unexpected Error with model {model_id}: {str(e)}")
                continue

    # If all models fail
    print("All models failed to process the image.")
    return None