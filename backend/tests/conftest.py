"""Pytest fixtures for SafetySignal backend tests.

Provides isolation from dev/prod data via a dedicated test database
(`safetysignal_test`) created and dropped per test session, with each
test wrapped in a transaction that rolls back on completion.
"""
import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from safetysignal import models  # noqa: F401 -- registers models with Base.metadata
from safetysignal.db import Base
from safetysignal.deps import get_db
from safetysignal.main import app

TEST_DB_NAME = "safetysignal_test"


def _swap_db_name(url: str, new_name: str) -> str:
    """Replace the database name segment in a SQLAlchemy URL."""
    base, _ = url.rsplit("/", 1)
    return f"{base}/{new_name}"


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    """Create the test database, apply the schema, yield an engine, drop on teardown."""
    main_url = os.environ.get("DATABASE_URL")
    if not main_url:
        raise RuntimeError("DATABASE_URL not set; can't initialize test database")

    test_url = _swap_db_name(main_url, TEST_DB_NAME)

    # Connect to the main DB to issue CREATE/DROP DATABASE statements,
    # which can't run against the DB you're connected to.
    admin = create_engine(main_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    admin.dispose()

    engine = create_engine(test_url)
    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()

    admin = create_engine(main_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    admin.dispose()


@pytest.fixture
def db(test_engine: Engine) -> Generator[Session, None, None]:
    """Yield a Session in a transaction that rolls back at end of test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """Yield a FastAPI TestClient wired to use the test DB session.

    Overrides the `get_db` dependency so endpoint code uses our rollback-
    bound test session instead of opening real connections to the prod DB.
    """

    def override_get_db() -> Generator[Session, None, None]:
        # Don't close the session here — the `db` fixture owns its lifecycle.
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
