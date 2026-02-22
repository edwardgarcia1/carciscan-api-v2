from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text


def search_chemicals(db: Session, search_terms: List[str]) -> List[Dict[str, Any]]:
    """
    Performs fuzzy search for a list of terms against the compounds table.
    """

    # 1. Set the similarity threshold for this transaction
    # We use text() to execute raw SQL
    db.execute(text("SET pg_trgm.similarity_threshold = 0.5"))

    # 2. Define the main query
    # We use :terms as the bind parameter for the list
    query_str = text("""
        WITH search_terms(term) AS (
            SELECT unnest(:terms)
        )
        SELECT
            s.term AS searched_term,
            c.cid,
            c.name,
            c.smiles,
            similarity(c.name, s.term) AS score
        FROM search_terms s
        CROSS JOIN LATERAL (
            SELECT cid, name, smiles
            FROM compounds
            WHERE name % s.term
            ORDER BY name <-> s.term
            LIMIT 1
        ) c;
    """)

    # 3. Execute the query
    # SQLAlchemy automatically converts the Python list to a Postgres array for :terms
    result = db.execute(query_str, {"terms": search_terms})

    # 4. Format the results
    # result.mappings() gives us access to columns by name
    return [dict(row._mapping) for row in result]