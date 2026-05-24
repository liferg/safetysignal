"""Shared FastAPI dependencies.

Centralizes things like the DB session so endpoint code doesn't have
to manage session lifecycle by hand.
"""
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from safetysignal.db import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a DB session, closing it on exit (success or failure)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# A reusable type alias so endpoints can write `db: DbSession` instead of
# the wordy `db: Annotated[Session, Depends(get_db)]`.
DbSession = Annotated[Session, Depends(get_db)]
