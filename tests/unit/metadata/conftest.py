"""SQLite in-memory engine for repository tests.

Production uses PostgreSQL (ADR-009); SQLite here is a fast, dependency-free
stand-in that exercises the same SQLAlchemy Core/ORM calls the repositories
make, not a claim that SQLite is used in production.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.metadata.orm import Base


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        yield s
