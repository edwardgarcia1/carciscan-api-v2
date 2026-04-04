from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# create the engine with optimized connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # good practice to check connections
    pool_size=20,  # base number of connections in the pool
    max_overflow=30,  # additional connections allowed under load
    pool_timeout=30,  # seconds to wait for a connection before timeout
    pool_recycle=1800,  # recycle connections after 30 minutes
)

# create a SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency function that yields a db session.
    Ensures the session is closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()