"""Read TypeScript and TSX into systemap's language-neutral facts."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path, PurePosixPath
from typing import Any

import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from systemap.config import ConfigError

SOURCE_SUFFIXES = (".ts", ".tsx")
TEST_SUFFIXES = (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")
SKIP_PARTS = {".git", ".venv", "node_modules", "build", "dist"}
UPPER_NAME = re.compile(r"[A-Z][A-Z0-9_]{2,}")
WHOLE_MODULE = "*"
CONSTANTS_KEPT = 14
TESTS_KEPT = 25

TS = Language(tree_sitter_typescript.language_typescript())
TSX = Language(tree_sitter_typescript.language_tsx())


def _root(raw: str, path: str = "") -> Node | None:
    language = TSX if path.endswith(".tsx") else TS
    tree = Parser(language).parse(raw.encode("utf-8"))
    return None if tree.root_node.has_error else tree.root_node


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(node: Node | None) -> str:
    return (node.text or b"").decode("utf-8") if node is not None else ""


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _string(node: Node | None) -> str:
    if node is None or node.type != "string":
        return ""
    fragment = next((c for c in node.named_children if c.type == "string_fragment"), None)
    return _text(fragment)


def _source(node: Node) -> str:
    return _string(node.child_by_field_name("source"))


def _module_name(name: str) -> str:
    return name.removeprefix("@").replace("/", ".").replace("-", "_")


def _without_script_suffix(specifier: str) -> str:
    for suffix in (".d.ts", ".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs"):
        if specifier.endswith(suffix):
            return specifier[: -len(suffix)]
    return specifier


def _resolve(
    specifier: str,
    module: str,
    known: set[str],
    repo: Path | None = None,
    paths: dict[str, Path] | None = None,
) -> str | None:
    if repo is not None and paths is not None and module in paths:
        resolved = _target_from_path(specifier, paths[module], paths, repo)
        if resolved:
            return resolved
    specifier = _without_script_suffix(specifier)
    if specifier.startswith("."):
        parts = module.split(".")[:-1]
        for part in PurePosixPath(specifier).parts:
            if part == ".":
                continue
            if part == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(part.replace("-", "_"))
        candidate = ".".join(parts)
    else:
        candidate = _module_name(specifier)
    for choice in (candidate, f"{candidate}.index"):
        if choice in known:
            return choice
    return None


def _imported_names(node: Node) -> set[str]:
    clause = next((c for c in node.named_children if c.type == "import_clause"), None)
    if clause is None:
        return {WHOLE_MODULE}
    if any(c.type == "namespace_import" for c in _walk(clause)):
        return {WHOLE_MODULE}
    out: set[str] = set()
    if any(c.type == "identifier" for c in clause.named_children):
        out.add("default")
    for specifier in (c for c in _walk(clause) if c.type == "import_specifier"):
        original = next((c for c in specifier.named_children if c.type == "identifier"), None)
        if original is not None:
            out.add(_text(original))
    return out


def _exported_names(node: Node) -> set[str]:
    clause = next((c for c in node.named_children if c.type == "export_clause"), None)
    if clause is None:
        return {WHOLE_MODULE}
    out: set[str] = set()
    for specifier in (c for c in clause.named_children if c.type == "export_specifier"):
        original = next((c for c in specifier.named_children if c.type == "identifier"), None)
        if original is not None:
            out.add(_text(original))
    return out or {WHOLE_MODULE}


def _imports(root: Node) -> Iterator[tuple[str, set[str]]]:
    for node in root.named_children:
        specifier = _source(node)
        if not specifier:
            continue
        if node.type == "import_statement":
            yield specifier, _imported_names(node)
        elif node.type == "export_statement":
            yield specifier, _exported_names(node)


def _header(node: Node) -> str:
    body = node.child_by_field_name("body")
    if body is None:
        return _one_line(_text(node).rstrip(";"))
    length = body.start_byte - node.start_byte
    return _one_line((node.text or b"")[:length].decode("utf-8").strip())


def _public_methods(node: Node) -> list[str]:
    body = node.child_by_field_name("body")
    if body is None:
        body = next(
            (c for c in node.named_children if c.type in ("class_body", "interface_body")), None
        )
    if body is None:
        return []
    out: list[str] = []
    for method in body.named_children:
        if method.type not in ("method_definition", "method_signature"):
            continue
        modifiers = {_text(c) for c in method.named_children if c.type == "accessibility_modifier"}
        if modifiers & {"private", "protected"}:
            continue
        out.append(_header(method))
    return out


def _type_record(node: Node) -> tuple[dict[str, Any], bool] | None:
    name = node.child_by_field_name("name")
    if name is None:
        name = next(
            (c for c in node.named_children if c.type in ("identifier", "type_identifier")), None
        )
    public = _text(name) or "default"
    heritage = next((c for c in node.named_children if c.type == "class_heritage"), None)
    is_error = node.type == "class_declaration" and "Error" in _text(heritage)
    return {"name": public, "methods": _public_methods(node)}, is_error


def _arrow_signature(name: str, node: Node) -> str:
    params = node.child_by_field_name("parameters") or node.child_by_field_name("parameter")
    result = node.child_by_field_name("return_type")
    return f"const {name} = {_text(params)}{_text(result)} =>"


def _reexports(node: Node) -> list[dict[str, str]]:
    clause = next((c for c in node.named_children if c.type == "export_clause"), None)
    source = _source(node)
    if clause is None or not source:
        return []
    out: list[dict[str, str]] = []
    for specifier in (c for c in clause.named_children if c.type == "export_specifier"):
        identifiers = [c for c in specifier.named_children if c.type == "identifier"]
        if not identifiers:
            continue
        original = _text(identifiers[0])
        public = _text(identifiers[-1])
        entry = {"name": public, "kind": "reexport", "reexport_of": source}
        if public != original:
            entry["defined_as"] = original
        out.append(entry)
    return out


def parse_surface(raw: str, path: str = "") -> dict[str, Any] | None:
    """The exported surface of one TypeScript or TSX module."""
    root = _root(raw, path)
    if root is None:
        return None
    functions: list[dict[str, str]] = []
    classes: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    constants: list[dict[str, str]] = []
    names: list[dict[str, str]] = []
    for export in (n for n in root.named_children if n.type == "export_statement"):
        names += _reexports(export)
        declaration = export.child_by_field_name("declaration")
        if declaration is None:
            continue
        if declaration.type in ("function_declaration", "generator_function_declaration"):
            name = _text(declaration.child_by_field_name("name")) or "default"
            functions.append({"name": name, "signature": _header(declaration)})
            names.append({"name": name, "kind": "function"})
        elif declaration.type in (
            "class_declaration",
            "interface_declaration",
            "type_alias_declaration",
            "enum_declaration",
        ):
            found = _type_record(declaration)
            if found is None:
                continue
            record, is_error = found
            (errors if is_error else classes).append(record)
            names.append({"name": record["name"], "kind": "error" if is_error else "class"})
        elif declaration.type == "lexical_declaration":
            for variable in (
                c for c in declaration.named_children if c.type == "variable_declarator"
            ):
                name = _text(variable.child_by_field_name("name"))
                value = variable.child_by_field_name("value")
                if not name or value is None:
                    continue
                if value.type == "arrow_function":
                    functions.append({"name": name, "signature": _arrow_signature(name, value)})
                    names.append({"name": name, "kind": "function"})
                elif UPPER_NAME.fullmatch(name):
                    constants.append({"name": name, "value": _one_line(_text(value))[:80]})
                    names.append({"name": name, "kind": "constant"})
                else:
                    names.append({"name": name, "kind": "object"})
    leading = next((n for n in root.named_children if n.type == "comment"), None)
    docstring = _text(leading).removeprefix("/**").removesuffix("*/").strip(" *\n")
    return {
        "docstring": _one_line(docstring),
        "functions": functions,
        "classes": classes,
        "errors": errors,
        "constants": constants,
        "names": names,
    }


def test_names(raw: str) -> list[str]:
    root = _root(raw)
    if root is None:
        return []
    out: list[str] = []
    for call in (n for n in _walk(root) if n.type == "call_expression"):
        function = call.child_by_field_name("function")
        if _text(function).rsplit(".", 1)[-1] not in ("test", "it"):
            continue
        arguments = call.child_by_field_name("arguments")
        first = arguments.named_children[0] if arguments and arguments.named_children else None
        name = _string(first)
        if name:
            out.append(name)
    return out


def _is_test_path(path: Path) -> bool:
    text = path.name
    return text.startswith("test_") or text.endswith(TEST_SUFFIXES)


def _path_choices(target: Path) -> list[Path]:
    if target.suffix in SOURCE_SUFFIXES:
        return [target]
    choices = [target.with_suffix(s) for s in SOURCE_SUFFIXES]
    choices += [(target / "index").with_suffix(s) for s in SOURCE_SUFFIXES]
    return choices


def _alias_targets(specifier: str, repo: Path) -> list[Path]:
    config = repo / "tsconfig.json"
    try:
        data = json.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}
    except (OSError, json.JSONDecodeError):
        return []
    compiler = data.get("compilerOptions", {}) if isinstance(data, dict) else {}
    if not isinstance(compiler, dict):
        return []
    base = repo / str(compiler.get("baseUrl", "."))
    aliases = compiler.get("paths", {})
    out: list[Path] = []
    if isinstance(aliases, dict):
        for pattern, targets in aliases.items():
            if not isinstance(pattern, str) or not isinstance(targets, list):
                continue
            before, marker, after = pattern.partition("*")
            if marker and specifier.startswith(before) and specifier.endswith(after):
                matched = specifier[len(before) : len(specifier) - len(after) if after else None]
            elif not marker and specifier == pattern:
                matched = ""
            else:
                continue
            for target in targets:
                if isinstance(target, str):
                    out.append(base / target.replace("*", matched))
    return [*out, base / specifier]


def _target_from_path(
    specifier: str,
    importer: Path,
    paths: dict[str, Path],
    repo: Path | None = None,
) -> str | None:
    if specifier.startswith("."):
        targets = [importer.parent / _without_script_suffix(specifier)]
    else:
        normalized = _module_name(_without_script_suffix(specifier))
        named = next((m for m in (normalized, f"{normalized}.index") if m in paths), None)
        if named:
            return named
        targets = _alias_targets(specifier, repo) if repo is not None else []
    resolved = {p.resolve(): module for module, p in paths.items()}
    return next(
        (
            resolved[choice.resolve()]
            for target in targets
            for choice in _path_choices(target)
            if choice.resolve() in resolved
        ),
        None,
    )


class TypeScriptLanguage:
    """TypeScript syntax normalized to the facts Python already consumes."""

    name = "typescript"

    def source_paths(self, root: Path) -> Iterable[Path]:
        return (
            path
            for suffix in SOURCE_SUFFIXES
            for path in root.rglob(f"*{suffix}")
            if not path.name.endswith(".d.ts")
            and not _is_test_path(path)
            and not any(part in SKIP_PARTS for part in path.parts)
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
    ) -> dict[str, Any] | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        surface = parse_surface(raw, path.as_posix())
        if surface is None:
            raise ConfigError(f"{path.relative_to(repo).as_posix()}: could not parse TypeScript")
        for entry in surface["names"]:
            if entry.get("kind") != "reexport":
                continue
            target = _resolve(entry["reexport_of"], module, known, repo, paths)
            if target:
                entry["reexport_of"] = target
        return {
            "file": path.relative_to(repo).as_posix(),
            "loc": len(raw.splitlines()),
            "sha": hashlib.sha1(raw.encode(), usedforsecurity=False).hexdigest()[:12],
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
    ) -> dict[str, set[str]]:
        root = _root(raw)
        if root is None:
            return {}
        uses: dict[str, set[str]] = defaultdict(set)
        for specifier, names in _imports(root):
            target = _resolve(specifier, module, known, repo, paths)
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
    ) -> list[str]:
        root = _root(raw)
        if root is None:
            return []
        out = {
            specifier
            for specifier, _names in _imports(root)
            if not specifier.startswith(".")
            and _resolve(specifier, module, set(paths or {}), repo, paths) is None
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
    ) -> dict[str, list[dict[str, Any]]]:
        roots = [repo / rel for rel in tests_dirs if rel] or [repo]
        files = {
            path
            for root in roots
            if root.is_dir()
            for path in root.rglob("*")
            if path.is_file()
            and _is_test_path(path)
            and not any(p in SKIP_PARTS for p in path.parts)
        }
        guards: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for path in sorted(files):
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError:
                continue
            root = _root(raw, path.as_posix())
            if root is None:
                continue
            targets = {
                target
                for specifier, _names in _imports(root)
                if (target := _target_from_path(specifier, path, paths, repo))
            }
            stem = path.name.split(".", 1)[0].removeprefix("test_")
            for target in targets:
                primary = stem == target.rsplit(".", 1)[-1]
                guards[target] += [
                    {"name": name, "primary": primary} for name in test_names(raw)[:TESTS_KEPT]
                ]
        return guards

    def entry_points(
        self,
        repo: Path,
        prefixes: set[str],
        components: dict[str, Any],
        sources: dict[str, str],
    ) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        package = repo / "package.json"
        try:
            data = json.loads(package.read_text(encoding="utf-8")) if package.is_file() else {}
        except (OSError, json.JSONDecodeError):
            data = {}
        bins = data.get("bin", {}) if isinstance(data, dict) else {}
        if isinstance(bins, str):
            bins = {str(data.get("name", repo.name)): bins}
        if isinstance(bins, dict):
            by_file = {record["file"]: module for module, record in components.items()}
            for name, target in sorted(bins.items()):
                if not isinstance(target, str):
                    continue
                module = by_file.get(target.removeprefix("./"))
                if module:
                    out.append(
                        {
                            "kind": "console_script",
                            "name": str(name),
                            "module": module,
                            "target": "",
                        }
                    )
        for prefix in sorted(prefixes):
            root_module = f"{prefix}.index"
            for function in components.get(root_module, {}).get("functions", []):
                out.append(
                    {
                        "kind": "public_function",
                        "name": function["name"],
                        "module": root_module,
                        "target": "",
                    }
                )
        return out

    def parse_surface(self, raw: str, path: str = "") -> dict[str, Any] | None:
        return parse_surface(raw, path)

    def test_names(self, raw: str) -> list[str]:
        return test_names(raw)

    def is_test_file(self, path: str, tests_dirs: tuple[str, ...]) -> bool:
        return _is_test_path(Path(path))


TYPESCRIPT = TypeScriptLanguage()
