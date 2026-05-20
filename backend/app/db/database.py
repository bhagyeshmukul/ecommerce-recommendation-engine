from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/ecommerce_recommendations",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Base = declarative_base()
