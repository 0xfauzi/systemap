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

The map draws what exists today. Every component names the modules that are
it and one entry point those modules define (any public module-level name:
a function, a class, an object such as `app`); `systemap check` refuses a
module or an entry the facts do not have, so a card on the page is always
code in the tree. Nothing on the map is a plan; nothing is declared done.

Positions are hand-placed because this is a topology, not a chart: a box's
place carries meaning. A fixed layout also means the same system always
draws the same picture, so a change in the drawing is a change in the
system. `Model.layout_problems()` checks the placement mechanically and
`meaning_problems()` checks that the meaning names only what the model has.

Six node kinds are drawn differently on purpose. A `component` does work, a
`store` holds state, an `actor` is outside the system. In an agentic system
an `agent` runs a model and acts on its output, a `tool` is a capability an
agent invokes, and a `context` is a store whose content enters an agent's
window. Drawing a store as if it were a processing step is the most common
lie in architecture diagrams.

Layers are readings of the map. Three are derived from the model with no
authoring (Structure, System context, and Agents when the model has an
agent or a `calls_model` component), four belong to the standard flow
kinds (data, control, context, tool; the last two likewise), and the rest
are the model's own, one per custom kind. The Agents reading is agents
only; the Context and Tools readings light every context and tool flow,
whichever end runs the model.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

Box = tuple[int, int, int, int]
Edge = tuple[str, str]

KINDS = ("component", "store", "actor", "agent", "tool", "context")
AGENT_KINDS = ("agent", "tool", "context")
TONES = ("host", "client", "server", "isolated")

# Card geometry the layout check shares with the drawing.
CARD_W = 150
CARD_H: dict[str, int] = {
    "component": 56,
    "store": 52,
    "actor": 44,
    "agent": 56,
    "tool": 56,
    "context": 52,
}


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
    and `y` are the card's top-left corner in canvas units. `note` is a
    caveat the reader should see; `interface` is the one-line signature the
    reader is told. `entry` is required for every kind but `store` and
    `context`, which may be a namespace with no way in. `calls_model` marks
    a single-shot call site: a part that calls a model once and is not an
    agent by the repository's own rule; a context or tool flow may end or
    start at it, and the model sdk judgement line is answered by the flag.
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
    note: str = ""
    calls_model: bool = False

    @property
    def model_end(self) -> bool:
        """May a context flow end here, or a tool flow start here?

        An agent, or a single-shot call site marked `calls_model`.
        """
        return self.kind == "agent" or self.calls_model

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


# ---- the standard layers and kinds ---------------------------------------------
# Two flow kinds every model may use without declaring them, and two more for
# agentic systems. Each has its own layer. The derived layers have no kind:
# the renderer computes them from the topology.

STANDARD_LAYERS: tuple[Layer, ...] = (
    Layer(
        "structure",
        "Structure",
        question="What are the parts, and where does each sit?",
        sub="every component inside its region and container; no edges",
    ),
    Layer(
        "system",
        "System context",
        question="Who and what is outside, and how does it reach in?",
        sub="the actors, and every edge that crosses the boundary",
    ),
    Layer(
        "data",
        "Data flow",
        question="What moves, and where does it go?",
        sub="an artifact moves: a file, a record, a message, a response",
    ),
    Layer(
        "control",
        "Control flow",
        question="Who drives whom?",
        sub="one part invokes, schedules or drives another: a call, a command, an event",
    ),
)

AGENT_LAYERS: tuple[Layer, ...] = (
    Layer(
        "agents",
        "Agents",
        question="Which parts run a model, and what do they reach?",
        sub="every agent, and every edge that touches one",
    ),
    Layer(
        "context",
        "Context",
        question="What enters each agent's window, and from where?",
        sub="a prompt, a memory, retrieved knowledge, a log: what an agent reads",
    ),
    Layer(
        "tools",
        "Tools",
        question="What can each agent do, and through what?",
        sub="every capability an agent invokes: a shell, an API, a search, an editor",
    ),
)

