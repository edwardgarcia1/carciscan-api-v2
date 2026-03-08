import pickle
import pandas as pd
from typing import List, Dict, Optional, Any
from app.core.constants import IARC_EVIDENCE

# --- Global Model Caches ---
# We load models into memory when the application starts.
_carcinogenicity_model_data = None


def get_carcinogenicity_model_data():
    """Loads and caches the carcinogenicity model data."""
    global _carcinogenicity_model_data
    if _carcinogenicity_model_data is None:
        try:
            # Updated path to the new ordinal model
            model_path = "app/pickle/final_model.pkl"
            with open(model_path, 'rb') as f:
                _carcinogenicity_model_data = pickle.load(f)
            print("✅ Final XGBOrdinal model loaded successfully.")
        except FileNotFoundError:
            print(f"❌ Error: Carcinogenicity model file not found at {model_path}")
            _carcinogenicity_model_data = {"error": "Model file not found"}
    return _carcinogenicity_model_data

# --- Helper function for preprocessing ---
def _preprocess_and_align(descriptor_dict: Dict[str, float], feature_names: List[str]) -> Optional[pd.DataFrame]:
    if not descriptor_dict or not feature_names:
        return None

    input_series = pd.Series(descriptor_dict)
    input_series.fillna(input_series.mean(), inplace=True)
    max_clip_value = 1e15
    min_clip_value = -1e15
    input_series.clip(lower=min_clip_value, upper=max_clip_value, inplace=True)
    aligned_series = input_series.reindex(feature_names, fill_value=0)
    aligned_df = pd.DataFrame([aligned_series])
    return aligned_df


# --- UPDATED Carcinogenicity Prediction ---
def predict_carcinogenicity(descriptor_dict: Dict[str, float]) -> dict[str, dict[Any, Any] | Any] | None:
    model_data = get_carcinogenicity_model_data()
    if "error" in model_data:
        return None

    # Unpack artifact contents
    model = model_data['model']
    feature_names = model_data['feature_names']
    # inv_ordinal_mapping maps integers (0, 1, 2) to labels ('Group 3', 'Group 2', 'Group 1')
    inv_mapping = model_data['inv_ordinal_mapping']

    aligned_df = _preprocess_and_align(descriptor_dict, feature_names)
    if aligned_df is None:
        return None

    try:
        # 1. Predict returns integers (e.g., 0, 1, 2)
        predicted_int = model.predict(aligned_df)[0]

        # 2. Convert integer prediction to string label
        # We cast to int because some ordinal implementations might return floats (e.g., 1.0)
        predicted_label = inv_mapping.get(int(predicted_int), "Unknown")

        # 3. Handle Confidence Scores
        confidence_scores = {}

        # Check if model supports predict_proba (Standard XGBOrdinal usually does,
        # but we check safely).
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(aligned_df)[0]

            # We need to map probability columns (0, 1, 2) to labels.
            # We assume standard ordering where index 0 = Class 0, etc.
            # We sort keys to ensure alignment: [0, 1, 2] -> ['Group 3', 'Group 2', 'Group 1']
            sorted_class_indices = sorted(inv_mapping.keys())
            class_labels = [inv_mapping[i] for i in sorted_class_indices]

            confidence_scores = dict(zip(class_labels, probabilities))
        else:
            # Fallback if probabilities aren't available
            confidence_scores = {predicted_label: 1.0}

        evidence = IARC_EVIDENCE.get(predicted_label, "Evidence not available.")

        return {
            "prediction": predicted_label,
            "confidence_scores": confidence_scores,
            "evidence": evidence
        }
    except Exception as e:
        print(f"An error occurred during carcinogenicity prediction: {e}")
        return None
