"""Python syntax rules of the Python adapter: empty package markers and decorators.

An empty package marker is an `__init__.py` file with no statement that holds code. A
docstring, `pass`, a `__future__` import, and a literal value for a dunder name such as
`__all__` or `__version__` hold no code. All other statements hold code. Without
`from __future__ import annotations`, the module operates the annotation of a name when
it starts. Then an annotation holds code if it has a part that is not a name, an
attribute, a subscript, a literal, or `|`. For example, a call holds code.

A declaration fingerprint includes the decorators of the declaration, because a decorator
can change the interface of a function or a method.

The stored facts must not change with the Python interpreter (issue 136). Thus each
stored syntax dump uses `dump`, and each stored source text from the tree uses `unparse`.
Both functions give the text of CPython 3.11 on each supported interpreter.
"""

from __future__ import annotations

import ast
import contextlib
import sys
from collections.abc import Callable, Iterator
from typing import Any

from systemap import python_tree

LITERAL_ERRORS = (ValueError, TypeError, SyntaxError, MemoryError, RecursionError)


def holds_no_code(raw: str) -> bool:
    """Give `True` if each top-level statement of the source holds no code.

    Source that does not parse gives `False`, because its statements are not known.
    """
    tree = python_tree.tree(raw)
    if tree is None:
        return False
    postponed = any(_postpones_annotations(node) for node in tree.body)
    return all(_inert(node, postponed) for node in tree.body)


def _postpones_annotations(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
    )


def _inert(node: ast.stmt, postponed: bool = False) -> bool:
    if isinstance(node, ast.Pass):
        return True
    if isinstance(node, ast.Expr):
        return isinstance(node.value, ast.Constant)
    if isinstance(node, ast.ImportFrom):
        return node.module == "__future__" and not node.level
    if isinstance(node, ast.AnnAssign) and not postponed and not _plain(node.annotation):
        return False
    if isinstance(node, ast.Assign | ast.AnnAssign):
        return _metadata(node)
    return False


# The annotation nodes that hold no call: a name, an attribute, a subscript, a literal,
# and `X | Y`. `ast.walk` also gives the operator and the context of each node.
_PLAIN = (
    ast.Name,
    ast.Attribute,
    ast.Subscript,
    ast.Constant,
    ast.Tuple,
    ast.List,
    ast.BinOp,
    ast.BitOr,
    ast.expr_context,
)


def _plain(annotation: ast.expr) -> bool:
    """Tell if the evaluation of an annotation holds no call."""
    return all(isinstance(node, _PLAIN) for node in ast.walk(annotation))


def _metadata(node: ast.Assign | ast.AnnAssign) -> bool:
    """Find a literal value for dunder names only, such as `__all__ = ["run"]`."""
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    if node.value is None or not all(_dunder(target) for target in targets):
        return False
    try:
        ast.literal_eval(node.value)
    except LITERAL_ERRORS:
        return False
    return True


def _dunder(target: ast.expr) -> bool:
    return (
        isinstance(target, ast.Name)
        and len(target.id) > 4
        and target.id.startswith("__")
        and target.id.endswith("__")
    )


def decorated(node: ast.FunctionDef | ast.AsyncFunctionDef, signature: str) -> str:
    """Give the signature with one line before it for each decorator.

    The decorator lines use the same syntax dump as the class fingerprints. A function
    without a decorator gives the signature without a change.
    """
    return "\n".join([*(f"@{dump(item)}" for item in node.decorator_list), signature])


# CPython 3.13 does not write empty lists in `ast.dump` by default.
SHOW_EMPTY = sys.version_info >= (3, 13)


def dump(node: ast.AST) -> str:
    """Give the `ast.dump` text of CPython 3.11 for a node, on each supported interpreter.

    The function does not change the node. Other steps read the same tree from
    `python_tree`.
    """
    # Python 3.12 added empty type_params; 3.13 stopped dumping empty
    # lists by default. Retain the 3.11 representation for shared syntax,
    # while retaining nonempty type parameters as meaningful source.
    empty_fields = {"show_empty": True} if SHOW_EMPTY else {}
    with _hidden_for_dump(node):
        return ast.dump(node, include_attributes=False, **empty_fields)