# The kinds a flow may carry without being declared in `flow_kinds`, and
# the layer each belongs to.
STANDARD_KINDS = ("data", "control", "context", "tool")
LAYER_OF_STANDARD_KIND: dict[str, str] = {
    "data": "data",
    "control": "control",
    "context": "context",
    "tool": "tools",
}
# The layers the renderer derives from the topology rather than from a kind.
DERIVED_LAYERS = ("structure", "system", "agents")
# Ids a custom layer may not take: the standard ones and the page's All.
RESERVED_LAYER_IDS = frozenset(
    [layer.id for layer in STANDARD_LAYERS + AGENT_LAYERS] + list(LAYER_OF_STANDARD_KIND) + ["all"]
)
STANDARD_VERBS: dict[str, tuple[str, str]] = {
    "data": ("hands to", "receives from"),
    "control": ("drives", "is driven by"),
    "context": ("informs", "reads"),
    "tools": ("invokes", "is invoked by"),
}


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

    @property
    def agentic(self) -> bool:
        """Does the model run a model anywhere? The agent layers appear only then.

        An agent, or a component marked `calls_model`: the Context and Tools
        readings exist for the flows into and out of either.
        """
        return any(c.model_end for c in self.components)

    def _model_end(self, cid: str) -> bool:
        return any(c.id == cid and c.model_end for c in self.components)

    def kind_of(self, cid: str) -> str:
        for c in self.components:
            if c.id == cid:
                return c.kind
        return ""

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
        and a kind that is standard or declared, no ordered pair may carry
        two flows, a context or tool flow
        must have an agent or a `calls_model` component at its agent end, and every invariant must
        carry its own number and govern known components. A card outside its band would draw a
        topology the model does not claim, which is the one lie a
        hand-placed layout can tell.
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
        pairs: dict[Edge, Flow] = {}
        for f in self.flows:
            if f.src not in ids or f.dst not in ids:
                out.append(f"flow {f.src} -> {f.dst} names an unknown component")
            if f.edge in pairs:
                out.append(
                    f"flow {f.src} -> {f.dst} appears twice ('{pairs[f.edge].artifact}' and "
                    f"'{f.artifact}'); one flow per ordered pair: pick the artifact that "
                    "matters, or draw one each way when something travels back"
                )
            pairs.setdefault(f.edge, f)
            if f.kind not in STANDARD_KINDS and f.kind not in self.flow_kinds:
                out.append(
                    f"flow {f.src} -> {f.dst} has kind {f.kind}, which is neither standard "
                    f"({', '.join(STANDARD_KINDS)}) nor declared in flow_kinds"
                )
            if f.kind == "context" and not self._model_end(f.dst):
                out.append(
                    f"flow {f.src} -> {f.dst} has kind context but {f.dst} is not an agent; "
                    f"a context flow ends at the agent whose window it enters: set {f.dst}'s "
                    "kind to agent, mark it calls_model=True if it makes a single-shot call, "
                    "or give the flow the kind data"
                )
            if f.kind == "tool" and not self._model_end(f.src):
                out.append(
                    f"flow {f.src} -> {f.dst} has kind tool but {f.src} is not an agent; "
                    f"a tool flow starts at the agent that invokes it: set {f.src}'s kind "
                    "to agent, mark it calls_model=True if it makes a single-shot call, or "
                    "give the flow the kind control"
                )
        numbered: dict[int, Invariant] = {}
        for inv in self.invariants:
            if inv.n in numbered:
                out.append(
                    f"invariant {inv.n} is numbered twice: '{numbered[inv.n].text}' and "
                    f"'{inv.text}'; give each rule its own number"
                )
            else:
                numbered[inv.n] = inv
            for cid in inv.governs:
                if cid not in ids:
                    out.append(f"invariant {inv.n} governs unknown component {cid}")
        return out


