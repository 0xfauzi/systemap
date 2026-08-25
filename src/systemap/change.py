"""Work out what a branch changes about the system, in logical terms.

A change view needs more than "these files differ". It needs to know which
components moved, what each one gained or lost, which exported names were
redefined on the wire, and how far the change reaches. Reach is computed here
rather than left to the reader, because "what does this affect" is the
question a change view exists to answer.

Everything is derived from the same primitives the map itself uses: the
public surface of a module is `extract.parse_surface` applied to the git
blob on each side of the diff, and reach follows the name-level imports the
facts record. Two answers about the same module can therefore never disagree,
because there is only one definition of what the module exports.

Reach and redefinition answer different questions on purpose. Reach is
behavioral: any edit to a module can change the behavior of everything that
imports it, so every direct importer is reached. Redefinition is interface:
only an exported name whose definition changed, and that some other module
imports by name, counts as redefined on the wire. A whole-module import
(`import m`) hides which names are used, so it contributes reach but never a
named artifact; that blind spot is accepted rather than guessed at.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from systemap.config import Config
from systemap.extract import (
    WHOLE_MODULE,
    internal_uses,
    module_of,
    parse_surface,
    test_names,
)
from systemap.model import Model, module_matches

# `gained` carries only the buckets the schematic's segmented bar draws
# (operations, types, refusals, tests), so its +N badge always equals the sum
# of the segments; constants stay in the surface detail.
BUCKETS = ("operations", "types", "refusals", "constants")


def _run(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=90)
    return proc.stdout if proc.returncode == 0 else ""


def _show(repo: Path, ref: str, path: str) -> str:
    """The file's content at a ref, or empty where it does not exist there."""
    return _run(["git", "show", f"{ref}:{path}"], repo)


def pr_meta(repo: Path, pr: str) -> dict[str, Any]:
    """Title and counts for a PR, or empty if gh cannot answer."""
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
    """Every path the diff touches, split on NUL so spaces in names survive."""
    out = _run(["git", "diff", "--name-only", "-z", merge_base, head, "--no-renames"], repo)
    return [f for f in out.split("\0") if f]


def _path_module(repo: Path, path: str, roots: list[tuple[Path, str]]) -> str | None:
    """The dotted module a repo-relative path implements, or None.

    Derived from the path alone so a file DELETED by the branch still maps:
    the facts are built from the head tree and cannot know a module that is
    gone from it.
    """
    if not path.endswith(".py"):
        return None
    absolute = repo / path
    for pkg_dir, pkg_name in roots:
        if absolute.is_relative_to(pkg_dir):
            return module_of(absolute, pkg_dir, pkg_name)
    return None


def _is_test_file(path: str, tests_dirs: tuple[str, ...]) -> bool:
    if not path.endswith(".py") or not path.split("/")[-1].startswith("test_"):
        return False
    return any(rel and path.startswith(rel.rstrip("/") + "/") for rel in tests_dirs)


def _empty_surface() -> dict[str, Any]:
    return {"functions": [], "classes": [], "errors": [], "constants": []}


def _identity(surface: dict[str, Any]) -> dict[str, dict[str, str]]:
    """bucket -> name -> the fingerprint whose change means redefinition."""
    return {
        "operations": {f["name"]: f["signature"] for f in surface["functions"]},
        "types": {c["name"]: ",".join(c["methods"]) for c in surface["classes"]},
        "refusals": {e["name"]: ",".join(e["methods"]) for e in surface["errors"]},
        "constants": {c["name"]: c["value"] for c in surface["constants"]},
    }


def surface_delta(base_raw: str, head_raw: str) -> dict[str, Any] | None:
    """What one module's public surface gained, lost, and changed.

    None means a side had source that does not parse, which is "cannot tell",
    never "nothing changed".
    """
    base = parse_surface(base_raw) if base_raw else _empty_surface()
    head = parse_surface(head_raw) if head_raw else _empty_surface()
    if base is None or head is None:
        return None
    before, after = _identity(base), _identity(head)
    delta: dict[str, Any] = {"added": {}, "removed": {}, "changed": {}}
    for bucket in BUCKETS:
        b, a = before[bucket], after[bucket]
        delta["added"][bucket] = sorted(set(a) - set(b))
        delta["removed"][bucket] = sorted(set(b) - set(a))
        delta["changed"][bucket] = sorted(n for n in set(a) & set(b) if a[n] != b[n])
    return delta


def _merge_names(target: dict[str, list[str]], extra: dict[str, list[str]]) -> None:
    for bucket, names in extra.items():
        target[bucket] = sorted(set(target[bucket]) | set(names))


def _touched_names(delta: dict[str, Any]) -> set[str]:
    return {
        name
        for part in ("added", "removed", "changed")
        for names in delta[part].values()
        for name in names
    }


def compute(
    cfg: Config,
    model: Model,
    base: str,
    facts: dict[str, Any],
    head: str = "HEAD",
    artifact_owner: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Everything the change view needs, or an empty change if there is none.

    `head` names the tip under study. It is not always the checked-out branch:
    pull requests stack, so a lesson or a review may ask about
    `origin/<branch>` while the tree sits on something else. Both refs are
    explicit for that reason. `artifact_owner` maps a flow label to the
    module that defines what travels on it; without one no flow is ever lit
    by a redefinition.
    """
    repo = cfg.root
    roots = cfg.roots
    if artifact_owner is None:
        artifact_owner = {}

    empty: dict[str, Any] = {
        "has_change": False,
        "direct": set(),
        "adjacent": set(),
        "modules": set(),
        "artifacts": set(),
        "flow_artifacts": set(),
        "per_component": {},
        "files": 0,
        "base": base,
        "head": head,
        "reach_known": True,
        "unparsed": [],
    }
    merge_base = _run(["git", "merge-base", base, head], repo).strip()
    if not merge_base:
        return empty
    files = _changed_files(repo, merge_base, head)
    if not files:
        return empty

    # Each changed source module: its surface delta, from the two git blobs.
    deltas: dict[str, dict[str, Any]] = {}
    unparsed: list[str] = []
    for path in files:
        module = _path_module(repo, path, roots)
        if not module or _is_test_file(path, cfg.test_dirs):
            continue
        delta = surface_delta(_show(repo, merge_base, path), _show(repo, head, path))
        if delta is None:
            unparsed.append(module)
            continue
        deltas[module] = delta
    modules = set(deltas) | set(unparsed)

    # Changed test files: added and removed tests, attributed to every module
    # the test file imports, the same rule collect_tests uses for guards.
    prefixes = set(facts.get("packages", []))
    known = set(facts.get("components", {})) | modules
    tests_added: dict[str, set[str]] = {}
    tests_removed: dict[str, set[str]] = {}
    for path in files:
        if not _is_test_file(path, cfg.test_dirs):
            continue
        base_raw = _show(repo, merge_base, path)
        head_raw = _show(repo, head, path)
        before_t, after_t = set(test_names(base_raw)), set(test_names(head_raw))
        if before_t == after_t:
            continue
        targets: set[str] = set()
        for raw in (base_raw, head_raw):
            targets |= set(internal_uses(raw, prefixes, known))
        for target in targets:
            tests_added.setdefault(target, set()).update(after_t - before_t)
            tests_removed.setdefault(target, set()).update(before_t - after_t)

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
        )
        hit = sorted(m for m in owned if m in modules)
        path_hit = any(
            f == prefix or f.startswith(prefix + "/") for prefix in path_prefixes for f in files
        )
        test_hit = sorted(m for m in owned if tests_added.get(m) or tests_removed.get(m))
        if not hit and not path_hit and not test_hit:
            continue
        direct.add(c.id)
        surface: dict[str, Any] = {
            part: {bucket: [] for bucket in BUCKETS} for part in ("added", "removed", "changed")
        }
        for m in hit:
            for part in ("added", "removed", "changed"):
                _merge_names(surface[part], deltas[m][part])
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
        }

    # Redefined on the wire: an exported name whose definition changed and that
    # some other module imports by name.
    imported_names: dict[str, set[str]] = {}
    fact_components = facts.get("components", {})
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
        "direct": direct,
        "adjacent": adjacent,
        "modules": modules,
        "artifacts": artifacts,
        "flow_artifacts": flow_artifacts,
        "per_component": per_component,
        "files": len(files),
        "base": base,
        "head": head,
        "reach_known": reach_known,
        "unparsed": sorted(unparsed),
    }
