"""The TypeScript adapter reads TypeScript and TSX into language-neutral source facts."""

from __future__ import annotations

import fnmatch
import hashlib
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from systemap import typescript_entry
from systemap.completeness import parse_state
from systemap.config import ConfigError
from systemap.source_facts import standard_label
from systemap.source_text import read_problems
from systemap.typescript_config import (
    DECLARATION_SUFFIXES,
    SOURCE_SKIP,
    TypeScriptConfig,
    alias_targets,
    input_files,
    is_alias,
    load_typescript_config,
    root_candidates,
    source_files,
)
from systemap.typescript_projects import TypeScriptProjects, path_choices, without_script_suffix
from systemap.typescript_repo import (
    TypeScriptRepository,
    compiler_record,
    configured_out_dir,
    out_dir_below,
    ts_skipped,
)
from systemap.typescript_surface import parse_problem, parse_surface
from systemap.typescript_syntax import _tree as parse_tree
from systemap.typescript_syntax import syntax_tree
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
        raw, problems = read_problems(path)
    except OSError:
        return {}
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
        {"file": path.relative_to(repo).as_posix(), "problem": _problem(0, reason, "")}
        for reason in problems
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


def _module_name(name: str) -> str:
    return name.removeprefix("@").replace("/", ".").replace("-", "_")


def _test_file(path: str, tests_dirs: tuple[str, ...], patterns: tuple[str, ...]) -> bool:
    relative = PurePosixPath(path).as_posix()
    if PurePosixPath(path).suffix not in SOURCE_SUFFIXES or relative.endswith(DECLARATION_SUFFIXES):
        return False
    if any(relative.startswith(f"{folder.rstrip('/')}/") for folder in tests_dirs if folder):
        return True
    if _test_name(PurePosixPath(path)):
        return True
    return any(
        fnmatch.fnmatchcase(relative, pattern)
        or fnmatch.fnmatchcase(relative, pattern.replace("**/", ""))
        for pattern in patterns
    )


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
    compiler = context.compiler_for(importer)
    if specifier.startswith("."):
        targets = _relative_targets(specifier, importer, compiler.root_dirs)
    else:
        targets = alias_targets(specifier, compiler, context.repo)
    found = _first_target(targets, context.modules_by_path)
    if found is not None or specifier.startswith("."):
        return found
    normalized = _module_name(without_script_suffix(specifier))
    return next((name for name in (normalized, f"{normalized}.index") if name in paths), None)


def _relative_targets(specifier: str, importer: Path, root_dirs: tuple[Path, ...]) -> list[Path]:
    relative = (importer.parent / without_script_suffix(specifier)).resolve()
    targets = [relative]
    containing = [root for root in root_dirs if relative.is_relative_to(root)]
    if containing:
        source_root = max(containing, key=lambda root: len(root.parts))
        tail = relative.relative_to(source_root)
        targets.extend(root / tail for root in root_dirs if root != source_root)
    return targets


def _first_target(targets: list[Path], modules_by_path: dict[Path, str]) -> str | None:
    return next(
        (
            modules_by_path[choice.resolve()]
            for target in targets
            for choice in path_choices(target)
            if choice.resolve() in modules_by_path
        ),
        None,
    )


def _module_candidate(specifier: str, module: str) -> str:
    specifier = without_script_suffix(specifier)
    if not specifier.startswith("."):
        return _module_name(specifier)
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
        target = _target_from_path(specifier, importer, paths, context)
        if target:
            return target
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
        original = next(
            (child for child in specifier.named_children if child.type == "identifier"), None
        )
        if original is not None:
            out.add(_text(original))
    return out


def _exported_names(node: Any) -> set[str]:
    clause = next((child for child in node.named_children if child.type == "export_clause"), None)
    if clause is None:
        return {WHOLE_MODULE}
    out: set[str] = set()
    for specifier in (child for child in clause.named_children if child.type == "export_specifier"):
        original = next(
            (
                child
                for child in specifier.named_children
                if child.type in ("identifier", "type_identifier")
            ),
            None,
        )
        if original is not None:
            out.add(_text(original))
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
    source = node.child_by_field_name("source")
    if source is None or source.type != "string":
        return ""
    fragment = next(
        (child for child in source.named_children if child.type == "string_fragment"), None
    )
    return (fragment.text or b"").decode("utf-8") if fragment is not None else ""


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
    arguments = node.child_by_field_name("arguments")
    first = arguments.named_children[0] if arguments and arguments.named_children else None
    if first is None or first.type != "string":
        return None
    fragment = next(
        (child for child in first.named_children if child.type == "string_fragment"),
        None,
    )
    return _text(fragment) if fragment is not None else None


def _imports(root: Any) -> Iterator[tuple[str, set[str]]]:
    yield from _static_imports(root)
    yield from _dynamic_imports(root)


def _program_inputs(inputs: list[Path], compiler: TypeScriptConfig, repo: Path) -> list[Path]:
    """This function adds source files from tsconfig inputs before it calculates the output
    root.
    """
    seen = {path.resolve() for path in inputs}
    queue = list(seen)
    for path in queue:
        for found in _program_dependencies(path, compiler, repo):
            if found not in seen:
                seen.add(found)
                queue.append(found)
    return queue


def _first_existing_target(targets: list[Path]) -> Path | None:
    return next(
        (
            choice.resolve()
            for target in targets
            for choice in path_choices(target)
            if choice.is_file()
        ),
        None,
    )


