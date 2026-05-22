"""SQLAlchemy session factory and request-scoped DB dependency."""

from sqlalchemy.orm import sessionmaker

from app.db.database import engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Yield a database session and always close it after request completion."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
