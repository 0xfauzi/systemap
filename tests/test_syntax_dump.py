"""The syntax dump of a module is the same on each supported Python version (issue 126).

CPython 3.12.3 adds an empty `Constant('')` at the end of a format spec that contains a
replacement field, for example `f"{x:<{width}}"`. CPython 3.11, 3.12.13 and 3.13 do not
add it. The source-review digest uses the dump, so the dump must remove the item.

The CI matrix has no 3.12.3. Thus a test makes the 3.12.3 tree from the parsed tree, and
the test gives the same result on each interpreter. The recorded digest came from
`bench/fstring_digest.py` on 3.11.18, 3.12.3, 3.12.13 and 3.13.18.
"""

from __future__ import annotations

import ast
import hashlib

from systemap import extract

SOURCE = 'width = 4\nx = "a"\ny = f"{x:<{width}}"\n'
# The digest of the dump of SOURCE on each measured interpreter after the change.
RECORDED = "3afa7b3e11e8eaa6f6f6b499c3c506b465bad46d0e1460865b607259f4bf18c6"


def as_on_3_12_3(tree: ast.AST) -> ast.AST:
    """Add the empty constant that CPython 3.12.3 puts at the end of each format spec
    with a replacement field."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FormattedValue) and isinstance(node.format_spec, ast.JoinedStr):
            parts = node.format_spec.values
            if any(isinstance(part, ast.FormattedValue) for part in parts):
                parts.append(ast.Constant(value=""))
    return tree


def digest(tree: ast.AST) -> str:
    return hashlib.sha256(extract._dump_python_syntax(tree).encode("utf-8")).hexdigest()


def test_the_dump_has_the_recorded_digest() -> None:
    assert digest(ast.parse(SOURCE)) == RECORDED


def test_the_3_12_3_tree_gives_the_same_dump() -> None:
    changed = as_on_3_12_3(ast.parse(SOURCE))
    assert "Constant(value='')" in ast.dump(changed), "the control: the 3.12.3 shape"
    assert digest(changed) == RECORDED


def test_other_format_specs_give_the_same_dump_as_on_3_12_3() -> None:
    text = 'w = 4\np = 2\nx = 1.5\na = f"{x:{w}.{p}f}"\nb = f"pre {x:{w}} post"\n'
    assert digest(as_on_3_12_3(ast.parse(text))) == digest(ast.parse(text))


def test_a_constant_with_text_stays() -> None:
    dump = extract._dump_python_syntax(ast.parse('x = 1\na = f"{x:>10} end"\n'))
    assert "Constant(value='>10')" in dump and "Constant(value=' end')" in dump


def test_the_dump_does_not_change_the_tree() -> None:
    tree = as_on_3_12_3(ast.parse(SOURCE))
    before = ast.dump(tree, include_attributes=True)
    extract._dump_python_syntax(tree)
    assert ast.dump(tree, include_attributes=True) == before
