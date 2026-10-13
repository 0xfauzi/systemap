"""Repairs of the Codex results for the Python adapter (adapters-2, -3, -5, -6).

Each test gives the same condition to the Python adapter and to the TypeScript adapter
where the behavior applies to the two languages. Each acceptance value is in the docstring of its
test. Each Python assertion was not satisfied on the commit d4b1514.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree

from systemap import change, config, extract, nest, source_facts
from systemap.cli import main
from systemap.typescript import TYPESCRIPT

TS_FIXTURE = Path(__file__).parent / "fixtures" / "typescript-app"
PY_TREE = {
    "systemap.toml": 'language = "python"\n',
    "pyproject.toml": '[project]\nname = "shop"\nversion = "1"\n',
    "src/shop/__init__.py": "",
    "src/shop/store.py": "def save() -> None:\n    pass\n",
}
TS_TREE = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": '{"name":"web"}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "src/store.ts": "export function save(): void {}\n",
}


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return proc.stdout.strip()


def facts_of(root: Path, tree: dict[str, str]) -> dict[str, Any]:
    write_tree(root, tree)
    return extract.build(config.load(root))


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


# ---- adapters-2: a package marker holds no statements -----------------------------


def test_an_executable_package_initializer_is_not_an_empty_marker(tmp_path: Path) -> None:
    """Acceptance: a package initializer with a private assignment of a function result is
    not an empty marker in 2 of 2 languages. A Python initializer with only a docstring and
    a `__future__` import is an empty marker. A TypeScript index file with only a comment is
    also an empty marker."""
    py = facts_of(
        tmp_path / "py",
        {
            **PY_TREE,
            "src/shop/state/__init__.py": '_state = open("state.json").read()\n',
            "src/shop/doc/__init__.py": '"""A marker."""\n\nfrom __future__ import annotations\n',
        },
    )["components"]
    ts = facts_of(
        tmp_path / "ts",
        {
            **TS_TREE,
            "src/state/index.ts": 'const state = JSON.parse("{}");\n',
            "src/doc/index.ts": "// A marker.\n",
        },
    )["components"]
    assert py["shop.state"]["empty_marker"] is False
    assert ts["web.state.index"]["empty_marker"] is False
    assert py["shop.doc"]["empty_marker"] is True
    assert ts["web.doc.index"]["empty_marker"] is True


# ---- adapters-3: test_patterns have the same meaning for each language --------------


def test_python_test_patterns_select_test_files_for_extract_and_delta(tmp_path: Path) -> None:
    """Acceptance: with `test_patterns = ["checks/*.py", "pkg/*_check.py"]`, the test in
    `checks/reader_check.py` refers to `pkg.reader`. `pkg/writer_check.py` is not a module.
    `delta` gives the added test of the configured file."""
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
            "pkg/writer_check.py": (
                "from pkg.writer import write\n\n\ndef test_writes() -> None:\n"
                "    assert write('a') == 'a'\n"
            ),
            "checks/reader_check.py": (
                "from pkg.reader import read\n\n\ndef test_reads() -> None:\n"
                "    assert read('a') == 'a'\n"
            ),
        },
    )
    init_two_cards(tmp_path, "--no-ci")
    settings = tmp_path / "systemap.toml"
    settings.write_text(
        'test_patterns = ["checks/*.py", "pkg/*_check.py"]\n'
        + settings.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    git(tmp_path, "init", "-q", "-b", "main")
    base = commit(tmp_path, "base")
    reader_check = tmp_path / "checks/reader_check.py"
    reader_check.write_text(
        reader_check.read_text(encoding="utf-8")
        + "\n\ndef test_reads_again() -> None:\n    assert read('b') == 'b'\n",
        encoding="utf-8",
    )
    commit(tmp_path, "add a configured test")

    cfg = config.load(tmp_path)
    facts = extract.build(cfg)
    components = facts["components"]
    assert "pkg.writer_check" not in components
    assert "checks/reader_check.py::test_reads" in components["pkg.reader"]["tests"]
    assert "pkg/writer_check.py::test_writes" in components["pkg.writer"]["tests"]
    found = change.compute(cfg, nest.load(cfg).top.model, base, facts)
    assert found["per_component"]["Reader"]["surface"]["tests_added"] == [
        "checks/reader_check.py::test_reads_again"
    ]


def test_typescript_test_patterns_select_a_test_file_outside_the_source_root(
    tmp_path: Path,
) -> None:
    """Acceptance: with `test_patterns = ["checks/*.ts"]`, the test in
    `checks/service_check.ts` refers to `acme.web.service`. This test is the
    TypeScript version of the Python test above."""
    shutil.copytree(TS_FIXTURE, tmp_path, dirs_exist_ok=True)
    settings = tmp_path / "systemap.toml"
    settings.write_text(
        'test_patterns = ["checks/*.ts"]\n' + settings.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    write_tree(
        tmp_path,
        {
            "checks/service_check.ts": (
                'import { serve } from "../src/service";\n'
                'test("checks service", () => serve("one"));\n'
            )
        },
    )
    facts = extract.build(config.load(tmp_path))
    tests = facts["components"]["acme.web.service"]["tests"]
    assert "checks/service_check.ts::checks service" in tests


def test_the_two_adapters_give_a_pattern_the_same_meaning() -> None:
    """Acceptance: for 6 of 6 pairs of a pattern and a path, the Python adapter and the
    TypeScript adapter give the same test-file result."""
    cases = (
        ("checks/*", "checks/reader_check", True),
        ("checks/*", "checks/deep/reader_check", True),
        ("**/checks/*", "checks/reader_check", True),
        ("**/checks/*", "app/checks/reader_check", True),
        ("checks/*", "app/checks/reader_check", False),
        ("other/*", "checks/reader_check", False),
    )
    for pattern, path, expected in cases:
        python = extract.PYTHON.is_test_file(f"{path}.py", (), (f"{pattern}.py",))
        typescript = TYPESCRIPT.is_test_file(f"{path}.ts", (), (f"{pattern}.ts",))
        assert python == typescript == expected, (pattern, path)
    assert not extract.PYTHON.is_test_file("checks/reader_check.ts", (), ("checks/*",))


# ---- adapters-5: a test file that cannot be read or parsed is not known -------------


def test_a_test_file_that_cannot_be_read_or_parsed_gives_a_not_known_record(
    tmp_path: Path,
) -> None:
    """Acceptance: in 2 of 2 languages, a test file with a syntax error gives one
    `test_file_issues` record and one `unknown surface: test file` line, and no
    `source inventory unresolved` line (trial-1: the record does not reject the map). A
    test file that is not UTF-8 gives the same results."""
    bad_bytes = b"\xff\xfe\xfa"
    py_root, ts_root = tmp_path / "py", tmp_path / "ts"
    write_tree(py_root, {**PY_TREE, "tests/test_parse.py": "def test_x(:\n"})
    (py_root / "tests/test_bytes.py").write_bytes(bad_bytes)
    write_tree(ts_root, {**TS_TREE, "tests/parse.spec.ts": "it('x', () => {\n"})
    (ts_root / "tests/bytes.spec.ts").write_bytes(bad_bytes)
    for root, parse, unread in (
        (py_root, "tests/test_parse.py", "tests/test_bytes.py"),
        (ts_root, "tests/parse.spec.ts", "tests/bytes.spec.ts"),
    ):
        facts = extract.build(config.load(root))
        issues = {issue["file"]: issue["problem"] for issue in facts["test_file_issues"]}
        assert set(issues) == {parse, unread}, root
        assert issues[parse]["line"] == 1
        assert issues[unread]["reason"].startswith("source could not be read")
        assert set(issues[unread]) == {"line", "reason", "source", "cause"}
        # A parse record can also give the parser version (facts format 11).
        assert set(issues[parse]) - {"parser"} == set(issues[unread])
        assert source_facts.inventory_issue_lines(facts) == []
        lines = "\n".join(source_facts.unknown_fact_lines(facts))
        assert f"unknown surface: test file {parse}: " in lines
        assert f"unknown surface: test file {unread}: source could not be read" in lines


def test_python_facts_without_a_test_file_problem_have_no_issue_list(tmp_path: Path) -> None:
    """Acceptance: Python facts without a test-file problem do not have `test_file_issues`,
    as before the repair."""
    facts = facts_of(tmp_path, {**PY_TREE, "tests/test_store.py": "def test_x() -> None: ..."})
    assert "test_file_issues" not in facts


# ---- adapters-6: a decorator is part of the declaration fingerprint -----------------


def _changed(before: str, after: str, language: Any, path: str) -> dict[str, list[str]]:
    delta = change.surface_delta(before, after, language, path)
    assert delta is not None
    return {bucket: names for bucket, names in delta["changed"].items() if names}


def test_a_decorator_change_is_a_public_surface_change() -> None:
    """Acceptance: in 2 of 2 languages, the removal of a function or method decorator gives
    one changed public name. A function without a decorator keeps its fingerprint."""
    py_before = (
        "from contextlib import contextmanager\n\n\n@contextmanager\ndef opened(): yield 1\n\n\n"
        "class Store:\n    @staticmethod\n    def get() -> int:\n        return 1\n"
    )
    py_function = py_before.replace("@contextmanager\n", "")
    py_method = py_before.replace("    @staticmethod\n", "")
    assert _changed(py_before, py_function, extract.PYTHON, "a.py") == {"operations": ["opened"]}
    assert _changed(py_before, py_method, extract.PYTHON, "a.py") == {"types": ["Store"]}
    plain = extract.parse_surface("def save(x: int) -> None:\n    pass\n")
    assert plain is not None
    assert plain["api"][0]["fingerprint"] == "def save(x: int) -> None"

    ts_before = (
        "function cached(target: unknown, key: string) {}\n"
        "export class Store {\n  @cached\n  get(): number { return 1; }\n}\n"
    )
    ts_after = ts_before.replace("  @cached\n", "")
    assert _changed(ts_before, ts_after, TYPESCRIPT, "a.ts") == {"types": ["Store"]}


def test_the_dead_extract_helpers_are_gone() -> None:
    """Acceptance (adapters-27): `extract` has no `internal_imports`, `first_line`, or
    `sentence`. An examination of the repository text found no use of these functions."""
    for name in ("internal_imports", "first_line", "sentence"):
        assert not hasattr(extract, name), name


def test_the_check_reports_a_python_test_file_that_cannot_be_parsed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: `systemap refresh` and `systemap check` each exit 0 and name a Python
    test file with a syntax error (trial-1: the record does not reject the map)."""
    write_tree(tmp_path, {"pkg/__init__.py": "", "pkg/reader.py": "def read() -> None: ..."})
    write_tree(tmp_path, {"pkg/writer.py": "def write() -> None: ...", "tests/test_x.py": "("})
    init_two_cards(tmp_path, "--no-ci")
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert main(["--root", str(tmp_path), "check"]) == 0
    out = capsys.readouterr().out
    assert out.count("test file tests/test_x.py: source could not be parsed: SyntaxError") == 2


def test_one_module_holds_the_test_pattern_rule() -> None:
    """Acceptance: the `test_patterns` rule (`**/` also matches at the repository root) is
    in `pattern_match.py` only. Each adapter calls `matches_test_pattern`.
    """
    source = Path(__file__).resolve().parents[1] / "src" / "systemap"
    rule = 'pattern.replace("**/", "")'
    holders = sorted(p.name for p in source.glob("*.py") if rule in p.read_text(encoding="utf-8"))
    assert holders == ["pattern_match.py"]
