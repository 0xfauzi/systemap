"""M5 of the nested parts design: a round trip of the self-map through nested parts.

Acceptance (written before the run, from docs/design/nested-parts.md):

- Divide the self-map (map/model.py of this repository) into nested parts that copy
  its current cards and flows. After the division, `systemap judgement` gives 0
  `boundary flow` lines and 0 `boundary import` lines. `systemap check` gives the same
  exit code as before the division, and `systemap rules` gives the same result text.

The division:

- Each region of the top map becomes one card `<Region>Part` on the top map. The card
  claims the claims of the components of the region, and it opens a nested map. The
  actors of the self-map stay on the top map.
- The nested map of a part has the components of the region, unchanged, without
  positions and without source reviews. It also has one actor for each top card that
  has a flow with the region or that a module of the region imports.
- A flow between two components of one region goes into the nested map of the region.
  A flow between two parts goes to the top map as a flow between the two part cards,
  and into each of the two nested maps as a flow with the actor of the other part. A
  flow between an actor and a component goes to the top map as a flow between the actor
  and the part card, and into the nested map as a flow with the actor. Each flow keeps
  its artifact, its kind, its source records, and its relation sentence.
- Each invariant goes to the top map. Its components change to their part cards.

Differences from the design, written before the run: the sequences, the flow layer
overrides, and the verb overrides of the self-map are not copied, because their steps
and keys name the flows of the self-map. The flow reviews and the source reviews are not
copied, because the claims change. Thus `check` and `judgement` can give lines about
sequences and reviews that the self-map does not have. The script gives these lines
for information only. They are not part of the acceptance.

The script copies the repository files that the map reads into a new temporary folder.
Each command is a new process (`python -m systemap`). The script sends no data out.

Run from the repository root: uv run python bench/jev/join_round_trip.py
"""

from __future__ import annotations

import collections
import dataclasses
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from systemap import config, flow_ids, model_convert, nest, parts
from systemap.evidence import owners
from systemap.model import Component, Flow, Meaning, Model, Region

ROOT = Path(__file__).resolve().parents[2]
COPIED = ("systemap.toml", "pyproject.toml", "map", "src", "tests", "docs/map")
SKIP = shutil.ignore_patterns("__pycache__", "*.lock", ".systemap")
KINDS = ("boundary flow", "boundary import")


class Failed(Exception):
    """A command of the experiment did not do its work. The message gives the output."""


