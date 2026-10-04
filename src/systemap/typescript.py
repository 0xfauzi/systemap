"""Read TypeScript and TSX into systemap's language-neutral facts."""

from __future__ import annotations

import fnmatch
import hashlib
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from systemap.config import ConfigError
from systemap.typescript_config import (
    TypeScriptConfig,
    alias_targets,
    input_files,
    load_typescript_config,
    package_json,
    root_candidates,
    source_targets,
)
from systemap.typescript_surface import _tree as parse_tree
from systemap.typescript_surface import parse_problem, parse_surface, test_names

SOURCE_SUFFIXES = (".ts", ".tsx")
TEST_SUFFIXES = (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")
TEST_FILES = ("test.ts", "test.tsx")
SKIP_PARTS = {".git", ".venv", "node_modules", "build", "dist"}
WHOLE_MODULE = "*"
BUILD_DIRS = {"build", "dist", "distribution", "lib"}
BUILD_FORMATS = {"cjs", "esm", "types"}
CONSTANTS_KEPT = 14
TESTS_KEPT = 25


@dataclass
class TypeScriptContext:
    """Indexes built once so each import does constant work."""

    repo: Path
    modules_by_path: dict[Path, str]
    compiler: TypeScriptConfig
    tests_dirs: tuple[str, ...]
    test_patterns: tuple[str, ...]
    # The folders tsc takes as rootDir, in the order to try; see root_candidates.
    source_roots: tuple[Path, ...] = ()
    test_issues: list[dict[str, Any]] = field(default_factory=list)


def _test_path(
    path: Path, repo: Path, tests_dirs: tuple[str, ...], patterns: tuple[str, ...]
) -> bool:
    if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
        return False
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    return _test_file(path.relative_to(repo).as_posix(), tests_dirs, patterns)


def _test_file_guards(
    path: Path,
    repo: Path,
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> dict[str, list[dict[str, Any]]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    root = parse_tree(raw, path.as_posix())
    if root.has_error:
        context.test_issues.append(
            {
                "file": path.relative_to(repo).as_posix(),
                "problem": parse_problem(raw, path.as_posix()),
            }
        )
        return {}
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


def _without_script_suffix(specifier: str) -> str:
    for suffix in (".d.ts", ".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs"):
        if specifier.endswith(suffix):
            return specifier[: -len(suffix)]
    return specifier


def _test_file(path: str, tests_dirs: tuple[str, ...], patterns: tuple[str, ...]) -> bool:
    relative = PurePosixPath(path).as_posix()
    if PurePosixPath(path).suffix not in SOURCE_SUFFIXES or relative.endswith(".d.ts"):
        return False
    if any(relative.startswith(f"{folder.rstrip('/')}/") for folder in tests_dirs if folder):
        return True
    name = PurePosixPath(path).name
    if name.startswith("test_") or name in TEST_FILES or name.endswith(TEST_SUFFIXES):
        return True
    return any(
        fnmatch.fnmatchcase(relative, pattern)
        or fnmatch.fnmatchcase(relative, pattern.replace("**/", ""))
        for pattern in patterns
    )


def _path_choices(target: Path) -> list[Path]:
    if target.suffix in SOURCE_SUFFIXES:
        return [target]
    if target.suffix in (".js", ".jsx", ".mjs", ".cjs"):
        target = Path(_without_script_suffix(str(target)))
    return [Path(str(target) + suffix) for suffix in SOURCE_SUFFIXES] + [
        target / f"index{suffix}" for suffix in SOURCE_SUFFIXES
    ]


def _target_from_path(
    specifier: str,
    importer: Path,
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> str | None:
    if specifier.startswith("."):
        targets = _relative_targets(specifier, importer, context.compiler.root_dirs)
    else:
        targets = alias_targets(specifier, context.compiler, context.repo)
    found = _first_target(targets, context.modules_by_path)
    if found is not None or specifier.startswith("."):
        return found
    normalized = _module_name(_without_script_suffix(specifier))
    return next((name for name in (normalized, f"{normalized}.index") if name in paths), None)


def _relative_targets(specifier: str, importer: Path, root_dirs: tuple[Path, ...]) -> list[Path]:
    relative = (importer.parent / _without_script_suffix(specifier)).resolve()
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
            for choice in _path_choices(target)
            if choice.resolve() in modules_by_path
        ),
        None,
    )


def _module_candidate(specifier: str, module: str) -> str:
    specifier = _without_script_suffix(specifier)
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
    """Include source files reached from tsconfig inputs before inferring emit root."""
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
            for choice in _path_choices(target)
            if choice.is_file()
        ),
        None,
    )


