"""The stub of a nested part (`systemap parts --stub CARD`).

A stub is a nested model file that has only the components that this module writes:

- one internal component for each `suggest` group of the modules of the card,
- one internal component `<Card>Other` for the modules that are alone in their package,
- the symbol claims of the card, unchanged, on the component that claims their module,
  or else on `<Card>Other`,
- one actor for each component of the parent map that has a boundary flow or a
  crossing import with the card,
- positions from the same placement as `systemap place`,
- no flows, and the `MODEL` and `MEANING` exports.

The stub must pass the nesting check and the model checks of `systemap check` before
the agent of the parent map sets `map=` on the card. Thus this module examines the stub
before it writes the file. If the stub has a problem, it writes no file and gives the
problem. It does not write over a file that exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from systemap import check, file_write, model_convert, nest, parts, parts_plan, place
from systemap.config import ArgumentError, Config
from systemap.entry_names import started_module
from systemap.model import (
    Component,
    Container,
    Meaning,
    Model,
    Region,
    is_symbol,
    public_names,
)

NOTE = (
    "systemap parts --stub wrote this file. Replace the stub components with components "
    "for tasks. Then write the flows, the sequences, and the contract of the nested map."
)


class StubError(ArgumentError):
    """The command cannot write the stub. The message gives the reason."""


def _entry(modules: tuple[str, ...], preferred: str, facts: dict[str, Any]) -> str:
    """Select an entry for a stub component.

    The entry of the card comes first, if the modules define it. Else the first public
    name of the modules, in module order. Else the name of an entry point that does not
    start one public name (`entry_names`). Else no entry."""
    records = facts.get("components", {})
    names = [sorted(public_names(records[m])) for m in modules]
    if preferred and (
        any(preferred in n for n in names) or started_module(preferred, modules, facts)
    ):
        return preferred
    for found in names:
        if found:
            return found[0]
    for point in facts.get("entry_points", []):
        if point.get("module") in modules and point.get("symbol") == "":
            return str(point["name"])
    return ""


def _internal(card: Component, plan: dict[str, Any], facts: dict[str, Any]) -> list[Component]:
    """Give the internal components of the stub, with their claims and entries."""
    claims = [(g["id"], tuple(g["modules"])) for g in plan["groups"]]
    other = f"{card.id}Other"
    symbols = [p for p in card.implemented_by if is_symbol(p)]
    homes = {m: cid for cid, modules in claims for m in modules}
    if other in plan["ids"]:
        claims.append((other, tuple(plan["alone"])))
    out = []
    for cid, modules in claims:
        own = tuple(p for p in symbols if homes.get(p.partition(":")[0], other) == cid)
        out.append(
            Component(
                id=cid,
                does=_does(cid, other, modules),
                implemented_by=modules + own,
                entry=_entry(modules, card.entry, facts),
                kind=card.kind,
                region="work",
            )
        )
    return out


def _does(cid: str, other: str, modules: tuple[str, ...]) -> str:
    if cid == other:
        return "Contains the modules that are alone in their package."
    return f"Contains the modules of the package group {cid} ({len(modules)} modules)."


def _actor(parent: nest.Map, cid: str) -> Component:
    found = parent.model.find(cid)
    does = found.does if found is not None else "An adjacent component."
    return Component(id=cid, does=does, kind="actor", container="around")


def build(
    tree: nest.Tree, parent: nest.Map, card: Component, facts: dict[str, Any]
) -> tuple[Model, Meaning]:
    """Give the model and the meaning of the stub for a card of the parent map."""
    child = nest.Map(
        parts.map_id(parent.id, card.id),
        parent.path,
        parent.rel,
        parent.model,
        parent.meaning,
        {},
        parent.id,
        card.id,
    )
    plan = _plan(tree, parent, child, facts)
    internal = _internal(card, plan, facts)
    actors = [a["id"] for a in plan["actors"]]
    _refuse_ids(parent, child.id, internal, actors)
    containers = [Container(id="part", label=card.id.upper(), box=(0, 0, 0, 0), tone="server")]
    if actors:
        containers.insert(0, Container(id="around", label="AROUND", box=(0, 0, 0, 0)))
    model = Model(
        canvas=(0, 0),
        containers=tuple(containers),
        regions=(Region(id="work", label="WORK", box=(0, 0, 0, 0), container="part"),),
        components=tuple([_actor(parent, cid) for cid in actors] + internal),
        flows=(),
        flow_kinds=(),
    )
    plain = {cid: parent.meaning.plain.get(cid, cid) for cid in actors}
    plain.update({c.id: f"the {c.id} modules" for c in internal})
    placement = place.compute(model)
    return place.apply(model, placement), Meaning(plain=plain)


def _plan(
    tree: nest.Tree, parent: nest.Map, child: nest.Map, facts: dict[str, Any]
) -> dict[str, Any]:
    """Give the groups and the adjacent components of the new part."""
    grown = nest.Tree((*tree.maps, child))
    card = parent.model.component(child.card)
    found = parts_plan.groups_of(parts_plan.modules_of(card, facts), facts)
    return {
        **parts_plan.groups_record(found),
        "ids": parts_plan.stub_ids(card, found),
        **parts_plan.boundary(grown, child, facts),
    }


def _refuse_ids(
    parent: nest.Map, map_id: str, internal: list[Component], actors: list[str]
) -> None:
    """Refuse an internal ID that is the same as an actor ID, and an actor that the parent
    map does not have. The actors of a nested map must be components of its parent map."""
    out = [
        f"{map_id}: the stub component {c.id} has the ID of the actor {c.id}. Give the "
        f"group a different ID in the stub, or open a map in a different component."
        for c in internal
        if c.id in actors
    ]
    where = parts.where(parent.id)
    out += [
        f"{map_id}: the stub needs the actor {cid}, but {where} has no component {cid}. "
        f"Add the actor {cid} to {where} first."
        for cid in actors
        if cid not in parent.model.ids
    ]
    if out:
        raise StubError("\n".join(out))


def problems(
    parent: nest.Map,
    card: Component,
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    rel: str,
) -> list[str]:
    """Give the problems of the stub from the model checks and the nesting check."""
    result = check.run(model, meaning, parent.theme, facts, coverage=False)
    nesting = check.check_nesting(parent.model, card, model, facts, rel)
    return [*result.problems, *result.entry, *result.interface, *nesting]


def source(map_id: str, model: Model, meaning: Meaning) -> str:
    """Give the text of the stub model file."""
    doc = f"The nested map {map_id}.\n\n{NOTE}"
    return model_convert.source_text(doc, model, meaning, note="")


def write(
    cfg: Config, tree: nest.Tree, parent: nest.Map, card_id: str, facts: dict[str, Any]
) -> Path:
    """Examine and write the stub for a card of the parent map. Give the path of the file."""
    card = _card(parent, card_id)
    map_id = parts.map_id(parent.id, card.id)
    others = [c.id for c in parent.model.components if c.map and c.id != card.id]
    stems = parts.stem_problems([map_id, *(parts.map_id(parent.id, cid) for cid in others)])
    if stems:
        raise StubError("\n".join(stems))
    path = parent.path.parent / parts.file_name(map_id)
    rel = cfg.rel(path)
    if path.exists() or path.is_symlink():
        raise StubError(f"{rel} exists. systemap parts --stub does not write over a file.")
    model, meaning = build(tree, parent, card, facts)
    found = problems(parent, card, model, meaning, facts, rel)
    if found:
        raise StubError(
            f"The stub of {map_id} has problems. systemap wrote no file:\n" + "\n".join(found)
        )
    text = source(map_id, model, meaning)
    model_convert.same_model(path, rel, text, model, meaning)
    file_write.write_atomic(cfg.root, path, text)
    return path


def _card(parent: nest.Map, card_id: str) -> Component:
    found = parent.model.find(card_id)
    where = parts.where(parent.id)
    if found is None or found.kind == "actor":
        raise StubError(f"{card_id} is not an internal component of {where}.")
    if found.map is not None:
        raise StubError(f"{card_id} already opens the map {found.map}. A stub is for a new part.")
    return found
