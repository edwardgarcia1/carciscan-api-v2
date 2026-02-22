from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.crud.carciscan import search_chemicals


def find_chemical_smiles(db: Session, search_terms: List[str]) -> List[Dict[str, Any]]:
    """
    Service layer to process search terms and retrieve fuzzy matches.

    Args:
        db: SQLAlchemy database session.
        search_terms: List of chemical names to search for.

    Returns:
        A list of dictionaries containing matched chemical data.
    """

    # 1. Input Validation / Pre-processing
    # Clean the input list: remove empty strings and strip whitespace
    clean_terms = [term.strip() for term in search_terms if term and term.strip()]

    if not clean_terms:
        return []

    # 2. Call the CRUD layer
    # The CRUD layer handles the raw SQL execution
    results = search_chemicals(db, clean_terms)

    # 3. Post-processing (Optional)
    # You can transform the data here if your API response needs a different format
    # For example, rounding the similarity score for cleaner JSON output
    formatted_results = []
    for item in results:
        formatted_results.append({
            "searched_term": item.get("searched_term"),
            "cid": item.get("cid"),
            "name": item.get("name"),
            "smiles": item.get("smiles"),
            # Round score to 2 decimal places for readability
            "score": round(float(item.get("score", 0.0)), 2)
        })

    return formatted_results