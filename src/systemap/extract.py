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
import importlib.metadata
import json
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from systemap import ways_in
from systemap.config import Config, ConfigError
from systemap.language import LanguageAdapter
from systemap.model import Model, is_symbol, module_matches, public_names

SKIP_PARTS = {".git", ".venv", "node_modules", "__pycache__", "build", "dist"}
# A stored file of an older facts format is reported as stale.
FORMAT = 4
TESTS_KEPT = 25
CONSTANTS_KEPT = 14
UPPER_NAME = re.compile(r"[A-Z][A-Z0-9_]{2,}")


class PythonLanguage:
    """Read Python syntax through the language adapter interface."""

    name = "python"

    def source_paths(
        self,
        root: Path,
        repo: Path,
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> Iterable[Path]:
        del repo, tests_dirs, test_patterns
        return root.rglob("*.py")

    def context(
        self,
        repo: Path,
        paths: dict[str, Path],
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> None:
        del repo, paths, tests_dirs, test_patterns
        return None

    def module_of(self, path: Path, root: Path, name: str) -> str:
        return module_of(path, root, name)

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
        del context
        return collect_tests(repo, tests_dirs, prefixes, set(paths))

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
            for issue in ways_in.registration_candidates(module, source)
        ]
        return entry_points(repo, prefixes, components, sources), issues

    def parse_surface(self, raw: str, path: str = "") -> dict[str, Any] | None:
        return parse_surface(raw)

    def test_names(self, raw: str, path: str = "") -> list[str]:
        return test_names(raw)

    def is_test_file(
        self, path: str, tests_dirs: tuple[str, ...], test_patterns: tuple[str, ...] = ()
    ) -> bool:
        del test_patterns
        if not path.endswith(".py") or not path.split("/")[-1].startswith("test_"):
            return False
        return any(rel and path.startswith(rel.rstrip("/") + "/") for rel in tests_dirs)


PYTHON = PythonLanguage()


def language_for(cfg: Config) -> LanguageAdapter:
    """Select the configured source-language adapter for this repository."""
    if cfg.language == PYTHON.name:
        return PYTHON
    if cfg.language == "typescript":
        try:
            from systemap.typescript import TYPESCRIPT
        except ModuleNotFoundError as exc:
            if exc.name not in {"tree_sitter", "tree_sitter_typescript"}:
                raise
            raise ConfigError(
                "TypeScript adapter is not installed. Install systemap[typescript]"
            ) from exc

        return TYPESCRIPT
    raise ValueError(f"unsupported language: {cfg.language}")


# Every field the extractor writes: (scope, field, what it holds). The
# scopes are the file itself, each module record under `components`, and
# each record under `entry_points`. `facts_doc` renders this table for the
# skill's schema reference; the test compares the rendered text with the
# shipped reference and the table with what `build` actually writes.
FIELDS: tuple[tuple[str, str, str], ...] = (
    (
        "facts",
        "version",
        "The facts format is 4, with portable syntax hashes and compiler provenance. "
        "`extract --check` marks older formats stale",
    ),
    (
        "facts",
        "built_at_commit",
        "The commit read during extraction (`HEAD`), or empty outside Git. The page "
        "prints `facts from <sha>`. Extraction precedes the commit recording facts",
    ),
    ("facts", "packages", "The import names of package roots"),
    (
        "facts",
        "provenance",
        "The parser and extraction inputs. A change makes a new source review "
        "necessary, even without source-file changes",
    ),
    (
        "facts",
        "tests_dirs",
        "Root-relative test directories: configured `tests_dir`, or every directory "
        "named `tests` or `test`",
    ),
    ("facts", "spec_sections", "The `##` headings in `spec_path`, with `level` and `title`"),
    ("facts", "entry_points", "One record per entry point, with the fields below"),
    (
        "facts",
        "entry_point_issues",
        "Package entry targets or Python decorators with unresolved framework "
        "bindings. Empty if there are none",
    ),
    (
        "facts",
        "test_file_issues",
        "TypeScript test files with unresolved imports or names after a parse error. "
        "Empty if there are none",
    ),
    (
        "facts",
        "config_issues",
        "TypeScript npm tsconfig packages in `extends` that cannot be read. Empty if "
        "there are none",
    ),
    ("facts", "components", "One module record per dotted name, with the fields below"),
    ("module", "id", "The dotted module name"),
    ("module", "file", "The root-relative source path"),
    ("module", "package", "The first module-name segment"),
    ("module", "plane", "The second module-name segment if `planes` includes it. If not, `core`"),
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
        "The parsed-syntax digest, without comments or formatting, for source review",
    ),
    ("module", "docstring", "The first module-docstring paragraph, with a length limit"),
    ("module", "functions", "Public functions with `name` and `signature`"),
    (
        "module",
        "classes",
        "Public classes excluding errors, with `name` and public method signatures in `methods`",
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
        "includes local re-exports with `reexport_of` and their defining kind. A "
        "full-module import uses kind `module`. `entry` and `interface` can use these "
        "names",
    ),
    (
        "module",
        "api",
        "Full export identities for public-surface comparisons: exported name, "
        "display bucket, and declaration fingerprint. The fingerprint excludes "
        "callable bodies",
    ),
    ("module", "executes", "Python-only: a top-level call makes a package initializer nonempty"),
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
    ("module", "tests_primary", "The number of those functions in a file named for this module"),
    ("module", "tests", "Up to 25 test names, with primary tests first"),
    (
        "module",
        "tests_digest",
        "A digest of every qualified test identity, including hidden identities",
    ),
    ("module", "parse_error", "Python source read or parse errors, with line and parser version"),
    (
        "entry point",
        "kind",
        "`console_script`, `main_module`, `main_function`, `subcommand`, or `public_function`",
    ),
    (
        "entry point",
        "name",
        "The script name, `python -m` command, `main`, subcommand name, or function name",
    ),
    ("entry point", "module", "The defining module"),
    (
        "entry point",
        "target",
        "The console-script function, or the console script for a subcommand. Empty "
        "for other kinds",
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
        "The following fields come from `systemap.extract.FIELDS`.",
    ]
    for scope, title in SCOPE_TITLES.items():
        out += ["", f"**{title}**", ""]
        out += [f"- `{name}`: {what}." for sc, name, what in FIELDS if sc == scope]
    out += [
        "",
        "**The extract summary**",
        "",
        "The quantities from `systemap extract` describe source facts.",
        "They do not describe component functions on the map.",
        "`modules` counts records under `components`.",
        "`functions`, `classes`, and `errors` sum the module fields with those names.",
        "`tests` sums `tests_total`. The count for same-name test files sums `tests_primary`.",
        "",
        "`empty package markers` counts `__init__` records without public `names`,",
        "`imports`, or `external` entries. Coverage automatically excludes these records.",
    ]
    return "\n".join(out) + "\n"


def module_of(path: Path, pkg_dir: Path, pkg_name: str) -> str:
    rel = path.relative_to(pkg_dir).with_suffix("")
    parts = [p for p in rel.parts if p != "__init__"]
    return ".".join([pkg_name, *parts]) if parts else pkg_name


def plane_of(module: str, planes: tuple[str, ...]) -> str:
    """Get the module plane from its dotted path."""
    parts = module.split(".")
    if len(parts) > 2 and parts[1] in planes:
        return parts[1]
    return "core"


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


def first_line(text: str | None) -> str:
    if not text:
        return ""
    for line in text.strip().splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def sentence(test_name: str) -> str:
    body = test_name[5:] if test_name.startswith("test_") else test_name
    return body.replace("_", " ").strip() or test_name


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
) -> list[dict[str, str]]:
    source = _reexport_source(node, module, prefixes)
    if source is None:
        return []
    names: list[dict[str, str]] = []
    for alias in node.names:
        public = alias.asname or alias.name
        if alias.name == "*" or public.startswith("_"):
            continue
        entry = {"name": public, "kind": "reexport", "reexport_of": source}
        if alias.asname:
            entry["defined_as"] = alias.name
        names.append(entry)
    return names


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
                members.append(signature(child))
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
        return [{"name": node.name, "bucket": "operations", "fingerprint": signature(node)}]
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


