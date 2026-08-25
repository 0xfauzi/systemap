"""The system map of systemap: what the parts are and what they are to each other.

systemap maps itself. This file was drafted by following the shipped skill
(src/systemap/skill/SKILL.md) against the facts `systemap extract` read out
of this package, and reviewed by the maintainer. Build state is derived: a
component is built when the entry named in `entry` exists in the modules
named in `implemented_by`, so nothing here says "done".

The map has three actors outside the code (the agent that authors, the
maintainer who reviews, the CI that refuses) and five bands inside it:
what you operate, what gathers, what means, what draws, what keeps the map
true. Positions are hand-placed on a grid; `systemap check` decides
whether the placement is clean.
"""

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

# The grid: card columns 190 apart (150 card, 40 gutter), rows 155 apart.
# Column c3 is empty below the first row on purpose: it is the corridor the
# long routes between the two halves of the map run down.
COL = {"out": 41, "c1": 300, "c2": 490, "c3": 680, "c4": 870, "c5": 1060}
ROW = {"r0": 70, "r1": 225, "r2": 380, "r3": 535}

CONTAINERS = (
    Container(
        id="outside",
        label="OUTSIDE THE PACKAGE",
        sub="the people and the runner that use it",
        box=(16, 16, 200, 668),
        tone="host",
    ),
    Container(
        id="systemap",
        label="SYSTEMAP",
        sub="one command-line process; nothing is fetched, nothing is served",
        box=(240, 16, 1024, 668),
        tone="server",
    ),
)

REGIONS = (
    Region("operate", "OPERATE", (264, 44, 976, 106), container="systemap"),
    Region("gather", "GATHER", (280, 190, 380, 125), container="systemap"),
    Region("mean", "MEAN", (850, 190, 380, 125), container="systemap"),
    Region("draw", "DRAW", (280, 350, 380, 290), container="systemap"),
    Region("keep", "KEEP TRUE", (850, 350, 380, 125), container="systemap"),
)

