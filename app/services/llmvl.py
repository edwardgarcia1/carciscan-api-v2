import base64
import httpx
import json
from typing import Optional

from app.core.config import settings
from app.services.parser import ParsedLabelResult

# --- Configuration ---
LLM_API_URL = settings.LLM_API_URL
LLM_API_KEY = settings.LLM_API_KEY
MODEL_ID = settings.MODEL_ID

# Cleaned System Prompt
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


async def parse_image_with_vlm(image_bytes: bytes) -> Optional[ParsedLabelResult]:
    """
    Sends preprocessed JPEG bytes to the VLM and parses the structured response.
    """
    # 1. OPTIMIZATION: Hardcode JPEG encoding (Input is guaranteed from ImageProcessor)
    b64_data = base64.standard_b64encode(image_bytes).decode("utf-8")
    image_data_uri = f"data:image/jpeg;base64,{b64_data}"

    # 2. Construct Payload
    request_payload = {
        "model": MODEL_ID,
        "temperature": 0.0,
        "max_tokens": 1024,
        "stream": False,

        # Use standard OpenAI response_format for better JSON compliance
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
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                LLM_API_URL,
                json=request_payload,
                headers={
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()

            data = response.json()

            # --- OpenAI Response Parsing ---
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("LLM response did not contain valid 'choices'")

            message = choices[0].get("message", {})
            raw_content = message.get("content", "")

            if not raw_content:
                raise ValueError("LLM response content was empty")

            # Strip markdown fences (safety fallback)
            cleaned_json = raw_content.strip()
            if cleaned_json.startswith("```json"):
                cleaned_json = cleaned_json[7:]
            if cleaned_json.startswith("```"):
                cleaned_json = cleaned_json[3:]
            if cleaned_json.endswith("```"):
                cleaned_json = cleaned_json[:-3]

            parsed_data = json.loads(cleaned_json.strip())

            # Validate via Pydantic model
            return ParsedLabelResult(**parsed_data)

    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e} - Raw response: {raw_content}")
        return None
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        return None