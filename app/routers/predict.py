import time
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlalchemy.orm import Session

from app.schemas.predict import PredictionResponse, OcrResult, PredictionDetails, IngredientDetails, PracticalAdvice
from app.db.session import get_db
from app.core.constants import CATEGORY_MAPPING
from app.services.analyzer import get_practical_advice

from app.services.ocr import extract_text_from_image
from app.services.parser import parse_ocr_text
from app.services.predictor import predict_carcinogenicity, predict_route
from app.services.smiles import find_chemical_smiles
from app.services.descriptors import calculate_rdkit_descriptors

router = APIRouter()

@router.post("/image", response_model=PredictionResponse)
async def predict_from_image(
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    start_time = time.time()

    # 1. OCR
    try:
        image_bytes = await file.read()
        raw_text = extract_text_from_image(image_bytes)
        if not raw_text:
            raise HTTPException(status_code=400, detail="Could not extract text from the image.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during image processing: {e}")

    print("OCR:", round(time.time() - start_time, 2))
    print(raw_text)

    # 2. Parsing
    parsed_text = await parse_ocr_text(raw_text)
    if not parsed_text:
        raise HTTPException(status_code=400, detail="Could not parse any ingredients from the extracted text.")

    print("Parsing:", round(time.time() - start_time, 2))

    ingredient_list = parsed_text.ingredients

    category_str = CATEGORY_MAPPING.get(parsed_text.category_id, "Unknown HUHS Substance")
    ocr_result = OcrResult(text=raw_text, ingredients=ingredient_list)

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
        route_pred_dict = predict_route(descriptors)
        prediction_details = None
        if carc_pred_dict and route_pred_dict:
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
                route_of_exposure=route_pred_dict.get("prediction", [])
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
    practical_advice = get_practical_advice(final_ingredient_details, category_str)


    # 6. Calculate processing time and return response
    processing_time = round(time.time() - start_time, 2)
    return PredictionResponse(
        success=True,
        message="Analysis complete.",
        ocr_result=ocr_result,
        ingredients=final_ingredient_details,
        processing_time=processing_time,
        practical_advice=PracticalAdvice(**practical_advice)
    )