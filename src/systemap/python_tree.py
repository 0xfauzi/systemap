"""The Python tree cache gives one syntax tree for each Python module text.

One extraction reads each module text in many steps: the public surface, the syntax
digest, the imports, the call sites, the empty marker, and the entry points. Without the
cache, each step parses the same text again. A large module then takes about ten times
the time and memory of one parse. Each step also reads all the nodes of the tree. `walk`
keeps the node list of a cached tree, so that a step does not make the list again.

The cache keeps the trees of the most recent texts. The total length of these texts is
not more than `KEPT`. When a new text goes above this limit, the cache removes the
oldest trees. A step then parses an old text again. The result is the same.

A caller must not change a tree from the cache, because other steps read the same tree.
"""

from __future__ import annotations

import ast
import threading
from collections import OrderedDict
from collections.abc import Iterable

# The maximum total length of the cached texts, in characters. This value is a guard for
# memory, not a measurement of systemap capacity. A tree uses about 30 times the memory of
# its text: the trees of the systemap source (1.9 MB) used 58 MB. A repository with less
# source text than this value parses each module one time in each extraction.
KEPT = 16 * 1024 * 1024

_Result = ast.Module | SyntaxError | ValueError
_trees: OrderedDict[str, _Result] = OrderedDict()
_size = [0]
# Each cached tree by its identity, with its node list in the order of `ast.walk`. The list
# is empty until a step asks for it.
_nodes: dict[int, tuple[ast.Module, list[ast.AST]]] = {}
_lock = threading.Lock()


def parse(raw: str) -> ast.Module:
    """Give the syntax tree of a Python module text, as `ast.parse(raw)` gives it.

    Text that does not parse gives the SyntaxError or the ValueError of `ast.parse`.
    """
    with _lock:
        found = _trees.get(raw)
        if found is not None:
            _trees.move_to_end(raw)
    if found is None:
        found = _parse(raw)
        _keep(raw, found)
    if isinstance(found, ast.Module):
        return found
    # A new traceback each time: the cached error must not keep the frames of old calls.
    raise found.with_traceback(None)


def tree(raw: str) -> ast.Module | None:
    """Give the syntax tree of a Python module text, or None if the text does not parse."""
    try:
        return parse(raw)
    except (SyntaxError, ValueError):
        return None


def walk(node: ast.AST) -> Iterable[ast.AST]:
    """Give the nodes of a tree in the order of `ast.walk`.

    For a tree from the cache, the function makes the node list one time and keeps it with
    the tree. For a different tree, the function gives `ast.walk(node)`.
    """
    with _lock:
        owner, found = _nodes.get(id(node), (None, []))
        # The list of a tree always has the tree itself. Thus an empty list is a new list.
        if owner is node and not found:
            found.extend(ast.walk(node))
    return found if owner is node else ast.walk(node)


def clear() -> None:
    """Remove all trees from the cache."""
    with _lock:
        _trees.clear()
        _nodes.clear()
        _size[0] = 0


def _parse(raw: str) -> _Result:
    try:
        return ast.parse(raw)
    except (SyntaxError, ValueError) as exc:
        return exc


def _keep(raw: str, found: _Result) -> None:
    if len(raw) > KEPT:
        return
    with _lock:
        if raw in _trees:
            return
        _trees[raw] = found
        _size[0] += len(raw)
        if isinstance(found, ast.Module):
            _nodes[id(found)] = (found, [])
        while _size[0] > KEPT:
            old, removed = _trees.popitem(last=False)
            _size[0] -= len(old)
            _nodes.pop(id(removed), None)
