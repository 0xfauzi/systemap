# A worked example of every part

A small pipeline: a person types input, a reader turns it into a request,
a parser splits it, a writer joins the parts and records the result in a
ledger. The modules are `pkg.reader`, `pkg.parser`, `pkg.writer` and
`pkg.ledger`. This model passes `systemap check` against those modules as
written; the test suite runs it.

```python
"""The system map of pkg: what the parts are and what they are to each other."""

from __future__ import annotations

from systemap import (
    Component,
    Container,
    Flow,
    Invariant,
    Journey,
    Layer,
    Meaning,
    Model,
    Region,
    Step,
)

# The grid: card columns 190 apart, rows 160 apart here because the two
# regions are stacked. Cards on the grid leave straight corridors for edges.
COL = {"c1": 270, "c2": 460, "c3": 650}
ROW = {"r1": 90, "r2": 250}

CONTAINERS = (
    # A hard boundary. The person is outside the system; the code is one process.
    Container("outside", "OUTSIDE", (16, 16, 186, 368), tone="host"),
    Container("system", "SYSTEM", (222, 16, 662, 368), sub="one process", tone="server"),
)

REGIONS = (
    # Soft bands inside the system: the phase that works, the phase that keeps.
    Region("work", "WORK", (240, 50, 626, 130), container="system"),
    Region("keep", "KEEP", (240, 210, 626, 130), container="system"),
)

COMPONENTS = (
    # An actor: outside the code, placed by container, claims no modules.
    Component("User", "Types the input.", kind="actor", container="outside", x=34, y=96),
    # A component: its entry `read` is a real function in pkg.reader.
    Component(
        id="Reader",
        does="Reads the input and turns it into a request.",
        interface="read(source) -> Request",
        implemented_by=("pkg.reader",),
        entry="read",
        region="work",
        x=COL["c1"],
        y=ROW["r1"],
    ),
    Component(
        id="Parser",
        does="Splits a request into the parts the writer needs.",
        interface="parse(request) -> list[str]",
        implemented_by=("pkg.parser",),
        entry="parse",
        region="work",
        x=COL["c2"],
        y=ROW["r1"],
    ),
    # A store: it holds state. Its entry is a class.
    Component(
        id="Ledger",
        does="Keeps every record ever written.",
        interface="Ledger.record / Ledger.history",
        implemented_by=("pkg.ledger",),
        entry="Ledger",
        kind="store",
        region="keep",
        x=COL["c2"],
        y=ROW["r2"],
    ),
    Component(
        id="Writer",
        does="Joins the parts and records the result.",
        interface="write(parts, ledger) -> str",
        implemented_by=("pkg.writer",),
        entry="write",
        region="keep",
        x=COL["c3"],
        y=ROW["r2"],
    ),
)

# (from, to, the artifact carried, the kind). data and control are
# standard; record is this model's own kind, declared below.
FLOWS = (
    Flow("User", "Reader", "input", "data"),
    Flow("Reader", "Parser", "parse", "control"),
    Flow("Parser", "Writer", "parts", "data"),
    Flow("Writer", "Ledger", "record", "record"),
    Flow("Ledger", "Parser", "history", "record"),
)

FLOW_KINDS = ("record",)

INVARIANTS = (
    # Copied from the repository's own words, with the source named.
    Invariant(1, "The writer never reads the input itself (README, Design).", governs=("Writer",)),
    Invariant(2, "Every record is written once (docs/ledger.md).", governs=("Writer", "Ledger")),
)

MODEL = Model(
    canvas=(900, 400),
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=FLOWS,
    flow_kinds=FLOW_KINDS,
    invariants=INVARIANTS,
)

# ---- meaning: the plain words, the layers, one sentence per flow ---------

PLAIN = {
    "User": "the person typing",
    "Reader": "the part that reads",
    "Parser": "the part that splits",
    "Ledger": "the record book",
    "Writer": "the part that writes",
}

# The model's own readings, after Structure, System context, Data flow and
# Control flow, which the page derives. Each is the question it answers.
LAYERS = (
    Layer("record", "Record", question="What is written down?"),
    Layer("memory", "Memory", question="What does the system remember?"),
)

# Every custom kind belongs to one layer; one edge is moved to another.
LAYER_OF_KIND = {"record": "record"}
LAYER_OVERRIDES = {("Ledger", "Parser"): "memory"}

# One sentence per edge, read from the source side.
RELATIONS = {
    ("User", "Reader"): "The user types one input at a time.",
    ("Reader", "Parser"): "The reader calls the parser on each request.",
    ("Parser", "Writer"): "The parser gives the writer the parts in order.",
    ("Writer", "Ledger"): "The writer records every result it produces.",
    ("Ledger", "Parser"): "The ledger tells the parser what was written before.",
}

# The verb on a spoke of the wheel: (when the clicked card is the source,
# when it is the target), per layer, and per edge where one edge differs.
# The standard layers have verbs already; data is given better ones here.
VERBS = {
    "data": ("hands to", "receives from"),
    "record": ("records in", "is written by"),
    "memory": ("reminds", "remembers through"),
}
VERB_OVERRIDES = {("User", "Reader"): ("types into", "is typed by")}

JOURNEYS = (
    Journey(
        id="input-to-record",
        label="An input becomes a record",
        steps=(
            Step(("User",), (), ("User", "Reader"), "The user types an input."),
            Step(("Reader",), (), ("Reader", "Parser"), "The reader calls the parser."),
            Step(("Parser",), ("Ledger",), ("Parser", "Writer"), "The parser splits it."),
            Step(("Writer",), ("Ledger",), ("Writer", "Ledger"), "The writer records it."),
        ),
    ),
)

MEANING = Meaning(
    plain=PLAIN,
    layers=LAYERS,
    layer_of_kind=LAYER_OF_KIND,
    layer_overrides=LAYER_OVERRIDES,
    relations=RELATIONS,
    verbs=VERBS,
    verb_overrides=VERB_OVERRIDES,
    journeys=JOURNEYS,
)
```

The configuration beside it, `systemap.toml`, needs nothing for this
model to check; one key is worth knowing. A package root module that only
marks the directory is ignored with a reason:

```toml
[coverage]
ignore = [
    { module = "pkg", reason = "the package root only marks the directory as a package" },
]
```