@dataclass(frozen=True)
class Meaning:
    """The hand-authored meaning of one system.

    `plain` is the plain word per component id. `layers` are the model's
    own layers, shown after the standard ones in this order; a model with
    no custom kind leaves it empty. `layer_of_kind` maps a custom flow kind
    to a layer (the standard kinds have theirs already) and
    `layer_overrides` moves single edges to another layer. `relations` is
    one sentence per edge, read from the source side. `verbs` gives (verb
    when the clicked component is the source, verb when it is the target)
    per layer, over the standard verbs; `verb_overrides` does the same per
    edge.
    """

    plain: Mapping[str, str]
    layers: tuple[Layer, ...] = ()
    layer_of_kind: Mapping[str, str] = field(default_factory=dict)
    relations: Mapping[Edge, str] = field(default_factory=dict)
    journeys: tuple[Journey, ...] = ()
    layer_overrides: Mapping[Edge, str] = field(default_factory=dict)
    verbs: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    verb_overrides: Mapping[Edge, tuple[str, str]] = field(default_factory=dict)

    def layer_for(self, edge: Edge, kind: str) -> str:
        """The one layer a flow belongs to.

        The override if any, else the layer the model gives the kind, else
        the standard kind's own layer. An undeclared custom kind is a
        KeyError, which the meaning check reports.
        """
        layer = (
            self.layer_overrides.get(edge)
            or self.layer_of_kind.get(kind)
            or LAYER_OF_STANDARD_KIND.get(kind)
        )
        if layer is None:
            raise KeyError(kind)
        return layer

    def verb_for(self, edge: Edge, layer: str, from_clicked: bool) -> str:
        """The verb to print on a spoke, read from the clicked component."""
        pair = (
            self.verb_overrides.get(edge)
            or self.verbs.get(layer)
            or STANDARD_VERBS.get(layer, ("to", "from"))
        )
        return pair[0] if from_clicked else pair[1]


def all_layers(model: Model, meaning: Meaning) -> tuple[Layer, ...]:
    """Every layer the page shows, in the order it shows them.

    Structure, System context, Data flow, Control flow; then Agents,
    Context and Tools when the model has an agent; then the model's own.
    The first is the one the page opens on.
    """
    standard = STANDARD_LAYERS + (AGENT_LAYERS if model.agentic else ())
    return standard + tuple(meaning.layers)


def flow_layers(model: Model, meaning: Meaning) -> tuple[Layer, ...]:
    """The layers a flow belongs to by its kind: every layer but the derived ones."""
    return tuple(layer for layer in all_layers(model, meaning) if layer.id not in DERIVED_LAYERS)


def edge_in_layer(model: Model, layer_id: str, edge_layer: str, src: str, dst: str) -> bool:
    """The one per-layer filter: does a flow belong to the reading `layer_id`?

    A kind layer holds the flows of its kind; `edge_layer` is the layer
    `Meaning.layer_for` gave the flow. A derived reading is computed from
    the endpoints instead: Structure shows no edge, System context the
    edges that cross the boundary (an actor at either end), Agents the
    edges that touch an agent. The page reads this function's result out
    of the detail JSON rather than deciding again in the browser, so a
    figure of one layer and the page's layer switch cannot disagree.
    """
    if layer_id == "all":
        return True
    if layer_id == "structure":
        return False
    if layer_id == "system":
        return model.kind_of(src) == "actor" or model.kind_of(dst) == "actor"
    if layer_id == "agents":
        return model.kind_of(src) == "agent" or model.kind_of(dst) == "agent"
    return edge_layer == layer_id


# The kind each derived or agent reading is about: its subject cards carry
# the reading's colour as their stroke and are never dimmed by it.
SUBJECT_KIND: dict[str, str] = {
    "system": "actor",
    "agents": "agent",
    "context": "context",
    "tools": "tool",
}


def subject_of_layer(model: Model, layer_id: str, cid: str) -> bool:
    """A card the reading is about even when no edge it shows touches it.

    Structure is about every card. System context is about the actors,
    Agents about the agents, Context about the context cards and Tools
    about the tools, whether or not an edge of the reading reaches them.
    """
    if layer_id == "structure":
        return True
    kind = SUBJECT_KIND.get(layer_id)
    return kind is not None and model.kind_of(cid) == kind


def reading(model: Model, meaning: Meaning, layer_id: str) -> tuple[list[int], list[str]]:
    """(the flows the reading shows, by index; the cards it is about, by id)."""
    edges = [
        i
        for i, f in enumerate(model.flows)
        if edge_in_layer(model, layer_id, meaning.layer_for(f.edge, f.kind), f.src, f.dst)
    ]
    subjects = [c.id for c in model.components if subject_of_layer(model, layer_id, c.id)]
    return edges, subjects


