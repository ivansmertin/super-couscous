from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base


def create_engine_and_session(sqlite_path: str) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(
        f"sqlite:///{sqlite_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, session_factory


def create_tables(engine: Engine) -> None:
    Base.metadata.create_all(engine)
