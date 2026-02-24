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

# --- VLM System Prompt (Qwen3-VL optimized) ---
VLM_SYSTEM_PROMPT = """/no_think You are an expert hazardous product label analyst with strong visual text recognition ability.

You will receive an image of a hazardous product label. Your task is to visually read every part of the label and return a single valid JSON object.

### Instructions

1. **Visual Scanning**:
   - Read all visible text across the entire label: front panel, ingredient list, back panel, and any side panels visible in the image.
   - Handle rotated text, small print, stylized fonts, and partially obscured areas to the best of your ability.
   - Do not guess ingredients that are not visible in the image.

2. **Product Categorization**:
   - Determine the product's physical form by reading its name, description, and any usage cues on the label.
   - Select the single best fitting category ID:
     1: "Aerosol / Spray (Disinfectant, Freshener, Cleaner)"
     2: "Liquid Solution (Bleach, Detergent, Cleaner, Chemical)"
     3: "Powder / Granular (Detergent, Cleanser, Chemical)"
     4: "Cream / Gel / Paste (Polish, Cleaner, Compound)"
     5: "Solid / Tablet / Block (Bleach solid, chemical block)"
     6: "Vapor / Strong Fumes (Solvent, Paint, Thinner, Chemical)"
   - If ambiguous, infer from the most common physical form for that product type.

3. **Ingredient Extraction**:
   - Extract only chemical ingredients or active/inactive components listed on the label.
   - Exclude: usage instructions, safety warnings, marketing claims, brand names, manufacturer addresses, and barcodes.
   - Normalize each ingredient to lowercase. Merge any line-break fragments (e.g. "so-\\ndium" → "sodium").
   - If no ingredients are visible, return an empty list.

4. **Output Format**:
   - Return ONLY a valid JSON object. No markdown fences, no explanation, no extra text.

### JSON Schema
{
  "category_id": integer,
  "category_name": string,
  "ingredients": string[]
}"""


def _detect_media_type(image_bytes: bytes) -> str:
    """Infer image MIME type from magic bytes."""
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"  # fallback


async def parse_image_with_vlm(image_bytes: bytes) -> Optional[ParsedLabelResult]:
    """
    Sends the image directly to the LLM as a vision (multimodal) request
    and returns structured label data — no OCR step required.

    Args:
        image_bytes: Raw bytes of the product label image.

    Returns:
        ParsedLabelResult with category and ingredients, or None on failure.
    """
    media_type = _detect_media_type(image_bytes)
    b64_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    request_payload = {
        "model": MODEL_ID,
        "temperature": 0.1,
        "system": VLM_SYSTEM_PROMPT,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "This is a hazardous product label image. "
                            "Extract the category and ingredients and return the JSON as instructed."
                        ),
                    },
                ],
            }
        ],
    }

    raw_content = None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                LLM_API_URL,
                json=request_payload,
                headers={
                    "Authorization": LLM_API_KEY,
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()

            data = response.json()
            print(data)

            content_blocks = data.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    raw_content = block.get("text", "")
                    break

            if not raw_content:
                if isinstance(data.get("content"), str):
                    raw_content = data["content"]
                else:
                    raise ValueError("LLM response did not contain a valid 'text' content block")

            # Strip markdown fences if the model ignored instructions
            cleaned_json = raw_content.strip()
            if cleaned_json.startswith("```json"):
                cleaned_json = cleaned_json[7:]
            if cleaned_json.startswith("```"):
                cleaned_json = cleaned_json[3:]
            if cleaned_json.endswith("```"):
                cleaned_json = cleaned_json[:-3]

            parsed_data = json.loads(cleaned_json.strip())
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
