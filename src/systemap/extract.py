"""Read source facts from the working tree.

Records contain module imports, public surface, owned types, errors, public names,
third-party imports, test references, and entry points. Test references do not
prove test coverage. The model module contains authored purpose statements.
The page uses different styles for source facts and authored meaning.

`FIELDS` gives every written field. The skill schema reference comes from this
table. A test compares the reference with the table.
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
from systemap.source_facts import empty_markers, standard_label

CONSTANTS_KEPT = 14
UPPER_NAME = re.compile(r"[A-Z][A-Z0-9_]{2,}")
PACKAGE_MODULE = "__init__.py"


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


# Every field the extractor writes: (scope, field, what it holds). The
# scopes are the file itself, each module record under `components`, and
# each record under `entry_points`. `facts_doc` renders this table for the
# skill's schema reference; the test compares the rendered text with the
# shipped reference and the table with what `build` actually writes.
FIELDS: tuple[tuple[str, str, str], ...] = (
    (
        "facts",
        "version",
        "The facts format is 8, with portable syntax hashes, compiler provenance, "
        "module completeness, the folder package in `package`, `call_sites`, and "
        "decorators in the `api` fingerprints. "
        "Each re-export has `defined_in` and `defined_as`. "
        "`extract --check` marks older formats stale",
    ),
    (
        "facts",
        "built_at_commit",
        "The commit read during extraction (`HEAD`), or empty outside Git. The page "
        "prints `facts from <sha>`. Extraction occurs before the commit that records the facts",
    ),
    ("facts", "packages", "The import names of package roots"),
    (
        "facts",
        "provenance",
        "The parser, the compiler settings, and the extraction inputs. A change to the "
        "extraction inputs makes a new source review necessary, even without source-file "
        "changes. A parser or compiler change alone does not, because these values can be "
        "different on another computer",
    ),
    (
        "facts",
        "tests_dirs",
        "Root-relative test directories: configured `tests_dir`, or every directory "
        "with the name `tests` or `test`",
    ),
    ("facts", "spec_sections", "The `##` headings in `spec_path`, with `level` and `title`"),
    ("facts", "entry_points", "One record for each entry point, with the fields below"),
    (
        "facts",
        "entry_point_issues",
        "Package entry targets or Python decorators with unresolved framework "
        "bindings. The list is empty if there are none",
    ),
    (
        "facts",
        "test_file_issues",
        "Test files that could not be read or parsed. Each record has `file`, and a "
        "`problem` with `line`, `reason`, and `source`. "
        "The test functions of these files are not known. The Python adapter does not "
        "write an empty list",
    ),
    (
        "facts",
        "config_issues",
        "TypeScript npm tsconfig packages in `extends` that cannot be read. The list is "
        "empty if there are none",
    ),
    ("facts", "components", "One module record for each dotted name, with the fields below"),
    ("module", "id", "The dotted module name"),
    ("module", "file", "The root-relative source path"),
    (
        "module",
        "package",
        "The dotted name of the package that contains the module. The language adapter "
        "writes it. A dot in a file name does not change it. A Python `__init__` module "
        "is in the parent package of its own package. A package root gives its own name",
    ),
    ("module", "plane", "The second module-name segment if `planes` includes it, or `core`"),
    ("module", "loc", "The file line count"),
    (
        "module",
        "sha",
        "The first twelve hex digits of the source SHA-1. This is the change-detector key",
    ),
    (
        "module",
        "source_sha256",
        "The full SHA-256 of UTF-8 source text with normalized newlines, for source references",
    ),
    (
        "module",
        "syntax_sha",
        "The parsed-syntax digest for source review. Comments and text format do not change it",
    ),
    (
        "module",
        "docstring",
        "The first paragraph of the module description, with a length limit. The Python "
        "adapter reads the module docstring. The TypeScript adapter reads the first "
        "documentation comment",
    ),
    ("module", "functions", "Public functions with `name` and `signature`"),
    (
        "module",
        "classes",
        "Public classes other than errors, with `name` and public method signatures in `methods`",
    ),
    (
        "module",
        "errors",
        "Public classes with Error or Exception in their names or bases. They use the "
        "same fields as classes",
    ),
    ("module", "constants", "The first 14 UPPER_CASE assignments, with `name` and `value`"),
    (
        "module",
        "names",
        "Public module-level names in source order, with `kind`: `function`, `class`, "
        "`error`, `constant` (UPPER_CASE), or `object` (other assignments such as "
        "`app`). TypeScript uses `unknown` for unresolved kinds. A package `__init__` "
        "includes local re-exports, with `reexport_of` and the kind in their source module. A "
        "full-module import uses kind `module`. Each re-export and each local alias has "
        "`defined_in` and `defined_as`: the module and the symbol that define it, through "
        "all re-exports and aliases. `defined_as` is `*` for a full module. The two values "
        "are `null` if the defining module is not known. A `*` re-export of the module does not "
        "give a name that has `star_export` set to `false`. A name with `star_export` set to "
        "`null` can be in the `*` re-export or not. The TypeScript adapter sets `false` for "
        "`default`. The Python adapter sets the value from `__all__`. `entry` and `interface` "
        "can use these names",
    ),
    (
        "module",
        "api",
        "Full export identities for public-surface comparisons: exported name, "
        "display bucket, and declaration fingerprint. The fingerprint includes "
        "decorators. It does not include callable bodies",
    ),
    ("module", "executes", "Python-only: a top-level call makes a package initializer nonempty"),
    (
        "module",
        "empty_marker",
        "`true` for a module that only marks a package and holds no code: a Python "
        "`__init__.py` file or a TypeScript `index` file without statements. A Python "
        "docstring, `pass`, `__future__` import, and literal value for a dunder name such "
        "as `__all__` are not statements for this rule. Coverage does not include these "
        "modules",
    ),
    (
        "module",
        "unknown",
        "TypeScript surface entries with unresolved syntax or kinds. Each has a "
        "source line, reason, and short source excerpt",
    ),
    (
        "module",
        "uses",
        "Imported local modules with the names taken from each. `*` means the full module",
    ),
    (
        "module",
        "call_sites",
        "The local names that the module gets from a name of a module in `uses`, and the "
        "lines that use them. Each record has `local`, `target`, `name` (`*` for the full "
        "module), `bound`, `line`, and `uses`. `bound` is `import` for a name that an import "
        "statement makes, or for a re-export without a local name, such as `export { a } "
        "from`. It is `value` for a name that gets its value or type from that "
        "name, such as `ledger` after `ledger = Ledger()`. `line` is the binding line. Each "
        "use is `[line, function line, property]`. The function line is the line of the "
        "named function or method that contains the use, or 0. The property is the "
        "attribute that the use reads, or an empty string. The value is `null` if the "
        "source did not parse",
    ),
    ("module", "imports", "The keys of `uses`"),
    ("module", "imported_by", "Local modules that import this module"),
    (
        "module",
        "external",
        "Third-party dotted import names, such as `anthropic` or `google.adk`. "
        "Standard-library and local-package imports are excluded. `model sdk` "
        "findings read this field",
    ),
    (
        "module",
        "tests_total",
        "The number of test functions with an import reference to this module",
    ),
    ("module", "tests_primary", "The number of those functions in a file with the module name"),
    ("module", "tests", "Up to 25 test names, with primary tests first"),
    (
        "module",
        "tests_digest",
        "A digest of every qualified test identity. It also includes hidden identities",
    ),
    (
        "module",
        "parse_error",
        "Python source read or parse errors, with line and parser version. Other "
        "systemap modules read `completeness`",
    ),
    (
        "module",
        "completeness",
        "The read condition of the module, with the same meaning for each language. "
        "`parsed` is `false` if the extractor could not read or parse all of the source, "
        "and `line` and `reason` then give the first problem. `unresolved_imports` lists "
        "each local import, as the source writes it, that has no module in the facts. A "
        "local import is a relative import, a path, a TypeScript path alias, or a name below a "
        "package root. If `parsed` is `false`, the import list is not known and is `null`. "
        "Third-party packages, standard-library modules, Node.js built-in modules, and imports "
        "with a calculated module name are not in the list",
    ),
    (
        "entry point",
        "kind",
        "`console_script`, `main_module`, `main_function`, `subcommand`, `public_function`, "
        "`route`, `command`, `task`, or `plugin`",
    ),
    (
        "entry point",
        "name",
        "The script name, `python -m` command, `main`, subcommand name, route, command "
        "name, plugin hook, or function name",
    ),
    ("entry point", "module", "The module that defines the entry point"),
    (
        "entry point",
        "target",
        "The console-script function, the console script for a subcommand, or the "
        "registered function. It is empty for other kinds",
    ),
    (
        "entry point",
        "label",
        "The display name that the language adapter gives to the entry point. A sequence "
        "can name it in `starts`",
    ),
)

SCOPE_TITLES = {
    "facts": "The file",
    "module": "Each module, under `components`",
    "entry point": "Each entry point, under `entry_points`",
}


def fields_of(scope: str) -> set[str]:
    return {name for sc, name, _ in FIELDS if sc == scope}


def facts_doc() -> str:
    """Write the skill facts reference from `FIELDS`."""
    out = [
        "## The facts file",
        "",
        "`systemap extract` writes `docs/map/map.json` by default.",
        "These fields come from `systemap.extract.FIELDS`.",
    ]
    for scope, title in SCOPE_TITLES.items():
        out += ["", f"**{title}**", ""]
        out += [f"- `{name}`: {what}." for sc, name, what in FIELDS if sc == scope]
    out += [
        "",
        "**The extract summary**",
        "",
        "The numbers from `systemap extract` describe source facts.",
        "They do not describe the purposes of the map components.",
        "`modules` counts records under `components`.",
        "`functions`, `classes`, and `errors` give the sums of those module fields.",
        "`tests` gives the sum of `tests_total`. The count for test files with the module",
        "name gives the sum of `tests_primary`.",
        "",
        "`empty package markers` counts the records with `empty_marker` set to true.",
        "Coverage automatically excludes these records.",
    ]
    return "\n".join(out) + "\n"


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
    python_exports.mark_star_exports(statements, names)
    return {
        "docstring": opening(ast.get_docstring(tree)),
        "functions": functions,
        "classes": classes,
        "errors": errors,
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
    return []


def _python_api_reexports(node: ast.ImportFrom) -> list[dict[str, str]]:
    source = "." * node.level + (node.module or "")
    return [
        {
            "name": alias.asname or alias.name,
            "bucket": "constants",
            "fingerprint": f"reexport:{source}:{alias.name}",
        }
        for alias in node.names
        if (alias.asname or alias.name) != "*" and not (alias.asname or alias.name).startswith("_")
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
        raw = repo_files.read_text(repo, repo_files.relative(repo, path), encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raw = ""
        issue = {
            "line": 0,
            "reason": f"source could not be read: {repo_files.reason(exc)}",
            "parser": sys.version.split()[0],
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
                }
        surface = {
            "docstring": "",
            "functions": [],
            "classes": [],
            "errors": [],
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


def read_facts(path: Path) -> dict[str, Any]:
    """Read stored facts.

    Give an empty table if the file is missing or the JSON parser cannot read it.
    """
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data) if isinstance(data, dict) else {}


def dumps(facts: dict[str, Any]) -> str:
    """Write compact facts with sorted keys and one module record per line.

    Indented output was 635 KB on a 144-module tree and exceeded a repository hook.
    Compact module records have no spaces. A diff can compare records by module.
    Top-level keys also use one line each.
    """

    def compact(value: Any) -> str:
        return json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=False)

    parts: list[str] = []
    for key in sorted(facts):
        value = facts[key]
        if key == "components" and isinstance(value, dict):
            records = ",\n".join(
                f"{json.dumps(module)}:{compact(record)}"
                for module, record in sorted(value.items())
            )
            parts.append(f'"components":{{\n{records}\n}}')
        else:
            parts.append(f"{json.dumps(key)}:{compact(value)}")
    return "{\n" + ",\n".join(parts) + "\n}\n"


def write_facts(path: Path, facts: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(facts), encoding="utf-8", newline="\n")


def summary(facts: dict[str, Any]) -> list[str]:
    """Give extraction counts with their source fields.

    These counts supply the change detector. The map does not show them.
    `modules` counts `components`. Functions, classes, and errors use their module
    fields. Test counts use `tests_total` and `tests_primary`.
    Empty markers are package records without public names, imports, or execution.
    """
    comps = facts["components"]
    guarded = sum(c["tests_total"] for c in comps.values())
    primary = sum(c["tests_primary"] for c in comps.values())
    dirs: list[str] = list(facts.get("tests_dirs", []))
    if guarded:
        tests = f"{guarded} test functions import a module, {primary} in a file with its name"
    elif dirs:
        # Zero is a finding, not a count: say where the extractor looked, so
        # a tests directory it did not find is set in `tests_dir`.
        tests = f"none import a module. The extractor searched {', '.join(dirs)}"
    else:
        tests = "none import a module. The extractor found no tests or test directory"
    out = [
        "facts for the change detector (these never appear on the map):",
        f"  modules:          {len(comps)}",
        f"  functions:        {sum(len(c['functions']) for c in comps.values())}",
        f"  classes:          {sum(len(c['classes']) for c in comps.values())}",
        f"  errors:           {sum(len(c['errors']) for c in comps.values())}",
        f"  tests:            {tests}",
    ]
    markers = empty_markers(facts)
    if markers:
        out.append(
            f"  empty package markers: {len(markers)} ({', '.join(markers)}). Each only marks a "
            "package and holds no code. The coverage rule omits them."
        )
    return out
