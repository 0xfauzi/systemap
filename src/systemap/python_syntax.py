"""Python syntax rules of the Python adapter: empty package markers and decorators.

An empty package marker is an `__init__.py` file with no statement that holds code. A
docstring, `pass`, a `__future__` import, and a literal value for a dunder name such as
`__all__` or `__version__` hold no code. All other statements hold code. Without
`from __future__ import annotations`, the module operates the annotation of a name when
it starts. Then an annotation holds code if it has a part that is not a name, an
attribute, a subscript, a literal, or `|`. For example, a call holds code.

A declaration fingerprint includes the decorators of the declaration, because a decorator
can change the interface of a function or a method.
"""

from __future__ import annotations

import ast

from systemap import python_tree, syntax_text

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


def fingerprint(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Give the fingerprint of a function: one line for each decorator, then the signature.

    Each line uses the syntax text (`syntax_text`), as the class fingerprints do. Thus a
    change of the formatting or of the comments does not change the fingerprint. A
    function without a decorator gives the signature line only.
    """
    returns = None if node.returns is None else syntax_text.text(node.returns)
    line = function_line(node, syntax_text.text(node.args), returns)
    return "\n".join([*(f"@{syntax_text.text(item)}" for item in node.decorator_list), line])


def function_line(
    node: ast.FunctionDef | ast.AsyncFunctionDef, arguments: str, returns: str | None
) -> str:
    """Give `def name(arguments) -> returns`, with `async def` for an async function.

    The fingerprint and the stored signature (`source_segment.signature`) use this form.
    """
    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    line = f"{prefix}{node.name}({arguments})"
    return line if returns is None else f"{line} -> {returns}"


def active_statements(body: list[ast.stmt]) -> list[ast.stmt]:
    """Select the top-level statements that `extract` reads.

    An `if` with a `bool` constant test gives only the statements of its selected branch.
    `extract` and `python_earlier_text` must select the same statements.
    """
    out: list[ast.stmt] = []
    for node in body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Constant):
            if isinstance(node.test.value, bool):
                out.extend(active_statements(node.body if node.test.value else node.orelse))
                continue
        out.append(node)
    return out
