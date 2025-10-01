from __future__ import annotations
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session as SASession

_engine = None
SessionLocal = None  # type: ignore
Base = declarative_base()

def init_engine_and_session(database_url: str):
    global _engine, SessionLocal
    _engine = create_engine(database_url, echo=False, future=True)
    # CLAVE: evitar DetachedInstanceError después del commit
    SessionLocal = sessionmaker(
        bind=_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )

def get_engine():
    if _engine is None:
        raise RuntimeError("DB engine no inicializado. Llama init_engine_and_session primero.")
    return _engine

@contextmanager
def get_session() -> Generator[SASession, None, None]:
    if SessionLocal is None:
        raise RuntimeError("SessionLocal no inicializada. Llama init_engine_and_session primero.")
    session: SASession = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
