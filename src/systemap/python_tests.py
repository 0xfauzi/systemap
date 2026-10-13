"""Find the Python test files and the modules that their test functions use.

A test file is a `test_*.py` file in a test directory, or a `.py` file that a configured
test pattern selects. A test function refers to a module if its file imports the module.
A test file that cannot be read or parsed gives a `test_file_issues` record. The record
has the same fields as the record of the TypeScript adapter. The test functions of that
file are not known.
"""

from __future__ import annotations

import ast
import os
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap import python_calls, python_repo, unknown_causes
from systemap.pattern_match import matches_test_pattern
from systemap.source_text import read_problems

EXCERPT = 120


@dataclass
class PythonTests:
    """The test patterns of one extraction, and the test files that have a problem."""

    test_patterns: tuple[str, ...] = ()
    test_issues: list[dict[str, Any]] = field(default_factory=list)


def is_test_file(path: str, tests_dirs: tuple[str, ...], test_patterns: tuple[str, ...]) -> bool:
    """Give `True` for the repository-relative `.py` path of a test file."""
    if not path.endswith(".py"):
        return False
    if matches_test_pattern(path, test_patterns):
        return True
    if not path.split("/")[-1].startswith("test_"):
        return False
    return any(rel and path.startswith(rel.rstrip("/") + "/") for rel in tests_dirs)


def test_files(repo: Path, tests_dirs: tuple[str, ...], patterns: tuple[str, ...]) -> list[Path]:
    """List the test files: the test directories first, then the test pattern files."""
    files = list(dict.fromkeys(_directory_files(repo, tests_dirs)))
    if patterns:
        seen = set(files)
        files += [
            path
            for path in _python_files(repo)
            if path not in seen
            and matches_test_pattern(path.relative_to(repo).as_posix(), patterns)
        ]
    return files


def _directory_files(repo: Path, tests_dirs: tuple[str, ...]) -> Iterator[Path]:
    for rel in tests_dirs:
        test_dir = repo / rel
        if not rel or not test_dir.is_dir():
            continue
        # The walk does not go into the skipped folders. The sort keeps the order of
        # the earlier `rglob` result: a path order, not the order of the walk.
        yield from sorted(python_repo.python_paths(test_dir, "test_*.py"))


def _python_files(repo: Path) -> Iterator[Path]:
    """Give the `.py` files of the repository in a stable sequence, without skipped folders."""
    for current, names, files in os.walk(repo):
        names[:] = sorted(name for name in names if name not in python_repo.PYTHON_SKIP)
        for name in sorted(files):
            if name.endswith(".py"):
                yield Path(current, name)


def test_names(raw: str) -> list[str]:
    """Get test function identities, including their enclosing definitions."""
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return []
    return _names(tree)


def _names(tree: ast.AST) -> list[str]:
    found: list[str] = []

    def visit(node: ast.AST, parents: tuple[str, ...]) -> None:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            parents = (*parents, node.name)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "test_"
            ):
                found.append(".".join(parents))
        for child in ast.iter_child_nodes(node):
            visit(child, parents)

    visit(tree, ())
    return found


def _issue(relative: str, line: int, problem: tuple[str, str], source: str = "") -> dict[str, Any]:
    reason, cause = problem
    record = {"line": line, "reason": reason, "source": source, "cause": cause}
    return {"file": relative, "problem": record}


def _parse_test(repo: Path, path: Path, issues: list[dict[str, Any]]) -> ast.Module | None:
    """Read and parse one test file. A problem goes to `issues`, and the result is None."""
    relative = path.relative_to(repo).as_posix()
    try:
        raw, problems = read_problems(path, repo)
    except OSError as exc:
        raw, problems = "", [unknown_causes.read_problem(exc)]
    if problems:
        issues.append(_issue(relative, 0, problems[0]))
        return None
    try:
        return ast.parse(raw)
    except (SyntaxError, ValueError) as exc:
        line = getattr(exc, "lineno", 0) or 0
        excerpt = " ".join(str(getattr(exc, "text", "") or "").split())[:EXCERPT]
        reason = f"source could not be parsed: {type(exc).__name__}"
        issues.append(_issue(relative, line, (reason, unknown_causes.SYNTAX), excerpt))
        return None


def collect_tests(
    repo: Path,
    tests_dirs: tuple[str, ...],
    prefixes: set[str],
    known: set[str],
    tests: PythonTests,
) -> dict[str, list[dict[str, Any]]]:
    """Give the test functions that refer to each imported module.

    Each test name includes the file and the enclosing definitions. An import does not
    show that a test examines the module.
    """
    guards: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in test_files(repo, tests_dirs, tests.test_patterns):
        tree = _parse_test(repo, path, tests.test_issues)
        if tree is not None:
            for target, entries in _references(repo, path, tree, prefixes, known).items():
                guards[target].extend(entries)
    return guards


def _references(
    repo: Path, path: Path, tree: ast.Module, prefixes: set[str], known: set[str]
) -> dict[str, list[dict[str, Any]]]:
    """Give the test functions of one parsed test file, for each imported module."""
    targets = {
        target
        for _node, _local, target, _name, _line in python_calls.import_targets(
            tree, prefixes, known
        )
    }
    names = _names(tree) if targets else []
    stem = path.stem[5:] if path.stem.startswith("test_") else path.stem
    relative = path.relative_to(repo).as_posix()
    # A test file named after the module is its primary guard. A file that only imports
    # the module also uses it. The difference stops a shared helper from a claim on each
    # test.
    return {
        target: [
            {"name": f"{relative}::{name}", "primary": stem == target.split(".")[-1]}
            for name in names
        ]
        for target in targets
    }