COMPONENTS = (
    # ---- outside: the agent authors, the maintainer reviews, CI refuses ----
    Component(
        id="Agent",
        does="Reads the skill, runs the commands, writes the model, and fixes what the check names.",
        kind="actor",
        container="outside",
        x=COL["out"],
        y=120,
    ),
    Component(
        id="CI",
        does="Runs the check on every pull request and fails the ones that leave the map behind.",
        kind="actor",
        container="outside",
        x=COL["out"],
        y=340,
    ),
    Component(
        id="Maintainer",
        does="Reads the judgement list, corrects the model where it disagrees, and commits the map.",
        kind="actor",
        container="outside",
        x=COL["out"],
        y=540,
    ),
    # ---- operate: the commands, the configuration, what init writes ----
    Component(
        id="CLI",
        does="The commands the agent runs: init, extract, check, render, figure, refresh, judgement, skill. Every non-zero exit names what to run next.",
        interface="systemap <command> [--root DIR]; exit 0 current, 1 failed or stale, 2 unusable",
        implemented_by=("systemap.cli", "systemap.__main__"),
        entry="main",
        region="operate",
        x=COL["c1"],
        y=ROW["r0"],
    ),
    Component(
        id="Scaffold",
        does="What init writes once and never overwrites: the configuration, a starter model that passes every check, the output directory, the workflow.",
        interface="write(root, name, package, roots, ci) -> one line per file",
        implemented_by=("systemap.scaffold",),
        entry="write",
        region="operate",
        x=COL["c2"],
        y=ROW["r0"],
    ),
    Component(
        id="Config",
        does="systemap.toml, or [tool.systemap] in pyproject.toml, resolved with defaults. Unknown keys and ignores without a reason are refused.",
        interface="load(root) -> Config; load_model(path) -> (MODEL, MEANING)",
        implemented_by=("systemap.config",),
        entry="load",
        kind="store",
        region="operate",
        x=COL["c3"],
        y=ROW["r0"],
    ),
    # ---- gather: the mechanical truth ----
    Component(
        id="FactsExtractor",
        does="Walks the package's syntax tree and writes the facts: every module, its public surface, what it imports, the tests that import it. Nothing anyone writes changes what it finds.",
        interface="build(cfg) -> facts; drift(fresh, stored) -> what no longer matches",
        implemented_by=("systemap.extract",),
        entry="build",
        region="gather",
        x=COL["c1"],
        y=ROW["r1"],
    ),
    Component(
        id="ChangeDetector",
        does="Works out what a branch changes in the map's terms: which components moved, what each gained or lost on its public surface, which exported names were redefined, and how far the change reaches through imports.",
        interface="compute(cfg, model, base, facts, head) -> change",
        implemented_by=("systemap.change",),
        entry="compute",
        region="gather",
        x=COL["c2"],
        y=ROW["r1"],
    ),
    # ---- mean: the judgement ----
    Component(
        id="Skill",
        does="The procedure the agent follows: extract, read the repository's words, group, write flows and layers and sentences, check until complete, hand back the judgement calls. Plain text, shipped in the package.",
        interface="text() -> the skill; write(dir) -> the installed file",
        implemented_by=("systemap.skill",),
        entry="text",
        region="mean",
        x=COL["c4"],
        y=ROW["r1"],
    ),
    Component(
        id="Model",
        does="The schema a map is written in, and the file the agent writes in it: containers, regions, components, flows, invariants, and the meaning tables. Checks that the meaning names only what the model has.",
        interface="MODEL: Model and MEANING: Meaning, exported by map/model.py",
        implemented_by=("systemap.model", "systemap"),
        entry="Model",
        kind="store",
        region="mean",
        x=COL["c5"],
        y=ROW["r1"],
    ),
    # ---- draw: one generator for every picture ----
    Component(
        id="Router",
        does="Routes every flow orthogonally through the gutters between cards, never through a card it does not connect, never across a band it neither starts nor ends in, and seats each label where it touches nothing.",
        interface="route_all(...) -> routes; place_labels(...) -> placed labels and collisions",
        implemented_by=("systemap.route",),
        entry="route_all",
        region="draw",
        x=COL["c1"],
        y=ROW["r2"],
    ),
    Component(
        id="Schematic",
        does="Draws the SVG: cards filled by build state, routes coloured by layer, and the interaction script that lights a clicked component's neighbours, switches layers, steps journeys, pans and zooms. The theme is one table of tokens.",
        interface="render(model, meaning, theme, facts) -> (svg, detail JSON)",
        implemented_by=("systemap.schematic", "systemap.theme"),
        entry="render",
        region="draw",
        x=COL["c2"],
        y=ROW["r2"],
    ),
    Component(
        id="Page",
        does="Wraps the schematic into one self-contained HTML page: layer switch, journeys, the focus drawer, the index by region, the invariants. No fonts, scripts or images are fetched.",
        interface="build(cfg, model, meaning, theme, facts, change) -> html",
        implemented_by=("systemap.page",),
        entry="build",
        region="draw",
        x=COL["c1"],
        y=ROW["r3"],
    ),
    Component(
        id="Figures",
        does="One figure from the same generator, for a document: the whole system, a plan's reach, or a change. A .svg output is the bare drawing on its ground.",
        interface="make(cfg, model, meaning, theme, facts, ...) -> (html, collisions)",
        implemented_by=("systemap.figure",),
        entry="make",
        region="draw",
        x=COL["c2"],
        y=ROW["r3"],
    ),
    # ---- keep true: what refuses, and what asks a person ----
    Component(
        id="Check",
        does="Every rule that refuses a lie: coverage, entry, tracker, placement, routes, labels, type size, meaning, wheels, and stale outputs. Each failure prints its fix; exit 1 on the first.",
        interface="run(model, meaning, theme, facts, ...) -> Result; stale(cfg, ...) -> lines",
        implemented_by=("systemap.check",),
        entry="run",
        region="keep",
        x=COL["c4"],
        y=ROW["r2"],
    ),
    Component(
        id="Judgement",
        does="The list a maintainer must confirm: components with a single module, modules folded under a name they share no word with, flows without a sentence, layers that light almost nothing, every ignore. A report, never a gate.",
        interface="run(model, meaning, facts, ignores) -> lines; always exit 0",
        implemented_by=("systemap.judgement",),
        entry="run",
        region="keep",
        x=COL["c5"],
        y=ROW["r2"],
    ),
)

