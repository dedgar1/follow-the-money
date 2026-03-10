"""Unit tests for infrastructure/database.py session management."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.database import get_session


def _mock_session_local():
    """Returns a mock that behaves like SessionLocal() — returns a mock Session."""
    mock_session = MagicMock()
    mock_cls = MagicMock(return_value=mock_session)
    return mock_cls, mock_session


def test_get_session_commits_on_success():
    mock_cls, mock_session = _mock_session_local()
    with patch("infrastructure.database.SessionLocal", mock_cls):
        with get_session() as db:
            assert db is mock_session

    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_not_called()
    mock_session.close.assert_called_once()


def test_get_session_rolls_back_on_exception():
    mock_cls, mock_session = _mock_session_local()
    with patch("infrastructure.database.SessionLocal", mock_cls):
        with pytest.raises(ValueError, match="boom"):
            with get_session():
                raise ValueError("boom")

    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()
    mock_session.close.assert_called_once()


def test_get_session_always_closes_even_on_exception():
    """close() must be called regardless — no connection leak."""
    mock_cls, mock_session = _mock_session_local()
    with patch("infrastructure.database.SessionLocal", mock_cls):
        with pytest.raises(RuntimeError):
            with get_session():
                raise RuntimeError("unexpected")

    mock_session.close.assert_called_once()
