"""The four workspace packages install and import (docs/ARCHITECTURE.md section 2)."""

from __future__ import annotations

import importlib
import importlib.metadata

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("module", "distribution"),
    [
        ("munim_core", "munim-core"),
        ("munim_ai", "munim-ai"),
        ("munim_web", "munim-web"),
        ("munim_mcp", "munim-mcp"),
    ],
)
def test_package_imports_and_matches_its_distribution_version(
    module: str, distribution: str
) -> None:
    package = importlib.import_module(module)
    assert package.__version__ == importlib.metadata.version(distribution)
