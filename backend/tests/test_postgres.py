"""Opt-in real PostgreSQL migration test; isolated schema is removed afterwards."""

import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL for PostgreSQL integration",
)


def test_migrations_upgrade_legacy_schema_and_preserve_data():
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    schema = f"test_{uuid.uuid4().hex}"
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        with engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{schema}"'))
            connection.commit()
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "001_create_recommendation_tables")
            connection.execute(
                text(
                    "INSERT INTO products (product_id, product_name, category) VALUES ('OLD', 'Preserved item', 'Home')"
                )
            )
            connection.commit()
            command.upgrade(config, "head")
            assert (
                connection.scalar(
                    text("SELECT product_name FROM products WHERE product_id = 'OLD'")
                )
                == "Preserved item"
            )
            assert "dataset_snapshot" in inspect(connection).get_table_names(
                schema=schema
            )
            assert {
                column["name"]
                for column in inspect(connection).get_columns(
                    "user_interactions", schema=schema
                )
            } >= {"invoice_id", "quantity", "unit_price"}
            # Alembic is safe to repeat on a current database.
            command.upgrade(config, "head")
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
