"""Extract the derived tier of the system map from the working tree.

Everything here is a fact read out of the code: module graph, public surface,
owned types, refusals, every public module-level name, the third-party
imports, the tests that guard each component, and the entry points a run of
the system can start from. No prose is invented; what the system is MEANT
to do lives in the consumer's model module, and the page styles the two
differently on purpose.

Every field written is declared once, in `FIELDS`; the skill's schema
reference is generated from that table and a test compares the two, so
the facts file cannot carry a field the reader was not told about.
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
FORMAT = 3
TESTS_KEPT = 25
CONSTANTS_KEPT = 14
UPPER_NAME = re.compile(r"[A-Z][A-Z0-9_]{2,}")


class PythonLanguage:
    """Python syntax as the language-neutral extractor asks to read it."""

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
    """The one source-language reader configured for this repository."""
    if cfg.language == PYTHON.name:
        return PYTHON
    if cfg.language == "typescript":
        try:
            from systemap.typescript import TYPESCRIPT
        except ModuleNotFoundError as exc:
            if exc.name not in {"tree_sitter", "tree_sitter_typescript"}:
                raise
            raise ConfigError(
                "TypeScript support is not installed; install systemap[typescript]"
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
        "the facts format; 3, with extraction provenance and complete test identity digests; "
        "`extract --check` reports a file of an older format as stale",
    ),
    (
        "facts",
        "built_at_commit",
        "the commit the tree was read at (HEAD when extract ran), or empty outside git; the "
        "page prints it as `facts from <sha>`, and it is the commit before the one that "
        "records the facts, since they are committed after they are read",
    ),
    ("facts", "packages", "the import names of the package roots"),
    (
        "facts",
        "provenance",
        "the source-language parser and extraction inputs used for these facts; a change "
        "requires a fresh review even when source files are unchanged",
    ),
    (
        "facts",
        "tests_dirs",
        "the directories test files were read from, relative to the root: the "
        "configured `tests_dir`, or every directory named `tests` or `test`",
    ),
    ("facts", "spec_sections", "the `##` headings of `spec_path`, each with `level` and `title`"),
    ("facts", "entry_points", "where a run can start: one record per point, fields below"),
    (
        "facts",
        "entry_point_issues",
        "package entry targets or Python decorators whose framework binding could not be "
        "verified; empty when none",
    ),
    (
        "facts",
        "test_file_issues",
        "TypeScript-only: test files that could not be parsed for their imports and names; "
        "empty when none",
    ),
    (
        "facts",
        "config_issues",
        "TypeScript-only: npm tsconfig packages named by `extends` that could not be read; "
        "empty when none",
    ),
    ("facts", "components", "one record per module, keyed by its dotted name, fields below"),
    ("module", "id", "the dotted module name"),
    ("module", "file", "the path relative to the root"),
    ("module", "package", "the first segment of the name"),
    ("module", "plane", "the second segment when `planes` names it, else `core`"),
    ("module", "loc", "lines in the file"),
    ("module", "sha", "twelve hex digits of the source's SHA-1: the change detector's key"),
    ("module", "source_sha256", "full SHA-256 of source bytes, for reviewed source references"),
    (
        "module",
        "syntax_sha",
        "digest of parsed syntax without comments or formatting, for source review",
    ),
    ("module", "docstring", "the first paragraph of the module docstring, capped"),
    ("module", "functions", "public functions: `name` and `signature`"),
    (
        "module",
        "classes",
        "public classes that are not errors: `name` and `methods` (public method signatures)",
    ),
    ("module", "errors", "public classes named or based on Error or Exception, the same fields"),
    ("module", "constants", "UPPER_CASE assignments: `name` and `value`, the first 14"),
    (
        "module",
        "names",
        "every public module-level name in source order, with its `kind`: `function`, "
        "`class`, `error`, `constant` (UPPER_CASE), `object` (any other assignment, "
        "such as `app` or `root_agent`), or TypeScript `unknown` when the kind cannot be "
        "determined. A package `__init__` also lists every name it "
        "imports from the package's own modules, with `reexport_of` naming the module "
        "that defines it and the kind that module gives it (`module` for a submodule "
        "imported whole). A component's `entry` and `interface` may name any of them",
    ),
    (
        "module",
        "api",
        "the complete exported identities used by surface diffs: exported name, display bucket, "
        "and a declaration fingerprint that excludes callable bodies",
    ),
    (
        "module",
        "executes",
        "Python-only: a top-level call makes a package initializer more than an empty marker",
    ),
    (
        "module",
        "unknown",
        "TypeScript-only surface entries the parser could not read or classify; each has a source "
        "line, reason and short source excerpt",
    ),
    (
        "module",
        "uses",
        "the package's modules this one imports, each with the names taken from it, "
        "or `*` for the whole module",
    ),
    ("module", "imports", "the keys of `uses`"),
    ("module", "imported_by", "the package's modules that import this one"),
    (
        "module",
        "external",
        "third-party modules imported, as the dotted names written in the import "
        "(`anthropic`, `google.adk`); the standard library and the package's own "
        "modules are left out. The judgement's `model sdk` line reads it",
    ),
    ("module", "tests_total", "how many test functions import this module"),
    ("module", "tests_primary", "how many of those sit in a file named after the module"),
    ("module", "tests", "the names of up to 25 of those tests, primary first"),
    (
        "module",
        "tests_digest",
        "a digest of every qualified test identity, including those not displayed",
    ),
    (
        "module",
        "parse_error",
        "Python-only: the source file could not be read or parsed, with line and parser version",
    ),
    (
        "entry point",
        "kind",
        "`console_script`, `main_module`, `main_function`, `subcommand` or `public_function`",
    ),
    (
        "entry point",
        "name",
        "the script name, the `python -m` line, `main`, the subcommand word, or the function name",
    ),
    ("entry point", "module", "the module that defines it"),
    (
        "entry point",
        "target",
        "the function a console script names, or the console script a subcommand "
        "belongs to; else empty",
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
    """The facts section of the skill's schema reference, from `FIELDS`."""
    out = [
        "## The facts file",
        "",
        "`docs/map/map.json` by default, written by `systemap extract`. Every field,",
        "from the extractor's own table (`systemap.extract.FIELDS`):",
    ]
    for scope, title in SCOPE_TITLES.items():
        out += ["", f"**{title}**", ""]
        out += [f"- `{name}`: {what}." for sc, name, what in FIELDS if sc == scope]
    out += [
        "",
        "**The extract summary**",
        "",
        "The counts `systemap extract` prints, each mapped to a field above, and none of",
        "them for the map: `modules` counts the records under `components`; `functions`,",
        "`classes` and `errors` sum each module's field of that name; `tests` sums",
        "`tests_total`, and the number in a file named after the module `tests_primary`;",
        "`empty package markers` lists every `__init__` record with no public `names`",
        "and nothing under `imports` or `external`, which the coverage rule leaves out on",
        "its own.",
    ]
    return "\n".join(out) + "\n"


