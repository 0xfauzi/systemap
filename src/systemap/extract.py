"""Read source facts from the working tree.

Records contain module imports, public surface, owned types, errors, public names,
third-party imports, test references, and entry points. Test references do not
prove test coverage. The model module contains authored purpose statements.
The page uses different styles for source facts and authored meaning.
"""

from __future__ import annotations

import ast
import contextlib
import functools
import hashlib
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap import (
    fact_cache,
    file_names,
    notice_text,
    python_calls,
    python_entry,
    python_exports,
    python_repo,
    python_syntax,
    python_tests,
    python_tree,
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
from systemap.python_imports import NamespaceCache, python_unresolved
from systemap.python_repo import PythonRepository
from systemap.source_facts import standard_label

CONSTANTS_KEPT = 14
UPPER_NAME = re.compile(r"[A-Z][A-Z0-9_]{2,}")
PACKAGE_MODULE = "__init__.py"
# The `type X = ...` statement exists from Python 3.12. An earlier parser cannot read it.
TYPE_ALIAS: tuple[type, ...] = (ast.TypeAlias,) if hasattr(ast, "TypeAlias") else ()


@dataclass
class PythonContext(python_tests.PythonTests):
    """The data of one Python extraction: the test data and the namespace packages."""

    namespaces: NamespaceCache = field(default_factory=NamespaceCache)


def _not_test(repo: Path, test_patterns: tuple[str, ...], path: Path) -> bool:
    return not matches_test_pattern(path.relative_to(repo).as_posix(), test_patterns)


class PythonLanguage(PythonRepository):
    """Read Python syntax through the language adapter interface."""

    def source_paths(
        self,
        root: Path,
        repo: Path,
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
        refused: list[Path] | None = None,
    ) -> Iterable[Path]:
        del tests_dirs
        names: list[Path] = []
        found = python_repo.python_paths(root, refused=names)
        source = functools.partial(_not_test, repo, test_patterns)
        return file_names.selected(found, names, source, refused)

    def context(
        self,
        repo: Path,
        paths: dict[str, Path],
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> PythonContext:
        del repo, paths, tests_dirs
        return PythonContext(test_patterns)

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

    def extra_facts(self, context: Any, entry_issues: list[dict[str, Any]]) -> dict[str, Any]:
        """Give the issue lists. An empty issue list is not written."""
        test_issues = getattr(context, "test_issues", [])
        lists = {"entry_point_issues": entry_issues, "test_file_issues": test_issues}
        return {key: value for key, value in lists.items() if value}

    def keep_facts(self, context: Any, cache: Any) -> None:
        """Let the extraction use the kept facts of the cache (`extraction.build`).

        The facts of one Python file come only from its text, the module paths, the
        configuration, and the public names of the modules that it imports."""
        if isinstance(context, python_tests.PythonTests):
            context.cache = cache

    def release(self, context: Any) -> None:
        """Remove the cached syntax trees of the extraction."""
        del context
        python_tree.clear()

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
        del repo
        is_package = self.is_package_module(paths[module])
        # One namespace set for each extraction. A set for each module made the
        # extraction time grow with the square of the module count.
        cache = context.namespaces if isinstance(context, PythonContext) else NamespaceCache()
        namespaces = cache.of(known)
        return python_unresolved(raw, prefixes, known, module, is_package, namespaces)

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
        return python_tests.collect_tests(repo, tests_dirs, prefixes, paths, tests)

    def entry_points(
        self,
        repo: Path,
        prefixes: set[str],
        components: dict[str, Any],
        sources: dict[str, str],
        context: Any,
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        cache = getattr(context, "cache", None)
        issues = [
            issue
            for module, source in sources.items()
            for issue in fact_cache.kept(
                cache,
                "registrations",
                module,
                fact_cache.text_digest(source),
                functools.partial(python_entry.registration_candidates, module, source),
            )
        ]
        return python_entry.entry_points(repo, prefixes, components, sources), issues

    def parse_surface(self, raw: str, path: str = "") -> dict[str, Any] | None:
        try:
            return parse_surface(raw)
        except unknown_causes.DEPTH_ERRORS:
            # A surface with too many levels is not known, as for a parse error.
            return None

    def test_names(self, raw: str, path: str = "") -> list[str]:
        return python_tests.test_names(raw)

    def is_test_file(
        self, path: str, tests_dirs: tuple[str, ...], test_patterns: tuple[str, ...] = ()
    ) -> bool:
        return python_tests.is_test_file(path, tests_dirs, test_patterns)


PYTHON = PythonLanguage()


def module_of(path: Path, pkg_dir: Path, pkg_name: str) -> str:
    """Give the dotted module of a file. Only a last part `__init__` (the package file)
    is not in the name. A folder with the name `__init__` keeps its part."""
    parts = list(path.relative_to(pkg_dir).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
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
    """Get the first docstring paragraph that is not a license notice, with a length
    limit (`notice_text`).

    The page shows a module's opening text and a link to the source file.
    """
    return notice_text.description(text)


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
    tree = python_tree.tree(raw)
    if tree is None:
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
    # Overload signatures give one public name, as in the TypeScript adapter. Each
    # signature keeps its record in `functions`.
    if {"name": node.name, "kind": "function"} not in names:
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
    """Serialize shared Python syntax the same way across supported interpreters.

    The function does not change the tree. Other steps read the same tree from
    `python_tree`.
    """
    # Python 3.12 added empty type_params; 3.13 stopped dumping empty
    # lists by default. Retain the 3.11 representation for shared syntax,
    # while retaining nonempty type parameters as meaningful source.
    hidden = _hide_empty_type_params(tree)
    empty_fields = {"show_empty": True} if sys.version_info >= (3, 13) else {}
    try:
        return ast.dump(tree, include_attributes=False, **empty_fields)
    finally:
        for node in hidden:
            del vars(node)["_fields"]


def _hide_empty_type_params(tree: ast.AST) -> list[ast.AST]:
    """Remove an empty `type_params` field from the fields that `ast.dump` writes.

    The function gives the changed nodes. The caller must remove the change after the
    dump.
    """
    hidden = [node for node in python_tree.walk(tree) if getattr(node, "type_params", None) == []]
    for node in hidden:
        vars(node)["_fields"] = tuple(field for field in node._fields if field != "type_params")
    return hidden


def _surface_and_syntax(
    raw: str, module: str, is_package: bool, prefixes: frozenset[str], read: bool
) -> tuple[dict[str, Any] | None, str]:
    """Give the public surface and the normalized syntax of a module text.

    A text that was not `read`, or that does not parse, gives no surface. A text that
    does not parse gives itself as the syntax. If the surface or the syntax has too many
    levels, the tree cache refuses the text. Then no later step reads its tree, and the
    module has no surface."""
    try:
        surface = (
            parse_surface(raw, module=module, is_package=is_package, prefixes=prefixes)
            if read
            else None
        )
        return surface, _normalized(raw)
    except unknown_causes.DEPTH_ERRORS:
        python_tree.refuse(raw)
        return None, raw


def _normalized(raw: str) -> str:
    try:
        return _dump_python_syntax(python_tree.parse(raw))
    except (SyntaxError, ValueError):
        return raw


def _parse_issue(raw: str) -> dict[str, Any] | None:
    """Give the parse problem of a module text that has no surface, or None."""
    try:
        python_tree.parse(raw)
    except python_tree.TooDeep:
        return {
            "line": 0,
            "reason": unknown_causes.DEPTH_REASON,
            "parser": sys.version.split()[0],
            "cause": unknown_causes.DEPTH,
        }
    except (SyntaxError, ValueError) as exc:
        return {
            "line": getattr(exc, "lineno", 0) or 0,
            "reason": f"source could not be parsed: {type(exc).__name__}",
            "parser": sys.version.split()[0],
            "cause": unknown_causes.SYNTAX,
        }
    return None


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
    is_package = path.name == "__init__.py"
    surface, normalized = _surface_and_syntax(raw, module, is_package, prefixes, issue is None)
    if surface is None:
        issue = issue or _parse_issue(raw)
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
    tree = python_tree.tree(raw)
    if tree is None:
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
    tree = python_tree.tree(raw)
    if tree is None:
        return []
    out: set[str] = set()
    for node in python_tree.walk(tree):
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