# (from, to, the artifact carried, the dataflow kind)
FLOWS = (
    # where you stand: how the thing is driven
    Flow("Agent", "CLI", "commands", "stand"),
    Flow("CI", "CLI", "check", "stand"),
    Flow("Config", "CLI", "settings", "stand"),
    Flow("CLI", "Scaffold", "init", "stand"),
    Flow("Scaffold", "Model", "starter", "stand"),
    Flow("CLI", "FactsExtractor", "extract", "stand"),
    Flow("CLI", "Check", "check", "stand"),
    Flow("CLI", "Page", "render", "stand"),
    Flow("CLI", "Judgement", "judgement", "stand"),
    # what judges: the meaning, authored and reviewed
    Flow("Skill", "Agent", "procedure", "judge"),
    Flow("Agent", "Model", "map/model.py", "judge"),
    Flow("Maintainer", "Model", "corrections", "judge"),
    Flow("Model", "Judgement", "model", "judge"),
    Flow("Judgement", "Maintainer", "judgement list", "judge"),
    # what gathers: the facts
    Flow("FactsExtractor", "Check", "map.json", "gather"),
    Flow("FactsExtractor", "Schematic", "map.json", "gather"),
    Flow("ChangeDetector", "Page", "change map", "gather"),
    Flow("ChangeDetector", "Figures", "reach", "gather"),
    # what draws
    Flow("Model", "Schematic", "topology, meaning", "draw"),
    Flow("Router", "Schematic", "routes, labels", "draw"),
    Flow("Schematic", "Page", "svg, detail", "draw"),
    Flow("Schematic", "Figures", "svg", "draw"),
    Flow("Page", "Maintainer", "the page", "draw"),
    # what refuses
    Flow("Model", "Check", "model", "refuse"),
    Flow("Schematic", "Check", "geometry", "refuse"),
    Flow("Config", "Check", "ignores", "refuse"),
    Flow("Check", "Agent", "the fix", "refuse"),
    Flow("Check", "CI", "verdict", "refuse"),
)

FLOW_KINDS = ("stand", "judge", "gather", "draw", "refuse")

# Copied from the README's Principles, which is where the project states
# its own rules; each names the components it binds.
INVARIANTS = (
    Invariant(
        1,
        "No counts of code or tests anywhere on the page: the map explains what the system does, not how much of it there is (README, Principles).",
        governs=("Page", "Schematic", "Figures"),
    ),
    Invariant(
        2,
        "A component is something a reader would point at and name; a module is not a part (README, Principles).",
        governs=("Model", "Skill", "Judgement"),
    ),
    Invariant(
        3,
        "Edges carry the relationships; prose is for emphasis (README, Principles).",
        governs=("Model", "Schematic"),
    ),
    Invariant(
        4,
        "Nothing is declared done: build state is derived from an entry symbol that exists or does not (README, Principles).",
        governs=("FactsExtractor", "Schematic", "Check"),
    ),
    Invariant(
        5,
        "A planned part names the tracker item that will build it (README, Principles).",
        governs=("Model", "Check"),
    ),
    Invariant(
        6,
        "Positions are placed by hand and the checker decides, so the same system always draws the same picture (README, Principles).",
        governs=("Model", "Router", "Check"),
    ),
    Invariant(
        7,
        "The agent authors, the checker refuses, the person reviews (README, Principles).",
        governs=("Agent", "Check", "Maintainer", "Judgement"),
    ),
    Invariant(
        8,
        "The page fetches nothing and depends on nothing (README, opening).",
        governs=("Page",),
    ),
)

MODEL = Model(
    canvas=(1280, 700),
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=FLOWS,
    flow_kinds=FLOW_KINDS,
    invariants=INVARIANTS,
)

# ---- meaning: the plain words, the layers, one sentence per flow ---------

PLAIN = {
    "Agent": "the coding agent that draws the map",
    "CI": "the runner that refuses a stale map",
    "Maintainer": "the person who confirms the judgement",
    "CLI": "the commands",
    "Scaffold": "what init writes",
    "Config": "the configuration",
    "FactsExtractor": "what reads the code",
    "ChangeDetector": "what a branch changed",
    "Skill": "the procedure the agent follows",
    "Model": "the map as written",
    "Router": "what finds the routes",
    "Schematic": "what draws the map",
    "Page": "the page you open",
    "Figures": "a picture for a document",
    "Check": "what refuses",
    "Judgement": "what asks a person",
}

