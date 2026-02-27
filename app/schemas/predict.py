from pydantic import BaseModel, Field
from typing import List, Optional

# --- Schemas for Individual Ingredients ---
class PredictionDetails(BaseModel):
    carcinogenicity_group: Optional[str]
    evidence: Optional[str]
    confidence: Optional[float] = Field(..., ge=0, le=100, description="Confidence percentage from 0 to 100.")
    route_of_exposure: List[str]

class IngredientDetails(BaseModel):
    name: str
    prediction_details: Optional[PredictionDetails]
    matched_name: Optional[str]
    pubchem_url: Optional[str]
    status: Optional[str] = Field(..., description="Status of processing, e.g., 'Success', 'Synonym not found'")

# --- Schemas for the Overall Response ---
class OcrResult(BaseModel):
    text: str
    ingredients: List[str]

# PracticalAdvice object: structured practical advice instead of a flat list
class PracticalAdvice(BaseModel):
    highest_group: Optional[str]
    confidence: float = Field(..., ge=0, le=100, description="Confidence percentage for the highest grouping")
    hazard_level: str
    iarc_definition: Optional[str]
    route_advice: List[str]
    category_advice: str = Field(..., description="Category-specific safety advice")

class PredictionResponse(BaseModel):
    success: bool
    message: str
    ocr_result: Optional[OcrResult]
    ingredients: List[IngredientDetails]
    category: str
    processing_time: float
    practical_advice: PracticalAdvice