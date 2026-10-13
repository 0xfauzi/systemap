"""Python syntax rules of the Python adapter: empty package markers and decorators.

An empty package marker is an `__init__.py` file with no statement that holds code. A
docstring, `pass`, a `__future__` import, and a literal value for a dunder name such as
`__all__` or `__version__` hold no code. All other statements hold code.

A declaration fingerprint includes the decorators of the declaration, because a decorator
can change the interface of a function or a method.
"""

from __future__ import annotations

import ast

LITERAL_ERRORS = (ValueError, TypeError, SyntaxError, MemoryError, RecursionError)


def holds_no_code(raw: str) -> bool:
    """Give `True` if each top-level statement of the source holds no code.

    Source that does not parse gives `False`, because its statements are not known.
    """
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return False
    return all(_inert(node) for node in tree.body)


def _inert(node: ast.stmt) -> bool:
    if isinstance(node, ast.Pass):
        return True
    if isinstance(node, ast.Expr):
        return isinstance(node.value, ast.Constant)
    if isinstance(node, ast.ImportFrom):
        return node.module == "__future__" and not node.level
    if isinstance(node, ast.Assign | ast.AnnAssign):
        return _metadata(node)
    return False


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
    return "\n".join([*(f"@{ast.dump(item)}" for item in node.decorator_list), signature])