LAYERS = (
    Layer(
        id="stand",
        label="Where you stand",
        question="How is the thing driven, and by whom?",
        sub="the commands, the configuration, what init writes",
    ),
    Layer(
        id="judge",
        label="What judges",
        question="Where does the meaning come from, and who confirms it?",
        sub="the skill, the agent, the model, the maintainer",
    ),
    Layer(
        id="gather",
        label="What gathers",
        question="Where do the facts come from?",
        sub="the syntax tree, the git range",
    ),
    Layer(
        id="draw",
        label="What draws",
        question="How do the facts and the model become one picture?",
        sub="one generator for the page and every figure",
    ),
    Layer(
        id="refuse",
        label="What refuses",
        question="What stops the map from lying?",
        sub="every rule, and who hears the verdict",
    ),
)

LAYER_OF_KIND = {
    "stand": "stand",
    "judge": "judge",
    "gather": "gather",
    "draw": "draw",
    "refuse": "refuse",
}

RELATIONS = {
    (
        "Agent",
        "CLI",
    ): "The agent drives everything through the commands; it never imports the package.",
    ("CI", "CLI"): "The workflow init writes runs the check on every push and pull request.",
    (
        "Config",
        "CLI",
    ): "The configuration tells the commands where the packages, the model and the output are.",
    (
        "CLI",
        "Scaffold",
    ): "init hands the scaffold the project's name and package roots; the scaffold writes what does not exist yet.",
    (
        "Scaffold",
        "Model",
    ): "The starter model is the smallest map that passes every check; the agent replaces its words.",
    (
        "CLI",
        "FactsExtractor",
    ): "extract, and the first step of refresh, run the extractor over the configured package roots.",
    (
        "CLI",
        "Check",
    ): "check runs every rule and prints each failure with its fix; refresh runs the same rules before it renders.",
    ("CLI", "Page"): "render, and refresh, build the page from the facts and the model.",
    (
        "CLI",
        "Judgement",
    ): "judgement prints the list the maintainer must confirm and always exits 0.",
    (
        "Skill",
        "Agent",
    ): "The skill gives the agent the order of the work, the schema, a worked example, and what to hand back.",
    (
        "Agent",
        "Model",
    ): "The agent writes map/model.py: the groupings, the flows, the layers, the sentences, the journeys, the invariants.",
    (
        "Maintainer",
        "Model",
    ): "The maintainer corrects the calls they disagree with; the model is theirs once reviewed.",
    (
        "Model",
        "Judgement",
    ): "Judgement reads the model for the calls that could have gone another way.",
    (
        "Judgement",
        "Maintainer",
    ): "The list is short and mechanical to produce, so the review cannot be skipped.",
    (
        "FactsExtractor",
        "Check",
    ): "The facts are what the check judges coverage, entry and staleness against.",
    (
        "FactsExtractor",
        "Schematic",
    ): "Build state is derived from the facts: the entry symbol is looked up in the claimed modules.",
    (
        "ChangeDetector",
        "Page",
    ): "With --base, the page carries a change map: what moved, what it reached.",
    (
        "ChangeDetector",
        "Figures",
    ): "A change figure marks what a git range changed; a reach figure marks what a plan will.",
    (
        "Model",
        "Schematic",
    ): "The model is the topology the schematic draws and the meaning it prints on the wheel.",
    (
        "Router",
        "Schematic",
    ): "The router hands back the routes and the seated labels, and reports what could not be placed cleanly.",
    (
        "Schematic",
        "Page",
    ): "The page embeds the SVG and the detail JSON the interaction script reads.",
    ("Schematic", "Figures"): "A figure is the same SVG in a figure element, or bare for an image.",
    ("Page", "Maintainer"): "The maintainer opens the page: layers, click, journeys, pan and zoom.",
    (
        "Model",
        "Check",
    ): "The check reads the model's own contradictions first; nothing else is judged until they are gone.",
    (
        "Schematic",
        "Check",
    ): "The check renders once and reads the geometry back: routes, labels, type size, wheels.",
    (
        "Config",
        "Check",
    ): "An ignore with a reason takes a module out of the coverage rule, on record.",
    (
        "Check",
        "Agent",
    ): "Every failure names its fix; the agent edits until coverage is complete and the layout is clean.",
    ("Check", "CI"): "Exit 1 fails the pull request; the message says what to run.",
}

