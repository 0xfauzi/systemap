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
import sys
from functools import partial
from pathlib import Path
from typing import Any

from systemap import (
    change_tests,
    change_text,
    delta_git,
    delta_model,
    extraction,
    fact_cache,
    git_command,
    history,
    nest,
)
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


def _git(repo: Path, *args: str, worktree: bool = False) -> subprocess.CompletedProcess[bytes]:
    """This function runs Git through `git_command` with a time limit of 90 seconds."""
    return git_command.run(repo, *args, timeout=90, worktree=worktree, error=ChangeError)


def _run(repo: Path, *args: str) -> str:
    """This function gives the output of a Git command, or "" if Git gives an error."""
    # Git gives file contents and paths as bytes. Source is UTF-8, whatever the locale.
    proc = _git(repo, *args)
    return _text(proc.stdout, "replace") if proc.returncode == 0 else ""


def _text(raw: bytes, errors: str) -> str:
    """This function decodes UTF-8 with universal newlines, as the text mode of `subprocess`."""
    return raw.decode("utf-8", errors).replace("\r\n", "\n").replace("\r", "\n")


def _git_cause(proc: subprocess.CompletedProcess[bytes]) -> str:
    """This function gives " Git gave: <cause>." if Git wrote an error, or "" if not."""
    if not proc.stderr.strip():
        return ""
    return f" Git gave: {git_command.cause(proc.stderr, proc.returncode)}."


def pr_meta(repo: Path, pr: str) -> dict[str, Any]:
    """This function gets a pull request title and counts from gh, or an empty record.

    The data is optional. If gh cannot start, does not answer in time, gives an error, or
    gives text that is not JSON, the function writes one note with the cause to stderr.
    Then it gives an empty record.

    A value that starts with "-" is not a pull request number, URL, or branch. The function
    does not give such a value to gh, because gh can read it as an option.
    """
    if not pr or pr.startswith("-"):
        return {}
    fields = "number,title,url,additions,deletions,changedFiles,state"
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", pr, "--json", fields],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _no_meta(pr, f"gh could not start or did not answer: {exc}")
    if proc.returncode:
        lines = proc.stderr.strip().splitlines() or [f"exit code {proc.returncode}"]
        return _no_meta(pr, f"gh gave an error: {lines[-1]}")
    try:
        found = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _no_meta(pr, "gh gave text that is not JSON")
    return dict(found) if isinstance(found, dict) else _no_meta(pr, "gh gave no JSON object")


def _no_meta(pr: str, cause: str) -> dict[str, Any]:
    print(
        f"render: the data of pull request {pr} is not available: {cause}. "
        "The page has no pull request title.",
        file=sys.stderr,
    )
    return {}


def _changed_files(repo: Path, merge_base: str, *head: str) -> list[str]:
    """This function lists changed paths. NUL delimiters keep spaces in path names.

    Without a head commit, Git compares the merge base with the working tree. Then the
    command also gets the settings that stop the filters of the repository configuration.
    """
    proc = _git(
        repo, "diff", "--name-only", "-z", merge_base, *head, "--no-renames", worktree=not head
    )
    if proc.returncode:
        raise ChangeError(
            f"Git could not compare {merge_base} and {''.join(head) or WORKING_TREE}."
            f"{_git_cause(proc)}"
        )
    return [f for f in _text(proc.stdout, "surrogateescape").split("\0") if f]


def _untracked_files(repo: Path) -> list[str]:
    """This function lists the files that Git does not track and does not ignore.

    The list does not include the systemap cache directory `.systemap/`.
    """
    out = _run(repo, "ls-files", "--others", "--exclude-standard", "--exclude=/.systemap/", "-z")
    return [f for f in out.split("\0") if f]


def _resolve(repo: Path, ref: str) -> str:
    """This function gives the full commit SHA of `ref`, or raises ChangeError.

    If Git writes an error, for example because it refuses the repository, the error text
    gives the Git cause.
    """
    proc = _git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}")
    revision = _text(proc.stdout, "replace").strip() if proc.returncode == 0 else ""
    if revision:
        return revision
    if _git_cause(proc):
        raise ChangeError(f"Git cannot resolve the revision {ref}.{_git_cause(proc)}")
    raise ChangeError(
        f"unknown revision {ref}. Give a commit, branch, or tag that Git can resolve."
    )


def _comparison_revisions(repo: Path, base: str, head: str) -> tuple[str, str, str]:
    base_revision, head_revision = _resolve(repo, base), _resolve(repo, head)
    proc = _git(repo, "merge-base", base_revision, head_revision)
    shared = _text(proc.stdout, "replace").strip() if proc.returncode == 0 else ""
    if not shared:
        raise ChangeError(
            f"{base} and {head} have no common ancestor for the comparison.{_git_cause(proc)}"
        )
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

    # The working tree has no commit. The test comparison reads its files on disk.
    revision = None

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
    return {"functions": [], "classes": [], "errors": [], "types": [], "constants": []}


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
        "types": {
            c["name"]: ",".join(c["methods"]) for c in surface["classes"] + surface.get("types", [])
        },
        "refusals": {e["name"]: ",".join(e["methods"]) for e in surface["errors"]},
        "constants": {c["name"]: c["value"] for c in surface["constants"]},
    }