def module_of(path: Path, pkg_dir: Path, pkg_name: str) -> str:
    rel = path.relative_to(pkg_dir).with_suffix("")
    parts = [p for p in rel.parts if p != "__init__"]
    return ".".join([pkg_name, *parts]) if parts else pkg_name


def plane_of(module: str, planes: tuple[str, ...]) -> str:
    """The architectural plane a module belongs to, from its dotted path."""
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
    """The first paragraph of a docstring, capped.

    The map is read for orientation, not as a mirror of the source: the page
    shows a module's opening line, and the file itself is one click away. Storing
    every docstring in full doubled the facts file for text nobody rendered.
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
    """The public surface of one module's source, or None if it cannot parse.

    This is the ONE definition of "public surface" in the map: the extractor
    stores it and the change detector diffs it between two git blobs, so the
    two can never disagree about what a module exports.

    A package `__init__` (`is_package`, with its dotted `module` name and
    the package `prefixes`) also records the names it imports from the
    package's own modules, under `names` with `reexport_of`: the package's
    public face is those names, and a card may name one as its entry. The
    kind is filled in by `build`, which knows the defining module; here it
    is `reexport`.
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
    """Statements whose top-level branch is decidable without running the module."""
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
    """The dotted module a `from ... import` in a package `__init__` reads from,
    when it is one of the package's own; None for anything else."""
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
    """Give every re-exported name the kind its defining module records.

    `from . import mod` re-exports a module: its kind is `module` and
    `reexport_of` the module itself. A name the source module does not
    define (imported from elsewhere in turn, or from a module the facts
    lack) keeps `reexport_of` and takes the kind `object`.
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
        normalized = ast.dump(ast.parse(raw), include_attributes=False)
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
    """target module -> the names this source takes from it.

    A value containing WHOLE_MODULE means the source imported the module
    itself, so any name in it may be used. Relative imports resolve against
    `module` (the importer's own dotted name); without it they are skipped.
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
    """The third-party modules one source imports, as the dotted names written.

    The standard library, `__future__` and the package's own modules are
    left out; relative imports are the package's own. The names are kept
    dotted (`google.adk`, not `google`) because that is the level at which
    a model SDK is told apart from its namespace.
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
    """Test functions in one file, qualified by their enclosing definitions."""
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
    """module -> the behaviours asserted by tests that import it.

    `tests_dirs` are read in order; a file under two of them is read once.
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
    """The argparse subcommand names one module's source adds, where detectable.

    A call `<anything>.add_parser("name", ...)` with a literal first
    argument is a subcommand. A name built from a variable is not
    detected; the judgement can only ask about what the tree states.
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
    """name -> (module, function) from `[project.scripts]` in pyproject.toml."""
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
    """The ways in that need no framework: a `__main__`, a `main`, a root's public names."""
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
    """Where a run of the system can start, read out of the tree.

    Console scripts in pyproject.toml, `__main__` modules, `main`
    functions, argparse subcommands where detectable, and the public
    functions of each package root. `systemap.ways_in` adds the ones a
    framework registers: web routes, click, typer, cleo and Django
    commands, background tasks, and published plugin hooks. Every one is
    a walk a reader may need; `systemap judgement` asks about each that
    has no journey. A subcommand carries the console script that reaches
    its module, so the judgement can name it the way a person types it.
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
    """The ways in, each named once: two readers can find the same one."""
    seen: set[tuple[str, str, str, str]] = set()
    kept = []
    for point in points:
        key = (point["kind"], point["name"], point["module"], point["target"])
        if key not in seen:
            seen.add(key)
            kept.append(point)
    return kept


def entry_label(point: dict[str, str]) -> str:
    """The entry point the way a person would name it."""
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
    """Exact, stable identity of a way in, separate from its display name."""
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
    """Discovered files whose source inventory could not be read completely."""
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
                    f"module id {module} is shared by {first} and {second}; rename one file"
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
    settings = {
        "language": cfg.language,
        "roots": cfg.package_roots,
        "tests_dirs": cfg.test_dirs,
        "test_patterns": cfg.test_patterns,
        "planes": cfg.planes,
        "spec_path": cfg.spec_path,
        "compiler": repr(getattr(context, "compiler", None)),
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
    """The facts for the tree at `cfg.root`, ready to be written as JSON."""
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
    """Ways the stored facts no longer describe the tree. Empty means current."""
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
    """Compare entry points separately: a pyproject change has no module hash."""
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
    """Compare derived module facts and test attribution after source changes."""
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
    """Modules the model claims but the tree does not have.

    The component-to-module mapping is the one hand-authored input the facts
    have. Left unchecked, a rename would quietly leave a card on the page
    for code that is gone instead of failing loudly. The layout itself is
    checked too, since a card drawn outside its band is the same kind of
    quiet lie.
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
                out.append(f"{c.id} names module {module} which is not in the facts")
    out.extend(f"layout: {p}" for p in model.layout_problems())
    return out


def read_facts(path: Path) -> dict[str, Any]:
    """The stored facts, or an empty table when there are none or they do not parse."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data) if isinstance(data, dict) else {}


def dumps(facts: dict[str, Any]) -> str:
    """The facts as committed: compact, keys sorted, one module record per line.

    A pretty-printed file was 635 KB on a 144-module tree and tripped a
    repository's large-file hook. Each module's record is one line with no
    spaces, so the file stays small and a diff between two commits still
    reads module by module; the top-level keys are one per line too.
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
    """Is one module record an empty package marker?

    An `__init__.py` with no public names and no imports, inside or
    outside the package: a file that marks a directory as a package and
    nothing else. It has no place on the map, so the coverage rule leaves
    it out on its own and the extract summary lists it once; a package
    root that re-exports its modules, or imports anything, is a module
    like any other. This is the one definition; the summary and the
    coverage rule both read it.
    """
    if not str(record.get("file", "")).endswith("__init__.py"):
        return False
    if record.get("parse_error") or record.get("unknown") or record.get("executes"):
        return False
    return not public_names(record) and not record.get("imports") and not record.get("external")


def empty_markers(facts: Mapping[str, Any]) -> list[str]:
    """Every empty package marker in the facts, by name."""
    return sorted(m for m, r in facts.get("components", {}).items() if is_empty_marker(r))


def summary(facts: dict[str, Any]) -> list[str]:
    """The counts printed after an extract, labelled by the field each sums.

    The map carries no counts (the skill's rule); these feed the change
    detector, and the header says so, so an agent reading the numbers does
    not copy them onto a card. Each label is a field of the facts file, so
    the reference maps every word: `modules` counts `components`, the next
    three sum each module's `functions`, `classes` and `errors`, `tests`
    sums `tests_total` and `tests_primary`, and the markers are the
    `__init__` records with no public names and no imports.
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
