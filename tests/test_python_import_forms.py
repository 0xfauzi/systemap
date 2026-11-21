"""The Python adapter gives the import form of each import, and the imports by a string value.

Acceptance (facts format 15, written before the build):

- Each case of the specification gives its form: `load`, `call` or `type`. The adapter
  gives `type` only in a body that a test of `TYPE_CHECKING` controls.
- A target with statements of two forms has both forms.
- A call of `__import__`, of `importlib.import_module`, or of `import_module` after
  `from importlib import import_module` gives a record. A call of a different function,
  for example `import_string`, gives no record.
- Text that does not parse gives `import_forms.NONE`. A deep tree gives no
  RecursionError.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import config, extract, import_forms, python_calls, python_import_forms

PREFIXES = {"pkg"}
KNOWN = {"pkg", "pkg.a", "pkg.b", "pkg.c", "pkg.x"}


def forms(source: str) -> dict[str, tuple[str, ...]]:
    found = python_import_forms.import_facts(source, PREFIXES, KNOWN, "pkg.main")
    return dict(found.forms)


def dynamic(source: str) -> list[dict[str, object]]:
    found = python_import_forms.import_facts(source, PREFIXES, KNOWN, "pkg.main")
    return [dict(item) for item in found.dynamic]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import pkg.a\n", ("load",)),
        ("def f():\n    import pkg.a\n", ("call",)),
        ("class K:\n    def m(self):\n        import pkg.a\n", ("call",)),
        ("def f():\n    def g():\n        from pkg import a\n", ("call",)),
        ("class K:\n    import pkg.a\n", ("load",)),
        ("from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import pkg.a\n", ("type",)),
        ("import typing\nif typing.TYPE_CHECKING:\n    import pkg.a\n", ("type",)),
        ("from typing import TYPE_CHECKING as TC\nif TC:\n    import pkg.a\n", ("type",)),
        (
            "from typing_extensions import TYPE_CHECKING\nif TYPE_CHECKING:\n    import pkg.a\n",
            ("type",),
        ),
        ("if not TYPE_CHECKING:\n    pass\nelse:\n    import pkg.a\n", ("type",)),
        ("if not TYPE_CHECKING:\n    import pkg.a\n", ("load",)),
        ("if TYPE_CHECKING:\n    pass\nelse:\n    import pkg.a\n", ("load",)),
        ("if TYPE_CHECKING or flag:\n    import pkg.a\n", ("load",)),
        ("if TYPE_CHECKING:\n    def f():\n        import pkg.a\n", ("type",)),
        ("try:\n    import pkg.a\nexcept ImportError:\n    pass\n", ("load",)),
    ],
)
def test_the_form_of_one_import(source: str, expected: tuple[str, ...]) -> None:
    assert forms(source) == {"pkg.a": expected}


def test_a_target_with_two_forms_has_both_forms() -> None:
    source = "from pkg.a import x\nif TYPE_CHECKING:\n    from pkg.a import Y\n"
    assert forms(source) == {"pkg.a": ("load", "type")}


def test_the_stored_map_is_sparse_and_limited_to_uses() -> None:
    found = import_forms.ImportFacts(
        {"pkg.a": ("load",), "pkg.b": ("type", "load"), "pkg.c": ("call",)}, ()
    )
    assert import_forms.normal(found, {"pkg.a": ["*"], "pkg.b": ["*"]}) == {
        "pkg.b": ["load", "type"]
    }


def test_the_readers_of_a_record() -> None:
    record = {"uses": {"pkg.a": ["*"], "pkg.b": ["*"]}, "import_forms": {"pkg.b": ["type"]}}
    assert import_forms.forms(record, "pkg.a") == ("load",)
    assert import_forms.runtime(record, "pkg.a") and not import_forms.runtime(record, "pkg.b")
    assert import_forms.runtime(None, "pkg.b")
    assert not import_forms.deferred(record, "pkg.a")
    assert import_forms.deferred({**record, "import_forms": {"pkg.a": ["call"]}}, "pkg.a")
    # A key that is not in `uses` is ignored.
    assert import_forms.forms({**record, "uses": {}}, "pkg.b") == ("load",)


def test_imports_by_a_string_value() -> None:
    source = (
        "import importlib\n"
        "from importlib import import_module\n"
        'importlib.import_module("pkg.x")\n'
        "__import__(name)\n"
        'import_module("other.y")\n'
    )
    assert dynamic(source) == [
        {"call": "import_module", "text": "pkg.x", "target": "pkg.x", "line": 3},
        {"call": "__import__", "text": "", "target": "", "line": 4},
        {"call": "import_module", "text": "other.y", "target": "", "line": 5},
    ]


def test_a_call_of_a_different_function_gives_no_record() -> None:
    source = 'from django.utils.module_loading import import_string\nimport_string("pkg.x")\n'
    assert dynamic(source) == []
    assert dynamic('import_module("pkg.x")\n') == []


def test_text_that_does_not_parse_gives_no_facts() -> None:
    assert python_import_forms.import_facts("def (:\n", PREFIXES, KNOWN) == import_forms.NONE


def test_a_deep_tree_gives_no_recursion_error() -> None:
    """A tree of 3000 levels. The parser refuses such a text, so the test builds the tree."""
    where = {"lineno": 1, "col_offset": 0}
    body: list[ast.stmt] = [ast.Import(names=[ast.alias(name="pkg.a", **where)], **where)]
    for _ in range(3000):
        body = [ast.If(test=ast.Name(id="flag", **where), body=body, orelse=[], **where)]
    tree = ast.Module(body=body, type_ignores=[])
    found = python_import_forms.tree_facts(tree, PREFIXES, KNOWN, "pkg.main")
    assert found.forms == {"pkg.a": ("load",)}
    # A deep text: the parser of some Python versions refuses it. Then the facts are empty.
    deep = "x = " + "+".join(["1"] * 3000) + "\n" + "import pkg.a\n"
    assert forms(deep) in ({}, {"pkg.a": ("load",)})
    assert forms("x = " + "(" * 3000 + ")" * 3000 + "\n") == {}


def test_extraction_writes_the_keys_only_when_they_have_values(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "python"\n[package_roots]\n"pkg" = "pkg"\n',
            "pkg/__init__.py": "",
            "pkg/a.py": "X = 1\n",
            "pkg/b.py": "from pkg import a\n",
            "pkg/c.py": (
                "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from pkg import a\n"
                'import importlib\nimportlib.import_module("pkg.b")\n'
            ),
        },
    )
    facts = extract.build(config.load(tmp_path))
    assert facts["import_details"] == ["call", "dynamic", "type"]
    records = facts["components"]
    assert "import_forms" not in records["pkg.b"] and "dynamic_imports" not in records["pkg.b"]
    assert records["pkg.c"]["import_forms"] == {"pkg.a": ["type"]}
    assert records["pkg.c"]["dynamic_imports"] == [
        {"call": "import_module", "text": "pkg.b", "target": "pkg.b", "line": 5}
    ]
    # The new keys do not change `uses`.
    assert records["pkg.c"]["uses"] == {"pkg.a": ["*"]}


def test_a_depth_error_removes_both_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "python"\n[package_roots]\n"pkg" = "pkg"\n',
            "pkg/__init__.py": "",
            "pkg/a.py": "X = 1\n",
            "pkg/c.py": "def f():\n    from pkg import a\n__import__(name)\n",
        },
    )

    def deep(*args: object, **kwargs: object) -> import_forms.ImportFacts:
        raise RecursionError

    monkeypatch.setattr(python_import_forms, "import_facts", deep)
    record = extract.build(config.load(tmp_path))["components"]["pkg.c"]
    assert "import_forms" not in record and "dynamic_imports" not in record
    assert record["uses"] == {"pkg.a": ["*"]}


def test_a_depth_error_of_the_call_sites_also_removes_both_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "python"\n[package_roots]\n"pkg" = "pkg"\n',
            "pkg/__init__.py": "",
            "pkg/a.py": "X = 1\n",
            "pkg/c.py": "def f():\n    from pkg import a\n__import__(name)\n",
        },
    )

    def deep(*args: object, **kwargs: object) -> None:
        raise RecursionError

    monkeypatch.setattr(python_calls, "call_sites", deep)
    record = extract.build(config.load(tmp_path))["components"]["pkg.c"]
    assert "import_forms" not in record and "dynamic_imports" not in record
    assert record["unknown"][-1]["cause"] == "depth"