def resolve_reexports(components: dict[str, Any]) -> None:
    """Give each re-export the kind recorded by its defining module.

    `from . import mod` has kind `module`, with the module itself in `reexport_of`.
    A name absent from the source module keeps `reexport_of` and has kind `object`.
    The source can import that name from elsewhere, including an unextracted module.
    """
    _expand_star_exports(components)
    _resolve_named_reexports(components)


def _expand_star_exports(components: dict[str, Any]) -> None:
    for module, record in components.items():
        expanded = _expanded_names(module, record, components)
        record["names"] = expanded
        ambiguous = _ambiguous_exports(expanded)
        if ambiguous:
            record.setdefault("unknown", []).extend(ambiguous)


def _expanded_names(
    module: str, record: dict[str, Any], components: dict[str, Any]
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for entry in record.get("names", []):
        if not entry.get("star"):
            expanded.append(entry)
            continue
        source = entry["reexport_of"]
        expanded.extend(
            {
                "name": item["name"],
                "kind": "reexport",
                "reexport_of": source,
                "defined_as": item["name"],
            }
            for item in _star_names(source, components, {module})
        )
    return expanded


def _ambiguous_exports(expanded: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: dict[str, set[str]] = defaultdict(set)
    for entry in expanded:
        if entry.get("reexport_of"):
            sources[entry["name"]].add(entry["reexport_of"])
    return [
        {"line": 0, "reason": f"ambiguous star export {name}", "source": ""}
        for name, origins in sources.items()
        if len(origins) > 1
    ]


def _resolve_named_reexports(components: dict[str, Any]) -> None:
    for record in components.values():
        for entry in record.get("names", []):
            if entry.get("kind") == "reexport":
                _resolve_named_reexport(entry, components)


def _resolve_named_reexport(entry: dict[str, Any], components: dict[str, Any]) -> None:
    source = entry["reexport_of"]
    original = entry.pop("defined_as", entry["name"])
    if f"{source}.{original}" in components:
        entry["reexport_of"] = f"{source}.{original}"
        entry["kind"] = "module"
    else:
        entry["kind"] = _defined_kind(source, original, components, set())


def _defined_kind(
    source: str, name: str, components: dict[str, Any], visited: set[tuple[str, str]]
) -> str:
    if (source, name) in visited:
        return "unknown"
    if f"{source}.{name}" in components:
        return "module"
    record = components.get(source)
    if record is None:
        return "unknown"
    for item in record.get("names", []):
        if item["name"] != name:
            continue
        if item["kind"] == "reexport":
            return _defined_kind(
                item["reexport_of"],
                item.get("defined_as", item["name"]),
                components,
                visited | {(source, name)},
            )
        return str(item["kind"])
    return "unknown"


def _star_names(module: str, components: dict[str, Any], visited: set[str]) -> list[dict[str, Any]]:
    """The public names reached through local `export *` statements."""
    if module not in components or module in visited:
        return []
    out: list[dict[str, Any]] = []
    for entry in components[module].get("names", []):
        if entry.get("star"):
            out.extend(_star_names(entry["reexport_of"], components, visited | {module}))
        elif entry.get("name") != "default":
            out.append(entry)
    return out


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
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raw = ""
        issue = {
            "line": 0,
            "reason": f"source could not be read: {type(exc).__name__}",
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
    }
    if issue is not None:
        record["parse_error"] = issue
    return record


# In a `uses` mapping, this marks "the whole module": `import m` gives access
# to every name in m, so no list of names would be honest.
WHOLE_MODULE = "*"


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

    def resolve(name: str) -> str | None:
        if name in known:
            return name
        parts = name.split(".")
        while len(parts) > 1:
            parts.pop()
            candidate = ".".join(parts)
            if candidate in known:
                return candidate
        return None

    uses: dict[str, set[str]] = defaultdict(set)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _in_package(alias.name, prefixes):
                    target = resolve(alias.name)
                    if target:
                        uses[target].add(WHOLE_MODULE)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if not module:
                    continue
                # The anchor package: a module's own package, or the package
                # itself when the source is an __init__. Each further level
                # climbs one package up.
                anchor = module.split(".")
                if not is_package:
                    anchor = anchor[:-1]
                if node.level > 1:
                    anchor = anchor[: len(anchor) - (node.level - 1)]
                if not anchor:
                    continue
                parts = [*anchor, *node.module.split(".")] if node.module else anchor
                src = ".".join(parts)
            else:
                if not node.module:
                    continue
                src = node.module
            if not _in_package(src, prefixes):
                continue
            base = resolve(src)
            for alias in node.names:
                if alias.name == "*":
                    if base:
                        uses[base].add(WHOLE_MODULE)
                    continue
                # Exact membership only: resolve() walks prefixes upward, so it
                # would resolve a class name to its module and misread every
                # from-import as a whole-module import.
                if f"{src}.{alias.name}" in known:
                    uses[f"{src}.{alias.name}"].add(WHOLE_MODULE)
                elif base:
                    uses[base].add(alias.name)
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


def internal_imports(path: Path, prefixes: set[str], known: set[str]) -> set[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(internal_uses(raw, prefixes, known))


def test_names(raw: str) -> list[str]:
    """Get test function identities, including their enclosing definitions."""
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return []
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


def collect_tests(
    repo: Path, tests_dirs: tuple[str, ...], prefixes: set[str], known: set[str]
) -> dict[str, list[dict[str, Any]]]:
    """Map imported modules to test function references.

    Use qualified test identities. An import reference does not prove coverage.
    """
    guards: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[Path] = set()
    files: list[Path] = []
    for rel in tests_dirs:
        test_dir = repo / rel
        if not rel or not test_dir.is_dir():
            continue
        for path in sorted(test_dir.rglob("test_*.py")):
            if path in seen or any(p in SKIP_PARTS for p in path.parts):
                continue
            seen.add(path)
            files.append(path)
    for path in files:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        targets = set(internal_uses(raw, prefixes, known))
        if not targets:
            continue
        names = test_names(raw)
        stem = path.stem[5:] if path.stem.startswith("test_") else path.stem
        for target in targets:
            # A test file named after the module is its primary guard; a file
            # that merely imports it exercises it. Both are true, and the
            # distinction is what stops a shared helper from claiming every test.
            primary = stem == target.split(".")[-1]
            for name in names:
                guards[target].append(
                    {"name": f"{path.relative_to(repo).as_posix()}::{name}", "primary": primary}
                )
    return guards


def spec_sections(repo: Path, spec_path: str) -> list[dict[str, str]]:
    if not spec_path:
        return []
    path = repo / spec_path
    if not path.is_file():
        return []
    out: list[dict[str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for match in re.finditer(r"^(#{2,4})\s+(.+)$", text, re.M):
        out.append({"level": str(len(match.group(1))), "title": match.group(2).strip()})
    return out


# ---- entry points: where a run of the system starts ----------------------------


def subcommands(raw: str) -> list[str]:
    """Read argparse subcommand names from one module.

    A call `<anything>.add_parser("name", ...)` with a literal first argument
    specifies a subcommand. The parser does not find names made from variables.
    Judgement can give findings only for names in the syntax tree.
    """
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return []
    out: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            out.append(node.args[0].value)
    return out


def console_scripts(repo: Path) -> dict[str, tuple[str, str]]:
    """Map `[project.scripts]` names to module and function targets."""
    data = ways_in.read_pyproject(repo)
    scripts = data.get("project", {}).get("scripts", {})
    out: dict[str, tuple[str, str]] = {}
    if isinstance(scripts, dict):
        for name, target in scripts.items():
            if isinstance(target, str) and ":" in target:
                module, func = target.split(":", 1)
                out[str(name)] = (module.strip(), func.strip())
    return out


def _plain_ways(module: str, record: dict[str, Any], is_root: bool) -> list[dict[str, str]]:
    """Get entry points from `__main__`, `main`, and public package-root names."""
    out: list[dict[str, str]] = []
    if module.endswith(".__main__"):
        pkg = module[: -len(".__main__")]
        out.append(
            {"kind": "main_module", "name": f"python -m {pkg}", "module": module, "target": ""}
        )
    if any(f["name"] == "main" for f in record["functions"]):
        out.append({"kind": "main_function", "name": "main", "module": module, "target": "main"})
    if is_root:
        out += [
            {"kind": "public_function", "name": f["name"], "module": module, "target": ""}
            for f in record["functions"]
        ]
    return out


def entry_points(
    repo: Path, prefixes: set[str], components: dict[str, Any], sources: dict[str, str]
) -> list[dict[str, str]]:
    """Read entry points from the source tree.

    Include console scripts, `__main__`, `main`, literal argparse subcommands, and
    public package-root functions. `systemap.ways_in` adds framework routes, click,
    typer, cleo, Django commands, tasks, and plugin hooks.

    Judgement gives findings for entry points without examined sequences.
    A subcommand records its console script so the display can use the typed command.
    """
    scripts = {
        name: (module, func)
        for name, (module, func) in sorted(console_scripts(repo).items())
        if module in components
    }
    script_of_module = {module: name for name, (module, _f) in scripts.items()}
    out: list[dict[str, str]] = []
    for name, (module, func) in scripts.items():
        out.append({"kind": "console_script", "name": name, "module": module, "target": func})
    for module, record in sorted(components.items()):
        out += _plain_ways(module, record, module in prefixes)
        out += [
            {
                "kind": "subcommand",
                "name": sub,
                "module": module,
                "target": script_of_module.get(module, ""),
            }
            for sub in subcommands(sources.get(module, ""))
        ]
        out += ways_in.in_source(module, sources.get(module, ""))
    out += ways_in.in_pyproject(ways_in.read_pyproject(repo), components)
    return _once_each(out)


def _once_each(points: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep each entry point one time when source readers find identical records."""
    seen: set[tuple[str, str, str, str]] = set()
    kept = []
    for point in points:
        key = (point["kind"], point["name"], point["module"], point["target"])
        if key not in seen:
            seen.add(key)
            kept.append(point)
    return kept


def entry_label(point: dict[str, str]) -> str:
    """Give the entry point a display name for the reader."""
    kind, name, module, target = point["kind"], point["name"], point["module"], point["target"]
    if kind == "console_script":
        return f"{name} (console script)"
    if kind == "main_module":
        return name
    if kind == "main_function":
        return f"main() in {module}"
    if kind == "subcommand":
        return f"{target} {name} (subcommand)" if target else f"{name} (subcommand in {module})"
    return ways_in.label(point) or f"{name}() in {module}"


def entry_identity(point: dict[str, str]) -> str:
    """Get an entry-point identity that is separate from its display name."""
    return json.dumps(
        [point["kind"], point["module"], point.get("target", ""), point["name"]],
        separators=(",", ":"),
        ensure_ascii=False,
    )


def unknown_fact_lines(facts: dict[str, Any]) -> list[str]:
    """The TypeScript facts this extractor could not fully read or connect."""
    out: list[str] = []
    for module, record in sorted(facts.get("components", {}).items()):
        file = record.get("file", module)
        if issue := record.get("parse_error"):
            location = f"{file}:{issue['line']}" if issue.get("line") else file
            out.append(
                f"unknown surface: module {module} ({location}): {issue['reason']} "
                f"under Python {issue['parser']}"
            )
        for issue in record.get("unknown", []):
            line = issue.get("line", 0)
            location = f"{file}:{line}" if line else file
            out.append(f"unknown surface: module {module} ({location}): {issue['reason']}")
    for issue in facts.get("entry_point_issues", []):
        out.append(
            f"unknown surface: {issue['kind']} {issue['name']} -> {issue['target']}: "
            f"{issue['reason']}"
        )
    for issue in facts.get("test_file_issues", []):
        problem = issue["problem"]
        out.append(
            f"unknown surface: test file {issue['file']}:{problem.get('line', 0)}: "
            f"{problem['reason']}"
        )
    for issue in facts.get("config_issues", []):
        out.append(
            f"unknown surface: {issue['file']} extends {issue['reference']!r}: "
            "the npm tsconfig package could not be read"
        )
    return out


def inventory_issue_lines(facts: dict[str, Any]) -> list[str]:
    """List files with an unresolved source inventory."""
    out: list[str] = []
    for module, record in sorted(facts.get("components", {}).items()):
        if record.get("parse_error"):
            out.append(f"source inventory unresolved: {module} ({record['file']})")
        elif any(
            "syntax could not be parsed" in issue.get("reason", "")
            for issue in record.get("unknown", [])
        ):
            out.append(f"source inventory unresolved: {module} ({record['file']})")
    for issue in facts.get("test_file_issues", []):
        out.append(f"source inventory unresolved: test file {issue['file']}")
    return out


def _source_paths(cfg: Config, language: LanguageAdapter) -> dict[str, Path]:
    repo = cfg.root
    paths: dict[str, Path] = {}
    for pkg_dir, pkg_name in cfg.roots:
        for path in language.source_paths(pkg_dir, repo, cfg.test_dirs, cfg.test_patterns):
            if any(p in SKIP_PARTS for p in path.parts):
                continue
            module = language.module_of(path, pkg_dir, pkg_name)
            if module in paths and paths[module] != path:
                first = paths[module].relative_to(repo).as_posix()
                second = path.relative_to(repo).as_posix()
                raise ConfigError(
                    f"module id {module} is shared by {first} and {second}. Rename one file"
                )
            paths[module] = path
    return paths


def _module_facts(
    cfg: Config,
    language: LanguageAdapter,
    module: str,
    path: Path,
    prefixes: set[str],
    known: set[str],
    paths: dict[str, Path],
    context: Any,
) -> tuple[dict[str, Any], str, set[str]] | None:
    record = language.collect_module(
        path, cfg.root, module, frozenset(prefixes), known, paths, context
    )
    if record is None:
        return None
    record["id"] = module
    record["package"] = module.split(".")[0]
    record["plane"] = plane_of(module, cfg.planes)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        raw = ""
    uses = language.internal_uses(
        raw,
        prefixes,
        known,
        module=module,
        is_package=path.name == "__init__.py",
        repo=cfg.root,
        paths=paths,
        context=context,
    )
    uses.pop(module, None)
    record["uses"] = {
        target: [WHOLE_MODULE] if WHOLE_MODULE in names else sorted(names)
        for target, names in sorted(uses.items())
    }
    record["external"] = language.external_imports(
        raw, prefixes, module=module, repo=cfg.root, paths=paths, context=context
    )
    return record, raw, set(uses)


def _collect_modules(
    cfg: Config,
    language: LanguageAdapter,
    paths: dict[str, Path],
    prefixes: set[str],
    context: Any,
) -> tuple[dict[str, Any], dict[str, set[str]], dict[str, str]]:
    known = set(paths)
    components: dict[str, Any] = {}
    imports: dict[str, set[str]] = {}
    sources: dict[str, str] = {}
    for module, path in sorted(paths.items()):
        facts = _module_facts(cfg, language, module, path, prefixes, known, paths, context)
        if facts is None:
            continue
        record, raw, uses = facts
        sources[module] = raw
        imports[module] = uses
        components[module] = record
    return components, imports, sources


def _link_importers(components: dict[str, Any], imports: dict[str, set[str]]) -> None:
    importers: dict[str, set[str]] = defaultdict(set)
    for module, deps in imports.items():
        for dep in deps:
            importers[dep].add(module)
    for module, record in components.items():
        record["imports"] = sorted(imports.get(module, set()))
        record["imported_by"] = sorted(importers.get(module, set()))


def _attach_test_facts(components: dict[str, Any], guards: dict[str, list[dict[str, Any]]]) -> None:
    for module, record in components.items():
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in guards.get(module, []):
            if item["name"] in seen:
                continue
            seen.add(item["name"])
            unique.append(item)
        unique.sort(key=lambda t: (not t["primary"], t["name"]))
        record["tests_total"] = len(unique)
        record["tests_primary"] = sum(1 for t in unique if t["primary"])
        record["tests_digest"] = hashlib.sha256(
            json.dumps(sorted(t["name"] for t in unique)).encode("utf-8")
        ).hexdigest()
        # The full list is recoverable from the tree; the map keeps a sample so
        # a committed file that changes on every merge stays diffable by eye.
        # Names only: the sentence is derived where it is displayed.
        record["tests"] = [t["name"] for t in unique[:TESTS_KEPT]]


def _provenance(cfg: Config, context: Any) -> dict[str, Any]:
    from systemap.typescript_config import compiler_settings

    compiler = getattr(context, "compiler", None)
    settings = {
        "language": cfg.language,
        "roots": cfg.package_roots,
        "tests_dirs": cfg.test_dirs,
        "test_patterns": cfg.test_patterns,
        "planes": cfg.planes,
        "spec_path": cfg.spec_path,
        "compiler": compiler_settings(compiler, cfg.root) if compiler is not None else None,
    }
    files: dict[str, str] = {}
    for relative in ("pyproject.toml", "package.json", "tsconfig.json"):
        path = cfg.root / relative
        if path.is_file():
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    # CPython patch releases share a grammar. Keep minor changes visible,
    # because they can change the AST used to derive the public surface.
    parser = f"{sys.version_info.major}.{sys.version_info.minor}"
    if cfg.language == "typescript":
        parser = ", ".join(
            f"{package} {importlib.metadata.version(package)}"
            for package in ("tree-sitter", "tree-sitter-typescript")
        )
    return {
        "parser": parser,
        "settings": hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest(),
        "files": files,
    }


def _facts_file(
    cfg: Config,
    prefixes: set[str],
    components: dict[str, Any],
    tests_dirs: tuple[str, ...],
    points: list[dict[str, str]],
    entry_issues: list[dict[str, str]],
    context: Any,
) -> dict[str, Any]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cfg.root, capture_output=True, text=True
    )
    facts = {
        "version": FORMAT,
        "built_at_commit": head.stdout.strip() if head.returncode == 0 else "",
        "packages": sorted(prefixes),
        "provenance": _provenance(cfg, context),
        "tests_dirs": list(tests_dirs),
        "spec_sections": spec_sections(cfg.root, cfg.spec_path),
        "entry_points": points,
        "components": components,
    }
    if entry_issues:
        facts["entry_point_issues"] = entry_issues
    test_issues = getattr(context, "test_issues", [])
    if cfg.language == "typescript":
        facts["entry_point_issues"] = entry_issues
        facts["test_file_issues"] = test_issues
        facts["config_issues"] = [
            {"file": file, "reference": reference} for file, reference in context.compiler.issues
        ]
    return facts


def build(cfg: Config) -> dict[str, Any]:
    """Make facts for the tree at `cfg.root`, ready for JSON output."""
    repo = cfg.root
    language = language_for(cfg)
    roots = cfg.roots
    prefixes = {name for _, name in roots}
    paths = _source_paths(cfg, language)
    context = language.context(repo, paths, cfg.test_dirs, cfg.test_patterns)
    components, imports, sources = _collect_modules(cfg, language, paths, prefixes, context)
    # Re-export kinds require every defining module to have been parsed.
    resolve_reexports(components)
    _link_importers(components, imports)
    guards = language.collect_tests(repo, cfg.test_dirs, prefixes, paths, context)
    _attach_test_facts(components, guards)
    points, issues = language.entry_points(repo, prefixes, components, sources, context)
    return _facts_file(cfg, prefixes, components, cfg.test_dirs, points, issues, context)


def drift(fresh: dict[str, Any], stored: dict[str, Any]) -> list[str]:
    """Compare stored facts with extracted facts. An empty list means no differences."""
    out: list[str] = []
    new_c, old_c = fresh["components"], (stored or {}).get("components", {})
    # A file written by an older extractor records less than this one
    # reads (a re-export, say), whatever the tree did since.
    if stored and stored.get("version") != fresh.get("version"):
        out.append(
            f"facts format {stored.get('version')} is older than the extractor's "
            f"{fresh.get('version')}; the file records less than the extractor reads"
        )
    if stored and stored.get("provenance") != fresh.get("provenance"):
        out.append("extraction inputs changed since the map was built")
    out.extend(_entry_drift(fresh, stored))
    added = sorted(set(new_c) - set(old_c))
    gone = sorted(set(old_c) - set(new_c))
    moved = sorted(m for m in set(new_c) & set(old_c) if new_c[m]["sha"] != old_c[m]["sha"])
    # A source module's hash says nothing about the TESTS that guard it. A new
    # test file changes what the system guarantees without touching a single
    # module, and comparing only shas would let that pass as current. `fresh`
    # is a full rebuild, so the attribution is authoritative here.
    guards_changed = sorted(
        m
        for m in set(new_c) & set(old_c)
        if new_c[m].get("tests_digest") != old_c[m].get("tests_digest")
    )
    for m in added:
        out.append(f"missing from the map: {m}")
    for m in gone:
        out.append(f"in the map but gone from the tree: {m}")
    for m in moved:
        out.append(f"code changed since the map was built: {m}")
    out.extend(_component_drift(new_c, old_c, moved, guards_changed))
    return out


def _entry_drift(fresh: dict[str, Any], stored: dict[str, Any]) -> list[str]:
    """Compare entry points separately because a pyproject edit has no module hash."""
    new_entries = fresh.get("entry_points", [])
    old_entries = (stored or {}).get("entry_points", [])
    new_e = {entry_label(e) for e in new_entries}
    old_e = {entry_label(e) for e in old_entries}
    out = [f"entry point not in the map: {label}" for label in sorted(new_e - old_e)]
    out += [
        f"entry point in the map but gone from the tree: {label}" for label in sorted(old_e - new_e)
    ]
    if {json.dumps(e, sort_keys=True) for e in new_entries} != {
        json.dumps(e, sort_keys=True) for e in old_entries
    } and new_e == old_e:
        out.append("entry point targets changed since the map was built")
    return out


def _component_drift(
    new_c: dict[str, Any], old_c: dict[str, Any], moved: list[str], guards_changed: list[str]
) -> list[str]:
    """Compare derived module facts and test references after source changes."""
    out: list[str] = []
    derived = (
        "uses",
        "imports",
        "imported_by",
        "external",
        "names",
        "functions",
        "classes",
        "errors",
        "constants",
        "unknown",
        "parse_error",
    )
    for m in sorted(set(new_c) & set(old_c) - set(moved)):
        if any(new_c[m].get(key) != old_c[m].get(key) for key in derived):
            out.append(f"derived facts changed since the map was built: {m}")
    for m in guards_changed:
        was = (old_c[m] or {}).get("tests_total", 0)
        now = new_c[m].get("tests_total", 0)
        out.append(f"tests guarding it changed ({was} -> {now}): {m}")
    return out


def mapping_drift(fresh: dict[str, Any], model: Model, prefixes: set[str]) -> list[str]:
    """Find claimed modules absent from the source tree.

    Component module claims are authored input. A rename can leave a claim for an
    absent module. This function finds that difference and also examines layout.
    """
    known = set(fresh["components"])
    out: list[str] = []
    for c in model.components:
        for m in c.implemented_by:
            # A symbol claim names its module before the colon; the name
            # itself is the entry rule's business.
            module = m.partition(":")[0] if is_symbol(m) else m
            if module.split(".")[0] in prefixes and not any(
                module_matches(module, k) for k in known
            ):
                out.append(
                    f"{c.id} has a module claim for {module}, which is missing from the facts."
                )
    out.extend(f"layout: {p}" for p in model.layout_problems())
    return out


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


def is_empty_marker(record: Mapping[str, Any]) -> bool:
    """Determine whether a record is an empty package marker.

    The file must be `__init__.py`, without public names, internal imports, external
    imports, parse errors, unknown records, or top-level calls.
    Coverage excludes these markers, and the extraction summary lists them.
    A root that re-exports names or imports modules is not empty.
    The summary and coverage rule use this same definition.
    """
    if not str(record.get("file", "")).endswith("__init__.py"):
        return False
    if record.get("parse_error") or record.get("unknown") or record.get("executes"):
        return False
    return not public_names(record) and not record.get("imports") and not record.get("external")


def empty_markers(facts: Mapping[str, Any]) -> list[str]:
    """List each empty package marker by module name."""
    return sorted(m for m, r in facts.get("components", {}).items() if is_empty_marker(r))


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
        tests = f"{guarded} test functions import a module, {primary} in a file named after it"
    elif dirs:
        # Zero is a finding, not a count: say where the extractor looked, so
        # a tests directory it did not find is set in `tests_dir`.
        tests = f"none import a module; searched {', '.join(dirs)}"
    else:
        tests = "none import a module; no directory named tests or test was found"
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
            f"  empty package markers: {len(markers)} ({', '.join(markers)}); an __init__ with "
            "no public names and no imports, left out of the coverage rule"
        )
    return out