def _type_categories(surface: dict[str, Any]) -> dict[str, list[str]]:
    """Give the source category of each type name: `class` from the `classes` fact, or
    the category in the `types` fact. A name without a category in the facts is not in
    the result, because its category is not known."""
    out: dict[str, set[str]] = {}
    for c in surface.get("classes", []):
        out.setdefault(c["name"], set()).add("class")
    for t in surface.get("types", []):
        if t.get("category"):
            out.setdefault(t["name"], set()).add(str(t["category"]))
    return {name: sorted(found) for name, found in out.items()}


def _changed_categories(
    delta: dict[str, Any], base: dict[str, Any], head: dict[str, Any]
) -> dict[str, list[str]]:
    """Give the category of each changed type. A removed type gets it from the base."""
    before, after = _type_categories(base), _type_categories(head)
    out = {n: before[n] for n in delta["removed"]["types"] if n in before}
    for part in ("added", "changed"):
        out |= {n: after[n] for n in delta[part]["types"] if n in after}
    return out


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
    delta["categories"] = _changed_categories(delta, base, head)
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
    categories: dict[str, list[str]] = {}
    for module in hit:
        delta = deltas.get(module)
        if delta is None:
            continue
        for part in ("added", "removed", "changed"):
            _merge_names(surface[part], delta[part])
        for name, found in delta.get("categories", {}).items():
            categories[name] = sorted(set(categories.get(name, [])) | set(found))
        if "unknown" in delta:
            unknown[module] = delta["unknown"]
    surface["categories"] = categories
    return surface, unknown


def _touched_names(delta: dict[str, Any]) -> set[str]:
    return {
        name
        for part in ("added", "removed", "changed")
        for names in delta[part].values()
        for name in names
    }


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
    language: LanguageAdapter,
    sources: dict[str, str],
    texts: _Sides,
    cache: fact_cache.FactCache | None = None,
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
        make = partial(surface_delta, before.raw, after.raw, language, path)
        key = fact_cache.text_digest(json.dumps([before.raw, after.raw]))
        delta = fact_cache.kept(cache, "surface", path, key, make)
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
    refused_paths: tuple[str, ...] = ()


def source_change(
    cfg: Config,
    base: str,
    facts: dict[str, Any],
    head: str = "HEAD",
    cache: fact_cache.FactCache | None = None,
) -> SourceChange:
    """This function compares the changed source files of a Git ref and a head.

    With the head `WORKING_TREE`, `facts` are the facts of the working tree. For a commit
    head, the facts come from the commit. With a cache, the function uses the kept
    surface delta of each pair of texts and the kept tests of each side.
    """
    language = extraction.language_for(cfg)
    base_revision, head_revision, merge_base, side = _sides(cfg, base, head, facts)
    found = SourceChange(base, head, base_revision, head_revision, merge_base)
    files = side.files(merge_base)
    if not files:
        return found
    snapshot_facts = side.facts()
    test_dirs = cfg.test_dirs
    tests = [p for p in files if language.is_test_file(p, test_dirs, cfg.test_patterns)]
    sources = {
        path: module
        for path in files
        if path not in tests
        for module in [language.module_for_path(cfg.root, path, cfg.roots)]
        if module
    }
    wanted = [*sources, *tests]
    refused = _refusals(files)
    texts = _Sides(
        _refused(change_text.at(cfg.root, merge_base, wanted), refused),
        _refused(side.texts(wanted), refused),
    )
    deltas, unparsed = _source_deltas(language, sources, texts, cache)
    tests_added, tests_removed, unread = change_tests.compare(
        cfg,
        language,
        ({path: texts.base[path] for path in tests}, {path: texts.head[path] for path in tests}),
        (merge_base, side.revision),
        cache,
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
        refused_paths=_refused_lines(refused, snapshot_facts),
    )


def _refusals(files: list[str]) -> dict[str, str]:
    """This function gives each changed path that the tree reader refuses, with its cause."""
    return {path: cause for path in files for cause in [delta_git.refusal(path)] if cause}


def _refused(
    texts: dict[str, change_text.Text], refused: dict[str, str]
) -> dict[str, change_text.Text]:
    """This function gives a read problem for each path that the tree reader refuses.

    The facts at a commit have no record for such a path. Thus its changes are not known
    on each side, also if Git or the disk can give its text.
    """
    return {
        path: change_text.Text(problem=f"the tree reader refuses the path: {refused[path]}")
        if path in refused
        else text
        for path, text in texts.items()
    }


def _refused_lines(refused: dict[str, str], facts: dict[str, Any]) -> tuple[str, ...]:
    """This function gives each refused path and its cause: the changed paths, and the
    paths that the facts of a commit head did not record."""
    found = dict(refused)
    for record in facts.get("refused_paths", []):
        found.setdefault(record["path"], record["reason"])
    return tuple(f"{path}: {cause}" for path, cause in sorted(found.items()))


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
        "refused_paths": [],
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
        "refused_paths": list(source.refused_paths),
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