def _is_empty_string(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value == ""


@contextlib.contextmanager
def _hidden_for_dump(tree: ast.AST) -> Iterator[None]:
    """Change the tree for the dump in one walk. Restore each changed node at the end.

    - An empty `type_params` field leaves the fields that `ast.dump` writes.
    - Each f-string loses each empty string constant from its parts. CPython 3.12.3 adds
      `Constant('')` at the end of a format spec that ends with a replacement field, for
      example `f"{x:<{width}}"`. CPython 3.11, 3.12.13 and 3.13 do not add it (issue 126).
    """
    hidden: list[ast.AST] = []
    emptied: list[tuple[ast.JoinedStr, list[ast.expr]]] = []
    try:
        for node in python_tree.walk(tree):
            if getattr(node, "type_params", None) == []:
                hidden.append(node)
                vars(node)["_fields"] = tuple(f for f in node._fields if f != "type_params")
            elif isinstance(node, ast.JoinedStr) and any(map(_is_empty_string, node.values)):
                emptied.append((node, node.values))
                node.values = [v for v in node.values if not _is_empty_string(v)]
        yield
    finally:
        for node in hidden:
            del vars(node)["_fields"]
        for joined, values in emptied:
            joined.values = values


# CPython 3.12.3 writes this f-string as f'{x['a']}'. CPython 3.11, 3.12.13 and 3.13 select
# a quote that is not in a replacement field.
_PROBE = "f\"{x['a']}\""
# The quotes of the CPython unparser, in the order of preference.
_MULTI_QUOTES = ('"""', "'''")
_ALL_QUOTES = ("'", '"', *_MULTI_QUOTES)
_UNPARSERS: dict[Callable[[ast.AST], str], Callable[[ast.AST], str]] = {}


def unparse(node: ast.AST) -> str:
    """Give the `ast.unparse` text of CPython 3.11 for a node, on each supported interpreter.

    If `ast.unparse` writes the quotes of an f-string as CPython 3.12.3 does, the function
    uses the f-string step of CPython 3.12.13. The two versions are different only in
    that step.
    """
    current = ast.unparse
    chosen = _UNPARSERS.get(current)
    if chosen is None:
        probe = ast.parse(_PROBE, mode="eval").body
        chosen = current if current(probe) == _PROBE else _corrected_unparse(current)
        _UNPARSERS[current] = chosen
    return chosen(node)


def _corrected_unparse(current: Callable[[ast.AST], str]) -> Callable[[ast.AST], str]:
    """Give an unparse function that selects the quotes of an f-string as CPython 3.11 does.

    The class `ast._Unparser` is not public. If the interpreter has no such class, the
    function gives `ast.unparse` without a change.
    """
    base: Any = getattr(ast, "_Unparser", None)
    if base is None:
        return current
    if sys.version_info < (3, 12):
        # The unparser of CPython 3.11 is the reference.
        return lambda node: str(base().visit(node))

    class Unparser(base):  # type: ignore[misc]
        visit_JoinedStr = _visit_joined_str

    return lambda node: str(Unparser().visit(node))


def _visit_joined_str(self: Any, node: ast.JoinedStr) -> None:
    """Write an f-string as the `visit_JoinedStr` step of CPython 3.12.13 does."""
    self.write("f")
    parts = []
    for value in node.values:
        with self.buffered() as buffer:
            self._write_fstring_inner(value)
        parts.append(("".join(buffer), isinstance(value, ast.Constant)))
    quotes, written = _fstring_quotes(self, parts)
    self.write(f"{quotes[0]}{''.join(written)}{quotes[0]}")


def _fstring_quotes(self: Any, parts: list[tuple[str, bool]]) -> tuple[list[str], list[str]]:
    """Select the quotes of an f-string and give the text of each part.

    A quote that is in a replacement field is not selected, if a different quote is
    possible. CPython 3.12.13 has this rule, and CPython 3.12.3 does not.
    """
    quote_types = list(_ALL_QUOTES)
    written: list[str] = []
    for value, is_constant in parts:
        if is_constant:
            text, new_quote_types = self._str_literal_helper(
                value, quote_types=quote_types, escape_special_whitespace=True
            )
            if set(new_quote_types).isdisjoint(quote_types):
                # No quote is possible for each part: use repr and triple single quotes.
                return ["'''"], [_repr_part(part, constant) for part, constant in parts]
            quote_types = new_quote_types
            written.append(text)
        else:
            quote_types = _field_quotes(quote_types, value)
            written.append(value)
    return quote_types, written


def _field_quotes(quote_types: list[str], field: str) -> list[str]:
    """Remove the quotes that a replacement field does not permit, if a quote stays."""
    if "\n" in field:
        quote_types = [q for q in quote_types if q in _MULTI_QUOTES]
    return [q for q in quote_types if q not in field] or quote_types


def _repr_part(value: str, is_constant: bool) -> str:
    # The repr of a text that starts with '"' uses single quotes.
    return repr('"' + value)[2:-1] if is_constant else value
