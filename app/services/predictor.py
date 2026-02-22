import pickle
import pandas as pd
from typing import List, Dict, Optional, Any
from app.core.constants import IARC_EVIDENCE

# --- Global Model Caches ---
# We load models into memory when the application starts.
_carcinogenicity_model_data = None
_route_model_data = None


def get_carcinogenicity_model_data():
    """Loads and caches the carcinogenicity model data."""
    global _carcinogenicity_model_data
    if _carcinogenicity_model_data is None:
        try:
            model_path = "app/pickle/carcinogenicity.pkl"
            with open(model_path, 'rb') as f:
                _carcinogenicity_model_data = pickle.load(f)
            print("✅ Carcinogenicity model and encoder loaded successfully.")
        except FileNotFoundError:
            print(f"❌ Error: Carcinogenicity model file not found at {model_path}")
            _carcinogenicity_model_data = {"error": "Model file not found"}
    return _carcinogenicity_model_data


def get_route_model_data():
    """Loads and caches the route model data."""
    global _route_model_data
    if _route_model_data is None:
        try:
            model_path = "app/pickle/route.pkl"
            with open(model_path, 'rb') as f:
                _route_model_data = pickle.load(f)
            print("✅ Route model and binarizer loaded successfully.")
        except FileNotFoundError:
            print(f"❌ Error: Route model file not found at {model_path}")
            _route_model_data = {"error": "Model file not found"}
    return _route_model_data


# --- Helper function for preprocessing ---
def _preprocess_and_align(descriptor_dict: Dict[str, float], feature_names: List[str]) -> Optional[pd.DataFrame]:
    # ... (This function is perfect as designed above, let's copy it in)
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
    model = model_data['model']
    encoder = model_data['label_encoder']
    feature_names = model_data['feature_names']

    aligned_df = _preprocess_and_align(descriptor_dict, feature_names)
    if aligned_df is None:
        return None

    try:
        predicted_index = model.predict(aligned_df)[0]
        probabilities = model.predict_proba(aligned_df)[0]
        predicted_label = encoder.inverse_transform([predicted_index])[0]
        confidence_scores = dict(zip(encoder.classes_, probabilities))
        evidence = IARC_EVIDENCE.get(predicted_label, "Evidence not available.")
        return {
            "prediction": predicted_label,
            "confidence_scores": confidence_scores,
            "evidence": evidence
        }
    except Exception as e:
        print(f"An error occurred during carcinogenicity prediction: {e}")
        return None


# --- UPDATED Route Prediction ---
def predict_route(descriptor_dict: Dict[str, float]) -> Optional[Dict[str, float]]:
    model_data = get_route_model_data()
    if "error" in model_data:
        return None
    model = model_data['model']
    mlb = model_data['multi_label_binarizer']
    feature_names = model_data['feature_names']

    aligned_df = _preprocess_and_align(descriptor_dict, feature_names)
    if aligned_df is None:
        return None

    try:
        predicted_matrix = model.predict(aligned_df)
        proba_list = model.predict_proba(aligned_df)
        positive_probabilities = [p[0][1] for p in proba_list]
        predicted_routes = mlb.inverse_transform(predicted_matrix)[0]
        confidence_scores = dict(zip(mlb.classes_, positive_probabilities))
        return {"prediction": list(predicted_routes), "confidence_scores": confidence_scores}
    except Exception as e:
        print(f"An error occurred during route prediction: {e}")
        return None