def _program_dependencies(path: Path, compiler: TypeScriptConfig, repo: Path) -> Iterator[Path]:
    try:
        root = syntax_tree(path.read_text(encoding="utf-8"), path.as_posix())
    except (OSError, UnicodeError):
        return
    for specifier, _ in _imports(root):
        targets = (
            _relative_targets(specifier, path, compiler.root_dirs)
            if specifier.startswith(".")
            else alias_targets(specifier, compiler, repo)
        )
        found = _first_existing_target(targets)
        if found is not None and not found.name.endswith(DECLARATION_SUFFIXES):
            yield found


def _projects(repo: Path, compiler: TypeScriptConfig, paths: dict[str, Path]) -> TypeScriptProjects:
    """This function loads the tsconfig project of each source module.

    A tsconfig error then stops the extraction before the modules are read.
    """
    projects = TypeScriptProjects(repo, compiler)
    for path in paths.values():
        projects.config_for(path)
    return projects


def _node_module(specifier: str) -> bool:
    """This function tells if a specifier names a built-in module of Node.js."""
    return specifier.startswith("node:") or specifier in NODE_MODULES


def _problem(line: int, reason: str, source: str) -> dict[str, Any]:
    return {"line": line, "reason": reason, "source": source[:120]}


def _resolve_reexports(
    surface: dict[str, Any],
    path: Path,
    module: str,
    known: set[str],
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> None:
    """This function replaces each re-export specifier with its module.

    A re-export from an npm package keeps the package name and has no unknown record.
    A `*` re-export from an npm package gives no public name.
    """
    surface["names"] = [
        entry
        for entry in surface["names"]
        if not entry.get("reexport_of")
        or _resolve_reexport(entry, surface, path, module, known, paths, context)
    ]


def _resolve_reexport(
    entry: dict[str, Any],
    surface: dict[str, Any],
    path: Path,
    module: str,
    known: set[str],
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> bool:
    source = entry["reexport_of"]
    target = _resolve(source, module, known, paths, context)
    if target:
        entry["reexport_of"] = target
        return True
    star = entry.pop("star", None)
    entry["kind"] = "unknown"
    if _is_package(source, path, context):
        return not star
    surface["unknown"].append(
        _problem(1, f"the re-export target {source!r} is outside the extracted module set.", source)
    )
    return True


def _unresolved(
    root: Any,
    module: str,
    prefixes: set[str],
    known: set[str],
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> set[tuple[str, bool]]:
    """This function gives each import without a target module, and if it is local.

    A local import is a relative or absolute path, a `paths` alias, or a name below a
    package root. Another import names an npm package. Node.js modules are not included.
    """
    importer = paths.get(module)
    out: set[tuple[str, bool]] = set()
    for specifier, _names in _imports(root):
        if _node_module(specifier) or _resolve(specifier, module, known, paths, context):
            continue
        name = _module_name(specifier)
        local = any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)
        if importer is not None:
            local = local or not _is_package(specifier, importer, context)
        else:
            local = local or specifier.startswith(".")
        out.add((specifier, local))
    return out


def _is_package(specifier: str, importer: Path, context: TypeScriptContext) -> bool:
    """This function tells if an import that does not resolve names an npm package."""
    return not specifier.startswith((".", "/")) and not is_alias(
        specifier, context.compiler_for(importer)
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
        return (
            path
            for suffix in SOURCE_SUFFIXES
            for path in root.rglob(f"*{suffix}")
            if not ts_skipped(path, root, out_dir)
            and not path.name.endswith(DECLARATION_SUFFIXES)
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
        projects = _projects(repo, compiler, paths)
        return TypeScriptContext(
            repo=repo,
            modules_by_path={path.resolve(): module for module, path in paths.items()},
            compiler=projects.combined(),
            tests_dirs=tests_dirs,
            test_patterns=test_patterns,
            source_roots=root_candidates(
                compiler, _program_inputs(input_files(compiler), compiler, repo)
            ),
            projects=projects,
        )

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
                {"file": file, "reference": reference}
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
            raw, problems = read_problems(path)
        except OSError:
            return None
        surface = parse_surface(raw, path.as_posix())
        problem = _problem(0, problems[0], "") if problems else None
        if surface is None:
            problem = parse_problem(raw, path.as_posix())
            surface = {
                "docstring": "",
                "functions": [],
                "classes": [],
                "errors": [],
                "constants": [],
                "names": [],
                "api": [],
                "unknown": [problem],
            }
        surface["unknown"].extend(_problem(0, reason, "") for reason in problems)
        _resolve_reexports(surface, path, module, known, paths, context)
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

    def external_imports(
        self,
        raw: str,
        prefixes: set[str],
        module: str = "",
        repo: Path | None = None,
        paths: dict[str, Path] | None = None,
        context: TypeScriptContext | None = None,
    ) -> list[str]:
        source_path = (paths or {}).get(module)
        root = syntax_tree(raw, source_path.as_posix() if source_path else "")
        if context is None:
            return []
        found = _unresolved(root, module, prefixes, set(paths or {}), paths or {}, context)
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
        del repo
        source_path = paths.get(module)
        root = syntax_tree(raw, source_path.as_posix() if source_path else "")
        found = _unresolved(root, module, prefixes, known, paths, context)
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
