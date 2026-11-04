"""The stored syntax values are the same on each supported Python version (issue 136).

Before the change, `ast.dump` gave the `api` fingerprints, and `ast.unparse` gave the
signatures, the `constants` previews and the class bases. CPython does not keep these two
functions the same between versions: `ast.dump` on 3.13 does not write empty lists, and
`ast.unparse` on 3.12.3 writes the quotes of an f-string differently. Now systemap writes
its own syntax text (`syntax_text`), and it takes the values that a person reads from the
source text (`source_segment`).

The tests compare each value with a recorded text. Thus each test gives the same result
on each interpreter. CI operates them on 3.11, 3.12, 3.13 and 3.14.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any, ClassVar

import pytest
from conftest import write_tree

from systemap import config, extract, failures, python_syntax, source_segment, syntax_text

# The source text uses no syntax that 3.11 cannot parse.
SOURCE = '''\
"""Doc."""
import os as system
from . import part


@decorator(1, key="v")
async def run(a, /, b: "int" = 2, *rest: str, c=None, **more) -> list[int]:
    async with lock as held:
        x = [i async for i in source() if i]
    match a:
        case {"k": [1, *others]} | None:
            return f"{a!r:>{b}} end {c=}"
    try:
        del a
    except* ValueError:
        raise
    return {k: v for k, v in more.items()}, lambda: (yield)


class Model(Base, metaclass=Meta):
    size: int = 1
    b"\\x00", 1.5, 2j, ..., True
'''

# The syntax text of SOURCE. Each supported interpreter gives this text.
RECORDED = (
    "Module(body=[Expr(value=Constant(value='Doc.')), Import(names=[alias(name='os', "
    "asname='system')]), ImportFrom(names=[alias(name='part')], level=1), "
    "AsyncFunctionDef(name='run', args=arguments(posonlyargs=[arg(arg='a')], "
    "args=[arg(arg='b', annotation=Constant(value='int'))], vararg=arg(arg='rest', "
    "annotation=Name(id='str', ctx=Load())), kwonlyargs=[arg(arg='c')], "
    "kw_defaults=[Constant()], kwarg=arg(arg='more'), defaults=[Constant(value=2)]), "
    "body=[AsyncWith(items=[withitem(context_expr=Name(id='lock', ctx=Load()), "
    "optional_vars=Name(id='held', ctx=Store()))], body=[Assign(targets=[Name(id='x', "
    "ctx=Store())], value=ListComp(elt=Name(id='i', ctx=Load()), "
    "generators=[comprehension(target=Name(id='i', ctx=Store()), iter=Call(func="
    "Name(id='source', ctx=Load())), ifs=[Name(id='i', ctx=Load())], is_async=1)]))]), "
    "Match(subject=Name(id='a', ctx=Load()), cases=[match_case(pattern=MatchOr("
    "patterns=[MatchMapping(keys=[Constant(value='k')], patterns=[MatchSequence("
    "patterns=[MatchValue(value=Constant(value=1)), MatchStar(name='others')])]), "
    "MatchSingleton()]), body=[Return(value=JoinedStr(values=[FormattedValue(value="
    "Name(id='a', ctx=Load()), conversion=114, format_spec=JoinedStr(values=["
    "Constant(value='>'), FormattedValue(value=Name(id='b', ctx=Load()), "
    "conversion=-1)])), Constant(value=' end c='), FormattedValue(value=Name(id='c', "
    "ctx=Load()), conversion=114)]))])]), TryStar(body=[Delete(targets=[Name(id='a', "
    "ctx=Del())])], handlers=[ExceptHandler(type=Name(id='ValueError', ctx=Load()), "
    "body=[Raise()])]), Return(value=Tuple(elts=[DictComp(key=Name(id='k', ctx=Load()), "
    "value=Name(id='v', ctx=Load()), generators=[comprehension(target=Tuple(elts=["
    "Name(id='k', ctx=Store()), Name(id='v', ctx=Store())], ctx=Store()), iter=Call("
    "func=Attribute(value=Name(id='more', ctx=Load()), attr='items', ctx=Load())), "
    "is_async=0)]), Lambda(args=arguments(), body=Yield())], ctx=Load()))], "
    "decorator_list=[Call(func=Name(id='decorator', ctx=Load()), args=[Constant("
    "value=1)], keywords=[keyword(arg='key', value=Constant(value='v'))])], returns="
    "Subscript(value=Name(id='list', ctx=Load()), slice=Name(id='int', ctx=Load()), "
    "ctx=Load())), ClassDef(name='Model', bases=[Name(id='Base', ctx=Load())], "
    "keywords=[keyword(arg='metaclass', value=Name(id='Meta', ctx=Load()))], body=["
    "AnnAssign(target=Name(id='size', ctx=Store()), annotation=Name(id='int', "
    "ctx=Load()), value=Constant(value=1), simple=1), Expr(value=Tuple(elts=["
    "Constant(value=b'\\x00'), Constant(value=1.5), Constant(value=2j), "
    "Constant(value=Ellipsis), Constant(value=True)], ctx=Load()))])])"
)


def test_the_syntax_text_of_a_fixed_source_is_the_recorded_text() -> None:
    assert syntax_text.text(ast.parse(SOURCE)) == RECORDED


def test_the_syntax_text_does_not_call_ast_dump_or_ast_unparse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before the change, the fingerprints, the previews and the signatures used them."""

    def refuse(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("a stored value used a function of CPython")

    monkeypatch.setattr(ast, "dump", refuse)
    monkeypatch.setattr(ast, "unparse", refuse)
    surface = extract.parse_surface(SOURCE + "LIMIT = 'x'\n")
    assert surface is not None
    assert surface["api"] and surface["constants"] and surface["classes"]
    assert extract._normalized(SOURCE) == RECORDED


def test_an_empty_list_and_an_absent_field_give_the_same_text() -> None:
    """3.12 added an empty `type_params`. 3.13 changed `ast.dump` for empty lists."""
    tree = ast.parse("def f(x):\n    pass\n\nclass C:\n    pass\n")
    before = syntax_text.text(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.ClassDef):
            node.type_params = []  # type: ignore[attr-defined]
    assert syntax_text.text(tree) == before
    assert "type_params" not in before and "decorator_list" not in before


def test_the_function_fingerprint_is_the_recorded_text() -> None:
    """On 3.13, `ast.dump` without `show_empty` gave a different fingerprint."""
    node = ast.parse("@cache\ndef get(key: str, *, default: int = 0) -> int:\n    ...\n").body[0]
    assert isinstance(node, ast.FunctionDef)
    assert python_syntax.fingerprint(node) == (
        "@Name(id='cache', ctx=Load())\n"
        "def get(arguments(args=[arg(arg='key', annotation=Name(id='str', ctx=Load()))], "
        "kwonlyargs=[arg(arg='default', annotation=Name(id='int', ctx=Load()))], "
        "kw_defaults=[Constant(value=0)])) -> Name(id='int', ctx=Load())"
    )


def test_a_change_of_the_formatting_keeps_the_fingerprints() -> None:
    one = extract.parse_surface("def f(a: 'x' = 1) -> None: ...\nLIMIT = {'a': 1}\n")
    two = extract.parse_surface(
        'def f(\n    a: "x" = 1,  # note\n) -> None: ...\nLIMIT = {"a": 1}\n'
    )
    assert one is not None and two is not None
    assert one["api"] == two["api"]


def test_the_previews_and_the_signatures_are_the_source_text() -> None:
    """On 3.12.3, `ast.unparse` wrote the quotes of an f-string differently from 3.11."""
    source = (
        'MESSAGES = {"serving": lambda e: f"map: at {e["url"]}."}\n'
        if sys.version_info >= (3, 12)
        else 'MESSAGES = {"serving": lambda e: f"map: at {e[\'url\']}."}\n'
    )
    source += (
        "LONG = [\n    1,  # one\n    '#',\n]\n"
        'def f(a: dict[str,\n      int] = "x", /, *, b=1, **kw) -> list[\n    int\n]: ...\n'
    )
    surface = extract.parse_surface(source)
    assert surface is not None
    values = {item["name"]: item["value"] for item in surface["constants"]}
    assert values["MESSAGES"] == source.splitlines()[0].removeprefix("MESSAGES = ")
    assert values["LONG"] == "[1, '#',]"
    assert surface["functions"] == [
        {"name": "f", "signature": 'def f(a: dict[str, int]="x", /, *, b=1, **kw) -> list[int]'}
    ]


def test_a_preview_keeps_the_length_limit() -> None:
    surface = extract.parse_surface("NAMES = [\n" + "    'name',\n" * 100 + "]\n")
    assert surface is not None
    value = surface["constants"][0]["value"]
    assert len(value) == extract.PREVIEW_LIMIT
    assert value.startswith("['name', 'name',")


def test_the_column_positions_count_utf8_bytes() -> None:
    raw = 'def f(a: "é" = "ü", b: int = 1) -> "ä": ...\n'
    node = ast.parse(raw).body[0]
    assert isinstance(node, ast.FunctionDef)
    text = source_segment.signature(node, source_segment.Source(raw))
    assert text == 'def f(a: "é"="ü", b: int=1) -> "ä"'


@pytest.mark.parametrize(
    ("text", "flat"),
    [
        ("a", "a"),
        ("(\n  a,\n  b\n)", "(a, b)"),
        ("[\n  1,  # the first\n  '# not a comment',\n]", "[1, '# not a comment',]"),
        ('"a" \\\n  "b"', '"a" "b"'),
        ('"""one\n# two"""', '"""one # two"""'),
    ],
)
def test_a_value_on_more_lines_becomes_one_line(text: str, flat: str) -> None:
    assert source_segment.flat(text) == flat


@pytest.mark.skipif(sys.version_info < (3, 12), reason="PEP 701 f-strings start in 3.12")
def test_a_hash_in_a_nested_string_of_an_f_string_is_not_a_comment() -> None:
    raw = 'KEYS = [\n    f"{d["#"]}",  # the key\n]\n'
    surface = extract.parse_surface(raw)
    assert surface is not None
    assert surface["constants"] == [{"name": "KEYS", "value": '[f"{d["#"]}",]'}]


def test_a_large_integer_gives_the_same_text_with_each_conversion_limit() -> None:
    tree = ast.parse("MASK = 0x" + "f" * 4000 + "\nSMALL = 12\n")
    limit = sys.get_int_max_str_digits()
    try:
        texts = set()
        for digits in (0, 640, limit):
            sys.set_int_max_str_digits(digits)
            texts.add(syntax_text.text(tree))
    finally:
        sys.set_int_max_str_digits(limit)
    assert len(texts) == 1
    (text,) = texts
    assert "value=0x" + "f" * 4000 in text
    assert "value=12" in text


def test_a_deep_tree_has_the_same_depth_limit_as_ast_dump() -> None:
    tree = ast.parse("X = " + "+".join(["1"] * 900) + "\n")
    ast.dump(tree)
    assert syntax_text.text(tree).count("BinOp(") == 899


class Spam(ast.expr):
    """A node class that no Python version has."""

    _fields: ClassVar[tuple[str, ...]] = ()


def test_an_unknown_node_class_stops_the_text_with_its_name_and_the_version() -> None:
    tree = ast.parse("x = 1\n")
    assign = tree.body[0]
    assert isinstance(assign, ast.Assign)
    assign.value = Spam()
    with pytest.raises(syntax_text.UnknownSyntax) as caught:
        syntax_text.text(tree)
    message = str(caught.value)
    assert "the node class Spam" in message
    assert f"of Python {sys.version.split()[0]}." in message


def test_an_unknown_node_class_stops_the_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The extraction does not record a digest without the node (AGENTS.md)."""
    write_tree(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "pkg"\nversion = "0.1"\n',
            "pkg/__init__.py": "",
            "pkg/a.py": "def f():\n    pass\n",
        },
    )
    fields = {name: value for name, value in syntax_text.FIELDS.items() if name != "Pass"}
    monkeypatch.setattr(syntax_text, "FIELDS", fields)
    monkeypatch.setattr(syntax_text, "_plans", {})
    with pytest.raises(syntax_text.UnknownSyntax) as caught:
        extract.build(config.load(tmp_path))
    assert failures.report(caught.value) == failures.STALE
    error = capsys.readouterr().err
    assert "the node class Pass" in error and sys.version.split()[0] in error
    assert failures.SYNTAX_FIX in error.replace("\n", " ")


def test_an_unknown_field_stops_the_text() -> None:
    node = ast.Name(id="x", ctx=ast.Load())
    extra: Any = type("Name", (ast.expr,), {"_fields": ("id", "ctx", "spam")})
    copy = extra(id="x", ctx=ast.Load(), spam=1)
    assert syntax_text.text(node) == "Name(id='x', ctx=Load())"
    with pytest.raises(syntax_text.UnknownSyntax, match=r"the field Name\.spam"):
        syntax_text.text(copy)


def test_the_tables_agree_with_the_node_classes_of_this_interpreter() -> None:
    """A later CPython with a new field or a removed field fails this test in CI."""
    for name, fields in syntax_text.FIELDS.items():
        kind = getattr(ast, name, None)
        since = syntax_text.SINCE.get((name, ""))
        if kind is None:
            assert since is not None and sys.version_info[:2] < since, name
            continue
        present = set(kind._fields)
        assert present <= set(fields), name
        for field in set(fields) - present:
            assert sys.version_info[:2] < syntax_text.SINCE[(name, field)], (name, field)
