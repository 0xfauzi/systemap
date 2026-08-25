"""The schema a system map is written in, and the checks that keep it honest.

A map has two hand-authored halves and one derived one:

    Model ..... the topology: containers (hard boundaries), regions (soft
                bands), components (with a fixed place on the canvas), the
                flows between them with the artifact each carries, and the
                invariants that govern them
    Meaning ... what the topology means: a plain word per component, the
                layers a reader can switch between, one sentence per flow,
                the journeys a reader can step through, and the verb each
                spoke of the relationship wheel prints
    facts ..... read out of the code by `systemap extract`: every module,
                its public surface, and the tests that import it

Build state is DERIVED, never declared: a component is built when the modules
named in `implemented_by` exist in the facts and carry the entry point named
in `entry`. A component that carries a `tracker` (a roadmap item) is planned
until that entry appears, so the map cannot claim something is finished
before the code lands, and cannot keep calling it planned after it does.

Positions are hand-placed because this is a topology, not a chart: a box's
place carries meaning. A fixed layout also means the same system always
draws the same picture, so a change in the drawing is a change in the
system. `Model.layout_problems()` checks the placement mechanically and
`meaning_problems()` checks that the meaning names only what the model has.

Three node kinds are drawn differently on purpose. A `component` does work,
a `store` holds state, an `actor` is outside the system. Drawing a store as
if it were a processing step is the most common lie in architecture
diagrams.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

Box = tuple[int, int, int, int]
Edge = tuple[str, str]

KINDS = ("component", "store", "actor")
TONES = ("host", "client", "server", "isolated")

# Card geometry the layout check shares with the drawing.
CARD_W = 150
CARD_H: dict[str, int] = {"component": 56, "store": 52, "actor": 44}


@dataclass(frozen=True)
class Container:
    """A hard boundary: a process, a host, a directory the system may not cross."""

    id: str
    label: str
    box: Box
    sub: str = ""
    tone: str = "host"


@dataclass(frozen=True)
class Region:
    """A soft band inside a container: a phase, a concern, a team."""

    id: str
    label: str
    box: Box
    container: str | None = None


@dataclass(frozen=True)
class Component:
    """One card on the map.

    `region` places a component or store; `container` places an actor. `x`
    and `y` are the card's top-left corner in canvas units. `tracker` marks
    a roadmap item whose code has not landed; `note` is a caveat the reader
    should see; `interface` is the one-line signature the reader is told.
    """

    id: str
    does: str
    interface: str = ""
    implemented_by: tuple[str, ...] = ()
    entry: str = ""
    kind: str = "component"
    region: str | None = None
    container: str | None = None
    x: int = 0
    y: int = 0
    tracker: str = ""
    note: str = ""

    @property
    def home(self) -> str:
        return self.region or self.container or ""

    @property
    def box(self) -> Box:
        return self.x, self.y, CARD_W, CARD_H[self.kind]


@dataclass(frozen=True)
class Flow:
    """One artifact travelling from `src` to `dst`, in one dataflow `kind`."""

    src: str
    dst: str
    artifact: str
    kind: str

    @property
    def edge(self) -> Edge:
        return self.src, self.dst


@dataclass(frozen=True)
class Invariant:
    """A load-bearing rule, numbered, and the components it directly governs."""

    n: int
    text: str
    governs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Step:
    """One step of a journey: who acts, who measures, the edge it traces."""

    acts: tuple[str, ...]
    measures: tuple[str, ...]
    edge: Edge
    say: str


@dataclass(frozen=True)
class Journey:
    id: str
    label: str
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class Layer:
    """One reading of the map: the question it answers and a sub-line."""

    id: str
    label: str
    question: str = ""
    sub: str = ""


@dataclass(frozen=True)
class Model:
    """The hand-authored topology of one system."""

    canvas: tuple[int, int]
    containers: tuple[Container, ...]
    regions: tuple[Region, ...]
    components: tuple[Component, ...]
    flows: tuple[Flow, ...]
    flow_kinds: tuple[str, ...]
    invariants: tuple[Invariant, ...] = ()

    @property
    def ids(self) -> set[str]:
        return {c.id for c in self.components}

    def component(self, cid: str) -> Component:
        for c in self.components:
            if c.id == cid:
                return c
        raise KeyError(cid)

    def rules_of(self, cid: str) -> list[int]:
        """The invariant numbers governing a component, in invariant order."""
        return [inv.n for inv in sorted(self.invariants, key=lambda i: i.n) if cid in inv.governs]

    def layout_problems(self) -> list[str]:
        """Ways the hand-placed topology contradicts itself. Empty means clean.

        Every card must sit inside the region (or container) the model
        assigns it, no two cards may overlap, a region that names a
        container must sit inside it, every flow must name known components
        and a known kind, and every invariant must govern known components.
        A card outside its band would draw a topology the model does not
        claim, which is the one lie a hand-placed layout can tell.
        """
        out: list[str] = []
        regions = {r.id: r.box for r in self.regions}
        containers = {c.id: c.box for c in self.containers}
        ids = self.ids
        seen: set[str] = set()
        for c in self.components:
            if c.id in seen:
                out.append(f"{c.id} is defined twice")
            seen.add(c.id)
            if c.kind not in KINDS:
                out.append(f"{c.id} has unknown kind {c.kind}")
        for box in self.containers:
            if box.tone not in TONES:
                out.append(f"container {box.id} has unknown tone {box.tone}")
        for region in self.regions:
            if region.container is None:
                continue
            outer = containers.get(region.container)
            if outer is None:
                out.append(f"region {region.id} names unknown container {region.container}")
            elif not _inside(region.box, outer):
                out.append(f"region {region.id} is not inside {region.container}")
        for c in self.components:
            if c.kind not in CARD_H:
                continue
            outer = regions.get(c.home) or containers.get(c.home)
            if not c.home:
                out.append(f"{c.id} names no region or container")
            elif outer is None:
                out.append(f"{c.id} names unknown region or container {c.home}")
            elif not _inside(c.box, outer):
                out.append(f"{c.id} is drawn outside {c.home}")
        drawable = [c for c in self.components if c.kind in CARD_H]
        for i, a in enumerate(drawable):
            for b in drawable[i + 1 :]:
                if _overlap(a.box, b.box):
                    out.append(f"{a.id} overlaps {b.id}")
        for f in self.flows:
            if f.src not in ids or f.dst not in ids:
                out.append(f"flow {f.src} -> {f.dst} names an unknown component")
            if f.kind not in self.flow_kinds:
                out.append(f"flow {f.src} -> {f.dst} has unknown kind {f.kind}")
        for inv in self.invariants:
            for cid in inv.governs:
                if cid not in ids:
                    out.append(f"invariant {inv.n} governs unknown component {cid}")
        return out


@dataclass(frozen=True)
class Meaning:
    """The hand-authored meaning of one system.

    `plain` is the plain word per component id. `layers` is the order the
    layer switch shows them; the first is on by default. `layer_of_kind`
    maps a flow kind to a layer and `layer_overrides` moves single edges to
    another layer. `relations` is one sentence per edge, read from the
    source side. `verbs` gives (verb when the clicked component is the
    source, verb when it is the target) per layer; `verb_overrides` does
    the same per edge.
    """

    plain: Mapping[str, str]
    layers: tuple[Layer, ...]
    layer_of_kind: Mapping[str, str]
    relations: Mapping[Edge, str]
    journeys: tuple[Journey, ...] = ()
    layer_overrides: Mapping[Edge, str] = field(default_factory=dict)
    verbs: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    verb_overrides: Mapping[Edge, tuple[str, str]] = field(default_factory=dict)

    def layer_for(self, edge: Edge, kind: str) -> str:
        """The one layer a flow belongs to: the override if any, else its kind's."""
        return self.layer_overrides.get(edge) or self.layer_of_kind[kind]

    def verb_for(self, edge: Edge, layer: str, from_clicked: bool) -> str:
        """The verb to print on a spoke, read from the clicked component."""
        pair = self.verb_overrides.get(edge) or self.verbs.get(layer, ("to", "from"))
        return pair[0] if from_clicked else pair[1]