VERBS = {
    "stand": ("runs", "is run by"),
    "judge": ("informs", "reads"),
    "gather": ("feeds", "reads from"),
    "draw": ("supplies", "draws from"),
    "refuse": ("is checked by", "checks"),
}

VERB_OVERRIDES = {
    ("Config", "CLI"): ("configures", "is configured by"),
    ("Scaffold", "Model"): ("writes the first", "starts as"),
    ("Skill", "Agent"): ("guides", "follows"),
    ("Agent", "Model"): ("writes", "is written by"),
    ("Maintainer", "Model"): ("corrects", "is corrected by"),
    ("Judgement", "Maintainer"): ("asks", "answers"),
    ("Schematic", "Page"): ("fills", "wraps"),
    ("Schematic", "Figures"): ("fills", "wraps"),
    ("Page", "Maintainer"): ("is read by", "reads"),
    ("Config", "Check"): ("excuses modules to", "takes ignores from"),
    ("Check", "Agent"): ("refuses", "is refused by"),
    ("Check", "CI"): ("answers", "asks"),
}

JOURNEYS = (
    Journey(
        id="first-map",
        label="The first map of a repository",
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs systemap init: configuration, starter model, the skill, the workflow.",
            ),
            Step(
                acts=("Skill",),
                measures=(),
                edge=("Skill", "Agent"),
                say="The skill gives the agent the order of the work and the schema.",
            ),
            Step(
                acts=("FactsExtractor",),
                measures=(),
                edge=("CLI", "FactsExtractor"),
                say="systemap extract reads every module, its surface and its tests out of the tree.",
            ),
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "Model"),
                say="The agent writes map/model.py: components, flows, layers, one sentence per edge.",
            ),
            Step(
                acts=("Check",),
                measures=("Check",),
                edge=("Check", "Agent"),
                say="systemap check names each failure and its fix; the agent edits until coverage is N/N and the layout is clean.",
            ),
            Step(
                acts=("Page",),
                measures=(),
                edge=("CLI", "Page"),
                say="systemap refresh renders the page and every configured figure.",
            ),
            Step(
                acts=("Judgement",),
                measures=("Maintainer",),
                edge=("Judgement", "Maintainer"),
                say="systemap judgement hands the maintainer the calls to confirm; the maintainer commits docs/map.",
            ),
        ),
    ),
    Journey(
        id="refactor",
        label="A refactor moves a module",
        steps=(
            Step(
                acts=("CI",),
                measures=(),
                edge=("CI", "CLI"),
                say="A pull request moves a module; the workflow runs systemap check.",
            ),
            Step(
                acts=("FactsExtractor",),
                measures=("Check",),
                edge=("FactsExtractor", "Check"),
                say="A fresh extraction differs from the committed facts: the map is stale.",
            ),
            Step(
                acts=("Check",),
                measures=("CI",),
                edge=("Check", "CI"),
                say="The check fails the pull request and names the fix: systemap refresh.",
            ),
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs refresh, moves the module's claim if a component changed, and commits docs/map.",
            ),
            Step(
                acts=("Page",),
                measures=("Maintainer",),
                edge=("Page", "Maintainer"),
                say="The maintainer reads the page: the moved part is where the code now says it is.",
            ),
        ),
    ),
    Journey(
        id="planned-ships",
        label="A planned component ships",
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "Model"),
                say="The agent adds a card with a tracker and no entry; the map draws it as a ghost.",
            ),
            Step(
                acts=("Model",),
                measures=("Check",),
                edge=("Model", "Check"),
                say="The check accepts the ghost because it names the item that will build it.",
            ),
            Step(
                acts=("FactsExtractor",),
                measures=(),
                edge=("FactsExtractor", "Schematic"),
                say="The code lands and the entry symbol appears in the facts.",
            ),
            Step(
                acts=("Schematic",),
                measures=(),
                edge=("Schematic", "Page"),
                say="The card draws built. Nobody declared it; the code did.",
            ),
        ),
    ),
)

MEANING = Meaning(
    plain=PLAIN,
    layers=LAYERS,
    layer_of_kind=LAYER_OF_KIND,
    relations=RELATIONS,
    journeys=JOURNEYS,
    verbs=VERBS,
    verb_overrides=VERB_OVERRIDES,
)