def meaning_problems(model: Model, meaning: Meaning) -> list[str]:
    """Ways the meaning names something the model does not have, or misses one."""
    out: list[str] = []
    ids = model.ids
    edges = {f.edge for f in model.flows}
    # A standard layer is known here whether or not the model has an agent:
    # a context flow with no agent is the placement rule's finding.
    layer_ids = {layer.id for layer in STANDARD_LAYERS + AGENT_LAYERS + meaning.layers}
    for own in meaning.layers:
        if own.id in RESERVED_LAYER_IDS:
            out.append(f"layer {own.id} is a standard layer; it is derived, not declared")
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


def is_symbol(pattern: str) -> bool:
    """Is one `implemented_by` entry a symbol claim, `pkg.mod:name`?"""
    return ":" in pattern


def symbol_claims(component: Component) -> list[tuple[str, str]]:
    """The (module, name) pairs a component claims by symbol."""
    out: list[tuple[str, str]] = []
    for pattern in component.implemented_by:
        if is_symbol(pattern):
            module, _, name = pattern.partition(":")
            out.append((module, name))
    return out


def module_matches(pattern: str, module: str) -> bool:
    """Does one `implemented_by` entry name this module?

    An entry is an exact module name, or a package name followed by `.*`,
    which names the package module itself and everything beneath it. A
    symbol claim (`pkg.mod:name`) names one public name inside a module
    and never the module: the module's owner is whoever claims the
    module, so a symbol claim counts for no module and conflicts with no
    claim. This is the one place the convention is defined; the build
    state, the coverage rule, the drift check and the change map all read
    it from here so they cannot disagree about what a component claims.
    """
    if is_symbol(pattern):
        return False
    if pattern.endswith(".*"):
        head = pattern[:-2]
        return module == head or module.startswith(head + ".")
    return module == pattern


def claimed(component: Component, modules: Iterable[str]) -> list[str]:
    """The modules, among `modules`, that the component's `implemented_by` names."""
    patterns = component.implemented_by
    return [m for m in modules if any(module_matches(p, m) for p in patterns)]


BUILT = "built"


def public_names(record: Mapping[str, Any]) -> set[str]:
    """Every public module-level name one facts record declares.

    The `names` list carries them all with their kinds (a function, a
    class, an error, an UPPER_CASE constant, any other object such as
    `app` or `root_agent`); a facts file from before it was recorded has
    only functions and classes to offer.
    """
    names = record.get("names")
    if names is not None:
        return {n["name"] for n in names}
    return {f["name"] for f in record.get("functions", [])} | {
        c["name"] for c in record.get("classes", [])
    }


def defines_entry(component: Component, facts: Mapping[str, Any]) -> bool:
    """Does one of the component's claimed modules define its entry?

    The entry rule of `systemap check` reads this; it is the one place the
    lookup is written, so a rule and a drawing cannot disagree about
    whether a name exists. Any public module-level name counts, in a
    claimed module or claimed by symbol (then the symbol rule checks that
    the module defines it).
    """
    components = facts.get("components", {})
    if any(component.entry in public_names(components[m]) for m in claimed(component, components)):
        return True
    return any(name == component.entry for _module, name in symbol_claims(component))


def entry_module(component: Component, facts: Mapping[str, Any]) -> str:
    """The module that defines the component's entry, for the panel's `entry: name (module)`.

    The first claimed module (in the facts' order) whose public names hold
    the entry, else the module of the symbol claim that names it, else
    empty: an entry the check refused, or a store or context with none.
    """
    components = facts.get("components", {})
    for m in claimed(component, components):
        if component.entry and component.entry in public_names(components[m]):
            return m
    for module, name in symbol_claims(component):
        if name == component.entry:
            return module
    return ""


def build_state(component: Component, facts: Mapping[str, Any]) -> str:
    """The one build state a drawn component has: `built`.

    There is nothing to derive. A component whose modules or entry are not
    in the facts never reaches the drawing, because the entry rule of
    `systemap check` refuses it; what is drawn exists. The function stays
    so the word is defined in one place and read from it.
    """
    del component, facts
    return BUILT


def _inside(inner: Box, outer: Box) -> bool:
    ix, iy, iw, ih = inner
    ox, oy, ow, oh = outer
    return ix >= ox and iy >= oy and ix + iw <= ox + ow and iy + ih <= oy + oh


def _overlap(a: Box, b: Box) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
