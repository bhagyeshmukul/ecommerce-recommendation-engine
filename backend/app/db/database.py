"""Database connection configuration, shared by ORM sessions and migrations.

An engine is a connection pool, not one permanently open connection. Sessions
borrow a connection when needed and return it when get_db() closes the session.
"""

from __future__ import annotations
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:55432/ecommerce_recommendations",
)

# A stale pooled connection is checked before reuse. SQLite is useful for isolated
# unit tests; both native and Docker demos and migration checks use PostgreSQL.
options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    options["connect_args"] = {"check_same_thread": False}
else:
    options.update(pool_size=5, max_overflow=5, connect_args={"connect_timeout": 5})
engine = create_engine(DATABASE_URL, **options)


class Base(DeclarativeBase):
    """All ORM models share this metadata; Alembic owns schema changes."""
