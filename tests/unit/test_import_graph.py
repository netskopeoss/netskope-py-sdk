"""The package imports acyclically, at module level, with nothing deferred.

Every resource module pairs with a private decoder holding its ``with_response``
accessors, and the decoder needs the resource's paths and payload builders. Left
importing each other directly that is a cycle, and the cycle was previously kept
alive by imports hidden inside method bodies plus a matching ``TYPE_CHECKING``
block. Both hide the dependency from every static tool the repo runs, and a
function-local import is a latent import-order bug.

The shared pieces now live in a third module, ``resources/_<area>_query.py``,
that both sides import — the shape ``_alert_query.py`` used before the rest of
the package followed it. These tests keep it that way.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "netskope"


def _modules() -> dict[str, pathlib.Path]:
    out: dict[str, pathlib.Path] = {}
    for path in _SRC.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        parts = path.relative_to(_SRC.parent).with_suffix("").parts
        name = ".".join(parts)
        out[name.removesuffix(".__init__")] = path
    return out


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module.startswith("netskope"):
                found.add(node.module)
                # `from netskope.resources import x` binds a module, not a name.
                found.update(
                    f"{node.module}.{alias.name}"
                    for alias in node.names
                    if f"{node.module}.{alias.name}" in _MODULES
                )
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("netskope"))
    return found


_MODULES = _modules()


def _cycles() -> list[list[str]]:
    graph = {name: {i for i in _imports(path) if i in _MODULES} for name, path in _MODULES.items()}
    found: list[list[str]] = []
    colour: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> None:
        colour[node] = 1
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            if colour.get(nxt, 0) == 0:
                visit(nxt)
            elif colour.get(nxt) == 1:
                found.append([*stack[stack.index(nxt) :], nxt])
        stack.pop()
        colour[node] = 2

    for node in sorted(graph):
        if colour.get(node, 0) == 0:
            visit(node)
    return found


def test_the_package_has_no_import_cycles() -> None:
    cycles = _cycles()
    rendered = "\n".join(" -> ".join(c) for c in cycles)
    assert not cycles, f"{len(cycles)} import cycle(s):\n{rendered}"


@pytest.mark.parametrize("name,path", sorted(_MODULES.items()))
def test_no_resource_import_hides_inside_a_function(name: str, path: pathlib.Path) -> None:
    """A deferred import is how the cycles used to survive; none should remain.

    `netskope.exceptions` and the models are exempt: a local import of those is
    a readability choice, not a cycle break.
    """
    tree = ast.parse(path.read_text())
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.ImportFrom)
                and sub.module
                and sub.module.startswith("netskope.resources.")
            ):
                offenders.append(f"{path.name}:{sub.lineno} imports {sub.module}")
    assert not offenders, "deferred resource imports:\n" + "\n".join(offenders)
