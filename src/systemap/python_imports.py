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


def namespace_packages(known: Iterable[str]) -> frozenset[str]:
    """Give each dotted package prefix of the known modules.

    For the module `a.b.c`, the prefixes are `a` and `a.b`. A directory without
    `__init__.py` is a namespace package, and a module below it resolves it. The time
    of the function increases linearly with the length of the names. Thus an extraction
    calculates the set one time. It gives the set to `python_unresolved` for each
    module.
    """
    out: set[str] = set()
    for name in known:
        end = name.rfind(".")
        while end >= 0:
            out.add(name[:end])
            end = name.rfind(".", 0, end)
    return frozenset(out)


class NamespaceCache:
    """Keep the namespace packages of one module set for one extraction.

    The cache calculates the set again only for a different module set object. Thus
    the caller must not change the module set during the extraction.
    """

    def __init__(self) -> None:
        self._known: set[str] | None = None
        self._namespaces: frozenset[str] = frozenset()

    def of(self, known: set[str]) -> frozenset[str]:
        """Give `namespace_packages(known)`."""
        if known is not self._known:
            self._known = known
            self._namespaces = namespace_packages(known)
        return self._namespaces


def python_unresolved(
    raw: str,
    prefixes: set[str],
    known: set[str],
    module: str,
    is_package: bool,
    namespaces: frozenset[str] | None = None,
) -> list[str]:
    """List the local Python imports that have no module in the facts.

    A local import names a package root, or it is a relative import. A directory
    without `__init__.py` is a namespace package, and a module below it resolves it.
    `namespaces` is `namespace_packages(known)`. If it is None, the function calculates
    it. Third-party and standard-library imports are not in the list, because the
    extractor does not examine the installed packages. Extraction does not use this
    function for source that does not parse, because that import list is not known.
    """
    tree = python_tree.tree(raw)
    if tree is None:
        return []
    if namespaces is None:
        namespaces = namespace_packages(known)
    out: set[str] = set()
    for node in python_tree.walk(tree):
        for written, source in _python_targets(node, module, is_package):
            if source is None:
                out.add(written)
            elif _local(source, prefixes) and source not in known and source not in namespaces:
                out.add(written)
    return sorted(out)
