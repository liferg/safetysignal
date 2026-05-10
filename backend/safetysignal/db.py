from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from safetysignal.config import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
