"""The stored module facts are the same on each supported Python version (issue 136).

Two facts used the interpreter text directly:

- An `api` fingerprint used `ast.dump`. CPython 3.13 does not write empty lists by
  default, for example `args=[]`.
- A `constants` preview used `ast.unparse`. CPython 3.12.3 writes the quotes of an
  f-string differently when a replacement field contains a quote. CPython 3.11, 3.12.13
  and 3.13 select a different quote. CPython 3.12 and 3.13 also add a backslash before a
  quote or a newline of a format spec, and CPython 3.11 does not.

The CI matrix has 3.11 and 3.13 and no 3.12.3. Thus each test of an interpreter puts a
model of that interpreter in place of `ast.dump` or `ast.unparse`, and the tests give the
same result on each interpreter. The recorded texts came from CPython 3.11.15, 3.12.3
and 3.13.14 on 2026-11-03.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Callable
from typing import Any

import pytest

from systemap import extract, python_syntax

SOURCE = """import functools
from dataclasses import dataclass

LIMITS = frozenset()


@functools.lru_cache()
def run(a: int = 1) -> None: ...


@dataclass()
class Point:
    x: list[int]

    def move(self) -> None: ...
"""

# The fingerprints of SOURCE on CPython 3.11.15 with systemap 3.0.0.
RECORDED_API = [
    "reexport:dataclasses:dataclass",
    "Assign(targets=[Name(id='LIMITS', ctx=Store())], value=Call(func=Name(id='frozenset', "
    "ctx=Load()), args=[], keywords=[]))",
    "@Call(func=Attribute(value=Name(id='functools', ctx=Load()), attr='lru_cache', "
    "ctx=Load()), args=[], keywords=[])\ndef run(a: int=1) -> None",
    '{"bases": [], "decorators": ["Call(func=Name(id=\'dataclass\', ctx=Load()), args=[], '
    'keywords=[])"], "members": ["x:Subscript(value=Name(id=\'list\', ctx=Load()), '
    'slice=Name(id=\'int\', ctx=Load()), ctx=Load())", "def move(self) -> None"]}',
]
# The default `ast.dump` of the `LIMITS` statement on CPython 3.13.14.
RECORDED_3_13 = (
    "Assign(targets=[Name(id='LIMITS', ctx=Store())], value=Call(func=Name(id='frozenset', "
    "ctx=Load())))"
)

# For each f-string: the `ast.unparse` text on CPython 3.11.15 (also 3.12.13 and 3.13.14),
# and the text on CPython 3.12.3.
PREVIEWS = {
    "f\"{x['a']}\"": ("f\"{x['a']}\"", "f'{x['a']}'"),
    "{'serving': lambda e: f\"map: {e['url']}.\"}": (
        "{'serving': lambda e: f\"map: {e['url']}.\"}",
        "{'serving': lambda e: f'map: {e['url']}.'}",
    ),
    'f\'a"{g(".07")}"b\'': ("f'''a\"{g('.07')}\"b'''", "f'a\"{g('.07')}\"b'"),
    "f\"{os.sep}{(os.altsep if os.altsep else '')}\"": (
        "f\"{os.sep}{(os.altsep if os.altsep else '')}\"",
        "f'{os.sep}{(os.altsep if os.altsep else '')}'",
    ),
    "f'plain {x}'": ("f'plain {x}'", "f'plain {x}'"),
}
# For each f-string with a quote or a newline in a format spec: the `ast.unparse` text on
# CPython 3.11.15, on CPython 3.12.3, and on CPython 3.12.13 and 3.13.14. CPython 3.12 and
# 3.13 add a backslash before the quote or the newline.
FORMAT_SPECS = {
    'f"{x:\'}"': ('f"{x:\'}"', "f'{x:\\'}'", 'f"{x:\\\'}"'),
    'f"{x[\'a\']:\\"}"': (
        'f"""{x[\'a\']:"}"""',
        "f'{x['a']:\\\"}'",
        'f"""{x[\'a\']:\\"}"""',
    ),
    'f"""{x:\n}"""': ('f"""{x:\n}"""', "f'{x:\\n}'", "f'{x:\\n}'"),
}
PREVIEWS.update(
    {text: (earlier, on_3_12_3) for text, (earlier, on_3_12_3, _) in FORMAT_SPECS.items()}
)

REAL_DUMP = ast.dump
REAL_UNPARSE = ast.unparse
# Without `show_empty=True`, the `ast.dump` of this interpreter writes no empty list.
OMITS_EMPTY = sys.version_info >= (3, 13)


def fingerprints(raw: str) -> list[str]:
    surface = extract.parse_surface(raw)
    assert surface is not None
    return [entry["fingerprint"] for entry in surface["api"]]