def systemap(root: Path, *argv: str) -> tuple[int, str]:
    done = subprocess.run(
        [sys.executable, "-m", "systemap", "--root", str(root), *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, done.stdout + done.stderr


def must(root: Path, *argv: str) -> str:
    code, out = systemap(root, *argv)
    if code != 0:
        raise Failed(f"systemap {' '.join(argv)} gave exit code {code}: {out}")
    return out


def copy_repository(target: Path) -> None:
    for rel in COPIED:
        source = ROOT / rel
        if source.is_dir():
            shutil.copytree(source, target / rel, ignore=SKIP)
        else:
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target / rel)


def results(root: Path) -> dict[str, Any]:
    """Give the check exit code and lines, the rules text, and the judgement kinds."""
    code, check_out = systemap(root, "check")
    _rules_code, rules_out = systemap(root, "rules")
    _code, judged = systemap(root, "judgement", "--json")
    payload = json.loads(judged[judged.index("{") :])
    kinds = collections.Counter(row["kind"] for row in payload["open"])
    return {
        "check_exit": code,
        "check": [line for line in check_out.splitlines() if "UV_NATIVE_TLS" not in line],
        "rules": [line for line in rules_out.splitlines() if "UV_NATIVE_TLS" not in line],
        "open": payload["open"],
        "kinds": dict(kinds),
    }


def bare(c: Component) -> Component:
    return dataclasses.replace(c, x=None, y=None, pinned=False, source_review="", map=None)


def part_id(region: str) -> str:
    return f"{region[:1].upper()}{region[1:]}Part"


@dataclasses.dataclass
class Division:
    """The parts of the self-map: the part of each component and the new models."""

    model: Model
    meaning: Meaning
    part_of: dict[str, str]
    top_flows: list[Flow] = dataclasses.field(default_factory=list)
    top_relations: dict[str, str] = dataclasses.field(default_factory=dict)
    flows: dict[str, list[Flow]] = dataclasses.field(default_factory=dict)
    relations: dict[str, dict[str, str]] = dataclasses.field(default_factory=dict)
    actors: dict[str, set[str]] = dataclasses.field(default_factory=dict)


def divide(model: Model, meaning: Meaning, facts: dict[str, Any]) -> Division:
    part_of = {
        c.id: (part_id(c.region) if c.kind != "actor" and c.region else c.id)
        for c in model.components
    }
    regions = [r.id for r in model.regions]
    found = Division(model, meaning, part_of)
    for r in regions:
        found.flows[part_id(r)] = []
        found.relations[part_id(r)] = {}
        found.actors[part_id(r)] = set()
    for n, f in enumerate(model.flows):
        sentence = flow_ids.lookup(meaning.relations, f) or ""
        _place_flow(found, f, n, sentence)
    _import_actors(found, facts)
    return found


def _import_actors(found: Division, facts: dict[str, Any]) -> None:
    """Add an actor for each part that a module of a part imports."""
    model, part_of = found.model, found.part_of
    region_of = {c.id: part_of[c.id] for c in model.components if c.kind != "actor"}
    owner = owners(model, facts)
    for module, record in facts.get("components", {}).items():
        p = region_of.get(owner.get(module, ""))
        targets = {part_of.get(owner.get(target, "")) for target in record.get("uses", {})}
        if p:
            found.actors[p].update(q for q in targets if q and q != p)


def _place_flow(found: Division, f: Flow, n: int, sentence: str) -> None:
    a, b = found.part_of[f.src], found.part_of[f.dst]
    fid = f.id or f"f{n}"
    if a == b:
        found.flows[a].append(dataclasses.replace(f, id=fid, review_digest=""))
        found.relations[a][fid] = sentence
        return
    top = dataclasses.replace(f, src=a, dst=b, id=f"t{n}", review_digest="")
    found.top_flows.append(top)
    found.top_relations[top.id] = sentence
    if a in found.flows:
        found.flows[a].append(dataclasses.replace(f, dst=b, id=fid, review_digest=""))
        found.relations[a][fid] = sentence
        found.actors[a].add(b)
    if b in found.flows:
        found.flows[b].append(dataclasses.replace(f, src=a, id=fid, review_digest=""))
        found.relations[b][fid] = sentence
        found.actors[b].add(a)


def _actor(cid: str, model: Model) -> Component:
    known = model.find(cid)
    if known is not None and known.kind == "actor":
        return bare(known)
    return Component(
        id=cid, does="An adjacent part of systemap.", kind="actor", container="outside"
    )


def _part(root: Path, found: Division, r: Region) -> Component:
    """Write the nested map of one region, and give the part card of the region."""
    model, meaning = found.model, found.meaning
    pid = part_id(r.id)
    members = [c for c in model.components if c.kind != "actor" and c.region == r.id]
    claims = tuple(dict.fromkeys(p for c in members for p in c.implemented_by))
    card = Component(
        id=pid,
        does=f"Contains the components of the region {r.label}.",
        implemented_by=claims,
        entry=members[0].entry,
        region=r.id,
        map=parts.file_name(pid),
    )
    inner = [bare(c) for c in members]
    actors = [_actor(cid, model) for cid in sorted(found.actors[pid])]
    sub_model = dataclasses.replace(
        model,
        regions=(r,),
        components=(*actors, *inner),
        flows=tuple(found.flows[pid]),
        invariants=(),
        import_rules=(),
    )
    sub_meaning = Meaning(
        plain={c.id: meaning.plain.get(c.id, c.id.lower()) for c in (*actors, *inner)},
        layers=meaning.layers,
        layer_of_kind=meaning.layer_of_kind,
        relations=found.relations[pid],
        verbs=meaning.verbs,
    )
    text = model_convert.source_text(f"The nested map of {pid}.", sub_model, sub_meaning)
    (root / "map" / parts.file_name(pid)).write_text(text, encoding="utf-8")
    return card


def write_division(root: Path, found: Division) -> None:
    model, meaning = found.model, found.meaning
    outside = [bare(c) for c in model.components if c.kind == "actor"]
    cards = [_part(root, found, r) for r in model.regions]
    invariants = tuple(
        dataclasses.replace(i, governs=tuple(dict.fromkeys(found.part_of[g] for g in i.governs)))
        for i in model.invariants
    )
    top_model = dataclasses.replace(
        model,
        components=(*outside, *cards),
        flows=tuple(found.top_flows),
        invariants=invariants,
        import_rules=model.import_rules,
    )
    plain = {c.id: meaning.plain.get(c.id, c.id) for c in outside}
    top_meaning = Meaning(
        plain=plain | {c.id: c.id.lower() for c in cards},
        layers=meaning.layers,
        layer_of_kind=meaning.layer_of_kind,
        relations=found.top_relations,
        verbs=meaning.verbs,
    )
    for rel in ("map/flows.py", "map/journeys.py", "map/contract.py", "map/model.py"):
        (root / rel).unlink()
    text = model_convert.source_text("The self-map in nested parts.", top_model, top_meaning)
    (root / "map/model.py").write_text(text, encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        copy_repository(root)
        must(root, "refresh", "--quiet")
        before = results(root)
        cfg = config.load(root)
        tree = nest.load(cfg)
        facts = json.loads(cfg.facts_path.read_text(encoding="utf-8"))
        found = divide(tree.top.model, tree.top.meaning, facts)
        write_division(root, found)
        must(root, "place")
        code, refresh_out = systemap(root, "refresh", "--quiet")
        print(f"refresh after the division: exit code {code}")
        after = results(root)
        maps = nest.load(config.load(root)).ids
    boundary = [row for row in after["open"] if row["kind"] in KINDS]
    print(f"maps after the division: {len(maps)}")
    for label, value in (("before", before), ("after", after)):
        print(f"{label}: check exit {value['check_exit']}, open lines by kind {value['kinds']}")
    print("check lines before:", *before["check"], sep="\n  ")
    print("check lines after:", *after["check"], sep="\n  ")
    print("rules before:", *before["rules"], sep="\n  ")
    print("rules after:", *after["rules"], sep="\n  ")
    print("boundary lines after the division:", *[row["line"] for row in boundary], sep="\n  ")
    if code != 0:
        print(refresh_out)
    ok = not boundary and before["check_exit"] == after["check_exit"]
    ok = ok and before["rules"] == after["rules"]
    print(f"M5: {'pass' if ok else 'fail'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
