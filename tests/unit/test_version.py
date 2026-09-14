"""The packaged version and the runtime version must not drift apart.

``_version.__version__`` feeds the ``User-Agent`` the SDK sends to the API, while
``pyproject.toml`` decides what PyPI serves. They are separate literals, so a
release that bumps one and forgets the other misreports itself on every request.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from netskope import __version__

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_runtime_version_matches_pyproject() -> None:
    metadata = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert metadata["project"]["version"] == __version__
