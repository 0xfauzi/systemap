"""Find the source module of each Python import for the Python adapter.

The adapter writes the local imports without a target module into the language-neutral
`completeness` record.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator

from systemap import python_tree


def relative_source(module: str, is_package: bool, level: int, name: str) -> str | None:
    """Give the dotted source module of a Python relative import.

    The start package is the package of the module, or the module itself for a
    package `__init__`. Each level after the first moves up one package. An import that moves
    above the top package has no source module, and the function gives None.
    """
    anchor = module.split(".")
    if not is_package:
        anchor = anchor[:-1]
    up = level - 1
    if up >= len(anchor):
        return None
    if up:
        anchor = anchor[:-up]
    return ".".join([*anchor, *name.split(".")] if name else anchor)


def _local(name: str, prefixes: Iterable[str]) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)


def _python_targets(
    node: ast.AST, module: str, is_package: bool
) -> Iterator[tuple[str, str | None]]:
    """Give each import of one statement as source text and its dotted source module."""
    if isinstance(node, ast.Import):
        yield from ((alias.name, alias.name) for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        written = "." * node.level + (node.module or "")
        if not node.level:
            yield written, node.module
        elif module:
            yield written, relative_source(module, is_package, node.level, node.module or "")


def python_unresolved(
    raw: str, prefixes: set[str], known: set[str], module: str, is_package: bool
) -> list[str]:
    """List the local Python imports that have no module in the facts.

    A local import names a package root, or it is a relative import. A directory
    without `__init__.py` is a namespace package, and a module below it resolves it.
    Third-party and standard-library imports are not in the list, because the
    extractor does not examine the installed packages. Extraction does not use this
    function for source that does not parse, because that import list is not known.
    """
    tree = python_tree.tree(raw)
    if tree is None:
        return []
    namespaces = {
        ".".join(name.split(".")[:end]) for name in known for end in range(1, len(name.split(".")))
    }
    out: set[str] = set()
    for node in python_tree.walk(tree):
        for written, source in _python_targets(node, module, is_package):
            if source is None:
                out.add(written)
            elif _local(source, prefixes) and source not in known and source not in namespaces:
                out.add(written)
    return sorted(out)
