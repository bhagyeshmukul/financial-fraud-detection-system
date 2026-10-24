"""
Give each HTTP request a database session and close it afterward. Exceptions roll back
unfinished writes so a failed request cannot leave partial results.
"""

from sqlalchemy.orm import sessionmaker
from app.db.database import engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Yield one request-scoped session, roll back on errors, and close it after the request finishes."""
    with SessionLocal() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise
