"""The change analysis compares a committed source snapshot with a commit or the working tree.

It gives changed components, public names, and direct importers of changed modules.
Imports give possible effects for examination. They do not give evidence of runtime
impact.

The public surface comes from `extract.parse_surface` for each Git blob. The facts give
the name-level imports. A named import can show a redefined artifact. A whole-module
import gives importer scope but cannot identify an artifact.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path
from typing import Any

from systemap import change_text, delta_model, extraction, history, nest, repo_files
from systemap.config import Config
from systemap.language import LanguageAdapter
from systemap.model import Model, covers, symbol_claims
from systemap.source_facts import WHOLE_MODULE

# `gained` carries only the buckets the schematic's segmented bar draws
# (operations, types, refusals, tests), so its +N badge always equals the sum
# of the segments; constants stay in the surface detail.
BUCKETS = ("operations", "types", "refusals", "constants")
# The head of a comparison that includes the edits that are not in a commit. A Git ref
# name cannot contain a space character, so no Git ref has this name.
WORKING_TREE = "working tree"


class ChangeError(Exception):
    """The program cannot make the requested source comparison."""


def _run(args: list[str], cwd: Path) -> str:
    # Git gives file contents and paths as bytes. Source is UTF-8, whatever the locale.
    proc = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    return proc.stdout if proc.returncode == 0 else ""


def pr_meta(repo: Path, pr: str) -> dict[str, Any]:
    """This function gets a pull request title and counts, or an empty record if gh gives
    no usable answer.

    A value that starts with "-" is not a pull request number, URL, or branch. The function
    does not give such a value to gh, because gh can read it as an option.
    """
    if not pr or pr.startswith("-"):
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


def _changed_files(repo: Path, merge_base: str, *head: str) -> list[str]:
    """This function lists changed paths. NUL delimiters keep spaces in path names.

    Without a head commit, Git compares the merge base with the working tree.
    """
    proc = subprocess.run(
        ["git", "diff", "--name-only", "-z", merge_base, *head, "--no-renames"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
        timeout=90,
    )
    if proc.returncode:
        raise ChangeError(f"Git could not compare {merge_base} and {''.join(head) or WORKING_TREE}")
    return [f for f in proc.stdout.split("\0") if f]


def _untracked_files(repo: Path) -> list[str]:
    """This function lists the files that Git does not track and does not ignore.

    The list does not include the systemap cache directory `.systemap/`.
    """
    out = _run(
        ["git", "ls-files", "--others", "--exclude-standard", "--exclude=/.systemap/", "-z"],
        repo,
    )
    return [f for f in out.split("\0") if f]


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


def comparison_base(repo: Path, base: str) -> str:
    """This function gives the merge base of `base` and HEAD, or raises ChangeError."""
    return _comparison_revisions(repo, base, "HEAD")[2]


class _Commit:
    """The head of a comparison at a commit. Git gives the files, the facts and the text."""

    def __init__(self, cfg: Config, revision: str) -> None:
        self.cfg, self.revision = cfg, revision

    def files(self, merge_base: str) -> list[str]:
        return _changed_files(self.cfg.root, merge_base, self.revision)

    def facts(self) -> dict[str, Any]:
        return history.facts_at(self.cfg, self.revision)

    def texts(self, paths: list[str]) -> dict[str, change_text.Text]:
        return change_text.at(self.cfg.root, self.revision, paths)


class _WorkingTree:
    """The head of a comparison in the working tree.

    The changed files are the commits since the merge base, the edits that are not in a
    commit, and the untracked files. The disk gives the text. The caller gives the facts.
    """

    def __init__(self, cfg: Config, facts: dict[str, Any]) -> None:
        self.cfg, self._facts = cfg, facts

    def files(self, merge_base: str) -> list[str]:
        changed = _changed_files(self.cfg.root, merge_base)
        return sorted(set(changed) | set(_untracked_files(self.cfg.root)))

    def facts(self) -> dict[str, Any]:
        return self._facts

    def texts(self, paths: list[str]) -> dict[str, change_text.Text]:
        return {path: change_text.on_disk(self.cfg.root, path) for path in paths}


def _sides(
    cfg: Config, base: str, head: str, facts: dict[str, Any]
) -> tuple[str, str, str, _Commit | _WorkingTree]:
    """This function resolves the revisions and gives the head side of the comparison.

    The working tree uses HEAD for its revision and its merge base.
    """
    if head == WORKING_TREE:
        revisions = _comparison_revisions(cfg.root, base, "HEAD")
        return (*revisions, _WorkingTree(cfg, facts))
    revisions = _comparison_revisions(cfg.root, base, head)
    return (*revisions, _Commit(cfg, revisions[1]))


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
    language: LanguageAdapter,
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
        if repo_files.plain(record.get("file"))
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
    texts: tuple[str, str],
    prefixes: set[str],
    known: set[str],
    paths: dict[str, Path],
    context: Any,
) -> tuple[set[str], set[str], set[str]] | None:
    base_raw, head_raw = texts
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
    texts: _Sides,
) -> tuple[dict[str, set[str]], dict[str, set[str]], list[str]]:
    """This function gives the added and removed tests of each target module.

    A test file that a side cannot read is in the third list, with its problem. Its test
    changes are not known.
    """
    prefixes = set(facts.get("packages", []))
    known = set(facts.get("components", {})) | modules
    paths = _paths_for_change(cfg, language, files, facts)
    context = language.context(cfg.root, paths, cfg.test_dirs, cfg.test_patterns)
    tests_added: dict[str, set[str]] = {}
    tests_removed: dict[str, set[str]] = {}
    unread: list[str] = []
    for path in files:
        if not language.is_test_file(path, cfg.test_dirs, cfg.test_patterns):
            continue
        before, after = texts.base[path], texts.head[path]
        problem = before.problem or after.problem
        if problem:
            unread.append(f"{path}: {problem}")
            continue
        changes = _test_file_changes(
            cfg, language, path, (before.raw, after.raw), prefixes, known, paths, context
        )
        if changes is None:
            continue
        targets, added, removed = changes
        for target in targets:
            tests_added.setdefault(target, set()).update(added)
            tests_removed.setdefault(target, set()).update(removed)
    return tests_added, tests_removed, unread


def _package_records(
    cfg: Config, language: LanguageAdapter, files: list[str], facts: dict[str, Any]
) -> dict[str, Any]:
    """This function gives the module records that a claim match reads.

    The facts give the `package` fact of each module that they contain. A new or removed
    file is not in the facts. For such a file, the adapter gives the package from the
    path, as the extraction does. A claim then does not read a dot in a file name as a
    package.
    """
    records: dict[str, Any] = dict(facts.get("components", {}))
    for path in files:
        module = language.module_for_path(cfg.root, path, cfg.roots)
        if module and module not in records:
            package = extraction.package_for(cfg, language, module, cfg.root / path)
            records[module] = {"package": package}
    return records


@dataclasses.dataclass(frozen=True)
class _Sides:
    """The text of each changed file at the merge base and at the head."""

    base: dict[str, change_text.Text]
    head: dict[str, change_text.Text]


def _unread_delta(before: change_text.Text, after: change_text.Text) -> dict[str, Any]:
    """This function gives the surface delta of a source file that a side cannot read.

    The delta has no names. Its `unknown` record gives the read problem of each side.
    """
    delta: dict[str, Any] = {
        part: {bucket: [] for bucket in BUCKETS} for part in ("added", "removed", "changed")
    }
    delta["unknown"] = {
        side: [{"line": 0, "reason": text.problem}] if text.problem else []
        for side, text in (("base", before), ("head", after))
    }
    return delta


def _source_deltas(
    language: LanguageAdapter, sources: dict[str, str], texts: _Sides
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """This function gives the surface delta of each changed source module.

    A module whose source a side cannot read, or whose source does not parse, is in the
    second list. Its changes are not known.
    """
    deltas: dict[str, dict[str, Any]] = {}
    unparsed: list[str] = []
    for path, module in sources.items():
        before, after = texts.base[path], texts.head[path]
        if before.problem or after.problem:
            unparsed.append(module)
            deltas[module] = _unread_delta(before, after)
            continue
        delta = surface_delta(before.raw, after.raw, language, path)
        if delta is None:
            unparsed.append(module)
            continue
        deltas[module] = delta
    return deltas, unparsed


@dataclasses.dataclass(frozen=True)
class SourceChange:
    """The source comparison of one base and one head.

    The comparison does not use a model. Thus each map of one render can use the same
    comparison, and systemap reads and parses each changed file one time.
    """

    base: str
    head: str
    base_revision: str
    head_revision: str
    merge_base: str
    files: tuple[str, ...] = ()
    facts: dict[str, Any] = dataclasses.field(default_factory=dict)
    records: dict[str, Any] = dataclasses.field(default_factory=dict)
    deltas: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    unparsed: tuple[str, ...] = ()
    tests_added: dict[str, set[str]] = dataclasses.field(default_factory=dict)
    tests_removed: dict[str, set[str]] = dataclasses.field(default_factory=dict)
    unread_tests: tuple[str, ...] = ()


def source_change(
    cfg: Config, base: str, facts: dict[str, Any], head: str = "HEAD"
) -> SourceChange:
    """This function compares the changed source files of a Git ref and a head.

    With the head `WORKING_TREE`, `facts` are the facts of the working tree. For a commit
    head, the facts come from the commit.
    """
    language = extraction.language_for(cfg)
    base_revision, head_revision, merge_base, side = _sides(cfg, base, head, facts)
    found = SourceChange(base, head, base_revision, head_revision, merge_base)
    files = side.files(merge_base)
    if not files:
        return found
    snapshot_facts = side.facts()
    tests = [p for p in files if language.is_test_file(p, cfg.test_dirs, cfg.test_patterns)]
    sources = {
        path: module
        for path in files
        if path not in tests
        for module in [language.module_for_path(cfg.root, path, cfg.roots)]
        if module
    }
    wanted = [*sources, *tests]
    texts = _Sides(change_text.at(cfg.root, merge_base, wanted), side.texts(wanted))
    deltas, unparsed = _source_deltas(language, sources, texts)
    tests_added, tests_removed, unread = _changed_test_deltas(
        cfg, language, files, snapshot_facts, set(deltas) | set(unparsed), texts
    )
    return dataclasses.replace(
        found,
        files=tuple(files),
        facts=snapshot_facts,
        records=_package_records(cfg, language, files, snapshot_facts),
        deltas=deltas,
        unparsed=tuple(sorted(unparsed)),
        tests_added=tests_added,
        tests_removed=tests_removed,
        unread_tests=tuple(sorted(unread)),
    )


def compute(
    cfg: Config,
    model: Model,
    base: str,
    facts: dict[str, Any],
    head: str = "HEAD",
    artifact_owner: dict[str, str] | None = None,
    source: SourceChange | None = None,
) -> dict[str, Any]:
    """This function gives the change-view data for a Git ref and a head.

    The head ref can differ from the branch in the working tree. The facts come from the
    resolved head snapshot. With the head `WORKING_TREE`, the comparison includes the
    edits that are not in a commit and the untracked files, and `facts` are the facts of
    the working tree. The `artifact_owner` table assigns flow artifacts to their
    defining modules. Without this table, public-name changes do not highlight flow
    artifacts. A `source` from `source_change` with the same base and head replaces the
    source comparison.
    """
    if source is None:
        source = source_change(cfg, base, facts, head)
    if (source.base, source.head) != (base, head):
        raise ValueError(
            f"The source comparison is {source.base}..{source.head}, not {base}..{head}."
        )
    if artifact_owner is None:
        artifact_owner = {}
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
        "base_revision": source.base_revision,
        "head_revision": source.head_revision,
        "comparison_base": source.merge_base,
        "reach_known": True,
        "unparsed": [],
        "unread_tests": [],
    }
    if not source.files:
        return empty
    files, snapshot_facts, records = list(source.files), source.facts, source.records
    deltas, unparsed = source.deltas, list(source.unparsed)
    tests_added, tests_removed = source.tests_added, source.tests_removed
    modules = set(deltas) | set(unparsed)

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
            if any(covers(p, m, records) for p in module_ids)
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
            if any(covers(p, module_id, records) for p in c.implemented_by if "/" not in p):
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
        **empty,
        "has_change": True,
        "direct": direct,
        "adjacent": adjacent,
        "modules": modules,
        "artifacts": artifacts,
        "flow_artifacts": flow_artifacts,
        "per_component": per_component,
        "files": len(files),
        "reach_known": reach_known,
        "unparsed": sorted(unparsed),
        "unread_tests": list(source.unread_tests),
    }


def for_page(
    cfg: Config,
    m: nest.Map,
    base: str,
    facts: dict[str, Any],
    head: str = "HEAD",
    source: SourceChange | None = None,
) -> dict[str, Any]:
    """This function gives the change-view data of one map page, with its map changes.

    The map changes compare the committed model at the comparison base with the model
    of the page. A render of several maps gives the same `source` to each map.
    """
    ch = compute(cfg, m.model, base, facts, head, source=source)
    ch["map"] = delta_model.for_page(cfg, m.id, m.model, m.meaning, ch["comparison_base"])
    return ch
