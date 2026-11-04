"""The syntax text of a module is the same on each supported Python version (issue 126).

CPython 3.12.3 adds an empty `Constant('')` at the end of a format spec that ends with
a replacement field, for example `f"{x:<{width}}"`. A spec that ends with text, such as
`f"{x:{w}.{p}f}"`, gets no empty constant. CPython 3.11, 3.12.13 and 3.13 never add it.
The source-review digest uses the syntax text (`syntax_text`), so the text must not
include the item.

The CI matrix has no 3.12.3. Thus the tests make the 3.12.3 tree from the parsed tree,
and they give the same result on each interpreter. `SHAPES` records what a real 3.12.3
gave for each spec, so that the model of 3.12.3 stays correct. The recorded digest came
from `bench/jev/fstring_digest.py` on 3.11.18, 3.12.3, 3.12.13 and 3.13.18. Issue 136
replaced the dump with the syntax text of systemap (format 14). The digest then changed
one time for each version. The new value is the digest of the syntax text of SOURCE.
"""

from __future__ import annotations

import ast
import hashlib

import pytest

from systemap import syntax_text

SOURCE = 'width = 4\nx = "a"\ny = f"{x:<{width}}"\n'
# The digest of the syntax text of SOURCE (format 14).
RECORDED = "49fd3d23a53e206c3336a2b5bbbe7bfee361583433c23c85fe2dbc04058a8b7a"

# For each f-string: did CPython 3.12.3 add `Constant('')` at the end of its format spec?
# Measured with ast.parse on 3.12.3 and 3.13 on 2026-11-02.
SHAPES = {
    'f"{x:<{w}}"': True,
    'f"{x:{w}}"': True,
    'f"{x:{w}.{p}f}"': False,
    'f"{x:{w}{p}}"': True,
    'f"{x:>{w}} tail"': True,
    'f"{x:{w}.{p}}"': True,
    'f"{x:>10}"': False,
    'f"{x!r:{w}}"': True,
    'f"{x:{w}>}"': False,
    "f\"{x:{f'{w}'}}\"": True,
}


def format_specs(tree: ast.AST) -> list[list[ast.expr]]:
    """Give the parts of each format spec in the tree."""
    return [
        node.format_spec.values
        for node in ast.walk(tree)
        if isinstance(node, ast.FormattedValue) and isinstance(node.format_spec, ast.JoinedStr)
    ]


def as_on_3_12_3(tree: ast.AST) -> ast.AST:
    """Add the empty constant that CPython 3.12.3 puts at the end of each format spec
    that ends with a replacement field."""
    for parts in format_specs(tree):
        if parts and isinstance(parts[-1], ast.FormattedValue):
            parts.append(ast.Constant(value=""))
    return tree


def digest(tree: ast.AST) -> str:
    return hashlib.sha256(syntax_text.text(tree).encode("utf-8")).hexdigest()


@pytest.mark.parametrize("text", list(SHAPES))
def test_the_model_of_3_12_3_agrees_with_the_recorded_shapes(text: str) -> None:
    """On 3.12.3 the parser makes the shape itself. On other versions the model makes it."""
    last = format_specs(as_on_3_12_3(ast.parse(text)))[0][-1]
    assert (isinstance(last, ast.Constant) and last.value == "") is SHAPES[text]


@pytest.mark.parametrize("text", list(SHAPES))
def test_the_3_12_3_tree_gives_the_same_text(text: str) -> None:
    assert digest(as_on_3_12_3(ast.parse(text))) == digest(ast.parse(text))


def test_the_dump_has_the_recorded_digest() -> None:
    changed = as_on_3_12_3(ast.parse(SOURCE))
    assert "Constant(value='')" in ast.dump(changed), "the control: the 3.12.3 shape"
    assert digest(ast.parse(SOURCE)) == RECORDED
    assert digest(changed) == RECORDED


def test_a_constant_with_text_stays() -> None:
    text = syntax_text.text(ast.parse('x = 1\na = f"{x:>10} end"\n'))
    assert "Constant(value='>10')" in text and "Constant(value=' end')" in text
