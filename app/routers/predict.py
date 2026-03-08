import time
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.schemas.predict import PredictionResponse, OcrResult, PredictionDetails, IngredientDetails, PracticalAdvice
from app.db.session import get_db
from app.core.constants import CATEGORY_MAPPING
from app.services.analyzer import get_practical_advice

from app.services.llmvl import parse_image_with_vlm
from app.services.predictor import predict_carcinogenicity
from app.services.processor import ImageProcessor
from app.services.smiles import find_chemical_smiles
from app.services.descriptors import calculate_rdkit_descriptors

router = APIRouter()


# Schema for the /text endpoint
class TextPredictionRequest(BaseModel):
    ingredients: str
    category_id: Optional[int] = None


async def _run_prediction_pipeline(
        ingredient_list: List[str],
        category_id: Optional[int],
        db: Session,
        start_time: float
) -> PredictionResponse:
    """
    Shared logic for processing ingredients, running predictions, and generating advice.
    """
    # Handle cases where VLM might return a string "1" or None
    cat_id = category_id
    if isinstance(cat_id, str) and cat_id.isdigit():
        cat_id = int(cat_id)

    # Lookup category string for display purposes in the response
    category_str = CATEGORY_MAPPING.get(cat_id, "Unknown HUHS Substance")

    # Construct OCR result equivalent
    ocr_result = OcrResult(text=", ".join(ingredient_list), ingredients=ingredient_list)

    # 3. Searching
    search_res = find_chemical_smiles(db, ingredient_list)
    print("Searching:", round(time.time() - start_time, 2))

    # 4. Prediction
    final_ingredient_details = []
    for res in search_res:
        descriptors = calculate_rdkit_descriptors(res["smiles"])
        if not descriptors:
            final_ingredient_details.append(
                IngredientDetails(
                    name=res['searched_term'],
                    prediction_details=None,
                    matched_name=res['name'],
                    pubchem_url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{res['cid']}",
                    status="Could not calculate molecular descriptors"
                )
            )
            continue

        carc_pred_dict = predict_carcinogenicity(descriptors)
        prediction_details = None
        if carc_pred_dict:
            predicted_group = carc_pred_dict.get("prediction")
            raw_confidence = carc_pred_dict.get("confidence_scores", {}).get(predicted_group, 0)

            # raw_confidence is expected to be 0..1; convert to percent float (0..100)
            try:
                conf_val = float(raw_confidence)
                if conf_val <= 1.0:
                    conf_pct = conf_val * 100.0
                else:
                    conf_pct = conf_val
            except Exception:
                conf_pct = 0.0

            prediction_details = PredictionDetails(
                carcinogenicity_group=predicted_group,
                evidence=carc_pred_dict.get("evidence"),
                confidence=conf_pct,
            )
            status = "Success"
        else:
            status = "Prediction model failed"

        final_ingredient_details.append(
            IngredientDetails(
                name=res['searched_term'],
                prediction_details=prediction_details,
                matched_name=res['name'],
                pubchem_url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{res['cid']}",
                status=status
            )
        )
    print("Predictions:", round(time.time() - start_time, 2))

    # 5. Get practical advice
    # Pass the integer cat_id instead of the string
    practical_advice = get_practical_advice(final_ingredient_details, cat_id)

    # 6. Calculate processing time and return response
    processing_time = round(time.time() - start_time, 2)
    return PredictionResponse(
        success=True,
        message="Analysis complete.",
        ocr_result=ocr_result,
        ingredients=final_ingredient_details,
        category=category_str,
        processing_time=processing_time,
        practical_advice=PracticalAdvice(**practical_advice)
    )


@router.post("/image", response_model=PredictionResponse)
async def predict_from_image(
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    start_time = time.time()

    # 1. Read raw bytes
    try:
        raw_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading uploaded file: {e}")

    # 2. PREPROCESS IMAGE
    # This prevents the VLM from crashing on large PNGs or high-res photos
    try:
        processed_jpeg_bytes = ImageProcessor.resize_and_convert(
            raw_bytes,
            max_dim=1024,
            quality=85
        )
        print("Image Preprocessed:", round(time.time() - start_time, 2))
    except HTTPException as e:
        # Re-raise processing errors (e.g. corrupt file)
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image preprocessing failed: {str(e)}")

    # 3. VLM — Send processed JPEG bytes
    parsed_text = await parse_image_with_vlm(processed_jpeg_bytes)

    if not parsed_text:
        raise HTTPException(status_code=400, detail="Could not extract ingredients from the image.")

    print("VLM parsing:", round(time.time() - start_time, 2))
    print(parsed_text.category_name)

    return await _run_prediction_pipeline(
        ingredient_list=parsed_text.ingredients,
        category_id=parsed_text.category_id,
        db=db,
        start_time=start_time
    )


@router.post("/text", response_model=PredictionResponse)
async def predict_from_text(
        request: TextPredictionRequest,
        db: Session = Depends(get_db)
):
    start_time = time.time()

    # Parse the comma-separated string into a list
    # split(',') separates by comma, strip() removes leading/trailing whitespace from each item
    ingredient_list = [item.strip() for item in request.ingredients.split(',') if item.strip()]

    if not ingredient_list:
        raise HTTPException(status_code=400, detail="Ingredients list cannot be empty.")

    return await _run_prediction_pipeline(
        ingredient_list=ingredient_list,
        category_id=request.category_id,
        db=db,
        start_time=start_time
    )