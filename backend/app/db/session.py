"""One short-lived SQLAlchemy session per request, closed on success or failure."""

from collections.abc import Generator
from sqlalchemy.orm import Session, sessionmaker
from app.db.database import engine

SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        try:
            yield session
        except Exception:
            # Failed commits leave a session unusable until its transaction rolls back.
            session.rollback()
            raise