def _program_dependencies(path: Path, compiler: TypeScriptConfig, repo: Path) -> Iterator[Path]:
    try:
        root = parse_tree(path.read_text(encoding="utf-8"), path.as_posix())
    except (OSError, UnicodeError):
        return
    for specifier, _ in _imports(root):
        targets = (
            _relative_targets(specifier, path, compiler.root_dirs)
            if specifier.startswith(".")
            else alias_targets(specifier, compiler, repo)
        )
        found = _first_existing_target(targets)
        if found is not None and not found.name.endswith(".d.ts"):
            yield found


def _problem(line: int, reason: str, source: str) -> dict[str, Any]:
    return {"line": line, "reason": reason, "source": source[:120]}


class TypeScriptLanguage:
    """TypeScript syntax normalized to the facts Python already consumes."""

    name = "typescript"

    def source_paths(
        self,
        root: Path,
        repo: Path,
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> Iterable[Path]:
        return (
            path
            for suffix in SOURCE_SUFFIXES
            for path in root.rglob(f"*{suffix}")
            if not any(part in SKIP_PARTS for part in path.parts)
            and not path.name.endswith(".d.ts")
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
        return TypeScriptContext(
            repo=repo,
            modules_by_path={path.resolve(): module for module, path in paths.items()},
            compiler=compiler,
            tests_dirs=tests_dirs,
            test_patterns=test_patterns,
            source_roots=root_candidates(
                compiler, _program_inputs(input_files(compiler), compiler, repo)
            ),
        )

    def module_of(self, path: Path, root: Path, name: str) -> str:
        parts = path.relative_to(root).with_suffix("").parts
        return ".".join((name, *(part.replace("-", "_") for part in parts)))

    def module_for_path(self, repo: Path, path: str, roots: list[tuple[Path, str]]) -> str | None:
        absolute = repo / path
        if absolute.suffix not in SOURCE_SUFFIXES or absolute.name.endswith(".d.ts"):
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
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        surface = parse_surface(raw, path.as_posix())
        if surface is None:
            surface = {
                "docstring": "",
                "functions": [],
                "classes": [],
                "errors": [],
                "constants": [],
                "names": [],
                "api": [],
                "unknown": [parse_problem(raw, path.as_posix())],
            }
        for entry in surface["names"]:
            source = entry.get("reexport_of")
            if not source:
                continue
            target = _resolve(source, module, known, paths, context)
            if target:
                entry["reexport_of"] = target
            else:
                entry["kind"] = "unknown"
                entry.pop("star", None)
                surface["unknown"].append(
                    _problem(
                        1,
                        f"the re-export target {source!r} is outside the extracted modules",
                        source,
                    )
                )
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
        root = parse_tree(raw, source_path.as_posix() if source_path else "")
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
        root = parse_tree(raw, source_path.as_posix() if source_path else "")
        if context is None:
            return []
        out = {
            specifier
            for specifier, _names in _imports(root)
            if not specifier.startswith(".")
            and _resolve(specifier, module, set(paths or {}), paths or {}, context) is None
            and not any(
                _module_name(specifier) == prefix
                or _module_name(specifier).startswith(prefix + ".")
                for prefix in prefixes
            )
        }
        return sorted(out)

    def collect_tests(
        self,
        repo: Path,
        tests_dirs: tuple[str, ...],
        prefixes: set[str],
        paths: dict[str, Path],
        context: TypeScriptContext,
    ) -> dict[str, list[dict[str, Any]]]:
        del prefixes
        files = sorted(
            path
            for path in repo.rglob("*")
            if _test_path(path, repo, tests_dirs, context.test_patterns)
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
        package = package_json(repo)
        points: list[dict[str, str]] = []
        issues: list[dict[str, str]] = []
        for name, target in _bin_targets(package, repo):
            self._add_entry_target(points, issues, name, target, repo, context)
        root_modules = {f"{prefix}.index" for prefix in prefixes}
        export_modules, export_issues = self._package_exports(package, repo, context)
        root_modules.update(export_modules)
        issues.extend(export_issues)
        points.extend(_public_functions(root_modules, components))
        return _unique_points(points), issues

    def _add_entry_target(
        self,
        points: list[dict[str, str]],
        issues: list[dict[str, str]],
        name: str,
        target: str,
        repo: Path,
        context: TypeScriptContext,
    ) -> None:
        module = self._entry_module(target, repo, context)
        if module:
            points.append({"kind": "console_script", "name": name, "module": module, "target": ""})
        else:
            issues.append(
                {
                    "kind": "package_bin",
                    "name": name,
                    "target": target,
                    "reason": "package.json bin target could not be mapped to a TypeScript module",
                }
            )

    def _package_exports(
        self, package: dict[str, Any], repo: Path, context: TypeScriptContext
    ) -> tuple[set[str], list[dict[str, str]]]:
        name = str(package.get("name", repo.name))
        modules: set[str] = set()
        issues: list[dict[str, str]] = []
        unmapped: list[str] = []
        for target in _export_targets(package.get("exports")):
            if "*" in target:
                unmapped.append(target)
                continue
            if target.endswith(".d.ts") or not target.endswith(
                (".js", ".mjs", ".cjs", ".ts", ".tsx")
            ):
                continue
            module = self._entry_module(target, repo, context)
            if module:
                modules.add(module)
            else:
                unmapped.append(target)
        if unmapped:
            sample = unmapped[0]
            if len(unmapped) > 1:
                sample += f" (+{len(unmapped) - 1} more)"
            issues.append(
                _entry_issue(
                    "package_export",
                    name,
                    sample,
                    f"{len(unmapped)} package.json export targets could not be mapped "
                    "to TypeScript modules",
                )
            )
        return modules, issues

    def _entry_module(self, target: str, repo: Path, context: TypeScriptContext) -> str | None:
        if not target.endswith((".js", ".mjs", ".cjs", ".ts", ".tsx")):
            return None
        sources = source_targets(target, repo, context.compiler, context.source_roots)
        direct = _matching_entry_modules(sources, context)
        if len(direct) == 1:
            return next(iter(direct))
        if direct:
            # Two roots each name a module: which one tsc used is not knowable
            # from here, and a wrong answer costs more than none.
            return None
        fallback = _matching_entry_modules(_built_source_candidates(target, repo), context)
        return next(iter(fallback)) if len(fallback) == 1 else None

    def parse_surface(self, raw: str, path: str = "") -> dict[str, Any] | None:
        return parse_surface(raw, path)

    def test_names(self, raw: str, path: str = "") -> list[str]:
        return test_names(raw, path)

    def is_test_file(
        self, path: str, tests_dirs: tuple[str, ...], test_patterns: tuple[str, ...] = ()
    ) -> bool:
        return _test_file(path, tests_dirs, test_patterns)


def _matching_entry_modules(candidates: Iterable[Path], context: TypeScriptContext) -> set[str]:
    return {
        context.modules_by_path[choice.resolve()]
        for source in candidates
        for choice in _path_choices(source)
        if choice.resolve() in context.modules_by_path
    }


def _built_source_candidates(target: str, repo: Path) -> Iterator[Path]:
    parts = PurePosixPath(target.removeprefix("./")).parts
    if len(parts) < 2 or parts[0] not in BUILD_DIRS:
        return
    tails = [parts[1:]]
    if len(parts) > 2 and parts[1] in BUILD_FORMATS:
        tails.append(parts[2:])
    for root in ("src", "source"):
        for tail in tails:
            yield repo / root / Path(*tail)


def _export_targets(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value.removeprefix("./")
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _export_targets(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _export_targets(nested)


def _bin_targets(package: dict[str, Any], repo: Path) -> list[tuple[str, str]]:
    bins = package.get("bin", {})
    if isinstance(bins, str):
        return [(str(package.get("name", repo.name)), bins)]
    if not isinstance(bins, dict):
        return []
    return [(str(name), target) for name, target in sorted(bins.items()) if isinstance(target, str)]


def _entry_issue(kind: str, name: str, target: str, reason: str) -> dict[str, str]:
    return {"kind": kind, "name": name, "target": target, "reason": reason}


def _public_functions(modules: set[str], components: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"kind": "public_function", "name": function["name"], "module": module, "target": ""}
        for module in sorted(modules)
        for function in components.get(module, {}).get("names", [])
        if function.get("kind") == "function"
    ]


def _unique_points(points: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for point in points:
        key = point["kind"], point["name"], point["module"]
        if key not in seen:
            seen.add(key)
            out.append(point)
    return out


TYPESCRIPT = TypeScriptLanguage()
