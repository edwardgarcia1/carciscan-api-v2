import httpx
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from app.core.config import settings

# --- Configuration ---
LLM_API_URL = settings.LLM_API_URL
LLM_API_KEY = settings.LLM_API_KEY
MODEL_ID = settings.MODEL_ID

# --- The Optimized System Prompt ---
SYSTEM_PROMPT = """You are an expert Chemical Data Analyst specialized in OCR text processing and hazardous material identification. 

I will provide you with raw OCR text from a hazardous product label. Your task is to process this text and return a valid JSON object following the strict schema below.

### Instructions

1. **Product Categorization**:
   - Analyze the product name and description to determine its physical state.
   - Select the single best fitting category ID from the list below:
     1: "Aerosol / Spray (Disinfectant, Freshener, Cleaner)"
     2: "Liquid Solution (Bleach, Detergent, Cleaner, Chemical)"
     3: "Powder / Granular (Detergent, Cleanser, Chemical)"
     4: "Cream / Gel / Paste (Polish, Cleaner, Compound)"
     5: "Solid / Tablet / Block (Bleach solid, chemical block)"
     6: "Vapor / Strong Fumes (Solvent, Paint, Thinner, Chemical)"
   - If the text is ambiguous, infer the category based on common hazardous product forms.

2. **Ingredient Extraction & Cleaning**:
   - Extract only the ingredients. Ignore instructions, warnings, marketing text, or manufacturing addresses.
   - OCR Correction: Fix common OCR errors (e.g., "Sod ium" -> "Sodium", "HYP0CHLORITE" -> "HYPOCHLORITE").
   - Normalization: Merge fragmented text (e.g., "So- dium" -> "Sodium") and standardize capitalization (lower case).
   - If no ingredients are found, return an empty list.

3. **Output Format**:
   - Return ONLY a valid JSON object. Do not include markdown formatting (like ```json) or conversational text.

### JSON Schema
{
  "category_id": integer,
  "category_name": string,
  "ingredients": string[]
}"""


# --- Pydantic Models ---

class ParsedLabelResult(BaseModel):
    """The structured output expected from the LLM."""
    category_id: int
    category_name: str
    ingredients: List[str]


class AnthropicMessage(BaseModel):
    role: str = "user"
    content: str


class AnthropicRequest(BaseModel):
    model: str = MODEL_ID
    temperature: float = 0.1
    system: str = SYSTEM_PROMPT
    messages: List[AnthropicMessage]
    stream: bool = False


# --- Service Function ---

async def parse_ocr_text(ocr_text: str) -> Optional[ParsedLabelResult]:
    """
    Sends raw OCR text to the LLM endpoint and returns structured data.
    """

    # 1. Construct the Request Payload
    request_payload = AnthropicRequest(
        messages=[AnthropicMessage(content=ocr_text)]
    ).model_dump(exclude_none=True)

    # 2. Call the LLM API
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                LLM_API_URL,
                json=request_payload,
                headers={
                    "Authorization": LLM_API_KEY,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()

            data = response.json()
            print(data)
            # 3. Extract Content
            # Anthropic spec usually returns: {"content": [{"text": "..."}], ...}
            # Adjust this key path if your specific server wrapper differs
            raw_content = None
            content_blocks = data.get("content", [])

            for block in content_blocks:
                if block.get("type") == "text":
                    raw_content = block.get("text", "")
                    break

            if not raw_content:
                # Fallback: If no text block found, check if it's a simple string response
                # (handles non-standard responses)
                if isinstance(data.get("content"), str):
                    raw_content = data["content"]
                else:
                    raise ValueError("LLM response did not contain a valid 'text' content block")

            # 4. Clean and Parse JSON
            # Strip potential markdown code blocks if the model ignored instructions
            cleaned_json = raw_content.strip()
            if cleaned_json.startswith("```json"):
                cleaned_json = cleaned_json[7:]
            if cleaned_json.startswith("```"):
                cleaned_json = cleaned_json[3:]
            if cleaned_json.endswith("```"):
                cleaned_json = cleaned_json[:-3]

            parsed_data = json.loads(cleaned_json.strip())

            # 5. Validate with Pydantic
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
