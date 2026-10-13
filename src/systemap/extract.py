"""Read source facts from the working tree.

Records contain module imports, public surface, owned types, errors, public names,
third-party imports, test references, and entry points. Test references do not
prove test coverage. The model module contains authored purpose statements.
The page uses different styles for source facts and authored meaning.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from systemap import (
    python_calls,
    python_entry,
    python_exports,
    python_repo,
    python_syntax,
    python_tests,
    repo_files,
    source_text,
    unknown_causes,
)
from systemap.completeness import parse_state

# The shared extraction steps are in `extraction`. These names stay for the callers of
# the earlier interface.
from systemap.extraction import FORMAT as FORMAT
from systemap.extraction import build as build
from systemap.extraction import drift as drift
from systemap.extraction import language_for as language_for
from systemap.extraction import mapping_drift as mapping_drift
from systemap.pattern_match import matches_test_pattern
from systemap.python_imports import python_unresolved
from systemap.python_repo import PythonRepository
from systemap.source_facts import standard_label

CONSTANTS_KEPT = 14
UPPER_NAME = re.compile(r"[A-Z][A-Z0-9_]{2,}")
PACKAGE_MODULE = "__init__.py"
# The `type X = ...` statement exists from Python 3.12. An earlier parser cannot read it.
TYPE_ALIAS: tuple[type, ...] = (ast.TypeAlias,) if hasattr(ast, "TypeAlias") else ()


class PythonLanguage(PythonRepository):
    """Read Python syntax through the language adapter interface."""

    def source_paths(
        self,
        root: Path,
        repo: Path,
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> Iterable[Path]:
        del tests_dirs
        return (
            path
            for path in python_repo.python_paths(root)
            if not matches_test_pattern(path.relative_to(repo).as_posix(), test_patterns)
        )

    def context(
        self,
        repo: Path,
        paths: dict[str, Path],
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> python_tests.PythonTests:
        del repo, paths, tests_dirs
        return python_tests.PythonTests(test_patterns)

    def module_of(self, path: Path, root: Path, name: str) -> str:
        return module_of(path, root, name)

    def package_of(self, path: Path, root: Path, name: str) -> str:
        """Give the parent package of the module. An `__init__.py` module is in the parent
        package of its own package. A package root gives its own name."""
        module = module_of(path, root, name)
        return module.rpartition(".")[0] or module

    def is_package_module(self, path: Path) -> bool:
        return path.name == PACKAGE_MODULE

    def empty_marker(self, record: Mapping[str, Any], raw: str) -> bool:
        """Find an `__init__.py` file with no statement that holds code.

        A file that was not read or parsed is not empty, because its statements are not
        known. `python_syntax.holds_no_code` gives the statements that hold no code."""
        if not str(record.get("file", "")).endswith(PACKAGE_MODULE):
            return False
        if not record.get("completeness", {}).get("parsed"):
            return False
        return python_syntax.holds_no_code(raw)

    def entry_label(self, point: Mapping[str, str]) -> str:
        return standard_label(point)

    def compiler_record(self, context: Any, repo: Path) -> dict[str, str]:
        del context, repo
        return {}

    def extra_facts(self, context: Any, entry_issues: list[dict[str, str]]) -> dict[str, Any]:
        """Give the issue lists. An empty issue list is not written."""
        test_issues = getattr(context, "test_issues", [])
        lists = {"entry_point_issues": entry_issues, "test_file_issues": test_issues}
        return {key: value for key, value in lists.items() if value}

    def module_for_path(self, repo: Path, path: str, roots: list[tuple[Path, str]]) -> str | None:
        if not path.endswith(".py"):
            return None
        absolute = repo / path
        for package, name in roots:
            if absolute.is_relative_to(package):
                return module_of(absolute, package, name)
        return None

    def collect_module(
        self,
        path: Path,
        repo: Path,
        module: str,
        prefixes: frozenset[str],
        known: set[str],
        paths: dict[str, Path],
        context: Any,
    ) -> dict[str, Any] | None:
        del known, paths, context
        return collect_module(path, repo, module, prefixes)

    def internal_uses(
        self,
        raw: str,
        prefixes: set[str],
        known: set[str],
        module: str = "",
        is_package: bool = False,
        repo: Path | None = None,
        paths: dict[str, Path] | None = None,
        context: Any = None,
    ) -> dict[str, set[str]]:
        del repo, paths, context
        return internal_uses(raw, prefixes, known, module, is_package)

    def call_sites(
        self,
        raw: str,
        module: str,
        prefixes: set[str],
        known: set[str],
        components: Mapping[str, Mapping[str, Any]],
        is_package: bool = False,
        paths: dict[str, Path] | None = None,
        context: Any = None,
    ) -> list[dict[str, Any]] | None:
        del paths, context
        return python_calls.call_sites(raw, prefixes, known, components, module, is_package)

    def unresolved_imports(
        self,
        raw: str,
        prefixes: set[str],
        known: set[str],
        module: str,
        repo: Path,
        paths: dict[str, Path],
        context: Any,
    ) -> list[str]:
        del repo, context
        is_package = self.is_package_module(paths[module])
        return python_unresolved(raw, prefixes, known, module, is_package)

    def external_imports(
        self,
        raw: str,
        prefixes: set[str],
        module: str = "",
        repo: Path | None = None,
        paths: dict[str, Path] | None = None,
        context: Any = None,
    ) -> list[str]:
        del module, repo, paths, context
        return external_imports(raw, prefixes)

    def collect_tests(
        self,
        repo: Path,
        tests_dirs: tuple[str, ...],
        prefixes: set[str],
        paths: dict[str, Path],
        context: Any,
    ) -> dict[str, list[dict[str, Any]]]:
        isolated = python_tests.PythonTests()
        tests = context if isinstance(context, python_tests.PythonTests) else isolated
        return python_tests.collect_tests(repo, tests_dirs, prefixes, set(paths), tests)

    def entry_points(
        self,
        repo: Path,
        prefixes: set[str],
        components: dict[str, Any],
        sources: dict[str, str],
        context: Any,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        del context
        issues = [
            issue
            for module, source in sources.items()
            for issue in python_entry.registration_candidates(module, source)
        ]
        return python_entry.entry_points(repo, prefixes, components, sources), issues

    def parse_surface(self, raw: str, path: str = "") -> dict[str, Any] | None:
        return parse_surface(raw)

    def test_names(self, raw: str, path: str = "") -> list[str]:
        return python_tests.test_names(raw)

    def is_test_file(
        self, path: str, tests_dirs: tuple[str, ...], test_patterns: tuple[str, ...] = ()
    ) -> bool:
        return python_tests.is_test_file(path, tests_dirs, test_patterns)


PYTHON = PythonLanguage()


def module_of(path: Path, pkg_dir: Path, pkg_name: str) -> str:
    rel = path.relative_to(pkg_dir).with_suffix("")
    parts = [p for p in rel.parts if p != "__init__"]
    return ".".join([pkg_name, *parts]) if parts else pkg_name


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        args = ast.unparse(node.args)
    except (AttributeError, ValueError):
        args = "..."
    ret = ""
    if node.returns is not None:
        try:
            ret = f" -> {ast.unparse(node.returns)}"
        except (AttributeError, ValueError):
            ret = ""
    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    return f"{prefix}{node.name}({args}){ret}"


def opening(text: str | None) -> str:
    """Get the first docstring paragraph, with a length limit.

    The page shows a module's opening text and a link to the source file.
    Full docstrings doubled the facts file, but the page did not render that text.
    """
    if not text:
        return ""
    para = text.strip().split("\n\n")[0]
    para = " ".join(para.split())
    return para if len(para) <= 320 else para[:319] + "\u2026"


def parse_surface(
    raw: str,
    *,
    module: str = "",
    is_package: bool = False,
    prefixes: frozenset[str] = frozenset(),
) -> dict[str, Any] | None:
    """Read one module's public surface, or give None for a parse error.

    Extraction stores this surface. The change detector compares the same surface
    between Git blobs. Thus, the two commands use one export definition.

    For package `__init__` source, `module`, `is_package`, and `prefixes` select local
    re-exports. The `names` records include `reexport_of`. A component can use such
    a name as its entry. `build` gets the kind from the defining module.
    This function initially records `reexport`.
    """
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return None
    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    types: list[dict[str, Any]] = []
    constants: list[dict[str, str]] = []
    # Every public module-level name with its kind, so an `entry` can be a
    # lower-case object (`app`, `root_agent`) as well as a function or class.
    names: list[dict[str, str]] = []
    statements = _active_statements(tree.body)
    for node in statements:
        if isinstance(node, ast.ImportFrom) and is_package and module:
            names.extend(_surface_reexports(node, module, prefixes))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            _surface_function(node, names, functions)
        elif isinstance(node, ast.ClassDef):
            _surface_class(node, names, classes, errors)
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            _surface_assignment(node, names, constants)
        elif isinstance(node, TYPE_ALIAS):
            _surface_type_alias(node, names, types)
    python_exports.mark_star_exports(statements, names)
    return {
        "docstring": opening(ast.get_docstring(tree)),
        "functions": functions,
        "classes": classes,
        "errors": errors,
        "types": types,
        "constants": constants,
        "names": names,
        "api": _python_api(statements),
        "executes": any(
            isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) for node in statements
        ),
    }


def _surface_reexports(
    node: ast.ImportFrom, module: str, prefixes: frozenset[str]
) -> list[dict[str, Any]]:
    source = _reexport_source(node, module, prefixes)
    return [] if source is None else python_exports.reexports(node.names, source)


def _surface_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    names: list[dict[str, str]],
    functions: list[dict[str, Any]],
) -> None:
    if node.name.startswith("_"):
        return
    names.append({"name": node.name, "kind": "function"})
    functions.append({"name": node.name, "signature": signature(node)})


def _surface_class(
    node: ast.ClassDef,
    names: list[dict[str, str]],
    classes: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> None:
    if node.name.startswith("_"):
        return
    bases = []
    for base in node.bases:
        with contextlib.suppress(AttributeError, ValueError):
            bases.append(ast.unparse(base))
    is_error = node.name.endswith(("Error", "Exception")) or any(
        "Error" in base or "Exception" in base for base in bases
    )
    record = {
        "name": node.name,
        "methods": [
            signature(child)
            for child in node.body
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
            and not child.name.startswith("_")
        ],
    }
    (errors if is_error else classes).append(record)
    names.append({"name": node.name, "kind": "error" if is_error else "class"})


def _surface_type_alias(
    node: ast.stmt, names: list[dict[str, str]], types: list[dict[str, Any]]
) -> None:
    name = getattr(getattr(node, "name", None), "id", "")
    if not name or name.startswith("_"):
        return
    types.append({"name": name, "category": "type_alias", "methods": []})
    names.append({"name": name, "kind": "type"})


def _surface_assignment(
    node: ast.Assign | ast.AnnAssign,
    names: list[dict[str, str]],
    constants: list[dict[str, str]],
) -> None:
    # AnnAssign also covers measured caps declared as `NAME: Final = ...`.
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    for target in targets:
        if not isinstance(target, ast.Name) or target.id.startswith("_") or node.value is None:
            continue
        if not UPPER_NAME.fullmatch(target.id):
            names.append({"name": target.id, "kind": "object"})
            continue
        try:
            value = ast.unparse(node.value)
        except (AttributeError, ValueError):
            value = "?"
        constants.append({"name": target.id, "value": value[:80]})
        names.append({"name": target.id, "kind": "constant"})


def _active_statements(body: list[ast.stmt]) -> list[ast.stmt]:
    """Select top-level statements whose branch can be determined without module execution."""
    out: list[ast.stmt] = []
    for node in body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Constant):
            if isinstance(node.test.value, bool):
                out.extend(_active_statements(node.body if node.test.value else node.orelse))
                continue
        out.append(node)
    return out


def _python_class_api(node: ast.ClassDef) -> str:
    members: list[str] = []
    for child in node.body:
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            if child.name == "__init__" or not child.name.startswith("_"):
                members.append(python_syntax.decorated(child, signature(child)))
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            if not child.target.id.startswith("_"):
                members.append(f"{child.target.id}:{ast.dump(child.annotation)}")
    return json.dumps(
        {
            "bases": [ast.dump(base) for base in node.bases],
            "decorators": [ast.dump(decorator) for decorator in node.decorator_list],
            "members": members,
        },
        sort_keys=True,
    )


def _python_api(body: list[ast.stmt]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for node in body:
        out.extend(_python_api_entries(node))
    return out


def _python_api_entries(node: ast.stmt) -> list[dict[str, str]]:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith("_"):
        fingerprint = python_syntax.decorated(node, signature(node))
        return [{"name": node.name, "bucket": "operations", "fingerprint": fingerprint}]
    if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
        bases = [ast.unparse(base) for base in node.bases]
        error = node.name.endswith(("Error", "Exception")) or any(
            "Error" in base or "Exception" in base for base in bases
        )
        return [
            {
                "name": node.name,
                "bucket": "refusals" if error else "types",
                "fingerprint": _python_class_api(node),
            }
        ]
    if isinstance(node, ast.ImportFrom):
        return _python_api_reexports(node)
    if isinstance(node, ast.Assign | ast.AnnAssign):
        return _python_api_assignments(node)
    if isinstance(node, TYPE_ALIAS):
        name = getattr(getattr(node, "name", None), "id", "")
        public = name and not name.startswith("_")
        return [{"name": name, "bucket": "types", "fingerprint": ast.dump(node)}] if public else []
    return []


def _python_api_reexports(node: ast.ImportFrom) -> list[dict[str, str]]:
    """This function gives the export identity of each imported name.

    `from .service import *` gives the name `*`. One module text cannot supply the names
    that it gives, but the removal of the import is a change of the public surface.
    """
    source = "." * node.level + (node.module or "")
    return [
        {
            "name": alias.asname or alias.name,
            "bucket": "constants",
            "fingerprint": f"reexport:{source}:{alias.name}",
        }
        for alias in node.names
        if not (alias.asname or alias.name).startswith("_")
    ]


def _python_api_assignments(node: ast.Assign | ast.AnnAssign) -> list[dict[str, str]]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return [
        {
            "name": target.id,
            "bucket": "constants",
            "fingerprint": ast.dump(node, include_attributes=False),
        }
        for target in targets
        if isinstance(target, ast.Name) and not target.id.startswith("_")
    ]


def _reexport_source(node: ast.ImportFrom, module: str, prefixes: frozenset[str]) -> str | None:
    """Get the local source module of a package `from ... import` statement.

    Give None if the source is not in the package.
    """
    if node.level:
        # Relative to the package itself: `.mod` is a sibling module of
        # the __init__, each further level one package up.
        anchor = module.split(".")
        if node.level > 1:
            anchor = anchor[: len(anchor) - (node.level - 1)]
        if not anchor:
            return None
        return ".".join([*anchor, *node.module.split(".")] if node.module else anchor)
    if not node.module or not _in_package(node.module, prefixes):
        return None
    return node.module


def _in_package(name: str, prefixes: Iterable[str]) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)


def _dump_python_syntax(tree: ast.AST) -> str:
    """Serialize shared Python syntax the same way across supported interpreters."""
    # Python 3.12 added empty type_params; 3.13 stopped dumping empty
    # lists by default. Retain the 3.11 representation for shared syntax,
    # while retaining nonempty type parameters as meaningful source.
    for node in ast.walk(tree):
        if getattr(node, "type_params", None) == []:
            vars(node)["_fields"] = tuple(field for field in node._fields if field != "type_params")
    empty_fields = {"show_empty": True} if sys.version_info >= (3, 13) else {}
    return ast.dump(tree, include_attributes=False, **empty_fields)


def collect_module(
    path: Path, repo: Path, module: str = "", prefixes: frozenset[str] = frozenset()
) -> dict[str, Any] | None:
    issue: dict[str, Any] | None = None
    try:
        raw = source_text.read(repo, path)
    except (OSError, UnicodeError) as exc:
        raw = ""
        issue = {
            "line": 0,
            "reason": f"source could not be read: {repo_files.reason(exc)}",
            "parser": sys.version.split()[0],
            "cause": unknown_causes.read_cause(exc),
        }
    surface = (
        parse_surface(raw, module=module, is_package=path.name == "__init__.py", prefixes=prefixes)
        if issue is None
        else None
    )
    if surface is None:
        if issue is None:
            try:
                ast.parse(raw)
            except (SyntaxError, ValueError) as exc:
                issue = {
                    "line": getattr(exc, "lineno", 0) or 0,
                    "reason": f"source could not be parsed: {type(exc).__name__}",
                    "parser": sys.version.split()[0],
                    "cause": unknown_causes.SYNTAX,
                }
        surface = {
            "docstring": "",
            "functions": [],
            "classes": [],
            "errors": [],
            "types": [],
            "constants": [],
            "names": [],
            "api": [],
            "executes": False,
        }
    try:
        normalized = _dump_python_syntax(ast.parse(raw))
    except (SyntaxError, ValueError):
        normalized = raw
    record = {
        "file": path.relative_to(repo).as_posix(),
        "loc": len(raw.splitlines()),
        # A change detector for the map, never a security claim: usedforsecurity=False
        # states that and keeps the digest byte-identical, so committed facts files
        # stay comparable across the flag.
        "sha": hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).hexdigest()[:12],
        "source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "syntax_sha": hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16],
        **surface,
        "constants": surface["constants"][:CONSTANTS_KEPT],
        "completeness": parse_state(issue),
    }
    if issue is not None:
        record["parse_error"] = issue
    return record


def internal_uses(
    raw: str,
    prefixes: set[str],
    known: set[str],
    module: str = "",
    is_package: bool = False,
) -> dict[str, set[str]]:
    """Map each imported target module to the names taken from it.

    Relative imports use the source module and package state.
    Only targets in the extracted module inventory are included.
    """
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return {}
    uses: dict[str, set[str]] = defaultdict(set)
    for _node, _local, target, name, _line in python_calls.import_targets(
        tree, prefixes, known, module, is_package
    ):
        uses[target].add(name)
    return dict(uses)


def external_imports(raw: str, prefixes: set[str]) -> list[str]:
    """Get third-party import names from one source module.

    Keep dotted import names. Do not include standard-library or local-package imports.
    These records supply the model SDK findings.
    """
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return []
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            candidates = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            candidates = [node.module]
        else:
            continue
        for name in candidates:
            top = name.split(".")[0]
            if _in_package(name, prefixes) or top in sys.stdlib_module_names or top == "__future__":
                continue
            out.add(name)
    return sorted(out)
