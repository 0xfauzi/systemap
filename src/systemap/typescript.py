"""The TypeScript adapter reads TypeScript and TSX into language-neutral source facts."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from systemap import (
    typescript_calls,
    typescript_entry,
    typescript_package_imports,
    unknown_causes,
)
from systemap.completeness import parse_state
from systemap.config import ConfigError
from systemap.pattern_match import matches_test_pattern
from systemap.source_facts import standard_label
from systemap.source_text import read_problems
from systemap.typescript_config import (
    DECLARATION_SUFFIXES,
    SOURCE_SKIP,
    TypeScriptConfig,
    is_alias,
    load_typescript_config,
    resolved,
    root_candidates,
    source_files,
)
from systemap.typescript_projects import (
    TypeScriptProjects,
    without_script_suffix,
)
from systemap.typescript_reexport_targets import Targets, resolve_reexports
from systemap.typescript_repo import (
    TypeScriptRepository,
    compiler_record,
    configured_out_dir,
    out_dir_below,
    ts_skipped,
)
from systemap.typescript_resolve import (
    declaration_file,
    module_name,
    program_dependencies,
    target_module,
    workspace,
    workspace_module,
)
from systemap.typescript_surface import parse_problem, parse_surface
from systemap.typescript_syntax import _tree as parse_tree
from systemap.typescript_syntax import (
    first_argument,
    specifier_name,
    string_value,
    syntax_tree,
)
from systemap.typescript_tests import test_names

SOURCE_SUFFIXES = (".ts", ".tsx", ".mts", ".cts")
# The default test file names of Jest, Vitest, Playwright and Cypress.
TEST_SUFFIXES = tuple(
    f".{role}{suffix}" for role in ("test", "spec", "cy") for suffix in SOURCE_SUFFIXES
)
TEST_FILES = ("test.ts", "test.tsx")
# The file name of a module that a folder import reads, without its suffix.
INDEX = "index"
# Jest reads each file in a directory with this name as a test file.
TEST_DIRECTORY = "__tests__"
WHOLE_MODULE = "*"
CONSTANTS_KEPT = 14
TESTS_KEPT = 25
# The built-in modules of Node.js 22 (`require("module").builtinModules`). They are the
# standard library, which `external` does not include.
NODE_MODULES = frozenset(
    {
        *("_http_agent", "_http_client", "_http_common", "_http_incoming", "_http_outgoing"),
        *("_http_server", "_stream_duplex", "_stream_passthrough", "_stream_readable"),
        *("_stream_transform", "_stream_wrap", "_stream_writable", "_tls_common", "_tls_wrap"),
        *("assert", "assert/strict", "async_hooks", "buffer", "child_process", "cluster"),
        *("console", "constants", "crypto", "dgram", "diagnostics_channel", "dns"),
        *("dns/promises", "domain", "events", "fs", "fs/promises", "http", "http2", "https"),
        *("inspector", "inspector/promises", "module", "net", "os", "path", "path/posix"),
        *("path/win32", "perf_hooks", "process", "punycode", "querystring", "readline"),
        *("readline/promises", "repl", "stream", "stream/consumers", "stream/promises"),
        *("stream/web", "string_decoder", "sys", "timers", "timers/promises", "tls"),
        *("trace_events", "tty", "url", "util", "util/types", "v8", "vm", "wasi"),
        *("worker_threads", "zlib"),
    }
)


@dataclass
class TypeScriptContext:
    """This record contains indexes for module and package resolution."""

    repo: Path
    modules_by_path: dict[Path, str]
    compiler: TypeScriptConfig
    tests_dirs: tuple[str, ...]
    test_patterns: tuple[str, ...]
    # The folders tsc takes as rootDir, in the order to try; see root_candidates.
    source_roots: tuple[Path, ...] = ()
    test_issues: list[dict[str, Any]] = field(default_factory=list)
    # The tsconfig project of each file. Without it, the top-level compiler applies.
    projects: TypeScriptProjects | None = None
    # The nearest package.json above each folder (`typescript_package_imports`).
    package_scopes: dict[Path, Any] = field(default_factory=dict)
    # The folder of each workspace package name (`typescript_resolve`).
    workspaces: dict[str, Path] | None = None

    def compiler_for(self, path: Path) -> TypeScriptConfig:
        """This function gives the compiler settings of the project that contains a file."""
        return self.compiler if self.projects is None else self.projects.config_for(path)


def _test_path(
    path: Path,
    repo: Path,
    tests_dirs: tuple[str, ...],
    patterns: tuple[str, ...],
    out_dir: Path | None = None,
) -> bool:
    if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
        return False
    if ts_skipped(path, repo, out_dir):
        return False
    return _test_file(path.relative_to(repo).as_posix(), tests_dirs, patterns)


def _test_file_guards(
    path: Path,
    repo: Path,
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> dict[str, list[dict[str, Any]]]:
    try:
        raw, problems = read_problems(path, repo)
    except OSError as exc:
        raw, problems = "", [unknown_causes.read_problem(exc)]
    root = syntax_tree(raw, path.as_posix())
    if root.has_error:
        context.test_issues.append(
            {
                "file": path.relative_to(repo).as_posix(),
                "problem": parse_problem(raw, path.as_posix()),
            }
        )
        return {}
    context.test_issues.extend(
        {"file": path.relative_to(repo).as_posix(), "problem": _problem(0, *problem, "")}
        for problem in problems
    )
    targets = {
        target
        for specifier, _names in _imports(root)
        if (target := _target_from_path(specifier, path, paths, context))
    }
    names = test_names(raw, path.as_posix())
    stem = path.name.split(".", 1)[0].removeprefix("test_")
    guards: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for target in targets:
        primary = stem == target.rsplit(".", 1)[-1]
        relative = path.relative_to(repo).as_posix()
        guards[target] = [{"name": f"{relative}::{name}", "primary": primary} for name in names]
    return dict(guards)


def _test_file(path: str, tests_dirs: tuple[str, ...], patterns: tuple[str, ...]) -> bool:
    relative = PurePosixPath(path).as_posix()
    if PurePosixPath(path).suffix not in SOURCE_SUFFIXES or relative.endswith(DECLARATION_SUFFIXES):
        return False
    if any(relative.startswith(f"{folder.rstrip('/')}/") for folder in tests_dirs if folder):
        return True
    if _test_name(PurePosixPath(path)):
        return True
    return matches_test_pattern(relative, patterns)


def _test_name(path: PurePosixPath) -> bool:
    name = path.name
    return (
        name.startswith("test_")
        or name in TEST_FILES
        or name.endswith(TEST_SUFFIXES)
        or TEST_DIRECTORY in path.parts[:-1]
    )


def _target_from_path(
    specifier: str,
    importer: Path,
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> str | None:
    """Give the module that an import names (`typescript_resolve`)."""
    found = target_module(specifier, importer, context.compiler_for(importer), context)
    if found is not None or specifier.startswith("."):
        return found
    return workspace_module(specifier, importer, paths, context)


def _module_candidate(specifier: str, module: str) -> str:
    specifier = without_script_suffix(specifier)
    if not specifier.startswith("."):
        return module_name(specifier)
    parts = module.split(".")[:-1]
    for part in PurePosixPath(specifier).parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part.replace("-", "_"))
    return ".".join(parts)


def _known_module(candidate: str, known: set[str]) -> str | None:
    return next((choice for choice in (candidate, f"{candidate}.index") if choice in known), None)


def _resolve(
    specifier: str,
    module: str,
    known: set[str],
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> str | None:
    importer = paths.get(module)
    if importer is not None:
        # The file path gives the answer. A module id from the dotted name of the importer
        # is not a tsc rule: `./c` in src/a.b.ts does not name src/a/c.ts.
        return _target_from_path(specifier, importer, paths, context)
    return _known_module(_module_candidate(specifier, module), known)


def _imported_names(node: Any) -> set[str]:
    clause = next((child for child in node.named_children if child.type == "import_clause"), None)
    if clause is None:
        return {WHOLE_MODULE}
    if any(child.type == "namespace_import" for child in _walk(clause)):
        return {WHOLE_MODULE}
    out: set[str] = set()
    if any(child.type == "identifier" for child in clause.named_children):
        out.add("default")
    for specifier in (child for child in _walk(clause) if child.type == "import_specifier"):
        if original := specifier_name(specifier.child_by_field_name("name")):
            out.add(original)
    return out


def _exported_names(node: Any) -> set[str]:
    clause = next((child for child in node.named_children if child.type == "export_clause"), None)
    if clause is None:
        return {WHOLE_MODULE}
    out: set[str] = set()
    for specifier in (child for child in clause.named_children if child.type == "export_specifier"):
        # A string name, as in `export { 'a-b' as c } from`, is the name in the module.
        if original := specifier_name(specifier.child_by_field_name("name")):
            out.add(original)
    return out or {WHOLE_MODULE}


def _walk(node: Any) -> Iterator[Any]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(node: Any | None) -> str:
    return (node.text or b"").decode("utf-8") if node is not None else ""


def _syntax_tokens(node: Any) -> Iterator[str]:
    if node.type == "comment":
        return
    if not node.children:
        yield f"{node.type}:{_text(node)}"
    else:
        for child in node.children:
            yield from _syntax_tokens(child)


def _source(node: Any) -> str:
    return string_value(node.child_by_field_name("source"))


def _static_imports(root: Any) -> Iterator[tuple[str, set[str]]]:
    for node in root.named_children:
        imported = _static_import(node)
        if imported is not None:
            yield imported


def _static_import(node: Any) -> tuple[str, set[str]] | None:
    if node.has_error:
        return _error_import(node)
    specifier = _source(node)
    if node.type == "import_statement" and not specifier:
        clause = next(
            (child for child in node.named_children if child.type == "import_require_clause"),
            None,
        )
        if clause is not None and (specifier := _source(clause)):
            return specifier, {WHOLE_MODULE}
    if not specifier:
        return None
    if node.type == "import_statement":
        return specifier, _imported_names(node)
    if node.type == "export_statement":
        return specifier, _exported_names(node)
    return None


def _error_import(node: Any) -> tuple[str, set[str]] | None:
    if node.type == "export_statement" and _text(node).lstrip().startswith("export type * from"):
        if specifier := _source(node):
            return specifier, {WHOLE_MODULE}
    return None


def _dynamic_imports(root: Any) -> Iterator[tuple[str, set[str]]]:
    for node in _walk(root):
        specifier = _dynamic_specifier(node)
        if specifier is not None:
            yield specifier, {WHOLE_MODULE}


def _dynamic_specifier(node: Any) -> str | None:
    if node.type != "call_expression" or node.has_error:
        return None
    function = node.child_by_field_name("function")
    if _text(function) not in ("import", "require"):
        return None
    first = first_argument(node)
    if first is None or first.type != "string":
        return None
    return string_value(first)


def _imports(root: Any) -> Iterator[tuple[str, set[str]]]:
    yield from _static_imports(root)
    yield from _dynamic_imports(root)


def _projects(
    repo: Path, compiler: TypeScriptConfig, paths: dict[str, Path], context: TypeScriptContext
) -> TypeScriptProjects:
    """This function loads the tsconfig project of each source module.

    A tsconfig error then stops the extraction before the modules are read. The program
    of a project has the files that its files import, through the resolver of the module
    facts (`typescript_resolve`).
    """
    projects = TypeScriptProjects(
        repo,
        compiler,
        lambda path, config: program_dependencies(path, config, context, paths, _imports),
    )
    context.projects = projects
    for path in paths.values():
        projects.config_for(path)
    # The package records of the discovery used programs that were not complete.
    context.package_scopes.clear()
    return projects


def _node_module(specifier: str) -> bool:
    """This function tells if a specifier names a built-in module of Node.js."""
    return specifier.startswith("node:") or specifier in NODE_MODULES


def _problem(line: int, reason: str, cause: str, source: str) -> dict[str, Any]:
    return {"line": line, "reason": reason, "source": source[:120], "cause": cause}


def _mark_star_exports(names: list[dict[str, Any]]) -> None:
    """This function marks the names that `export * from` does not give.

    An `export *` statement does not re-export the default export of its module. The
    shared re-export resolver reads `star_export` and does not examine the name."""
    for entry in names:
        if entry.get("name") == "default":
            entry["star_export"] = False


def _reexport_targets(
    path: Path, module: str, known: set[str], paths: dict[str, Path], context: TypeScriptContext
) -> Targets:
    return Targets(
        lambda source: _resolve(source, module, known, paths, context),
        lambda source: _is_package(source, path, context),
        lambda source: declaration_file(source, path, context),
    )


def _unresolved(
    root: Any,
    module: str,
    known: set[str],
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> set[tuple[str, bool]]:
    """This function gives each import without a target module, and if it is local.

    A local import is a relative or absolute path, a `paths` alias, or an import that
    package.json makes local. Another import names an npm package. Node.js modules are
    not included.
    """
    importer = paths.get(module)
    out: set[tuple[str, bool]] = set()
    for specifier, _names in _imports(root):
        if _node_module(specifier) or _resolve(specifier, module, known, paths, context):
            continue
        package = typescript_package_imports.npm_package(specifier, importer, context)
        if package:
            # A subpath import can name an npm package or a Node.js module.
            out.update(() if _node_module(package) else ((package, False),))
            continue
        if declaration_file(specifier, importer, context):
            # A declaration file gives only types. It has no module, so no import rule
            # can apply to it, and it is not an unresolved import.
            continue
        out.add((specifier, _local(specifier, importer, context)))
    return out


def _local(specifier: str, importer: Path | None, context: TypeScriptContext) -> bool:
    """Tell if an import that does not resolve is local."""
    if importer is not None:
        return not _is_package(specifier, importer, context)
    return specifier.startswith(".")


def _is_package(specifier: str, importer: Path, context: TypeScriptContext) -> bool:
    """This function tells if an import that does not resolve names an npm package.

    A self-name import and a subpath import (`#name`) name the same package. An import of
    a different workspace package names a local package (`typescript_resolve`).
    """
    return (
        not specifier.startswith((".", "/"))
        and not is_alias(specifier, context.compiler_for(importer))
        and not typescript_package_imports.is_local(specifier, importer, context)
        and workspace(specifier, importer, context) is None
    )


class TypeScriptLanguage(TypeScriptRepository):
    """This adapter converts TypeScript syntax to the shared facts schema."""

    def source_paths(
        self,
        root: Path,
        repo: Path,
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> Iterable[Path]:
        out_dir = configured_out_dir(repo, root)
        # The walk does not enter node_modules and the other SOURCE_SKIP folders.
        return (
            path
            for path in source_files(root, SOURCE_SKIP)
            if not ts_skipped(path, root, out_dir)
            and not _test_file(path.relative_to(repo).as_posix(), tests_dirs, test_patterns)
        )

    def context(
        self,
        repo: Path,
        paths: dict[str, Path],
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> TypeScriptContext:
        try:
            compiler = load_typescript_config(repo)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        context = TypeScriptContext(
            repo=repo,
            modules_by_path={resolved(path): module for module, path in paths.items()},
            compiler=compiler,
            tests_dirs=tests_dirs,
            test_patterns=test_patterns,
        )
        projects = _projects(repo, compiler, paths, context)
        context.compiler = projects.combined()
        context.source_roots = root_candidates(compiler, projects.lazy_program_files(compiler))
        return context

    def module_of(self, path: Path, root: Path, name: str) -> str:
        parts = path.relative_to(root).with_suffix("").parts
        return ".".join((name, *(part.replace("-", "_") for part in parts)))

    def package_of(self, path: Path, root: Path, name: str) -> str:
        """Give the folder of the file as a dotted name. A dot in a file name, such as
        `user.service.ts`, does not make a package."""
        parts = path.relative_to(root).parent.parts
        return ".".join((name, *(part.replace("-", "_") for part in parts)))

    def is_package_module(self, path: Path) -> bool:
        return path.name.split(".", 1)[0] == INDEX and path.suffix in SOURCE_SUFFIXES

    def empty_marker(self, record: Mapping[str, Any], raw: str) -> bool:
        """Find an index file that has no statements: only comments, or no text.

        A file that did not parse is not empty, because its statements are not known."""
        if not self.is_package_module(Path(str(record.get("file", "")))):
            return False
        if not record.get("completeness", {}).get("parsed"):
            return False
        root = syntax_tree(raw, str(record.get("file", "")))
        return all(child.type == "comment" for child in root.named_children)

    def entry_label(self, point: Mapping[str, str]) -> str:
        return standard_label(point)

    def compiler_record(self, context: Any, repo: Path) -> dict[str, str]:
        return compiler_record(getattr(context, "compiler", None), repo)

    def extra_facts(self, context: Any, entry_issues: list[dict[str, str]]) -> dict[str, Any]:
        """Give the issue lists. Each list is written, also when it is empty."""
        return {
            "entry_point_issues": entry_issues,
            "test_file_issues": context.test_issues,
            "config_issues": [
                {"file": file, "reference": reference, "cause": unknown_causes.PACKAGE}
                for file, reference in context.compiler.issues
            ],
        }

    def module_for_path(self, repo: Path, path: str, roots: list[tuple[Path, str]]) -> str | None:
        absolute = repo / path
        if absolute.suffix not in SOURCE_SUFFIXES or absolute.name.endswith(DECLARATION_SUFFIXES):
            return None
        for root, name in roots:
            if absolute.is_relative_to(root):
                return self.module_of(absolute, root, name)
        return None

    def collect_module(
        self,
        path: Path,
        repo: Path,
        module: str,
        prefixes: frozenset[str],
        known: set[str],
        paths: dict[str, Path],
        context: TypeScriptContext,
    ) -> dict[str, Any] | None:
        del prefixes
        if path.name.endswith(DECLARATION_SUFFIXES):
            # A declaration file has no module record, as tsc emits no code for it.
            return None
        try:
            raw, problems = read_problems(path, repo)
        except OSError as exc:
            # The module stays in the facts, with a read problem: its surface is not known.
            raw, problems = "", [unknown_causes.read_problem(exc)]
        surface = parse_surface(raw, path.as_posix())
        problem = _problem(0, *problems[0], "") if problems else None
        if surface is None:
            problem = parse_problem(raw, path.as_posix())
            surface = {
                "docstring": "",
                "functions": [],
                "classes": [],
                "errors": [],
                "types": [],
                "constants": [],
                "names": [],
                "api": [],
                "unknown": [problem],
            }
        surface["unknown"].extend(_problem(0, *found, "") for found in problems)
        targets = _reexport_targets(path, module, known, paths, context)
        resolve_reexports(surface, raw, path.as_posix(), targets)
        _mark_star_exports(surface["names"])
        return {
            "file": path.relative_to(repo).as_posix(),
            "loc": len(raw.splitlines()),
            "sha": hashlib.sha1(raw.encode(), usedforsecurity=False).hexdigest()[:12],
            "source_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "syntax_sha": hashlib.sha256(
                "\0".join(_syntax_tokens(parse_tree(raw, path.as_posix()))).encode()
            ).hexdigest()[:16],
            **surface,
            "constants": surface["constants"][:CONSTANTS_KEPT],
            "completeness": parse_state(problem),
        }

    def internal_uses(
        self,
        raw: str,
        prefixes: set[str],
        known: set[str],
        module: str = "",
        is_package: bool = False,
        repo: Path | None = None,
        paths: dict[str, Path] | None = None,
        context: TypeScriptContext | None = None,
    ) -> dict[str, set[str]]:
        del prefixes, is_package, repo
        source_path = (paths or {}).get(module)
        root = syntax_tree(raw, source_path.as_posix() if source_path else "")
        if context is None:
            return {}
        uses: dict[str, set[str]] = defaultdict(set)
        for specifier, names in _imports(root):
            target = _resolve(specifier, module, known, paths or {}, context)
            if target:
                uses[target].update(names)
        return dict(uses)

    def call_sites(
        self,
        raw: str,
        module: str,
        prefixes: set[str],
        known: set[str],
        components: Mapping[str, Mapping[str, Any]],
        is_package: bool = False,
        paths: dict[str, Path] | None = None,
        context: TypeScriptContext | None = None,
    ) -> list[dict[str, Any]] | None:
        del prefixes, components, is_package
        found = paths or {}
        path = found[module].as_posix() if module in found else ""
        if context is None:
            return None
        resolve = lambda source: _resolve(source, module, known, found, context)  # noqa: E731
        return typescript_calls.call_sites(raw, path, module, resolve)

    def external_imports(
        self,
        raw: str,
        prefixes: set[str],
        module: str = "",
        repo: Path | None = None,
        paths: dict[str, Path] | None = None,
        context: TypeScriptContext | None = None,
    ) -> list[str]:
        del prefixes, repo
        source_path = (paths or {}).get(module)
        root = syntax_tree(raw, source_path.as_posix() if source_path else "")
        if context is None:
            return []
        found = _unresolved(root, module, set(paths or {}), paths or {}, context)
        return sorted(specifier for specifier, local in found if not local)

    def unresolved_imports(
        self,
        raw: str,
        prefixes: set[str],
        known: set[str],
        module: str,
        repo: Path,
        paths: dict[str, Path],
        context: TypeScriptContext,
    ) -> list[str]:
        del prefixes, repo
        source_path = paths.get(module)
        root = syntax_tree(raw, source_path.as_posix() if source_path else "")
        found = _unresolved(root, module, known, paths, context)
        return sorted(specifier for specifier, local in found if local)

    def collect_tests(
        self,
        repo: Path,
        tests_dirs: tuple[str, ...],
        prefixes: set[str],
        paths: dict[str, Path],
        context: TypeScriptContext,
    ) -> dict[str, list[dict[str, Any]]]:
        del prefixes
        out_dir = out_dir_below(repo, context.compiler.out_dir)
        files = sorted(
            path
            for path in source_files(repo, SOURCE_SKIP)
            if _test_path(path, repo, tests_dirs, context.test_patterns, out_dir)
        )
        guards: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for path in files:
            for module, entries in _test_file_guards(path, repo, paths, context).items():
                guards[module].extend(entries)
        return guards

    def entry_points(
        self,
        repo: Path,
        prefixes: set[str],
        components: dict[str, Any],
        sources: dict[str, str],
        context: TypeScriptContext,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        del sources
        return typescript_entry.entry_points(repo, prefixes, components, context)

    def parse_surface(self, raw: str, path: str = "") -> dict[str, Any] | None:
        return parse_surface(raw, path)

    def test_names(self, raw: str, path: str = "") -> list[str]:
        return test_names(raw, path)

    def is_test_file(
        self, path: str, tests_dirs: tuple[str, ...], test_patterns: tuple[str, ...] = ()
    ) -> bool:
        return _test_file(path, tests_dirs, test_patterns)


TYPESCRIPT = TypeScriptLanguage()
