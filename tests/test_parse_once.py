"""One extraction parses each Python module text one time, and a large file is not read.

Before this change, one extraction parsed each module text about ten times, and the
`__main__` alias step parsed the target module again for each use. Before the change, the
extraction of a 6 MB module took 158 s and 3.1 GB, and 2000 `__main__` uses took 49 s.
These tests count the work. They do not measure time.
"""

from __future__ import annotations

import ast
import collections
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import TINY_PACKAGE, write_tree

from systemap import (
    config,
    extract,
    python_entry,
    python_tree,
    source_facts,
    source_text,
    unknown_causes,
)

USES = 60

ALIAS_TREE = {
    **TINY_PACKAGE,
    "pyproject.toml": """
        [project]
        name = "pkg"
        version = "0.1"

        [project.scripts]
        pkg = "pkg.cli:main"
    """,
    "pkg/cli.py": """
        from pkg.tools import main
    """,
    "pkg/tools.py": "\n".join(
        ["import argparse", "", "def main():", "    pass", ""]
        + [f"def f{i}():\n    pass\n" for i in range(USES)]
    ),
    # The `__main__` module uses names that `pkg.api` imports. Thus the alias step reads the
    # module-level bindings of `pkg.api` for each use.
    "pkg/api.py": "from pkg.tools import " + ", ".join(f"f{i}" for i in range(USES)) + "\n",
    "pkg/__main__.py": "\n".join(
        [
            "from pkg.tools import main",
            "from pkg.api import " + ", ".join(f"f{i}" for i in range(USES)),
        ]
        + [f"f{i}()" for i in range(USES)]
        + ["main()", ""]
    ),
}


@pytest.fixture
def parses(monkeypatch: pytest.MonkeyPatch) -> Iterator[collections.Counter[str]]:
    """Count each call of `ast.parse` for a module text, with an empty tree cache."""
    calls: collections.Counter[str] = collections.Counter()
    real = ast.parse

    def counting(source: Any, *args: Any, **kwargs: Any) -> Any:
        if kwargs.get("mode", "exec") == "exec" and not args[1:] and isinstance(source, str):
            calls[source] += 1
        return real(source, *args, **kwargs)

    python_tree.clear()
    monkeypatch.setattr(ast, "parse", counting)
    yield calls
    python_tree.clear()


def _module_texts(root: Path, facts: dict[str, Any]) -> dict[str, str]:
    return {
        module: source_text.read(root, root / record["file"])
        for module, record in facts["components"].items()
    }


def test_one_extraction_parses_each_module_text_one_time(
    tmp_path: Path, parses: collections.Counter[str]
) -> None:
    write_tree(tmp_path, ALIAS_TREE)
    facts = extract.build(config.load(tmp_path))
    counts = {module: parses[text] for module, text in _module_texts(tmp_path, facts).items()}
    # Before the change, each module text had 9 or 10 parses.
    assert counts == dict.fromkeys(counts, 1)
    main_module = next(p for p in facts["entry_points"] if p["kind"] == "main_module")
    assert main_module["same_as"], "the alias step still finds the console script"


def test_the_main_alias_step_reads_each_module_one_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_tree(tmp_path, ALIAS_TREE)
    reads: list[str] = []
    real = python_entry._module_bindings

    def counting(*args: Any) -> Any:
        reads.append(args[0])
        return real(*args)

    monkeypatch.setattr(python_entry, "_module_bindings", counting)
    facts = extract.build(config.load(tmp_path))
    main_module = next(p for p in facts["entry_points"] if p["kind"] == "main_module")
    script = next(p for p in facts["entry_points"] if p["kind"] == "console_script")
    assert main_module["same_as"] == source_facts.entry_identity(script)
    # Before the change, the step read the target module again for each of the USES uses.
    assert len(reads) == len(set(reads)) <= len(facts["components"])


def test_a_file_larger_than_the_limit_gives_a_size_record_and_no_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parses: collections.Counter[str]
) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    big = "x = 1\n" * 1000
    assert all(len(text) < len(big) for text in TINY_PACKAGE.values())
    (tmp_path / "pkg" / "big.py").write_text(big, encoding="utf-8")
    monkeypatch.setattr(source_text, "MAX_BYTES", len(big) - 1)
    facts = extract.build(config.load(tmp_path))
    record = facts["components"]["pkg.big"]
    assert record["parse_error"]["cause"] == unknown_causes.SIZE
    assert record["parse_error"]["reason"] == (
        "source could not be read: the file is larger than the source size limit"
    )
    assert record["completeness"]["parsed"] is False
    assert parses[big] == 0
    assert facts["components"]["pkg.reader"]["completeness"]["parsed"] is True


