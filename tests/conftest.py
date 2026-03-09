"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app


@pytest.fixture(scope="session")
def client():
    """FastAPI test client — does not require running services."""
    return TestClient(app, raise_server_exceptions=False)
