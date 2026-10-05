# A complete model example

This illustrative model shows an input sequence with a reader, parser, writer, and record store.
The modules are `pkg.reader`, `pkg.parser`, `pkg.writer`, and `pkg.ledger`.
The tests do the model checks against a source fixture with these modules.
The example gives the positions so that the example is a complete file.
For an initial model, omit `x` and `y`. Then run `systemap place`.

```python
"""The system map of pkg and its component connections."""

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

# Columns are 190 units apart. Rows are 160 units apart.
# The spaces between cards give routes for the flows.
COL = {"c1": 270, "c2": 460, "c3": 650}
ROW = {"r1": 90, "r2": 250}

CONTAINERS = (
    # The user is outside the system. The source code runs in one process.
    Container("outside", "OUTSIDE", (16, 16, 186, 368), tone="host"),
    Container("system", "SYSTEM", (222, 16, 662, 368), sub="one process", tone="server"),
)

REGIONS = (
    # One region contains processing components. The other contains the record store.
    Region("work", "WORK", (240, 50, 626, 130), container="system"),
    Region("keep", "KEEP", (240, 210, 626, 130), container="system"),
)

COMPONENTS = (
    # This actor has a container position and no source modules.
    Component("User", "Types the input.", kind="actor", container="outside", x=34, y=96),
    # The entry point read is a function in pkg.reader.
    Component(
        id="Reader",
        does="Reads the input and makes a request.",
        interface="read(source) -> Request",
        implemented_by=("pkg.reader",),
        entry="read",
        region="work",
        x=COL["c1"],
        y=ROW["r1"],
    ),
    Component(
        id="Parser",
        does="Divides a request into the parts for the writer.",
        interface="parse(request) -> list[str]",
        implemented_by=("pkg.parser",),
        entry="parse",
        region="work",
        x=COL["c2"],
        y=ROW["r1"],
    ),
    # The store keeps records. Its entry point is a class.
    Component(
        id="Ledger",
        does="Keeps all records from the writer.",
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
        does="Puts the parts together and records the result.",
        interface="write(parts, ledger) -> str",
        implemented_by=("pkg.writer",),
        entry="write",
        region="keep",
        x=COL["c3"],
        y=ROW["r2"],
    ),
)

# Each flow gives its source, target, artifact, and kind.
# data and control are standard kinds. record is a custom kind.
FLOWS = (
    Flow("User", "Reader", "input", "data"),
    Flow("Reader", "Parser", "parse", "control"),
    Flow("Parser", "Writer", "parts", "data"),
    Flow("Writer", "Ledger", "record", "record"),
    Flow("Ledger", "Parser", "history", "record"),
)

FLOW_KINDS = ("record",)

INVARIANTS = (
    # Each invariant identifies its source document.
    Invariant(1, "The writer never reads the input itself (README, Design).", governs=("Writer",)),
    Invariant(
        2, "The writer records each result once (docs/ledger.md).", governs=("Writer", "Ledger")
    ),
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

# Names, layers, and flow sentences.

PLAIN = {
    "User": "the input user",
    "Reader": "the part that reads",
    "Parser": "the request parser",
    "Ledger": "the record store",
    "Writer": "the part that writes",
}

# Custom layers follow the standard layers. Each layer gives its question.
LAYERS = (
    Layer("record", "Record", question="Which results does the writer record?"),
    Layer("memory", "Memory", question="Which earlier records does the parser use?"),
)

# Each custom kind uses one layer. An override selects a different layer for one flow.
LAYER_OF_KIND = {"record": "record"}
LAYER_OVERRIDES = {("Ledger", "Parser"): "memory"}

# Each flow has a sentence from its source endpoint.
RELATIONS = {
    ("User", "Reader"): "The user types one input at a time.",
    ("Reader", "Parser"): "The reader calls the parser on each request.",
    ("Parser", "Writer"): "The parser gives the writer the parts in order.",
    ("Writer", "Ledger"): "The writer records each result.",
    ("Ledger", "Parser"): "The ledger supplies earlier records to the parser.",
}

# Each label pair gives the source-side and target-side text.
# Layer labels apply unless a flow has an override.
VERBS = {
    "data": ("sends to", "receives from"),
    "record": ("records in", "receives records from"),
    "memory": ("supplies records to", "receives records from"),
}
VERB_OVERRIDES = {("User", "Reader"): ("types into", "receives input from")}

JOURNEYS = (
    Journey(
        id="input-to-record",
        label="An input becomes a record",
        steps=(
            Step(("User",), (), ("User", "Reader"), "The user types an input."),
            Step(("Reader",), (), ("Reader", "Parser"), "The reader calls the parser."),
            Step(
                ("Parser",),
                ("Ledger",),
                ("Parser", "Writer"),
                "The parser divides the request into parts.",
            ),
            Step(("Writer",), ("Ledger",), ("Writer", "Ledger"), "The writer records the result."),
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

An empty `pkg/__init__.py` is a package marker in this example.
The extractor records that module. Coverage includes the marker without a component claim.
If a module with source code is outside the map, record a coverage ignore with an explanation.
The following configuration is illustrative:

```toml
[coverage]
ignore = [
    { module = "pkg.compat", reason = "Compatibility code for one release. No component imports it." },
    { module = "pkg.vendor.*", reason = "External package code in this repository." },
]
```