def test_a_file_at_the_limit_is_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # write_bytes keeps the size at 6 bytes. write_text writes "\r\n" on Windows.
    (tmp_path / "a.py").write_bytes(b"x = 1\n")
    monkeypatch.setattr(source_text, "MAX_BYTES", 6)
    assert source_text.read(tmp_path, tmp_path / "a.py") == "x = 1\n"
    monkeypatch.setattr(source_text, "MAX_BYTES", 5)
    text, problems = source_text.read_problems(tmp_path / "a.py", tmp_path)
    assert (text, [cause for _reason, cause in problems]) == ("", [unknown_causes.SIZE])


def test_the_limit_is_larger_than_the_largest_measured_source_file() -> None:
    # 7615641 bytes: the largest Python file that the measurement found (a generated
    # file of the Google Cloud SDK). The limit is a guard, not a capacity measurement.
    assert source_text.MAX_BYTES > 2 * 7615641


def test_the_cache_gives_the_same_tree_and_the_same_error(monkeypatch: pytest.MonkeyPatch) -> None:
    python_tree.clear()
    first = python_tree.parse("a = 1\n")
    assert python_tree.parse("a = 1\n") is first
    with pytest.raises(SyntaxError) as one:
        python_tree.parse("def (:\n")
    with pytest.raises(SyntaxError) as two:
        python_tree.parse("def (:\n")
    assert one.value.lineno == two.value.lineno == 1
    # Each of the two texts gives a tree of 5 nodes. Thus the second tree goes above 8.
    monkeypatch.setattr(python_tree, "KEPT", 8)
    python_tree.clear()
    kept = python_tree.parse("b = 2\n")
    python_tree.parse("c = 3\n")
    again = python_tree.parse("b = 2\n")
    assert again is not kept, "the cache removed the oldest tree"
    assert ast.dump(again) == ast.dump(kept)
    python_tree.clear()


def test_walk_gives_the_nodes_in_the_order_of_ast_walk() -> None:
    python_tree.clear()
    text = "import a\n\ndef f(x):\n    return a.g(x)\n"
    cached = python_tree.parse(text)
    first = python_tree.walk(cached)
    assert [type(n) for n in first] == [type(n) for n in ast.walk(ast.parse(text))]
    assert python_tree.walk(cached) is first, "the cache keeps the node list"
    other = ast.parse(text)
    assert list(python_tree.walk(other)) == list(ast.walk(other))
    python_tree.clear()


def test_the_syntax_digest_does_not_change_the_shared_tree() -> None:
    tree = ast.parse("def f(x: int) -> int:\n    return x\n\nclass C:\n    pass\n")
    before = ast.dump(tree, include_attributes=True)
    extract._dump_python_syntax(tree)
    assert ast.dump(tree, include_attributes=True) == before
    assert not any("_fields" in vars(node) for node in ast.walk(tree))


def test_the_limit_counts_nodes_not_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    # The text has 1006 characters and 5 nodes. Before the review fix, the limit counted
    # characters, and the cache did not keep this tree.
    monkeypatch.setattr(python_tree, "KEPT", 20)
    python_tree.clear()
    text = "a = '" + "x" * 1000 + "'\n"
    assert python_tree.parse(text) is python_tree.parse(text)
    python_tree.clear()


def test_a_tree_larger_than_the_limit_is_removed_before_the_next_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance (review fix): two trees larger than the limit are not kept at one time.

    Before the review fix, the cache kept 4 trees of 1 Mi nodes each. The extraction of
    4 modules of 256Ki lines then used 2527 MB, and the base used 1211 MB.
    """
    monkeypatch.setattr(python_tree, "KEPT", 3)
    python_tree.clear()
    large = python_tree.parse("b = 2\n")
    assert python_tree.parse("b = 2\n") is large, "the cache keeps the large tree"
    kept_at_parse: list[int] = []
    real = python_tree._parse

    def counting(raw: str) -> Any:
        kept_at_parse.append(len(python_tree._trees))
        return real(raw)

    monkeypatch.setattr(python_tree, "_parse", counting)
    python_tree.parse("c = 3\n")
    assert kept_at_parse == [0]
    python_tree.clear()


def test_the_extraction_removes_its_trees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parses: collections.Counter[str]
) -> None:
    """Acceptance (review fix): the cache holds 0 trees after an extraction, also after a
    failed extraction. Before the review fix, it held all the trees (162 for systemap)."""
    write_tree(tmp_path, ALIAS_TREE)
    cfg = config.load(tmp_path)
    extract.build(cfg)
    assert sum(parses.values()) > 0
    assert len(python_tree._trees) == 0

    def fail(*args: Any) -> Any:
        raise RuntimeError("stop")

    monkeypatch.setattr(extract.PythonLanguage, "entry_points", fail)
    with pytest.raises(RuntimeError):
        extract.build(cfg)
    assert len(python_tree._trees) == 0
