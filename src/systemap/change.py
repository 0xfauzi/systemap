"""The change analysis compares two committed source snapshots.

It gives changed components, public names, and direct importers of changed modules.
Imports give possible effects for examination. They do not give evidence of runtime
impact.

The public surface comes from `extract.parse_surface` for each Git blob. The facts give
the name-level imports. A named import can show a redefined artifact. A whole-module
import gives importer scope but cannot identify an artifact.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from systemap import extract, history
from systemap.config import Config
from systemap.extract import WHOLE_MODULE
from systemap.language import LanguageAdapter
from systemap.model import Model, module_matches, symbol_claims

# `gained` carries only the buckets the schematic's segmented bar draws
# (operations, types, refusals, tests), so its +N badge always equals the sum
# of the segments; constants stay in the surface detail.
BUCKETS = ("operations", "types", "refusals", "constants")


class ChangeError(Exception):
    """The program cannot make the requested source comparison."""


def _run(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=90)
    return proc.stdout if proc.returncode == 0 else ""


def _show(repo: Path, ref: str, path: str) -> str:
    """This function reads a file at a Git ref, or gives an empty string if the file is
    missing.
    """
    return _run(["git", "show", f"{ref}:{path}"], repo)


def pr_meta(repo: Path, pr: str) -> dict[str, Any]:
    """This function gets a pull request title and counts, or an empty record if gh gives
    no usable answer.
    """
    if not pr:
        return {}
    raw = _run(
        [
            "gh",
            "pr",
            "view",
            pr,
            "--json",
            "number,title,url,additions,deletions,changedFiles,state",
        ],
        repo,
    )
    try:
        return dict(json.loads(raw)) if raw else {}
    except json.JSONDecodeError:
        return {}


def _changed_files(repo: Path, merge_base: str, head: str) -> list[str]:
    """This function lists changed paths. NUL delimiters keep spaces in path names."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", "-z", merge_base, head, "--no-renames"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if proc.returncode:
        raise ChangeError(f"Git could not compare {merge_base} and {head}")
    return [f for f in proc.stdout.split("\0") if f]


def _resolve(repo: Path, ref: str) -> str:
    revision = _run(
        ["git", "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}"],
        repo,
    ).strip()
    if not revision:
        raise ChangeError(
            f"unknown revision {ref}. Give a commit, branch, or tag that Git can resolve."
        )
    return revision


def _comparison_revisions(repo: Path, base: str, head: str) -> tuple[str, str, str]:
    base_revision, head_revision = _resolve(repo, base), _resolve(repo, head)
    shared = _run(["git", "merge-base", base_revision, head_revision], repo).strip()
    if not shared:
        raise ChangeError(f"{base} and {head} have no common ancestor for the comparison.")
    return base_revision, head_revision, shared


def _empty_surface() -> dict[str, Any]:
    return {"functions": [], "classes": [], "errors": [], "constants": []}


def _identity(surface: dict[str, Any]) -> dict[str, dict[str, str]]:
    """This function indexes public names and fingerprints by surface bucket."""
    if "api" in surface:
        grouped: dict[str, dict[str, list[str]]] = {bucket: {} for bucket in BUCKETS}
        for entry in surface["api"]:
            grouped[entry["bucket"]].setdefault(entry["name"], []).append(entry["fingerprint"])
        return {
            bucket: {name: "\n".join(values) for name, values in names.items()}
            for bucket, names in grouped.items()
        }
    return {
        "operations": {f["name"]: f["signature"] for f in surface["functions"]},
        "types": {c["name"]: ",".join(c["methods"]) for c in surface["classes"]},
        "refusals": {e["name"]: ",".join(e["methods"]) for e in surface["errors"]},
        "constants": {c["name"]: c["value"] for c in surface["constants"]},
    }


def surface_delta(
    base_raw: str,
    head_raw: str,
    language: LanguageAdapter = extract.PYTHON,
    path: str = "",
) -> dict[str, Any] | None:
    """This function compares the public surfaces of two source files.

    If either source file cannot parse, the result is `None`. This result means that the
    changes are unknown. The result does not show that no change occurred.
    """
    base = language.parse_surface(base_raw, path) if base_raw else _empty_surface()
    head = language.parse_surface(head_raw, path) if head_raw else _empty_surface()
    if base is None or head is None:
        return None
    before, after = _identity(base), _identity(head)
    delta: dict[str, Any] = {"added": {}, "removed": {}, "changed": {}}
    for bucket in BUCKETS:
        b, a = before[bucket], after[bucket]
        delta["added"][bucket] = sorted(set(a) - set(b))
        delta["removed"][bucket] = sorted(set(b) - set(a))
        delta["changed"][bucket] = sorted(n for n in set(a) & set(b) if a[n] != b[n])
    if base.get("unknown") or head.get("unknown"):
        delta["unknown"] = {
            "base": base.get("unknown", []),
            "head": head.get("unknown", []),
        }
    return delta


