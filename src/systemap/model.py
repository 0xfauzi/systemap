"""The schema for a system map and its consistency checks.

Model contains containers, regions, components, flows, and invariants.
Meaning contains component names, layer questions, flow sentences, and sequences.
The extractor supplies source facts separately.

Each source component identifies its modules and a public entry point where applicable.
The checks compare those references with the source facts.
An import connection alone does not show a flow sentence.
A maintainer must examine source support for each authored claim.

The model records fixed card positions. The placement command keeps existing positions.
With --all, the command calculates positions again, except for pinned cards.
The layout checks compare card boundaries, regions, flow endpoints, and kinds.
The meaning checks compare references with the model.

The six component kinds are component, store, actor, agent, tool, and context.
An agent calls a model and acts on its output.
A component with calls_model makes a model call without the agent classification.
A context flow ends at either kind of model caller. A tool flow starts there.

The standard layers show structure, system context, data flow, and control flow.
For a model caller, the page also supplies Agents, Context, and Tools.
Agents shows agent components. Context and Tools show the applicable flow kinds.
Custom flow kinds use the layers in Meaning."""

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
    """A system boundary, such as a process, host, or source directory."""

    id: str
    label: str
    box: Box
    sub: str = ""
    tone: str = "host"


@dataclass(frozen=True)
class Region:
    """A component group with layout bounds inside an optional container."""

    id: str
    label: str
    box: Box
    container: str | None = None


@dataclass(frozen=True)
class Component:
    """A component card with source references and an optional fixed position.

    region identifies the group for a component or store.
    container identifies the group for an actor.
    x and y give the top-left card position in map coordinates.
    The placement command supplies missing positions. With --all, it keeps only pinned positions.

    note gives additional information for the reader.
    interface gives the component input and output.
    All kinds except store and context must have a public entry point.
    calls_model identifies a model call without the agent classification.
    A context flow can end there. A tool flow can start there.

    map gives a nested model path relative to this model file.
    The nested model must export MODEL and MEANING.
    Its source components must cover exactly the parent component modules.
    Its actors must refer to components in the parent model.

    source_review records an examination of source facts and component claims.
    The delta command opens the source review again when its digest changes."""

    id: str
    does: str
    interface: str = ""
    implemented_by: tuple[str, ...] = ()
    entry: str = ""
    kind: str = "component"
    region: str | None = None
    container: str | None = None
    x: int | None = None
    y: int | None = None
    note: str = ""
    calls_model: bool = False
    map: str | None = None
    pinned: bool = False
    source_review: str = ""

    @property
    def opens(self) -> bool:
        """True when the component has a nested map path."""
        return bool(self.map)

    @property
    def positioned(self) -> bool:
        """True when the component has both position coordinates."""
        return self.x is not None and self.y is not None

    @property
    def model_end(self) -> bool:
        """True for an agent or a component with calls_model."""
        return self.kind == "agent" or self.calls_model

    @property
    def home(self) -> str:
        return self.region or self.container or ""

    @property
    def box(self) -> Box:
        if self.x is None or self.y is None:
            raise ValueError(f"{self.id} has no position. Run: systemap place")
        return self.x, self.y, CARD_W, CARD_H[self.kind]


@dataclass(frozen=True)
class Flow:
    """A directed flow with one artifact, two endpoints, and one kind.

    source_refs identifies the source records for the flow claim.
    Each record contains a module, an optional symbol, and a source digest.
    review_digest connects that source review to the flow fields and relation sentence."""

    src: str
    dst: str
    artifact: str
    kind: str
    source_refs: tuple[str, ...] = ()
    review_digest: str = ""

    @property
    def edge(self) -> Edge:
        return self.src, self.dst


@dataclass(frozen=True)
class Invariant:
    """A numbered rule with the identifiers of the applicable components."""

    n: int
    text: str
    governs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Step:
    """A sequence step with acting components, measured components, a flow, and a sentence."""

    acts: tuple[str, ...]
    measures: tuple[str, ...]
    edge: Edge
    say: str


@dataclass(frozen=True)
class Journey:
    """An ordered sequence of steps through the system.

    starts identifies the initial entry point or component.
    covers contains exact entry point identities examined for this sequence.
    Each identity contains a kind, module, target, and local name.
    A new entry point on the same component is a separate source review."""

    id: str
    label: str
    steps: tuple[Step, ...]
    starts: str = ""
    # written by `systemap journeys` and not yet read by the maintainer
    drafted: bool = False
    # Stable identities of the exact ways in reviewed for this walk.
    covers: tuple[str, ...] = ()


