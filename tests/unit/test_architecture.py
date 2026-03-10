"""
Architecture boundary test — ensures the domain core never imports framework code.

The hexagonal architecture golden rule: domain/ must be pure Python.
No imports from sqlalchemy, fastapi, httpx, celery, redis, neo4j, alembic, etc.
This test catches drift early — a single accidentally-added framework import fails fast.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

DOMAIN_ROOT = Path(__file__).parent.parent.parent / "domain"

# Any import of these top-level packages from within domain/ is a violation
FORBIDDEN = {
    "sqlalchemy",
    "fastapi",
    "httpx",
    "celery",
    "redis",
    "neo4j",
    "alembic",
    "starlette",
    "strawberry",
    "pydantic_settings",
    "uvicorn",
}


def _get_imports(filepath: Path) -> set[str]:
    """Return the set of top-level module names imported by a file."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return set()

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:  # absolute import only
                names.add(node.module.split(".")[0])
    return names


def _domain_files() -> list[Path]:
    return [p for p in DOMAIN_ROOT.rglob("*.py") if p.name != "__init__.py"]


@pytest.mark.parametrize("filepath", _domain_files(), ids=lambda p: str(p.relative_to(DOMAIN_ROOT)))
def test_domain_has_no_framework_imports(filepath: Path) -> None:
    violations = _get_imports(filepath) & FORBIDDEN
    assert not violations, (
        f"domain/{filepath.relative_to(DOMAIN_ROOT)} imports framework code: {violations}\n"
        "The domain core must be pure Python — no framework imports ever."
    )