def meaning_problems(model: Model, meaning: Meaning) -> list[str]:
    """Ways the meaning names something the model does not have, or misses one."""
    out: list[str] = []
    ids = model.ids
    edges = {f.edge for f in model.flows}
    layer_ids = {layer.id for layer in meaning.layers}
    if not meaning.layers:
        out.append("no layers are defined")
    for f in model.flows:
        if f.edge not in meaning.relations:
            out.append(f"flow {f.src} -> {f.dst} has no sentence in relations")
        try:
            layer = meaning.layer_for(f.edge, f.kind)
        except KeyError:
            out.append(f"flow {f.src} -> {f.dst} has kind {f.kind} with no layer")
            continue
        if layer not in layer_ids:
            out.append(f"flow {f.src} -> {f.dst} names unknown layer {layer}")
    for edge in meaning.relations:
        if edge not in edges:
            out.append(f"relations names a flow the model does not have: {edge[0]} -> {edge[1]}")
    for edge in meaning.layer_overrides:
        if edge not in edges:
            out.append(f"layer_overrides names an unknown flow: {edge[0]} -> {edge[1]}")
    for edge in meaning.verb_overrides:
        if edge not in edges:
            out.append(f"verb_overrides names an unknown flow: {edge[0]} -> {edge[1]}")
    for cid in ids:
        if cid not in meaning.plain:
            out.append(f"{cid} has no plain word")
    for cid in meaning.plain:
        if cid not in ids:
            out.append(f"plain names an unknown component: {cid}")
    for j in meaning.journeys:
        for k, step in enumerate(j.steps, start=1):
            where = f"journey {j.id} step {k}"
            for role, members in (("acts", step.acts), ("measures", step.measures)):
                for cid in members:
                    if cid not in ids:
                        out.append(f"{where} {role} names unknown component {cid}")
            if step.edge not in edges:
                out.append(
                    f"{where} traces a flow the model does not have: "
                    f"{step.edge[0]} -> {step.edge[1]}"
                )
    return out


