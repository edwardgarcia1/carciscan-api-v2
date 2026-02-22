from typing import List
from app.schemas.predict import IngredientDetails  # Import for type hinting
from app.core.constants import ROUTE_ADVICE, IARC_EVIDENCE


def _group_priority(group_label: str) -> int:
    """
    Map a group label to a priority integer: higher = worse.
    Recognizes digits '1','2','3' anywhere in the label (e.g. 'Group 2A').
    Unknown groups get 0.
    """
    if not group_label:
        return 0
    if "1" in group_label:
        return 3
    if "2" in group_label:
        return 2
    if "3" in group_label:
        return 1
    return 0


def _compute_hazard_level(group_label: str, confidence_pct: float) -> str:
    """
    Simple hazard matrix combining group and confidence.
    Rules used:
      - Group 1: >=70% -> High, 40-70 -> Moderate, <40 -> Low
      - Group 2: >=70% -> Moderate, 40-70 -> Low, <40 -> Very Low
      - Group 3: >=70% -> Low, else -> Very Low
      - Unknown group: Very Low
    """
    if not group_label:
        return "Very Low"

    if "1" in group_label:
        if confidence_pct >= 70:
            return "High"
        if confidence_pct >= 40:
            return "Moderate"
        return "Low"

    if "2" in group_label:
        if confidence_pct >= 70:
            return "Moderate"
        if confidence_pct >= 40:
            return "Low"
        return "Very Low"

    if "3" in group_label:
        if confidence_pct >= 70:
            return "Low"
        return "Very Low"

    return "Very Low"


def _find_iarc_definition(group_label: str) -> str:
    """
    Return the IARC definition text for a given group_label using IARC_EVIDENCE.
    Tries exact match first, then falls back to matching by digit presence (1/2/3).
    """
    if not group_label:
        return None

    # exact match
    if group_label in IARC_EVIDENCE:
        return IARC_EVIDENCE[group_label]

    # fallback: look for same digit in keys
    for digit in ("1", "2", "3"):
        if digit in group_label:
            for k, v in IARC_EVIDENCE.items():
                if digit in k:
                    return v

    return None


def get_practical_advice(ingredient_results: List[IngredientDetails], category: str) -> dict:
    """
    Returns a structured practical advice dict:
      {
        highest_group: Optional[str],
        confidence: float,  # percent 0..100
        hazard_level: str,
        iarc_definition: Optional[str],  # only for highest_group
        route_advice: List[str],
        category_advice: str
      }
    """
    # Collect group -> list of confidences
    group_conf_pairs = []
    all_routes = []

    for ing in ingredient_results:
        if ing.prediction_details:
            grp = getattr(ing.prediction_details, "carcinogenicity_group", None)
            conf_raw = getattr(ing.prediction_details, "confidence", None)
            # confidence may be stored as a string percent like "75.00" or a float 0..100
            conf = 0.0
            if conf_raw is not None:
                try:
                    conf = float(conf_raw)
                except Exception:
                    try:
                        # If it's like 0.75 (float) convert to percent
                        conf = float(conf_raw) * 100.0
                    except Exception:
                        conf = 0.0

            if grp:
                group_conf_pairs.append((grp, conf))

            # collect routes while preserving order
            routes = getattr(ing.prediction_details, "route_of_exposure", []) or []
            for r in routes:
                if r not in all_routes:
                    all_routes.append(r)

    # Determine highest (worst) group by priority, break ties by max confidence
    highest_group = None
    highest_priority = 0
    highest_confidence_for_group = 0.0

    for grp, conf in group_conf_pairs:
        pr = _group_priority(grp)
        if pr > highest_priority:
            highest_priority = pr
            highest_group = grp
            highest_confidence_for_group = conf
        elif pr == highest_priority and pr != 0:
            if conf > highest_confidence_for_group:
                highest_group = grp
                highest_confidence_for_group = conf

    if not highest_group:
        highest_group_val = None
        confidence_val = 0.0
        hazard_level = "Very Low"
        iarc_def = None
    else:
        # compute max confidence among entries that match the chosen highest group (or same digit)
        max_conf = 0.0
        for grp, conf in group_conf_pairs:
            if grp and highest_group and (grp == highest_group or (
                    ("1" in grp and "1" in highest_group) or ("2" in grp and "2" in highest_group) or (
                    "3" in grp and "3" in highest_group))):
                if conf > max_conf:
                    max_conf = conf
        highest_group_val = highest_group
        confidence_val = round(max_conf, 2)
        hazard_level = _compute_hazard_level(highest_group, max_conf)
        iarc_def = _find_iarc_definition(highest_group)

    # Existing route-based practical advice (preserve ordering and uniqueness)
    route_advice_list = [ROUTE_ADVICE.get(route, "") for route in all_routes if ROUTE_ADVICE.get(route)]
    # Ensure unique and stable order: preserve first appearance
    seen = set()
    unique_route_advice = []
    for advice in route_advice_list:
        if advice not in seen:
            seen.add(advice)
            unique_route_advice.append(advice)

    # Generate category-specific advice
    category_advice = generate_category_advice(category, hazard_level)

    return {
        "highest_group": highest_group_val,
        "confidence": confidence_val,
        "hazard_level": hazard_level,
        "iarc_definition": iarc_def,
        "route_advice": unique_route_advice,
        "category_advice": category_advice
    }


# Helper function for category-specific safety advice
def generate_category_advice(category: str, hazard_level: str) -> str:
    """
    Generate category-specific safety advice based on product form and hazard level.
    """
    # Base advice for each category
    base_advice = {
        "Aerosol / Spray (Disinfectant, Freshener, Cleaner)":
            "Use in well-ventilated areas. Avoid direct inhalation. Do not spray near open flames.",
        "Liquid Solution (Bleach, Detergent, Cleaner, Chemical)":
            "Wear gloves and eye protection. Avoid skin contact. Store in original container.",
        "Powder / Granular (Detergent, Cleanser, Chemical)":
            "Avoid creating dust. Use in well-ventilated areas. Keep away from children.",
        "Cream / Gel / Paste (Polish, Cleaner, Compound)":
            "Wear gloves during application. Avoid contact with eyes. Store in cool, dry place.",
        "Solid / Tablet / Block (Bleach solid, chemical block)":
            "Handle with dry hands. Dissolve completely before use. Store away from moisture.",
        "Vapor / Strong Fumes (Solvent, Paint, Thinner, Chemical)":
            "Use only outdoors or in professionally ventilated areas. Wear respirator.",
        "Unknown HUHS Substance":
            "Handle with caution. Follow given instructions, if available."
    }

    # Hazard level modifiers
    hazard_modifiers = {
        "High": "EXTREME CAUTION REQUIRED. ",
        "Moderate": "Increased caution recommended. ",
        "Low": "Standard precautions sufficient. ",
        "Very Low": "Minimal precautions needed. "
    }

    # Get base advice for category, default to Mixed/Unknown if not found
    advice = base_advice.get(category, base_advice["Unknown HUHS Substance"])

    # Add hazard level warning prefix
    return hazard_modifiers.get(hazard_level, "") + advice