def _merge_names(target: dict[str, list[str]], extra: dict[str, list[str]]) -> None:
    for bucket, names in extra.items():
        target[bucket] = sorted(set(target[bucket]) | set(names))


def _component_surface(
    hit: list[str], deltas: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    surface: dict[str, Any] = {
        part: {bucket: [] for bucket in BUCKETS} for part in ("added", "removed", "changed")
    }
    unknown: dict[str, Any] = {}
    for module in hit:
        delta = deltas.get(module)
        if delta is None:
            continue
        for part in ("added", "removed", "changed"):
            _merge_names(surface[part], delta[part])
        if "unknown" in delta:
            unknown[module] = delta["unknown"]
    return surface, unknown


def _touched_names(delta: dict[str, Any]) -> set[str]:
    return {
        name
        for part in ("added", "removed", "changed")
        for names in delta[part].values()
        for name in names
    }


def _paths_for_change(
    cfg: Config,
    language: LanguageAdapter,
    files: list[str],
    facts: dict[str, Any],
) -> dict[str, Path]:
    paths = {
        module: cfg.root / record["file"]
        for module, record in facts.get("components", {}).items()
        if record.get("file")
    }
    for path in files:
        module = language.module_for_path(cfg.root, path, cfg.roots)
        if module:
            paths.setdefault(module, cfg.root / path)
    return paths


def _test_file_changes(
    cfg: Config,
    language: LanguageAdapter,
    path: str,
    base: str,
    head: str,
    prefixes: set[str],
    known: set[str],
    paths: dict[str, Path],
    context: Any,
) -> tuple[set[str], set[str], set[str]] | None:
    base_raw = _show(cfg.root, base, path)
    head_raw = _show(cfg.root, head, path)
    before = {f"{path}::{name}" for name in language.test_names(base_raw, path)}
    after = {f"{path}::{name}" for name in language.test_names(head_raw, path)}
    added, removed = after - before, before - after
    if not added and not removed:
        return None
    importer = f"__test__:{path}"
    context_paths = {**paths, importer: cfg.root / path}
    targets: set[str] = set()
    for raw in (base_raw, head_raw):
        targets.update(
            language.internal_uses(
                raw,
                prefixes,
                known,
                module=importer,
                repo=cfg.root,
                paths=context_paths,
                context=context,
            )
        )
    return targets, added, removed


def _changed_test_deltas(
    cfg: Config,
    language: LanguageAdapter,
    files: list[str],
    facts: dict[str, Any],
    modules: set[str],
    base: str,
    head: str,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    prefixes = set(facts.get("packages", []))
    known = set(facts.get("components", {})) | modules
    paths = _paths_for_change(cfg, language, files, facts)
    context = language.context(cfg.root, paths, cfg.test_dirs, cfg.test_patterns)
    tests_added: dict[str, set[str]] = {}
    tests_removed: dict[str, set[str]] = {}
    for path in files:
        if not language.is_test_file(path, cfg.test_dirs, cfg.test_patterns):
            continue
        changes = _test_file_changes(
            cfg, language, path, base, head, prefixes, known, paths, context
        )
        if changes is None:
            continue
        targets, added, removed = changes
        for target in targets:
            tests_added.setdefault(target, set()).update(added)
            tests_removed.setdefault(target, set()).update(removed)
    return tests_added, tests_removed


def compute(
    cfg: Config,
    model: Model,
    base: str,
    facts: dict[str, Any],
    head: str = "HEAD",
    artifact_owner: dict[str, str] | None = None,
) -> dict[str, Any]:
    """This function gives the change-view data for two explicit Git refs.

    The head ref can differ from the branch in the working tree. The facts come from the
    resolved head snapshot. The `artifact_owner` table assigns flow artifacts to their
    defining modules. Without this table, public-name changes do not highlight flow
    artifacts.
    """
    repo = cfg.root
    roots = cfg.roots
    language = extract.language_for(cfg)
    if artifact_owner is None:
        artifact_owner = {}

    base_revision, head_revision, merge_base = _comparison_revisions(repo, base, head)
    empty: dict[str, Any] = {
        "has_change": False,
        "comparison_requested": True,
        "direct": set(),
        "adjacent": set(),
        "modules": set(),
        "artifacts": set(),
        "flow_artifacts": set(),
        "per_component": {},
        "files": 0,
        "base": base,
        "head": head,
        "base_revision": base_revision,
        "head_revision": head_revision,
        "comparison_base": merge_base,
        "reach_known": True,
        "unparsed": [],
    }
    files = _changed_files(repo, merge_base, head_revision)
    if not files:
        return empty
    snapshot_facts = history.facts_at(cfg, head_revision)

    # Each changed source module: its surface delta, from the two git blobs.
    deltas: dict[str, dict[str, Any]] = {}
    unparsed: list[str] = []
    for path in files:
        module = language.module_for_path(repo, path, roots)
        if not module or language.is_test_file(path, cfg.test_dirs, cfg.test_patterns):
            continue
        delta = surface_delta(
            _show(repo, merge_base, path), _show(repo, head_revision, path), language, path
        )
        if delta is None:
            unparsed.append(module)
            continue
        deltas[module] = delta
    modules = set(deltas) | set(unparsed)

    tests_added, tests_removed = _changed_test_deltas(
        cfg, language, files, snapshot_facts, modules, merge_base, head_revision
    )

    direct: set[str] = set()
    per_component: dict[str, dict[str, Any]] = {}
    for c in model.components:
        implemented = list(c.implemented_by)
        module_ids = [m for m in implemented if "/" not in m]
        path_prefixes = [m for m in implemented if "/" in m]
        # The modules this component claims, among the changed ones and the
        # ones whose tests changed; a `pkg.*` entry claims the subtree.
        owned = sorted(
            m
            for m in modules | set(tests_added) | set(tests_removed)
            if any(module_matches(p, m) for p in module_ids)
            or any(sym_module == m for sym_module, _name in symbol_claims(c))
        )
        hit = sorted(m for m in owned if m in modules)
        path_hit = any(
            f == prefix or f.startswith(prefix + "/") for prefix in path_prefixes for f in files
        )
        test_hit = sorted(m for m in owned if tests_added.get(m) or tests_removed.get(m))
        if not hit and not path_hit and not test_hit:
            continue
        direct.add(c.id)
        surface, unknown = _component_surface(hit, deltas)
        surface["tests_added"] = sorted({t for m in owned for t in tests_added.get(m, set())})
        surface["tests_removed"] = sorted({t for m in owned for t in tests_removed.get(m, set())})
        gained = {
            bucket: len(surface["added"][bucket])
            for bucket in ("operations", "types", "refusals")
            if surface["added"][bucket]
        }
        if surface["tests_added"]:
            gained["tests"] = len(surface["tests_added"])
        per_component[c.id] = {
            "modules": hit,
            "gained": gained,
            "surface": surface,
            "unknown": unknown,
        }

    # Redefined on the wire: an exported name whose definition changed and that
    # some other module imports by name.
    imported_names: dict[str, set[str]] = {}
    fact_components = snapshot_facts.get("components", {})
    reach_known = any("uses" in r for r in fact_components.values())
    for record in fact_components.values():
        for target, names in record.get("uses", {}).items():
            if names != [WHOLE_MODULE]:
                imported_names.setdefault(target, set()).update(names)
    artifacts = {
        f"{module}.{name}"
        for module, delta in deltas.items()
        for name in _touched_names(delta) & imported_names.get(module, set())
    }

    # The drawing overlay: authored flow labels whose owning module redefined
    # part of its surface, so the diagram can highlight the affected wires.
    redefined_modules = {m for m, d in deltas.items() if _touched_names(d)}
    flow_artifacts = {
        label
        for label, owner in artifact_owner.items()
        if owner in redefined_modules or owner in unparsed
    }

    # Reach: every component with a module that imports a changed module.
    def owner_of(module_id: str) -> str:
        for c in model.components:
            if any(module_matches(p, module_id) for p in c.implemented_by if "/" not in p):
                return c.id
        return ""

    adjacent: set[str] = set()
    for module_id, record in fact_components.items():
        if module_id in modules:
            continue
        if modules & set(record.get("uses", {})):
            cid = owner_of(module_id)
            if cid:
                adjacent.add(cid)
    adjacent -= direct

    return {
        "has_change": True,
        "comparison_requested": True,
        "direct": direct,
        "adjacent": adjacent,
        "modules": modules,
        "artifacts": artifacts,
        "flow_artifacts": flow_artifacts,
        "per_component": per_component,
        "files": len(files),
        "base": base,
        "head": head,
        "base_revision": base_revision,
        "head_revision": head_revision,
        "comparison_base": merge_base,
        "reach_known": reach_known,
        "unparsed": sorted(unparsed),
    }
