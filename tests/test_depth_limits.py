"""A source file with too many syntax levels does not stop the extraction.

Findings g1full-3, exec-3, and g1ts-4 of the audit. Before the change, the TypeScript
call-site reader walked up the tree for each name, and built each property chain name
again for each link. `call_sites` took 81.5 s for a module with 20 chains of 800 links. A deep tree
gave RecursionError, and this error stopped the extraction of all modules.

Acceptance (written before the change):

- The 20 files of 1.8 KB of the audit take less than 2 s in `systemap extract`. The
  measured time before the change was 120.7 s on this host. After it, 0.8 s.
- Each deep fixture of the audit gives exit code 0. A deep module stays in the facts as
  a parsed record or as an unknown record with the cause `depth`.
- The facts of this repository do not change.

The tests do not measure a tight time. The one time bound is ten times the expected time.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import (
    config,
    extract,
    python_tests,
    python_tree,
    typescript,
    typescript_calls,
    typescript_package_imports,
    typescript_tests,
    unknown_causes,
)
from systemap.typescript_scopes import pattern_names
from systemap.typescript_surface import parse_surface as ts_surface
from systemap.typescript_syntax import _tree

PYTHON = {
    "systemap.toml": 'language = "python"\n[package_roots]\n"pkg" = "pkg"\n',
    "pkg/__init__.py": '"""A package."""\n',
    "pkg/good.py": '"""A good module."""\n\nfrom pkg import deep\n\n\ndef run() -> int:\n'
    "    return deep.X\n",
}
TYPESCRIPT = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": '{"name":"web"}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "src/o.ts": "export const y = { p: 1 };\n",
    "src/good.ts": 'import { y } from "./o";\nexport const g = y.p;\n',
}


def _chain(links: int, statements: int = 1) -> str:
    return 'import { y } from "./o";\n' + "".join(
        f"export const q{index} = y" + ".p" * links + ";\n" for index in range(statements)
    )


def _sites(raw: str) -> list[dict[str, Any]]:
    found = typescript_calls.call_sites(raw, "src/a.ts", "web.a", lambda source: "web.o")
    assert found is not None
    return found


def _facts(tmp_path: Path, files: dict[str, str]) -> dict[str, Any]:
    write_tree(tmp_path, files)
    return extract.build(config.load(tmp_path))


def test_the_chain_names_take_work_in_proportion_to_the_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Before the change, a chain of 400 links gave 81004 calls of `_text`, one call for
    # each link below each link. After it, the count is 404: one call for each link.
    calls = [0]
    text = typescript_calls._text

    def counted(node: Any) -> str:
        calls[0] += 1
        return text(node)

    monkeypatch.setattr(typescript_calls, "_text", counted)
    sites = _sites(_chain(400))
    assert calls[0] < 10 * 400
    assert [(s["local"], s["uses"]) for s in sites] == [("y", [[2, 0, "p"]]), ("q0", [])]


def test_many_long_chains_do_not_take_a_long_time() -> None:
    # Before the change, `call_sites` took 122.6 s for this module (30 chains of 800
    # links). After the change, it takes 0.3 s. The bound is 10 s.
    start = time.monotonic()
    sites = _sites(_chain(800, 30))
    assert time.monotonic() - start < 10
    assert len(sites) == 31


def test_a_chain_above_the_limit_has_no_name_but_its_head_is_a_use() -> None:
    # Before the change, a chain of 5000 links gave RecursionError.
    sites = _sites(_chain(5000))
    assert sites[0]["local"] == "y"
    assert sites[0]["uses"] == [[2, 0, "p"]]
    # The value of `q0` has more than MAX_LINKS links. Thus it is not a binding.
    assert [s["local"] for s in sites] == ["y"]
    limit = typescript_calls.MAX_LINKS
    assert [s["local"] for s in _sites(_chain(limit))] == ["y", "q0"]


def test_many_deep_uses_of_one_name_do_not_walk_the_tree_again() -> None:
    # Before the change, `y + y + ... ` with 20000 terms gave RecursionError. With the
    # stack walk but without the kept scopes, each use walked to the root again. Then
    # `systemap extract` took 88.6 s for this module. After the change, it takes 1.1 s.
    raw = 'import { y } from "./o";\nexport const q = ' + "y + " * 20000 + "1;\n"
    start = time.monotonic()
    sites = _sites(raw)
    assert time.monotonic() - start < 30
    assert len(sites[0]["uses"]) == 1  # All uses are on line 2.


def test_an_inner_declaration_still_hides_a_deep_use() -> None:
    raw = (
        'import { y } from "./o";\n'
        "export function f(y: number) { return " + "(" * 3000 + "y" + ")" * 3000 + "; }\n"
        "export function g() { return " + "(" * 3000 + "y" + ")" * 3000 + "; }\n"
    )
    sites = _sites(raw)
    assert sites[0]["local"] == "y"
    assert sites[0]["uses"] == [[3, 3, ""]]


def test_deep_typescript_walks_do_not_give_recursion_error() -> None:
    depth = 5000
    array = "export const v = " + "[" * depth + "]" * depth + ";\n"
    assert ts_surface(array, "a.ts") is not None
    tokens = list(typescript._syntax_tokens(_tree(array, "a.ts")))
    assert len(tokens) == 2 * depth + 5
    suites = "describe('a', () => {" * depth + "test('t', () => {});" + "});" * depth
    names = typescript_tests.test_names(suites, "a.test.ts")
    assert names == [" > ".join(["a"] * depth + ["t"])]
    pattern = "const " + "[" * depth + "a" + "]" * depth + " = [];\n"
    declarator = next(
        node
        for node in typescript._walk(_tree(pattern, "a.ts"))
        if node.type == "variable_declarator"
    )
    assert pattern_names(declarator.child_by_field_name("name")) == ["a"]


def test_a_deep_package_exports_value_gives_its_target() -> None:
    # Before the change, an `exports` array 400 deep gave RecursionError.
    table = {"./b": "./src/b.js"}
    value: Any = "./src/b.js"
    for _ in range(5000):
        value = [value]
    table["./c"] = value
    conditions = frozenset({"import", "default"})
    assert typescript_package_imports._match("./c", table, conditions) == "./src/b.js"
    # A null in a condition object stops that object and the objects that contain it. A
    # list then tries its next entry.
    blocked = {"import": None, "default": "./x.js"}
    match = typescript_package_imports._match
    assert match("./d", {"./d": [blocked, "./y.js"]}, conditions) == "./y.js"
    assert match("./d", {"./d": {"import": blocked, "default": "./z.js"}}, conditions) is None
    assert match("./d", {"./d": {"import": [blocked], "default": "./z.js"}}, conditions) == (
        "./z.js"
    )
    assert match("./d", {"./d": {"import": [[None]], "default": "./z.js"}}, conditions) == (
        "./z.js"
    )


@pytest.mark.parametrize("terms", [1000, 200000])
def test_a_deep_python_module_gives_a_depth_record(tmp_path: Path, terms: int) -> None:
    # Before the change, 1000 terms gave RecursionError in `ast.dump`, and 200000 terms
    # gave RecursionError in `ast.parse`. The extraction then stopped.
    files = {**PYTHON, "pkg/deep.py": "X = " + "1+" * terms + "1\n"}
    facts = _facts(tmp_path, files)
    deep = facts["components"]["pkg.deep"]
    assert deep["completeness"]["parsed"] is False
    assert deep["completeness"]["cause"] == unknown_causes.DEPTH
    assert deep["parse_error"]["reason"] == unknown_causes.DEPTH_REASON
    assert deep["names"] == []
    good = facts["components"]["pkg.good"]
    assert good["completeness"]["parsed"] is True
    assert good["uses"] == {"pkg.deep": ["*"]}


def test_a_refused_python_text_has_no_tree_until_clear() -> None:
    raw = "def f():\n    return " + "1+" * 1000 + "1\n"
    assert python_tree.tree(raw) is not None
    python_tree.refuse(raw)
    assert python_tree.tree(raw) is None
    with pytest.raises(python_tree.TooDeep):
        python_tree.parse(raw)
    python_tree.clear()
    assert python_tree.tree(raw) is not None
    python_tree.clear()


def test_the_python_adapter_gives_no_surface_and_no_tests_for_a_deep_text() -> None:
    raw = "def test_a():\n    assert " + "1+" * 1000 + "1\n"
    assert extract.PYTHON.parse_surface("X = " + "1+" * 1000 + "1\n") is None
    assert python_tests.test_names(raw) == []
    assert python_tests.test_names("def test_a():\n    pass\n") == ["test_a"]


def test_a_deep_python_test_file_gives_a_test_file_record(tmp_path: Path) -> None:
    files = {
        **PYTHON,
        "pkg/deep.py": "X = 1\n",
        "tests/test_deep.py": "import pkg.good\n\n\ndef test_a():\n    assert "
        + "1+" * 1000
        + "1\n",
        "tests/test_good.py": "import pkg.good\n\n\ndef test_b():\n    pass\n",
    }
    facts = _facts(tmp_path, files)
    issues = facts["test_file_issues"]
    assert [(i["file"], i["problem"]["cause"]) for i in issues] == [
        ("tests/test_deep.py", unknown_causes.DEPTH)
    ]
    assert facts["components"]["pkg.good"]["tests"] == ["tests/test_good.py::test_b"]


def _deep(raw: str, path: str = "") -> Any:
    if "deep" in path or "deep" in raw:
        raise RecursionError("maximum recursion depth exceeded")
    return original_surface(raw, path)


original_surface = typescript.parse_surface


def test_a_typescript_surface_error_gives_a_depth_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The new walks of the TypeScript reader use a stack. A later step that gives
    # RecursionError gives the same record. The test injects this error.
    monkeypatch.setattr(typescript, "parse_surface", _deep)
    files = {**TYPESCRIPT, "src/deep.ts": "export const deep = 1;\n"}
    facts = _facts(tmp_path, files)
    deep = facts["components"]["web.deep"]
    assert deep["completeness"]["cause"] == unknown_causes.DEPTH
    assert deep["unknown"][0]["reason"] == unknown_causes.DEPTH_REASON
    assert facts["components"]["web.good"]["completeness"]["parsed"] is True
    assert typescript.TYPESCRIPT.parse_surface("const deep = 1;\n", "a.ts") is None


def test_a_typescript_test_error_gives_a_test_file_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def names(raw: str, path: str = "") -> list[str]:
        if path.endswith("deep.test.ts"):
            raise RecursionError("maximum recursion depth exceeded")
        return ["t"]

    monkeypatch.setattr(typescript, "test_names", names)
    files = {
        **TYPESCRIPT,
        "tests/deep.test.ts": 'import { g } from "../src/good";\ntest("t", () => g);\n',
        "tests/good.test.ts": 'import { g } from "../src/good";\ntest("t", () => g);\n',
    }
    facts = _facts(tmp_path, files)
    assert [(i["file"], i["problem"]["cause"]) for i in facts["test_file_issues"]] == [
        ("tests/deep.test.ts", unknown_causes.DEPTH)
    ]
    assert facts["components"]["web.good"]["tests"] == ["tests/good.test.ts::t"]
    monkeypatch.setattr(typescript, "test_names", _deep)
    assert typescript.TYPESCRIPT.test_names("deep", "a.test.ts") == []


@pytest.mark.parametrize("step", ["internal_uses", "call_sites"])
def test_a_later_step_error_gives_a_depth_record_for_that_module_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    target = extract if step == "internal_uses" else extract.python_calls
    original = getattr(target, step)

    def failing(raw: str, *args: Any, **kwargs: Any) -> Any:
        if "DEEP" in raw:
            raise RecursionError("maximum recursion depth exceeded")
        return original(raw, *args, **kwargs)

    monkeypatch.setattr(target, step, failing)
    facts = _facts(tmp_path, {**PYTHON, "pkg/deep.py": "DEEP = 1\n"})
    deep = facts["components"]["pkg.deep"]
    assert deep["completeness"]["cause"] == unknown_causes.DEPTH
    assert deep["completeness"]["unresolved_imports"] is None
    assert deep["unknown"] == [
        {"line": 0, "reason": unknown_causes.DEPTH_REASON, "cause": unknown_causes.DEPTH}
    ]
    assert deep["call_sites"] is None
    assert facts["components"]["pkg.good"]["completeness"]["parsed"] is True
    assert facts["components"]["pkg.good"]["call_sites"] is not None


def test_the_depth_cause_has_a_fix_line() -> None:
    assert unknown_causes.DEPTH in unknown_causes.CAUSES
    lines = unknown_causes.fix_lines([unknown_causes.DEPTH])
    assert lines == [f"  fix: {unknown_causes.FIX[unknown_causes.DEPTH]}"]