@dataclass(frozen=True)
class Layer:
    """A map view with a name, question, and additional description."""

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
        question="Which components are in each region and container?",
        sub="components inside regions and containers, without flows",
    ),
    Layer(
        "system",
        "System context",
        question="Which actors connect to the system?",
        sub="actors and flows across the system boundary",
    ),
    Layer(
        "data",
        "Data flow",
        question="Which artifacts move between components?",
        sub="artifacts such as files, records, messages, and responses",
    ),
    Layer(
        "control",
        "Control flow",
        question="Which components cause other components to act?",
        sub="calls, commands, and events that cause component actions",
    ),
)

AGENT_LAYERS: tuple[Layer, ...] = (
    Layer(
        "agents",
        "Agents",
        question="Which agents call a model, and which components connect to them?",
        sub="agents and their connected flows",
    ),
    Layer(
        "context",
        "Context",
        question="Which inputs does each model caller receive?",
        sub="model inputs such as prompts, memory, search results, and logs",
    ),
    Layer(
        "tools",
        "Tools",
        question="Which tools does each model caller use?",
        sub="tool calls such as shell commands, API calls, searches, and file changes",
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
    "data": ("sends to", "receives from"),
    "control": ("starts", "receives control from"),
    "context": ("supplies input to", "receives input from"),
    "tools": ("calls", "receives calls from"),
}


@dataclass(frozen=True)
class Model:
    """The authored structure of one system."""

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
    def opening(self) -> tuple[Component, ...]:
        """Components with nested maps, in model order."""
        return tuple(c for c in self.components if c.opens)

    @property
    def agentic(self) -> bool:
        """True when an agent or a component with calls_model is in the model."""
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
        """The applicable invariant numbers, in numerical order."""
        return [inv.n for inv in sorted(self.invariants, key=lambda i: i.n) if cid in inv.governs]

    def layout_problems(self) -> list[str]:
        """Find inconsistent layout fields and model references.

        Each card must have a position inside its region or container.
        Cards must not overlap. Each region must fit inside its container.
        Flow endpoints and kinds must exist. Each ordered endpoint pair can have only one flow.
        Context and tool flows must connect to an agent or a component with calls_model.
        Invariant numbers must have different values, and their component references must exist.
        An actor must not open a nested map."""
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
            if c.map is not None and not c.map.strip():
                out.append(
                    f"{c.id} opens a map with an empty path. Give the nested model module path"
                )
            elif c.opens and c.kind == "actor":
                out.append(
                    f"{c.id} is an actor and opens a map ({c.map}). An actor has no source modules"
                )
        for box in self.containers:
            if box.tone not in TONES:
                out.append(f"container {box.id} has unknown tone {box.tone}")
        for region in self.regions:
            if region.container is None:
                continue
            outer = containers.get(region.container)
            if outer is None:
                out.append(f"region {region.id} has unknown container {region.container}")
            elif not _inside(region.box, outer):
                out.append(f"region {region.id} is not inside {region.container}")
        for c in self.components:
            if c.kind not in CARD_H:
                continue
            outer = regions.get(c.home) or containers.get(c.home)
            if not c.home:
                out.append(f"{c.id} has no region or container")
            elif outer is None:
                out.append(f"{c.id} has unknown region or container {c.home}")
            elif not c.positioned:
                out.append(f"{c.id} has no position (x, y). Run: systemap place")
            elif not _inside(c.box, outer):
                out.append(f"{c.id} is drawn outside {c.home}")
        drawable = [c for c in self.components if c.kind in CARD_H and c.positioned]
        for i, a in enumerate(drawable):
            for b in drawable[i + 1 :]:
                if _overlap(a.box, b.box):
                    out.append(f"{a.id} overlaps {b.id}")
        pairs: dict[Edge, Flow] = {}
        for f in self.flows:
            if f.src not in ids or f.dst not in ids:
                out.append(f"flow {f.src} -> {f.dst} has an unknown component")
            if f.edge in pairs:
                out.append(
                    f"flow {f.src} -> {f.dst} appears twice ('{pairs[f.edge].artifact}' and "
                    f"'{f.artifact}'). Each ordered pair can have only one flow. "
                    "Select one artifact, or add a reverse flow for a return artifact"
                )
            pairs.setdefault(f.edge, f)
            if f.kind not in STANDARD_KINDS and f.kind not in self.flow_kinds:
                out.append(
                    f"flow {f.src} -> {f.dst} has kind {f.kind}, which is neither standard "
                    f"({', '.join(STANDARD_KINDS)}) nor declared in flow_kinds"
                )
            if f.kind == "context" and not self._model_end(f.dst):
                out.append(
                    f"flow {f.src} -> {f.dst} has kind context but {f.dst} is not a model caller. "
                    f"A context flow ends at its model caller. Set {f.dst}'s "
                    "kind to agent, or set calls_model=True for one model call. "
                    "As an alternative, use kind data for the flow"
                )
            if f.kind == "tool" and not self._model_end(f.src):
                out.append(
                    f"flow {f.src} -> {f.dst} has kind tool but {f.src} is not a model caller. "
                    f"A tool flow starts at its model caller. Set {f.src}'s kind "
                    "to agent, or set calls_model=True for one model call. "
                    "As an alternative, use kind control for the flow"
                )
        numbered: dict[int, Invariant] = {}
        for inv in self.invariants:
            if inv.n in numbered:
                out.append(
                    f"invariant {inv.n} is numbered twice: '{numbered[inv.n].text}' and "
                    f"'{inv.text}'. Give each rule its own number"
                )
            else:
                numbered[inv.n] = inv
            for cid in inv.governs:
                if cid not in ids:
                    out.append(f"invariant {inv.n} has unknown component {cid}")
        return out


@dataclass(frozen=True)
class Meaning:
    """The authored names and explanations for a system model.

    plain gives a short description for each component identifier.
    layers gives custom layers after the standard layers, in the specified order.
    layer_of_kind connects each custom flow kind to its layer.
    layer_overrides selects a different layer for an individual flow.
    relations gives a sentence for each flow, from its source endpoint.

    verbs gives the source-side and target-side labels for each layer.
    verb_overrides supplies these labels for an individual flow.
    journeys contains the ordered sequences."""

    plain: Mapping[str, str]
    layers: tuple[Layer, ...] = ()
    layer_of_kind: Mapping[str, str] = field(default_factory=dict)
    relations: Mapping[Edge, str] = field(default_factory=dict)
    journeys: tuple[Journey, ...] = ()
    layer_overrides: Mapping[Edge, str] = field(default_factory=dict)
    verbs: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    verb_overrides: Mapping[Edge, tuple[str, str]] = field(default_factory=dict)

    def layer_for(self, edge: Edge, kind: str) -> str:
        """Select the flow override, custom kind layer, or standard kind layer.
        Missing kinds cause KeyError.
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
        """Get the connection label for the selected component and flow direction."""
        pair = (
            self.verb_overrides.get(edge)
            or self.verbs.get(layer)
            or STANDARD_VERBS.get(layer, ("to", "from"))
        )
        return pair[0] if from_clicked else pair[1]


def all_layers(model: Model, meaning: Meaning) -> tuple[Layer, ...]:
    """Get standard layers, applicable agent layers, and custom layers in page order."""
    standard = STANDARD_LAYERS + (AGENT_LAYERS if model.agentic else ())
    return standard + tuple(meaning.layers)


def flow_layers(model: Model, meaning: Meaning) -> tuple[Layer, ...]:
    """Get layers for flow kinds. Do not include derived layers."""
    return tuple(layer for layer in all_layers(model, meaning) if layer.id not in DERIVED_LAYERS)


def edge_in_layer(model: Model, layer_id: str, edge_layer: str, src: str, dst: str) -> bool:
    """True when a layer includes the flow.

    Structure includes no flows. System context includes flows with an actor endpoint.
    Agents includes flows with an agent endpoint. Other layers use the recorded kind or override.
    The page and figures use this same selection procedure."""
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
    """True when the component kind is a subject of the layer, with or without connected flows."""
    if layer_id == "structure":
        return True
    kind = SUBJECT_KIND.get(layer_id)
    return kind is not None and model.kind_of(cid) == kind


def reading(model: Model, meaning: Meaning, layer_id: str) -> tuple[list[int], list[str]]:
    """Get the flow indexes and component identifiers for a layer."""
    edges = [
        i
        for i, f in enumerate(model.flows)
        if edge_in_layer(model, layer_id, meaning.layer_for(f.edge, f.kind), f.src, f.dst)
    ]
    subjects = [c.id for c in model.components if subject_of_layer(model, layer_id, c.id)]
    return edges, subjects


def meaning_problems(model: Model, meaning: Meaning) -> list[str]:
    """Find missing explanations and references that do not exist in the model."""
    out: list[str] = []
    ids = model.ids
    edges = {f.edge for f in model.flows}
    # A standard layer is known here whether or not the model has an agent:
    # a context flow with no agent is the placement rule's finding.
    layer_ids = {layer.id for layer in STANDARD_LAYERS + AGENT_LAYERS + meaning.layers}
    for own in meaning.layers:
        if own.id in RESERVED_LAYER_IDS:
            out.append(f"layer {own.id} is a standard layer. Do not declare it as a custom layer")
    for f in model.flows:
        if f.edge not in meaning.relations:
            out.append(f"flow {f.src} -> {f.dst} has no sentence in relations")
        try:
            layer = meaning.layer_for(f.edge, f.kind)
        except KeyError:
            out.append(f"flow {f.src} -> {f.dst} has kind {f.kind} with no layer")
            continue
        if layer not in layer_ids:
            out.append(f"flow {f.src} -> {f.dst} has unknown layer {layer}")
    for edge in meaning.relations:
        if edge not in edges:
            out.append(f"relations has an unknown flow: {edge[0]} -> {edge[1]}")
    for edge in meaning.layer_overrides:
        if edge not in edges:
            out.append(f"layer_overrides has an unknown flow: {edge[0]} -> {edge[1]}")
    for edge in meaning.verb_overrides:
        if edge not in edges:
            out.append(f"verb_overrides has an unknown flow: {edge[0]} -> {edge[1]}")
    for cid in ids:
        if cid not in meaning.plain:
            out.append(f"{cid} has no plain word")
    for cid in meaning.plain:
        if cid not in ids:
            out.append(f"plain has an unknown component: {cid}")
    for j in meaning.journeys:
        out.extend(_journey_problems(j, ids, edges))
    return out


def _journey_problems(journey: Journey, ids: set[str], edges: set[Edge]) -> list[str]:
    """Find unknown sequence references, in step order."""
    out: list[str] = []
    if not journey.steps:
        out.append(f"journey {journey.id} has no steps. Add the examined sequence or remove it")
    for k, step in enumerate(journey.steps, start=1):
        where = f"journey {journey.id} step {k}"
        for role, members in (("acts", step.acts), ("measures", step.measures)):
            for cid in members:
                if cid not in ids:
                    out.append(f"{where} {role} has unknown component {cid}")
        if step.edge not in edges:
            out.append(f"{where} has an unknown flow: {step.edge[0]} -> {step.edge[1]}")
    return out


def problems(model: Model, meaning: Meaning) -> list[str]:
    """Get layout and meaning findings with their kind prefixes."""
    out = [f"placement: {p}" for p in model.layout_problems()]
    out += [f"meaning: {p}" for p in meaning_problems(model, meaning)]
    return out


def is_symbol(pattern: str) -> bool:
    """True when an implemented_by value is a symbol claim in pkg.mod:name form."""
    return ":" in pattern


def symbol_claims(component: Component) -> list[tuple[str, str]]:
    """Get the module and public name pairs for component symbol claims."""
    out: list[tuple[str, str]] = []
    for pattern in component.implemented_by:
        if is_symbol(pattern):
            module, _, name = pattern.partition(":")
            out.append((module, name))
    return out


def module_matches(pattern: str, module: str) -> bool:
    """True when an implemented_by pattern covers a module.

    An exact module name covers that module only.
    A package name with .* covers the package and its descendant modules.
    A symbol claim covers a public name, not the containing module.
    Coverage, source change, and map checks use this same procedure."""
    if is_symbol(pattern):
        return False
    if pattern.endswith(".*"):
        head = pattern[:-2]
        return module == head or module.startswith(head + ".")
    return module == pattern


def claimed(component: Component, modules: Iterable[str]) -> list[str]:
    """Select the modules that the component implemented_by patterns cover."""
    patterns = component.implemented_by
    return [m for m in modules if any(module_matches(p, m) for p in patterns)]


BUILT = "built"


def public_names(record: Mapping[str, Any]) -> set[str]:
    """Get public names from a module source record.

    The names field includes functions, classes, constants, and other public objects.
    Older source records supply only the functions and classes fields."""
    names = record.get("names")
    if names is not None:
        return {n["name"] for n in names}
    return {f["name"] for f in record.get("functions", [])} | {
        c["name"] for c in record.get("classes", [])
    }


def defines_entry(component: Component, facts: Mapping[str, Any]) -> bool:
    """True when a component module or symbol claim includes its entry point."""
    components = facts.get("components", {})
    if any(component.entry in public_names(components[m]) for m in claimed(component, components)):
        return True
    return any(name == component.entry for _module, name in symbol_claims(component))


def entry_module(component: Component, facts: Mapping[str, Any]) -> str:
    """Get the first component module with its entry point.

    Otherwise, get the module of its symbol claim.
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
    """Get the fixed build state identifier built.

    The check stops rendering when source references do not exist.
    This identifier does not show the component purpose or flow claims."""
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