def full_dump(node: ast.AST, *args: Any, **kwargs: Any) -> str:
    """Give the dump with each empty list, on each interpreter."""
    kwargs.pop("show_empty", None)
    if OMITS_EMPTY:
        kwargs["show_empty"] = True
    return REAL_DUMP(node, *args, **kwargs)


def dump_as_on_3_13(node: ast.AST, *args: Any, show_empty: bool = False, **kwargs: Any) -> str:
    """A model of `ast.dump` of CPython 3.13: without `show_empty`, no empty list."""
    text = full_dump(node, *args, **kwargs)
    if show_empty:
        return text
    return re.sub(r"\(, ", "(", re.sub(r"(, )?\b\w+=\[\]", "", text))


def unparse_as_on_3_12_3(node: ast.AST) -> str:
    """A model of `ast.unparse` of CPython 3.12.3 for the recorded f-strings."""
    text = REAL_UNPARSE(node)
    later = {earlier: on_3_12_3 for earlier, on_3_12_3 in PREVIEWS.values()}
    later.update({newer: on_3_12_3 for _, on_3_12_3, newer in FORMAT_SPECS.values()})
    return later.get(text, text)


def test_the_fingerprints_have_the_3_11_text() -> None:
    assert fingerprints(SOURCE) == RECORDED_API


def test_the_model_of_3_13_agrees_with_the_recorded_dump() -> None:
    statement = ast.parse(SOURCE).body[2]
    assert dump_as_on_3_13(statement) == RECORDED_3_13
    assert dump_as_on_3_13(statement, show_empty=True) == RECORDED_API[1]


def test_the_dump_of_3_13_gives_the_3_11_fingerprints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ast, "dump", dump_as_on_3_13)
    monkeypatch.setattr(python_syntax, "SHOW_EMPTY", True, raising=False)
    assert fingerprints(SOURCE) == RECORDED_API


@pytest.mark.parametrize("text", list(PREVIEWS))
def test_the_preview_has_the_3_11_text(text: str) -> None:
    surface = extract.parse_surface(f"VALUE = {text}\n")
    assert surface is not None
    assert surface["constants"] == [{"name": "VALUE", "value": PREVIEWS[text][0]}]


@pytest.mark.parametrize("text", list(PREVIEWS))
def test_the_unparse_of_3_12_3_gives_the_3_11_preview(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    monkeypatch.setattr(
        python_syntax, "_unparser", lambda: python_syntax.select(unparse_as_on_3_12_3)
    )
    assert unparse_as_on_3_12_3(ast.parse(text, mode="eval").body) == PREVIEWS[text][1]
    surface = extract.parse_surface(f"VALUE = {text}\n")
    assert surface is not None
    assert surface["constants"] == [{"name": "VALUE", "value": PREVIEWS[text][0]}]


def _with_all_quotes() -> ast.Expression:
    """An f-string whose text has each quote, so no quote is possible for each part."""
    constant = ast.Constant(value="' \" ''' \"\"\" ")
    field = ast.FormattedValue(value=ast.Name(id="x", ctx=ast.Load()), conversion=-1)
    return ast.fix_missing_locations(ast.Expression(body=ast.JoinedStr(values=[constant, field])))


@pytest.mark.parametrize("text", list(PREVIEWS))
def test_the_corrected_unparse_gives_the_3_11_text(text: str) -> None:
    corrected = python_syntax._corrected_unparse()
    assert corrected(ast.parse(text, mode="eval").body) == PREVIEWS[text][0]


# F-strings without a quote in a replacement field. CPython 3.12.3 writes them as the
# other versions do.
SAME_SHAPES: list[Callable[[], ast.AST]] = [
    lambda: ast.parse("f'a\\n{x}\\nb'", mode="eval").body,
    lambda: ast.parse("f'{x:>{w}}'", mode="eval").body,
    lambda: ast.parse("f'{x!r} and {y}'", mode="eval").body,
    lambda: _with_all_quotes().body,
]


@pytest.mark.parametrize("make", SAME_SHAPES)
def test_the_corrected_unparse_agrees_with_the_unparse_of_this_interpreter(
    make: Callable[[], ast.AST],
) -> None:
    corrected = python_syntax._corrected_unparse()
    assert corrected(make()) == REAL_UNPARSE(make())


def test_an_unparser_without_the_3_11_text_stops_the_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If no unparser gives the 3.11 text, the function stops and gives no stored text."""
    monkeypatch.setattr(python_syntax, "_corrected_unparse", lambda: unparse_as_on_3_12_3)
    with pytest.raises(python_syntax.UnparseError, match="cannot give the CPython 3.11 text"):
        python_syntax.select(unparse_as_on_3_12_3)
