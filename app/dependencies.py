from typing import Generator
from db.session import SessionLocal

def get_db() -> Generator:
    """
    FastAPI dependency that provides a database session.
    """
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()