"""The part plan: the facts for each nested part of one map (`systemap parts`).

A nested part is one nested map, its contract file, and the model files with its file
prefix. The plan does not select the boundaries of the parts. The agent of the parent map
selects them when it sets `map=` on a component. The plan gives the facts for these
boundaries: the modules of each part, the module groups, the adjacent components, the
flows and the imports across the boundary, and the entry points of the part.

The plan has two digests. `facts_digest` is the SHA-256 of the source facts: the facts
file without `built_at_commit` and without the provenance values of one computer
(`source_text.LOCAL_INPUTS`). Thus a refresh at a new commit with the same source facts
does not make the plan stale. `contract_digest` is the SHA-256 of the contract of the
parent map and of each map above it: the shared words (layers, regions, and flow
artifacts), the identity and the claims of each component, the flows, the invariants,
and the import rules. A level-2 record uses the owners in the maps above its parent map.
Thus a change in those maps also makes the plan stale. A change to a position or to a
description does not make the plan stale.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap import (
    contract,
    decisions_store,
    file_write,
    nest,
    parts,
    source_facts,
    source_text,
    suggest,
)
from systemap.config import Config
from systemap.evidence import owners
from systemap.journey_coverage import outside_map
from systemap.judgement import crossing_pairs
from systemap.model import Component, all_layers, claimed, is_symbol

# A part with more modules than this is a level-2 part: forty components with ten modules
# each. It is a value from two constants, not a measurement of readability.
LEVEL_2_ABOVE = nest.CARDS_PER_MAP * nest.MODULES_PER_CARD
STALE = "The plan is stale. Do systemap parts again."


@dataclass(frozen=True)
class Groups:
    """The module groups of a part from `suggest.proposals`, and the modules alone in
    their package."""

    groups: tuple[suggest.Proposal, ...]
    alone: tuple[str, ...]


def modules_of(card: Component, facts: dict[str, Any]) -> list[str]:
    """Give the modules of a component without the empty package markers."""
    components = facts.get("components", {})
    return [m for m in claimed(card, components) if not source_facts.is_empty_marker(components[m])]


def groups_of(modules: list[str], facts: dict[str, Any]) -> Groups:
    """Give the `suggest` groups of the modules of one part."""
    records = facts.get("components", {})
    found, alone = suggest.proposals({"components": {m: records[m] for m in modules}})
    return Groups(tuple(found), tuple(alone))


def facts_digest(cfg: Config) -> str:
    """Give the SHA-256 of the source facts (see the module docstring). A facts file that
    is missing gives an empty string. A file that is not JSON gives the SHA-256 of its
    text, so that a different file gives a different digest."""
    text = file_write.read_text(cfg.root, cfg.facts_path)
    if text is None:
        return ""
    try:
        facts = json.loads(text)
    except ValueError:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    return _digest(source_values(facts) if isinstance(facts, dict) else facts)


def source_values(facts: dict[str, Any]) -> dict[str, Any]:
    """Give the facts without the values that change when the source facts stay the same."""
    out = {key: value for key, value in facts.items() if key != "built_at_commit"}
    provenance = out.get("provenance")
    if isinstance(provenance, dict):
        out["provenance"] = {
            key: value for key, value in provenance.items() if key not in source_text.LOCAL_INPUTS
        }
    return out


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def vocabulary(m: nest.Map) -> dict[str, list[str]]:
    """Give the shared words of a map: the layer IDs, the region IDs, and the artifacts."""
    return {
        "layers": [layer.id for layer in all_layers(m.model, m.meaning)],
        "regions": [region.id for region in m.model.regions],
        "flow_artifacts": sorted({f.artifact for f in m.model.flows}),
    }


def _contract(m: nest.Map) -> dict[str, Any]:
    """Give the contract values of one map (see the module docstring)."""
    model = m.model
    return {
        "map": m.id,
        "vocabulary": vocabulary(m),
        "components": [[c.id, c.kind, list(c.implemented_by), c.map] for c in model.components],
        "flows": [[f.src, f.dst, f.artifact, f.kind, f.id] for f in model.flows],
        "invariants": [[i.n, i.text, list(i.governs)] for i in model.invariants],
        "import_rules": [[r.id, r.kind, list(r.src), list(r.dst)] for r in model.import_rules],
    }


def contract_digest(tree: nest.Tree, m: nest.Map) -> str:
    """Give the SHA-256 of the contract of a parent map and of each map above it."""
    path: list[dict[str, Any]] = []
    found: nest.Map | None = m
    while found is not None:
        path.insert(0, _contract(found))
        found = tree.parent_of(found)
    return _digest(path)


def outside_owners(tree: nest.Tree, child: nest.Map, facts: dict[str, Any]) -> dict[str, str]:
    """Give the owner of each module outside the part that opens `child`.

    The owner is the component of the nearest ancestor map that claims the module. A
    module of the card that opens a map on the path from the top map to `child` is
    inside the part, and has no owner here. At level 2, the owner can be a component of
    a map above the direct parent map. The direct parent map must then have an actor
    with the ID of the owner."""
    out: dict[str, str] = {}
    inside: set[str] = set()
    m: nest.Map | None = child
    while m is not None and m.parent is not None:
        parent = tree.get(m.parent)
        for module, owner in owners(parent.model, facts).items():
            if module in out or module in inside:
                continue
            if owner == m.card:
                inside.add(module)
            else:
                out[module] = owner
        m = parent
    return out


IMPORT, IMPORTED = "crossing import", "crossing import into the part"


def _actors(
    card: str, flows: list[dict[str, str]], imports: list[dict[str, str]], into: list[str]
) -> list[Any]:
    """Give each adjacent component of a part with the causes. `into` gives the components
    that import a module of the part."""
    because: dict[str, list[str]] = {}
    for f in flows:
        other = f["dst"] if f["src"] == card else f["src"]
        because.setdefault(other, []).append(f"flow {f['artifact']}")
    causes = [(row["card"], IMPORT) for row in imports] + [(cid, IMPORTED) for cid in into]
    for cid, cause in causes:
        found = because.setdefault(cid, [])
        if cause not in found:
            found.append(cause)
    return [{"id": cid, "because": because[cid]} for cid in sorted(because)]


Pairs = dict[tuple[str, str], list[tuple[str, str]]]


def pairs_of(tree: nest.Tree, child: nest.Map, facts: dict[str, Any]) -> Pairs:
    """Give the crossing imports between the components of the parent map of `child` and
    the owners above it. The value is the same for each nested part of one parent map.
    Thus a plan calculates it one time."""
    parent = tree.get(child.parent or "")
    owner = outside_owners(tree, child, facts)
    owner.update(dict.fromkeys(modules_of(parent.model.component(child.card), facts), child.card))
    return crossing_pairs(facts.get("components", {}), owner)


def boundary(
    tree: nest.Tree, child: nest.Map, facts: dict[str, Any], pairs: Pairs | None = None
) -> dict[str, Any]:
    """Give the flows, the imports, and the adjacent components at the boundary of a part.

    `pairs` is the value of `pairs_of`. If it is None, the function calculates it. An
    adjacent component can import a module of the part, or a module of the part can
    import a module of the adjacent component."""
    parent = tree.get(child.parent or "")
    card = child.card
    flows = [
        {"src": f.src, "dst": f.dst, "artifact": f.artifact}
        for f in parent.model.flows
        if card in (f.src, f.dst) and f.src != f.dst
    ]
    pairs = pairs_of(tree, child, facts) if pairs is None else pairs
    imports = [
        {"module": module, "imports": target, "card": q}
        for (p, q), rows in sorted(pairs.items())
        if p == card
        for module, target in rows
    ]
    into = sorted({p for p, q in pairs if q == card})
    return {
        "actors": _actors(card, flows, imports, into),
        "boundary_flows": flows,
        "boundary_imports": imports,
    }


def _entry_points(child: nest.Map, modules: list[str], facts: dict[str, Any]) -> list[str]:
    """Give the entry points that the part must cover with a sequence.

    Each entry point goes to the deepest map that claims its module. Thus a module that a
    nested map of the part claims is not in the list of the part."""
    skip = outside_map(child.model, False, facts)
    held = set(modules) - skip
    points = facts.get("entry_points", [])
    return [source_facts.entry_identity(p) for p in points if p.get("module") in held]


def groups_record(found: Groups) -> dict[str, Any]:
    """Give the groups and the modules alone in their package as plan values."""
    return {
        "groups": [{"id": g.id, "modules": list(g.modules)} for g in found.groups],
        "alone": list(found.alone),
    }


def lost_symbols(card: Component, found: Groups) -> list[str]:
    """Give the symbol claims of a card whose module is in no group."""
    held = {m for g in found.groups for m in g.modules}
    return [p for p in card.implemented_by if is_symbol(p) and p.partition(":")[0] not in held]


def stub_ids(card: Component, found: Groups) -> set[str]:
    """Give the IDs of the internal components of the stub of a card. `<Card>Other` holds
    the modules alone in their package and the symbol claims that no group holds."""
    other = {f"{card.id}Other"} if found.alone or lost_symbols(card, found) else set()
    return {g.id for g in found.groups} | other


def state(child: nest.Map, card: Component, found: Groups) -> str:
    """Give `stub` while the map has only the components of `systemap parts --stub`.

    `found` gives the groups of the modules of the card that opens the map."""
    inside = {c.id for c in child.model.components if c.kind != "actor"}
    return "stub" if inside == stub_ids(card, found) and not child.model.flows else "mapped"


def _source_bytes(cfg: Config, modules: list[str], facts: dict[str, Any]) -> int:
    """Give the sum of the file sizes of the modules. A file that is missing counts 0."""
    records = facts.get("components", {})
    total = 0
    for module in modules:
        path = cfg.root / str(records[module].get("file", ""))
        if records[module].get("file") and path.is_file():
            total += path.stat().st_size
    return total


def record(
    cfg: Config,
    tree: nest.Tree,
    child: nest.Map,
    facts: dict[str, Any],
    pairs: Pairs | None = None,
) -> dict[str, Any]:
    """Give the record of one nested part in the plan. `pairs` is as in `boundary`."""
    parent = tree.get(child.parent or "")
    card = parent.model.component(child.card)
    modules = modules_of(card, facts)
    found = groups_of(modules, facts)
    own = parts.stem(child.id)
    return {
        "map": child.id,
        "card": child.card,
        "stem": own,
        "model_file": cfg.rel(child.path),
        "contract_file": cfg.rel(contract.path_for(child.path)),
        "file_prefix": cfg.rel(child.path.parent / f"{own}_"),
        "result_file": cfg.rel(parts.result_path(cfg.model_path, child.id)),
        "modules": modules,
        "module_count": len(modules),
        "source_bytes": _source_bytes(cfg, modules, facts),
        **groups_record(found),
        **boundary(tree, child, facts, pairs),
        "import_rules": [r.id for r in parent.model.import_rules if child.card in r.src],
        "entry_points": _entry_points(child, modules, facts),
        "state": state(child, card, found),
        "level_2": len(modules) > LEVEL_2_ABOVE,
    }


def shared_files(cfg: Config, m: nest.Map) -> list[str]:
    """Give the files that only the agent of the parent map writes."""
    names = [
        "pyproject.toml" if cfg.source.startswith("pyproject.toml") else "systemap.toml",
        decisions_store.STORE,
        cfg.rel(m.path),
        cfg.rel(contract.path_for(m.path)),
        cfg.rel(parts.plan_path(cfg.model_path, m.id)),
        cfg.out_dir.rstrip("/") + "/",
    ]
    return list(dict.fromkeys(names))


def build(cfg: Config, tree: nest.Tree, m: nest.Map, facts: dict[str, Any]) -> dict[str, Any]:
    """Give the plan for the nested parts of the map `m`."""
    children = tree.children(m)
    pairs = pairs_of(tree, children[0], facts) if children else None
    found = [record(cfg, tree, child, facts, pairs) for child in children]
    order = sorted(found, key=lambda r: (-r["module_count"], r["map"]))
    return {
        "map": m.id,
        "base_commit": str(facts.get("built_at_commit", "")),
        "facts_digest": facts_digest(cfg),
        "contract_digest": contract_digest(tree, m),
        "vocabulary": vocabulary(m),
        "shared_files": shared_files(cfg, m),
        "parts": found,
        "order": [r["map"] for r in order],
    }


def problems(tree: nest.Tree, m: nest.Map) -> list[str]:
    """Give the lines for the stems of the nested parts of `m` that are not permitted."""
    return parts.stem_problems(child.id for child in tree.children(m))


def text(plan: dict[str, Any]) -> str:
    """Give the plan as JSON text with a final newline."""
    return json.dumps(plan, indent=2, ensure_ascii=False) + "\n"


def write(cfg: Config, plan: dict[str, Any]) -> Path:
    """Write the plan file of the map of the plan. Give its path."""
    path = parts.plan_path(cfg.model_path, plan["map"])
    file_write.folder(cfg.root, path)
    file_write.write_atomic(cfg.root, path, text(plan))
    return path


def read(cfg: Config, map_id: str) -> dict[str, Any] | None:
    """Read the plan file of a map. Give None if the file is missing.

    A file that is not a JSON object gives ValueError."""
    stored = file_write.read_text(cfg.root, parts.plan_path(cfg.model_path, map_id))
    if stored is None:
        return None
    data = json.loads(stored)
    if not isinstance(data, dict):
        raise ValueError("the plan file does not contain a JSON object")
    return data


def is_stale(cfg: Config, tree: nest.Tree, plan: dict[str, Any], m: nest.Map) -> bool:
    """Tell if a digest of the plan is different from the current tree."""
    current = (facts_digest(cfg), contract_digest(tree, m))
    return (plan.get("facts_digest"), plan.get("contract_digest")) != current


def summary(plan: dict[str, Any]) -> list[str]:
    """Give one line for each part, in the order of the plan."""
    by_map = {r["map"]: r for r in plan["parts"]}
    out = []
    for map_id in plan["order"]:
        r = by_map[map_id]
        actors = ", ".join(a["id"] for a in r["actors"]) or "none"
        level = ", level 2" if r["level_2"] else ""
        out.append(
            f"  {map_id} ({r['model_file']}): {r['module_count']} modules, "
            f"{len(r['entry_points'])} entry points, actors {actors}, {r['state']}{level}"
        )
    return out


def stale_warnings(cfg: Config, tree: nest.Tree) -> list[str]:
    """Give a warning for each stale plan of the selected map in a run with `--map`.

    The plans are the plan that has the selected map as a part, and the plan of its own
    nested parts. A plan that does not exist gives no line."""
    if not tree.partial:
        return []
    selected = tree.get(tree.selected or "")
    out: list[str] = []
    for m in (tree.parent_of(selected), selected):
        if m is None:
            continue
        rel = cfg.rel(parts.plan_path(cfg.model_path, m.id))
        try:
            plan = read(cfg, m.id)
        except ValueError:
            out.append(f"warning: systemap cannot read the plan file {rel}. {STALE}")
            continue
        if plan is not None and is_stale(cfg, tree, plan, m):
            out.append(f"warning: {STALE} The plan file is {rel}.")
    return out
