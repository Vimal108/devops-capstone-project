"""Configuration contract tests for PostgreSQL defaults and environment overrides."""
import importlib
import os
from unittest import TestCase
from unittest.mock import patch
from service import config


class TestConfiguration(TestCase):
    """Verify deployment configuration without connecting to a database."""

    def tearDown(self):
        importlib.reload(config)

    def test_default_database(self):
        """Use the lab PostgreSQL database when no override is supplied"""
        with patch.dict(os.environ, {}, clear=True):
            importlib.reload(config)
            self.assertEqual(
                config.SQLALCHEMY_DATABASE_URI,
                "postgresql://postgres:postgres@localhost:5432/postgres",
            )

    def test_database_override(self):
        """An explicit database URI takes precedence over individual settings"""
        with patch.dict(os.environ, {"DATABASE_URI": "sqlite:///:memory:"}):
            importlib.reload(config)
            self.assertEqual(config.SQLALCHEMY_DATABASE_URI, "sqlite:///:memory:")