def problems(model: Model, meaning: Meaning) -> list[str]:
    """Every placement and meaning problem, each prefixed with its kind."""
    out = [f"placement: {p}" for p in model.layout_problems()]
    out += [f"meaning: {p}" for p in meaning_problems(model, meaning)]
    return out


def build_state(component: Component, facts: Mapping[str, Any]) -> str:
    """built | partial | planned, derived from what the facts actually found.

    A component with a `tracker` is a roadmap item: until its entry exists it
    is planned, not "part built", even when the module it will land in
    already exists (a new command on an existing CLI module, for instance).
    """
    modules = list(component.implemented_by)
    if not modules:
        return "planned"
    components = facts.get("components", {})
    present = [m for m in modules if m in components]
    if not present:
        return "planned"
    entry = component.entry
    if not entry:
        # The parts exist but nothing named assembles them.
        return "partial"
    found = any(
        entry in [f["name"] for f in components[m]["functions"]]
        or entry in [c["name"] for c in components[m]["classes"]]
        for m in present
    )
    if not found:
        return "planned" if component.tracker else "partial"
    return "built" if len(present) == len(modules) else "partial"


def _inside(inner: Box, outer: Box) -> bool:
    ix, iy, iw, ih = inner
    ox, oy, ow, oh = outer
    return ix >= ox and iy >= oy and ix + iw <= ox + ow and iy + ih <= oy + oh


def _overlap(a: Box, b: Box) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
