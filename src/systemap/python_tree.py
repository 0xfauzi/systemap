"""The Python tree cache gives one syntax tree for each Python module text.

One extraction reads each module text in many steps: the public surface, the syntax
digest, the imports, the call sites, the empty marker, and the entry points. Without the
cache, each step parses the same text again. A large module then takes about ten times
the time of one parse. Each step also reads all the nodes of the tree. Thus the cache
keeps the node list of each tree, and `walk` gives this list.

The cache keeps the trees of the most recent texts. The total number of nodes in these
trees is not more than `KEPT`. When a new tree goes above this limit, the cache removes
the oldest trees. A step then parses an old text again. The result is the same.

One tree can have more nodes than `KEPT`. The cache keeps this tree only until the next
parse of a different text. Thus two large trees are not in memory at the same time.

A text with too many syntax levels gives `TooDeep`. `ast.parse` then gives RecursionError
or MemoryError. A later step can also give RecursionError on a tree that parsed, for
example `ast.dump`. That step calls `refuse`. After that call, each step gets `TooDeep`
for the text, and does not read the tree again.

The extraction calls `clear` when it is complete. Thus the cache does not keep trees
between two extractions, for example in the live map.

A caller must not change a tree or a node list from the cache, because other steps read
the same objects.
"""

from __future__ import annotations

import ast
import hashlib
import threading
from collections import OrderedDict
from collections.abc import Iterable

from systemap.unknown_causes import DEPTH_ERRORS, DEPTH_REASON

# The maximum total number of nodes in the cached trees. This value is a guard for memory,
# not a measurement of systemap capacity. The memory size of a node changes with the
# code. The measured values are 253 bytes (the systemap source, 259706 nodes) and 314
# bytes (lines of `x = 1`), with the node list. Thus the cache uses about 270 to 330 MB at
# this limit. A repository with fewer nodes parses each module one time in each
# extraction.
KEPT = 1024 * 1024

_Result = ast.Module | SyntaxError | ValueError
_trees: OrderedDict[str, _Result] = OrderedDict()
_size = [0]
# Each cached tree by its identity, with its node list in the order of `ast.walk`.
_nodes: dict[int, tuple[ast.Module, list[ast.AST]]] = {}
_lock = threading.Lock()
# The digests of the refused texts. The cache limit does not remove them.
_refused: set[str] = set()


class TooDeep(ValueError):
    """The text has too many syntax levels for the parser or for a later step."""


def refuse(raw: str) -> None:
    """Give `TooDeep` for each later parse of the text, until `clear`."""
    with _lock:
        _refused.add(_digest(raw))
        found = _trees.pop(raw, None)
        entry = _nodes.pop(id(found), None)
        if found is not None:
            _size[0] -= len(entry[1]) if entry else 1


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8", "surrogatepass")).hexdigest()


def parse(raw: str) -> ast.Module:
    """Give the syntax tree of a Python module text, as `ast.parse(raw)` gives it.

    Text that does not parse gives the SyntaxError or the ValueError of `ast.parse`.
    Text with too many syntax levels, or a refused text, gives `TooDeep`.
    """
    if _refused and _digest(raw) in _refused:
        raise TooDeep(DEPTH_REASON)
    found = _cached(raw)
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

    For a tree from the cache, the function gives the node list of the cache. For a
    different tree, the function gives `ast.walk(node)`.
    """
    with _lock:
        owner, found = _nodes.get(id(node), (None, []))
    return found if owner is node else ast.walk(node)


def clear() -> None:
    """Remove all trees and all refused texts from the cache."""
    with _lock:
        _refused.clear()
        _clear()


def _clear() -> None:
    _trees.clear()
    _nodes.clear()
    _size[0] = 0


def _cached(raw: str) -> _Result | None:
    """Give the cached result of the text, or None.

    If the text is not in the cache and the cache holds a tree that is larger than the
    limit, the function removes that tree before the caller parses the text.
    """
    with _lock:
        found = _trees.get(raw)
        if found is not None:
            _trees.move_to_end(raw)
        elif _size[0] > KEPT:
            _clear()
    return found


def _parse(raw: str) -> _Result:
    try:
        return ast.parse(raw)
    except (SyntaxError, ValueError) as exc:
        return exc
    except DEPTH_ERRORS:
        return TooDeep(DEPTH_REASON)


def _keep(raw: str, found: _Result) -> None:
    # An error counts as one node.
    nodes = list(ast.walk(found)) if isinstance(found, ast.Module) else []
    with _lock:
        if raw in _trees:
            return
        _trees[raw] = found
        _size[0] += max(len(nodes), 1)
        if isinstance(found, ast.Module):
            _nodes[id(found)] = (found, nodes)
        while _size[0] > KEPT and len(_trees) > 1:
            _remove_oldest()


def _remove_oldest() -> None:
    _old, removed = _trees.popitem(last=False)
    entry = _nodes.pop(id(removed), None)
    _size[0] -= len(entry[1]) if entry else 1
