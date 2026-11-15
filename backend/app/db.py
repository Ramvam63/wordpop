"""Database engine and session handling (PostgreSQL in production, SQLite for dev/tests)."""

from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # pool_pre_ping handles serverless Postgres (Neon) closing idle connections
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(bind=None) -> None:
    from . import models  # noqa: F401  (register models)

    bind = bind or engine
    Base.metadata.create_all(bind=bind)
    _add_missing_columns(bind)


def _add_missing_columns(bind) -> None:
    """create_all() makes new tables but never changes existing ones.
    This adds any new nullable columns to tables that already exist, so an
    existing database keeps working after an upgrade. (Alembic is on the roadmap.)"""
    inspector = inspect(bind)
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing or not column.nullable:
                    continue
                col_type = column.type.compile(dialect=bind.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {col_type}'))
        _widen_text_columns(conn, inspector)


def _widen_text_columns(conn, inspector) -> None:
    """Columns that became TEXT in the models (e.g. words.text, to allow sentences and poems)
    are widened in existing PostgreSQL databases. SQLite does not enforce lengths."""
    if conn.dialect.name != "postgresql":
        return
    from sqlalchemy import Text

    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        db_types = {c["name"]: c["type"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            current = db_types.get(column.name)
            if isinstance(column.type, Text) and current is not None and getattr(current, "length", None):
                conn.execute(text(f'ALTER TABLE {table.name} ALTER COLUMN "{column.name}" TYPE TEXT'))
