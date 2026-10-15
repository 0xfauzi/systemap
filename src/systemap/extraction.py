"""The shared extraction steps make the facts file and compare two facts files.

`build` asks the language adapter of the configuration for the source files, the module
records, the imports, the tests, and the entry points. It then writes the facts that
have the same meaning for each language. `drift` compares stored facts with extracted
facts. These steps do not examine a language name, a file suffix, or source syntax.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from systemap import language as languages
from systemap import repo_files, source_text
from systemap.config import Config, ConfigError
from systemap.language import LanguageAdapter
from systemap.model import Model, covers, is_symbol
from systemap.reexports import resolve_reexports
from systemap.source_facts import WHOLE_MODULE, entry_label

# A stored file of an older facts format is reported as stale. Format 6: the `package`
# fact is the folder package that the adapter gives, not the first module-name part.
# Format 7: each module record has the `call_sites` fact. Format 8: a Python `api`
# fingerprint includes decorators, and the Python `empty_marker` fact reads each
# top-level statement. Each re-export has `defined_in` and `defined_as`, the identity
# of its definition. A TypeScript type-only export has `type_only`, and `api` has a
# record for each `*` re-export. A type declaration that is not a class is in
# `types`, with its category, and not in `classes`. Each entry point has the
# `same_as` fact. Cached facts of format 7 have the earlier values. Format 9: each
# unknown record has the `cause` that `unknown_causes` specifies. Format 10: a TypeScript
# re-export target without a module gives one unknown record for each statement, at its
# line and with its names, and a declaration file target has the cause `declaration file`.
# An import of a declaration file is not an unresolved import. A string export name is
# the public name. Format 11: a TypeScript parse record has a fixed reason, the excerpt in
# `source`, and the parser version in `parser`, because a finding line must not contain
# them. An indirect re-export without a module gives the record of a direct re-export.
# Format 12: `provenance.files` has a digest for each configuration file that
# `extraction_inputs` of the adapter gives, and `provenance.installed` has the digests of
# such files in an installed package folder. Format 13: a `package_export` record has no
# count in `target` and `reason`, because a finding line must not contain a count. The
# record has the count in `count`.
FORMAT = 13
TESTS_KEPT = 25


def language_for(cfg: Config) -> LanguageAdapter:
    """Select the configured source-language adapter for this repository."""
    try:
        return languages.adapter(cfg.language)
    except languages.LanguageError as exc:
        raise ConfigError(str(exc)) from exc


def plane_of(module: str, planes: tuple[str, ...]) -> str:
    """Get the module plane from its dotted path."""
    parts = module.split(".")
    if len(parts) > 2 and parts[1] in planes:
        return parts[1]
    return "core"


def spec_sections(repo: Path, spec_path: str) -> list[dict[str, str]]:
    if not spec_path:
        return []
    path = repo / spec_path
    if not path.is_file():
        return []
    out: list[dict[str, str]] = []
    try:
        text = repo_files.read_text(repo, spec_path)
    except (OSError, UnicodeError):
        return []
    for match in re.finditer(r"^(#{2,4})\s+(.+)$", text, re.M):
        out.append({"level": str(len(match.group(1))), "title": match.group(2).strip()})
    return out


def _source_paths(cfg: Config, language: LanguageAdapter) -> dict[str, Path]:
    repo = cfg.root
    paths: dict[str, Path] = {}
    for pkg_dir, pkg_name in cfg.roots:
        for path in language.source_paths(pkg_dir, repo, cfg.test_dirs, cfg.test_patterns):
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
    record["package"] = package_for(cfg, language, module, path)
    record["plane"] = plane_of(module, cfg.planes)
    try:
        raw = source_text.read(cfg.root, path)
    except (OSError, UnicodeError):
        raw = ""
    uses = language.internal_uses(
        raw,
        prefixes,
        known,
        module=module,
        is_package=language.is_package_module(path),
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
    # Source that did not parse can hide imports: the list is then not known (None).
    record["completeness"]["unresolved_imports"] = (
        language.unresolved_imports(raw, prefixes, known, module, cfg.root, paths, context)
        if record["completeness"]["parsed"]
        else None
    )
    return record, raw, set(uses)


def package_for(cfg: Config, language: LanguageAdapter, module: str, path: Path) -> str:
    """Give the package that the adapter finds for the module, from its package root.

    The path can be a file that the facts do not contain, such as a new file of a change.
    A module outside each package root gives its own name."""
    for root, name in cfg.roots:
        if path.is_relative_to(root) and language.module_of(path, root, name) == module:
            return language.package_of(path, root, name)
    return module


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


def _attach_call_sites(
    cfg: Config,
    language: LanguageAdapter,
    components: dict[str, Any],
    sources: dict[str, str],
    paths: dict[str, Path],
    prefixes: set[str],
    context: Any,
) -> None:
    """Write the `call_sites` fact of each module after all module records exist.

    The value is None (not known) if the module source did not parse. Each record has a
    target in the `uses` fact of the module.
    """
    del cfg
    known = set(paths)
    for module, record in components.items():
        sites = None
        if record["completeness"]["parsed"]:
            sites = language.call_sites(
                sources[module],
                module,
                prefixes,
                known,
                components,
                is_package=language.is_package_module(paths[module]),
                paths=paths,
                context=context,
            )
        uses = record.get("uses", {})
        record["call_sites"] = None if sites is None else [s for s in sites if s["target"] in uses]


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


def _config_digests(cfg: Config, language: LanguageAdapter) -> dict[str, dict[str, str]]:
    """Give the digest of the values that extraction reads from each configuration file
    (`extraction_inputs` of the adapter).

    `files` has the files of the repository. `installed` has the files in a folder that
    the adapter skips, such as an installed package folder. A clone can be without such
    a file. A file that the adapter cannot read gives a ConfigError.
    """
    root = cfg.root
    folders = [package for package, _name in cfg.roots]
    folders += [root / rel for rel in cfg.test_dirs if rel]
    found: dict[str, dict[str, str]] = {"files": {}, source_text.INSTALLED: {}}
    for path, values in language.extraction_inputs(root, folders).items():
        relative = path.relative_to(root)
        group = "files"
        if language.skip_dirs.intersection(relative.parent.parts):
            group = source_text.INSTALLED
        found[group][relative.as_posix()] = source_text.text_digest(values)
    return {group: dict(sorted(files.items())) for group, files in found.items()}


def _provenance(cfg: Config, language: LanguageAdapter, context: Any) -> dict[str, Any]:
    settings = {
        "language": cfg.language,
        "roots": cfg.package_roots,
        "tests_dirs": cfg.test_dirs,
        "test_patterns": cfg.test_patterns,
        "planes": cfg.planes,
        "spec_path": cfg.spec_path,
        # Installed npm packages can change the compiler settings: a separate record.
        "compiler": None,
    }
    # The drift comparison finds a change of the facts that a parser version gives.
    return {
        "parser": language.parser_version(),
        "settings": hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest(),
        **_config_digests(cfg, language),
        **language.compiler_record(context, cfg.root),
    }


def _facts_file(
    cfg: Config,
    language: LanguageAdapter,
    prefixes: set[str],
    components: dict[str, Any],
    tests_dirs: tuple[str, ...],
    points: list[dict[str, str]],
    entry_issues: list[dict[str, Any]],
    context: Any,
) -> dict[str, Any]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cfg.root, capture_output=True, text=True
    )
    facts = {
        "version": FORMAT,
        "built_at_commit": head.stdout.strip() if head.returncode == 0 else "",
        "packages": sorted(prefixes),
        "provenance": _provenance(cfg, language, context),
        "tests_dirs": list(tests_dirs),
        "spec_sections": spec_sections(cfg.root, cfg.spec_path),
        "entry_points": points,
        "components": components,
    }
    facts.update(language.extra_facts(context, entry_issues))
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
    _attach_call_sites(cfg, language, components, sources, paths, prefixes, context)
    for module, record in components.items():
        record["empty_marker"] = language.empty_marker(record, sources[module])
    guards = language.collect_tests(repo, cfg.test_dirs, prefixes, paths, context)
    _attach_test_facts(components, guards)
    points, issues = language.entry_points(repo, prefixes, components, sources, context)
    for point in points:
        point["label"] = language.entry_label(point)
    return _facts_file(cfg, language, prefixes, components, cfg.test_dirs, points, issues, context)


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
    # The parser and compiler records can be different on another computer.
    # The comparisons below find a change of the facts that they give.
    if stored and source_text.inputs_changed(stored.get("provenance"), fresh.get("provenance")):
        out.append("extraction inputs changed since the map was built")
    out.extend(_entry_drift(fresh, stored))
    out.extend(_issue_drift(fresh, stored))
    # A heading change in the `spec_path` file changes no module and no input digest.
    if stored and fresh.get("spec_sections", []) != stored.get("spec_sections", []):
        out.append("specification sections changed since the map was built")
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


def _issue_drift(fresh: dict[str, Any], stored: dict[str, Any]) -> list[str]:
    """Compare the unknown records of the test files.

    A test file that does not parse changes no module record. Without this comparison,
    the stored facts do not get its unknown record. The comparison does not include
    `config_issues`: an installed configuration package can be different on another
    computer for the same commit."""
    if not stored or fresh.get("test_file_issues", []) == stored.get("test_file_issues", []):
        return []
    return ["unknown records changed since the map was built: test files"]


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
        "types",
        "constants",
        "unknown",
        "parse_error",
        "completeness",
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
                covers(module, k, fresh["components"]) for k in known
            ):
                out.append(
                    f"{c.id} has a module claim for {module}, which is missing from the facts."
                )
    out.extend(f"layout: {p}" for p in model.layout_problems())
    return out
