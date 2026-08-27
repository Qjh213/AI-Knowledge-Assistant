from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.database.session import SessionLocal


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session