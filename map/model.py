"""The system map of systemap: what the parts are and what they are to each other.

systemap maps itself. This file was drafted by following the shipped skill
(src/systemap/skill/) against the facts `systemap extract` read out of
this package, taken through the second pass until a full pass changed
nothing, and reviewed by the maintainer. Every card is code in the tree: a
component names modules the facts have and an entry they define, and the
check refuses anything else, so nothing here is a plan and nothing says
"done".

The map has three actors outside the code (the agent that authors, the
maintainer who reviews, the CI that refuses) and five bands inside it:
what you operate, what gathers, what means, what draws, what keeps the map
true. Positions are fixed in this file: `systemap place` writes a
position for a card without one and keeps every card that has one,
`systemap place --all` lays every card out again but the pinned ones;
`systemap check` decides whether the placement is clean, and `systemap
describe` says what the picture shows.
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

# Every position, box and the canvas below were written by `systemap place`:
# a card keeps its x and y until `place --all` lays the map out again, a
# card written without them is placed into a free slot of its region, and
# no card is pinned, so `place --all` may move any of them.

CONTAINERS = (
    Container(
        id="outside",
        label="OUTSIDE THE PACKAGE",
        sub="the people and the runner that use it",
        box=(16, 16, 190, 644),
        tone="host",
    ),
    Container(
        id="systemap",
        label="SYSTEMAP",
        sub="one command-line process; nothing is fetched, nothing is served",
        box=(230, 16, 848, 860),
        tone="server",
    ),
)

REGIONS = (
    Region("operate", "OPERATE", (250, 80, 380, 204), container="systemap"),
    Region("gather", "GATHER", (678, 80, 190, 204), container="systemap"),
    Region("mean", "MEAN", (250, 320, 190, 204), container="systemap"),
    Region("draw", "DRAW", (678, 320, 380, 204), container="systemap"),
    Region("keep", "KEEP TRUE", (250, 560, 190, 296), container="systemap"),
)

COMPONENTS = (
    # ---- outside: the agent authors, the maintainer reviews, CI refuses ----
    Component(
        id="Agent",
        does="Reads the skill, runs the commands, writes the model, fixes what the check names, and answers what the judgement asks.",
        kind="actor",
        container="outside",
        x=36,
        y=596,
    ),
    Component(
        id="CI",
        does="Runs the check on every pull request and fails the ones that leave the map behind.",
        kind="actor",
        container="outside",
        x=36,
        y=412,
    ),
    Component(
        id="Maintainer",
        does="Reads the judgement answers, corrects the model where it disagrees, and commits the map.",
        kind="actor",
        container="outside",
        x=36,
        y=504,
    ),
    # ---- operate: the commands, the configuration, what init writes ----
    Component(
        id="CLI",
        does="The commands the agent runs: init, extract, check, render, figure, refresh, judgement, describe, serve, skill. Every non-zero exit names what to run next.",
        interface="main(argv) -> exit code: 0 current, 1 failed or stale, 2 unusable",
        implemented_by=("systemap.cli", "systemap.__main__"),
        entry="main",
        region="operate",
        x=460,
        y=120,
    ),
    Component(
        id="Scaffold",
        does="What init writes once and never overwrites: the configuration, a starter model laid out as a grid of regions with corridors between them, the output directory, a pinned workflow.",
        interface="write(root, name, package, roots, ci) -> one line per file",
        implemented_by=("systemap.scaffold",),
        entry="write",
        note="never overwrites a file that exists: an upgrade of systemap edits nothing init wrote, so a pinned workflow is bumped by hand",
        region="operate",
        x=270,
        y=212,
    ),
    Component(
        id="Config",
        does="systemap.toml, or [tool.systemap] in pyproject.toml, resolved with defaults: package roots and tests directories discovered, judgement answers kept with their reasons. Unknown keys, ignores and answers without a reason are refused.",
        interface="load(root) -> Config; load_model(path) -> (MODEL, MEANING)",
        implemented_by=("systemap.config",),
        entry="load",
        kind="store",
        region="operate",
        x=460,
        y=212,
    ),
    # ---- gather: the mechanical truth ----
    Component(
        id="FactsExtractor",
        does="Walks the package's syntax tree and writes the facts: every module, its public surface and every public name, what it imports inside and outside the package, the tests that import it, and where a run can start. Nothing anyone writes changes what it finds; systemap facts reads them back one view at a time.",
        interface="build(cfg) -> facts; drift(fresh, stored) -> what no longer matches",
        implemented_by=("systemap.extract", "systemap.facts"),
        entry="build",
        region="gather",
        x=698,
        y=120,
    ),
    Component(
        id="ChangeDetector",
        does="Works out what a branch changes in the map's terms: which components moved, what each gained or lost on its public surface, which exported names were redefined, and how far the change reaches through imports. systemap delta reads the facts at two commits out of git and says what the change did to the map, one line per thing with its fix.",
        interface="compute(cfg, model, base, facts, head) -> change; delta.compute(cfg, model, meaning, base facts, head facts) -> Delta",
        implemented_by=("systemap.change", "systemap.delta"),
        entry="compute",
        region="gather",
        x=698,
        y=212,
    ),
    Component(
        id="Placer",
        does="A first position for every card without one: regions on a two-column grid with corridors between them, in the order the search scores best (every order tried, the best routed and scored by collisions, refusals, bends and length), cards on the grid inside, ordered by barycentre sweeps over the flows. Writes the positions into map/model.py in place; with --all, lays every card out again and keeps the pinned ones.",
        interface="compute(model) -> Placement; write(path, model, placement)",
        implemented_by=("systemap.place",),
        entry="compute",
        region="operate",
        x=270,
        y=120,
    ),
    # ---- mean: the judgement ----
    Component(
        id="Skill",
        does="The procedure the agent follows: extract, draft, check, judgement, render, the second pass, the stop condition, what to hand back, and the maintenance path when the code changed. A directory of plain text with references, shipped in the package.",
        interface="files() -> the skill directory; write(dir) -> the installed SKILL.md",
        implemented_by=("systemap.skill",),
        entry="write",
        region="mean",
        x=270,
        y=360,
    ),
    Component(
        id="Model",
        does="The schema a map is written in, and the file the agent writes in it: containers, regions, components, flows, invariants, and the meaning tables. Checks that the meaning names only what the model has, reads from the facts whether an import backs each flow (observed, external or declared), and loads the tree of maps when a card opens a map of its own.",
        interface="Model(canvas, containers, regions, components, flows, flow_kinds, invariants) and Meaning(plain, layers, relations, journeys, verbs), exported by map/model.py as MODEL and MEANING",
        implemented_by=("systemap.model", "systemap", "systemap.evidence", "systemap.nest"),
        entry="Model",
        kind="store",
        region="mean",
        x=270,
        y=452,
    ),
    # ---- draw: one generator for every picture ----
    Component(
        id="Router",
        does="Routes every flow orthogonally through the gutters between cards, never through a card it does not connect, never across a band it neither starts nor ends in, and seats each label where it touches nothing.",
        interface="route_all(edges, cards, actors, blocks, regions, region_of, canvas) -> routes; place_labels(routes, widths, height, obstacles, canvas) -> seated labels",
        implemented_by=("systemap.route",),
        entry="route_all",
        region="draw",
        x=698,
        y=452,
    ),
    Component(
        id="Schematic",
        does="Draws the SVG: cards marked by kind, routes coloured by layer, and the interaction script that lights a clicked component's neighbours, switches readings, steps journeys, pans and zooms. The theme is one table of tokens.",
        interface="render(model, meaning, theme, facts) -> (svg, detail JSON)",
        implemented_by=("systemap.schematic", "systemap.theme"),
        entry="render",
        region="draw",
        x=888,
        y=452,
    ),
    Component(
        id="Page",
        does="Wraps the schematic into one self-contained HTML page: the layer switch, journeys, the focus drawer, the index by region, the invariants. No fonts, scripts or images are fetched; systemap serve serves it over HTTP.",
        interface="build(cfg, model, meaning, theme, facts, change) -> html",
        implemented_by=("systemap.page",),
        entry="build",
        region="draw",
        x=888,
        y=360,
    ),
    Component(
        id="Figures",
        does="One figure from the same generator, for a document: the whole system, a plan's reach, or a change. A .svg output is the bare drawing on its ground.",
        interface="make(cfg, model, meaning, theme, facts, mode, components, base, head, caption, layer) -> (html, collisions)",
        implemented_by=("systemap.figure",),
        entry="make",
        region="draw",
        x=698,
        y=360,
    ),
    # ---- keep true: what refuses, and what asks a person ----
    Component(
        id="Check",
        does="Every rule that refuses a lie: coverage, entry, interface, placement, routes, labels and card text, type size, meaning, wheels, and stale outputs. Each failure prints its fix; exit 1 on the first.",
        interface="run(model, meaning, theme, facts, ignores) -> Result; stale(cfg, model, meaning, theme) -> lines",
        implemented_by=("systemap.check",),
        entry="run",
        region="keep",
        x=270,
        y=692,
    ),
    Component(
        id="Judgement",
        does="The list the agent acts on and the maintainer confirms: single-module components, odd folds, flows without a sentence, thin layers, entry points without a journey, imports across a boundary with no flow, model SDK imports outside an agent. Answered lines, singly or by family, are suppressed and counted. A report; a gate only with --strict. Before any of it, systemap suggest proposes a first grouping from the facts, to argue with.",
        interface="run(model, meaning, facts, sdks) -> lines; exit 1 with --strict while a line is open",
        implemented_by=("systemap.judgement", "systemap.suggest"),
        entry="run",
        region="keep",
        x=270,
        y=600,
    ),
    Component(
        id="Describe",
        does="What a look at the picture would tell an agent that cannot look: cards per region, bends and length per edge worst first, seats used per gutter, cards and edges per reading. A description, never a rule.",
        interface="run(model, meaning, theme, facts) -> lines; always exit 0",
        implemented_by=("systemap.describe",),
        entry="run",
        region="keep",
        x=270,
        y=784,
    ),
)

# (from, to, the artifact carried, the kind). control: one part drives
# another; data: an artifact moves; judge: this model's own kind, the loop
# in which the meaning is authored and confirmed.
FLOWS = (
    # control: who drives whom
    Flow("Agent", "CLI", "commands", "control"),
    Flow("CI", "CLI", "check", "control"),
    Flow("CLI", "Scaffold", "init", "control"),
    Flow("CLI", "Placer", "place", "control"),
    Flow("CLI", "Skill", "init, skill", "control"),
    Flow("CLI", "FactsExtractor", "extract", "control"),
    Flow("CLI", "ChangeDetector", "--base, delta", "control"),
    Flow("CLI", "Check", "check", "control"),
    Flow("CLI", "Page", "render", "control"),
    Flow("CLI", "Figures", "figure", "control"),
    Flow("CLI", "Judgement", "judgement", "control"),
    Flow("CLI", "Describe", "describe", "control"),
    Flow("Check", "Page", "render to compare", "control"),
    Flow("Check", "Figures", "render to compare", "control"),
    Flow("Check", "ChangeDetector", "interface rule", "control"),
    # data: what moves, and where it goes
    Flow("Config", "CLI", "settings", "data"),
    Flow("Config", "FactsExtractor", "package roots", "data"),
    Flow("Config", "ChangeDetector", "roots, tests dir", "data"),
    Flow("Config", "Page", "name, paths", "data"),
    Flow("Config", "Figures", "figures table", "data"),
    Flow("Config", "Check", "ignores", "data"),
    Flow("Config", "Judgement", "answers, sdks", "data"),
    Flow("Scaffold", "Model", "starter", "data"),
    Flow("FactsExtractor", "Check", "map.json", "data"),
    Flow("FactsExtractor", "Schematic", "map.json", "data"),
    Flow("FactsExtractor", "Judgement", "entry points", "data"),
    Flow("FactsExtractor", "ChangeDetector", "surfaces", "data"),
    Flow("ChangeDetector", "Page", "change map", "data"),
    Flow("ChangeDetector", "Figures", "reach", "data"),
    Flow("Model", "Placer", "cards, flows", "data"),
    Flow("Placer", "Model", "positions", "data"),
    Flow("Model", "FactsExtractor", "claims", "data"),
    Flow("Model", "ChangeDetector", "claims", "data"),
    Flow("Model", "Schematic", "topology, meaning", "data"),
    Flow("Model", "Check", "model", "data"),
    Flow("Router", "Schematic", "routes, labels", "data"),
    Flow("Router", "Describe", "gutters, seats", "data"),
    Flow("Router", "Placer", "routes, seats", "data"),
    Flow("Schematic", "Placer", "geometry", "data"),
    Flow("Placer", "Describe", "region order, score", "data"),
    Flow("Schematic", "Page", "svg, detail", "data"),
    Flow("Schematic", "Figures", "svg", "data"),
    Flow("Schematic", "Check", "geometry", "data"),
    Flow("Schematic", "Describe", "geometry", "data"),
    Flow("Describe", "Agent", "the picture in numbers", "data"),
    Flow("Page", "Maintainer", "the page", "data"),
    Flow("Check", "Agent", "the fix", "data"),
    Flow("Check", "CI", "verdict", "data"),
    # judge: where the meaning comes from, and who confirms it
    Flow("Skill", "Agent", "procedure", "judge"),
    Flow("Agent", "Model", "map/model.py", "judge"),
    Flow("Maintainer", "Model", "corrections", "judge"),
    Flow("Model", "Judgement", "model", "judge"),
    Flow("Judgement", "Agent", "second-pass list", "judge"),
    Flow("Judgement", "Maintainer", "judgement answers", "judge"),
)

FLOW_KINDS = ("judge",)

# The rules the repository states about itself, each with its source: the
# README's Principles, a guard clause, and a test whose name encodes a rule.
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
        "The map draws what exists today: every module a component names is in the facts, and nothing on the map is a plan (README, Principles).",
        governs=("Model", "Check", "FactsExtractor"),
    ),
    Invariant(
        5,
        "Positions are fixed in the model, written once by systemap place or by hand, and the checker decides, so the same system always draws the same picture (README, Principles).",
        governs=("Model", "Placer", "Router", "Check"),
    ),
    Invariant(
        6,
        "The agent authors, the checker refuses, the person reviews (README, Principles).",
        governs=("Agent", "Check", "Maintainer", "Judgement"),
    ),
    Invariant(
        7,
        "The map is built in passes; the second pass is the point (README, Principles).",
        governs=("Skill", "Judgement", "Agent"),
    ),
    Invariant(
        8,
        "The page fetches nothing and depends on nothing (README, opening).",
        governs=("Page",),
    ),
    Invariant(
        9,
        "An unknown configuration key is refused, never ignored (src/systemap/config.py, load: 'unknown key').",
        governs=("Config",),
    ),
    Invariant(
        10,
        "Every ignored module needs a reason (tests/test_coverage.py: test_ignore_without_reason_is_a_config_error).",
        governs=("Config", "Check"),
    ),
)

MODEL = Model(
    canvas=(1094, 892),
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=FLOWS,
    flow_kinds=FLOW_KINDS,
    invariants=INVARIANTS,
)

# ---- meaning: the plain words, the layers, one sentence per flow ---------

PLAIN = {
    "Agent": "the agent that draws",
    "CI": "the runner that refuses",
    "Maintainer": "the person who confirms",
    "CLI": "the commands",
    "Scaffold": "what init writes",
    "Placer": "what places the cards",
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
    "Judgement": "what asks",
    "Describe": "what the picture shows",
}

# The page derives Structure, System context, Data flow and Control flow.
# This model has one reading of its own: the loop in which the meaning is
# authored, questioned and confirmed.
LAYERS = (
    Layer(
        id="judge",
        label="What judges",
        question="Where does the meaning come from, and who confirms it?",
        sub="the skill, the agent, the model, the judgement, the maintainer",
    ),
)

LAYER_OF_KIND = {"judge": "judge"}

RELATIONS = {
    (
        "Agent",
        "CLI",
    ): "The agent drives everything through the commands; it never imports the package.",
    ("CI", "CLI"): "The workflow init writes runs the check on every push and pull request.",
    (
        "CLI",
        "Scaffold",
    ): "init hands the scaffold the project's name and package roots; the scaffold writes what does not exist yet.",
    (
        "CLI",
        "Skill",
    ): "init installs the skill directory beside the project, and skill reinstalls it; an upgrade of the package refreshes it.",
    (
        "CLI",
        "Placer",
    ): "place computes a position for every card without one, or with --all for every card not pinned, and writes it into the model; describe places them for one look without writing.",
    (
        "Router",
        "Placer",
    ): "The placer routes every shortlisted region order with the router and the label pass, and keeps the order with the fewest label collisions, refused routes, bends and length.",
    (
        "Schematic",
        "Placer",
    ): "The placer scores a candidate layout on the drawing's own geometry (the card boxes, the headers and empty containers as walls, what a label may not sit on) and reads the header measurements so a box it lays out holds its header.",
    (
        "Placer",
        "Describe",
    ): "Describe reads the region order off the map as placed and the score of the drawing under it, and says how many orders place tried when it chose the order for the look.",
    (
        "CLI",
        "FactsExtractor",
    ): "extract, and the first step of refresh, run the extractor over the configured package roots.",
    (
        "CLI",
        "ChangeDetector",
    ): "render --base and figure --base ask the change detector what a git range moved; delta asks it what a change did to the map, from the facts at two commits.",
    (
        "CLI",
        "Check",
    ): "check runs every rule and prints each failure with its fix; refresh runs the same rules before it renders.",
    ("CLI", "Page"): "render, and refresh, build the page from the facts and the model.",
    (
        "CLI",
        "Figures",
    ): "figure draws one figure to a file; refresh draws every figure the configuration lists.",
    (
        "CLI",
        "Judgement",
    ): "judgement prints the list to act on or answer; with --strict it exits 1 while a line is open.",
    (
        "CLI",
        "Describe",
    ): "describe draws the map the way the page does and prints what the drawing shows, in numbers.",
    (
        "Check",
        "Page",
    ): "The stale rule renders the page from the stored facts and compares it with the committed one.",
    (
        "Check",
        "Figures",
    ): "The stale rule renders every configured figure and compares it with the committed one.",
    (
        "Check",
        "ChangeDetector",
    ): "delta judges an interface name that vanished by the check's own interface rule, so the two cannot disagree about what a line may start with.",
    (
        "Config",
        "CLI",
    ): "The configuration tells the commands where the packages, the model and the output are.",
    (
        "Config",
        "FactsExtractor",
    ): "The package roots and the tests directory say what the extractor walks.",
    (
        "Config",
        "ChangeDetector",
    ): "The package roots and the tests directory say which changed files are modules and which are tests.",
    (
        "Config",
        "Page",
    ): "The page takes its title, its footer paths and the label for actors outside every region from the configuration.",
    (
        "Config",
        "Figures",
    ): "The [[figures]] table says which figures refresh regenerates, in which mode, to which file.",
    (
        "Config",
        "Check",
    ): "An ignore with a reason takes a module out of the coverage rule, on record.",
    (
        "Config",
        "Judgement",
    ): "The answers under [judgement] suppress the lines they cover, and [facts] model_sdks extends or reduces the SDK list the model sdk line reads.",
    (
        "Scaffold",
        "Model",
    ): "The starter model is the smallest map that passes every check; the agent replaces its words.",
    (
        "FactsExtractor",
        "Check",
    ): "The facts are what the check judges coverage, entry and staleness against.",
    (
        "FactsExtractor",
        "Schematic",
    ): "The facts file, written by extract and read back by every command, says which modules each card stands for and which flows an import backs.",
    (
        "FactsExtractor",
        "Judgement",
    ): "The entry points in the facts are what the judgement asks journeys for; the imports are what it walks for crossing edges.",
    (
        "FactsExtractor",
        "ChangeDetector",
    ): "The change detector reads a module's public surface with the extractor's parser, on both sides of the diff, so the two cannot disagree about what a module exports.",
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
        "Placer",
    ): "The placer reads the cards, their regions and the flows between them; a card with x and y is kept, and with --all only a pinned card is.",
    (
        "Placer",
        "Model",
    ): "The placer writes the positions, the boxes and the canvas into map/model.py in place; the rest of the file is kept byte for byte.",
    (
        "Model",
        "FactsExtractor",
    ): "The extractor reads the model's claims to warn about a module the tree no longer has.",
    (
        "Model",
        "ChangeDetector",
    ): "The change detector attributes changed modules to the components that claim them.",
    (
        "Model",
        "Schematic",
    ): "The model is the topology the schematic draws and the meaning it prints on the wheel.",
    (
        "Model",
        "Check",
    ): "The check reads the model's own contradictions first; nothing else is judged until they are gone.",
    (
        "Router",
        "Schematic",
    ): "The router hands back the routes and the seated labels, and reports what could not be placed cleanly, with the fix that applies.",
    (
        "Router",
        "Describe",
    ): "The router's gutters and seat counts are what describe reports per gutter.",
    (
        "Schematic",
        "Page",
    ): "The page embeds the SVG and the detail JSON the interaction script reads.",
    ("Schematic", "Figures"): "A figure is the same SVG in a figure element, or bare for an image.",
    (
        "Schematic",
        "Check",
    ): "The check renders once and reads the geometry back: routes, labels, type size, wheels.",
    (
        "Schematic",
        "Describe",
    ): "describe renders once and reads the geometry back as a description: regions, edges, gutters, readings.",
    (
        "Describe",
        "Agent",
    ): "An agent that cannot open the page reads the picture in numbers after every refresh.",
    (
        "Page",
        "Maintainer",
    ): "The maintainer opens the page: readings, click, journeys, pan and zoom.",
    (
        "Check",
        "Agent",
    ): "Every failure names its fix; the agent edits until coverage is complete and the layout is clean.",
    ("Check", "CI"): "Exit 1 fails the pull request; the message says what to run.",
    (
        "Skill",
        "Agent",
    ): "The skill gives the agent the loop, the schema, a worked example, the second pass, and what to hand back.",
    (
        "Agent",
        "Model",
    ): "The agent writes map/model.py: the groupings, the flows, the sentences, the journeys, the invariants.",
    (
        "Maintainer",
        "Model",
    ): "The maintainer corrects the calls they disagree with; the model is theirs once reviewed.",
    (
        "Model",
        "Judgement",
    ): "The judgement reads the model for the calls that could have gone another way.",
    (
        "Judgement",
        "Agent",
    ): "In the second pass the agent walks every crossing import and every entry point without a journey, and changes the model or answers the line.",
    (
        "Judgement",
        "Maintainer",
    ): "The maintainer reads the agent's answers, line by line; the list is mechanical to produce, so the review cannot be skipped.",
}

VERBS = {
    "control": ("runs", "is run by"),
    "data": ("feeds", "reads from"),
    "judge": ("informs", "reads"),
}

VERB_OVERRIDES = {
    ("Config", "CLI"): ("configures", "is configured by"),
    ("Scaffold", "Model"): ("writes the first", "starts as"),
    ("Placer", "Model"): ("places", "is placed by"),
    ("Skill", "Agent"): ("guides", "follows"),
    ("Agent", "Model"): ("writes", "is written by"),
    ("Maintainer", "Model"): ("corrects", "is corrected by"),
    ("Judgement", "Agent"): ("asks", "answers"),
    ("Judgement", "Maintainer"): ("reports to", "confirms"),
    ("Schematic", "Page"): ("fills", "wraps"),
    ("Schematic", "Figures"): ("fills", "wraps"),
    ("Page", "Maintainer"): ("is read by", "reads"),
    ("Config", "Check"): ("excuses modules to", "takes ignores from"),
    ("Check", "Agent"): ("refuses", "is refused by"),
    ("Describe", "Agent"): ("describes to", "reads"),
    ("Check", "CI"): ("answers", "asks"),
    ("Check", "Page"): ("compares", "is compared by"),
    ("Check", "Figures"): ("compares", "is compared by"),
    ("Check", "ChangeDetector"): ("lends its rule to", "judges by"),
}

JOURNEYS = (
    Journey(
        id="first-map",
        label="The first map: systemap init, extract, a draft, check",
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs systemap init: configuration, starter model, the workflow.",
            ),
            Step(
                acts=("CLI",),
                measures=(),
                edge=("CLI", "Skill"),
                say="init installs the skill directory beside the project; systemap skill reinstalls it later.",
            ),
            Step(
                acts=("Skill",),
                measures=(),
                edge=("Skill", "Agent"),
                say="The skill gives the agent the loop: extract, draft, check, judgement, render, second pass.",
            ),
            Step(
                acts=("FactsExtractor",),
                measures=(),
                edge=("CLI", "FactsExtractor"),
                say="systemap extract reads every module, its surface, its imports and the entry points out of the tree.",
            ),
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "Model"),
                say="The agent runs systemap suggest for a first grouping to argue with, then writes map/model.py: components, flows, one sentence per edge, a journey per entry point, and no positions.",
            ),
            Step(
                acts=("Placer",),
                measures=(),
                edge=("Placer", "Model"),
                say="systemap place lays the regions out on a grid with corridors between them, puts every card on it, and writes the positions into the file.",
            ),
            Step(
                acts=("Check",),
                measures=("Check",),
                edge=("Check", "Agent"),
                say="systemap check names each failure and its fix; the agent edits until coverage is N/N and the layout is clean.",
            ),
        ),
    ),
    Journey(
        id="second-pass",
        label="The second pass: judgement, then refresh",
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs systemap judgement.",
            ),
            Step(
                acts=("Judgement",),
                measures=(),
                edge=("FactsExtractor", "Judgement"),
                say="The judgement walks the imports in the facts for edges the model lacks, and the entry points for journeys it lacks.",
            ),
            Step(
                acts=("Judgement",),
                measures=("Judgement",),
                edge=("Judgement", "Agent"),
                say="One line per crossing import, per entry point without a journey, per thin layer: the agent changes the model or answers the line.",
            ),
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "Model"),
                say="The agent adds the missed edges, regroups what was grouped by directory, and reruns check; a full pass that changes nothing is the stop.",
            ),
            Step(
                acts=("Page",),
                measures=(),
                edge=("CLI", "Page"),
                say="systemap refresh renders the page and every configured figure; systemap describe says what the picture shows, and systemap serve opens the page for anyone who can look.",
            ),
            Step(
                acts=("Judgement",),
                measures=("Maintainer",),
                edge=("Judgement", "Maintainer"),
                say="The agent answers the remaining judgement lines in systemap.toml, under [judgement] answered, singly or by family; judgement --strict exits 0, and the maintainer reads the answers and commits docs/map.",
            ),
        ),
    ),
    Journey(
        id="refactor",
        label="A refactor moves a module: the maintenance path",
        steps=(
            Step(
                acts=("CI",),
                measures=(),
                edge=("CI", "CLI"),
                say="A pull request moves a module; the workflow runs systemap delta --base against the base branch and posts what the change did to the map as one comment.",
            ),
            Step(
                acts=("ChangeDetector",),
                measures=(),
                edge=("CLI", "ChangeDetector"),
                say="The detector reads the facts at both commits out of git, never from the working copy, and names the card that still names the old path, with the rename that fixes it.",
            ),
            Step(
                acts=("Check",),
                measures=("CI",),
                edge=("Check", "CI"),
                say="The job fails while a line needs a person; the comment names each fix, so the map is maintained in the pull request that changed the code.",
            ),
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent follows the maintenance path: acts on the delta's lines alone, never redrawing the map, then runs refresh, check and judgement --strict, and commits docs/map.",
            ),
            Step(
                acts=("Page",),
                measures=("Maintainer",),
                edge=("Page", "Maintainer"),
                say="The maintainer reads the page: the moved part is where the code now says it is.",
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
