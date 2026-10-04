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

from dataclasses import replace

import journeys  # the walks, beside this file: map/journeys.py

from systemap import (
    Component,
    Container,
    Flow,
    Invariant,
    Layer,
    Meaning,
    Model,
    Region,
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
    Region("keep", "KEEP TRUE", (250, 560, 380, 296), container="systemap"),
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
    Component(
        id="TypeSafe",
        does="The Jev model behind TypeSafe's HTTP API: answers typed questions about the map when a maintainer has set a key.",
        kind="actor",
        container="outside",
        x=36,
        y=276,
    ),
    # ---- operate: the commands, the configuration, what init writes ----
    Component(
        id="CLI",
        source_review="c7cda2f913a499a63bc76e27fd045734fd69044b848cd3e8c66fb0f34af50a6e",
        does="The commands the agent runs to create, inspect, check, render and update the map, and to request optional second opinions. Mechanical failures return a nonzero status. An optional second opinion can fail while the mechanical report remains successful.",
        interface="main(argv) -> exit code: 0 current, 1 failed or stale, 2 unusable",
        implemented_by=("systemap.cli", "systemap.__main__"),
        entry="main",
        region="operate",
        x=460,
        y=120,
    ),
    Component(
        id="Scaffold",
        source_review="dfd23cf19395df535c4534a8c615bd88601221ec6c44005c3f8f814f96976542",
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
        source_review="cdec022c224ca10fe44d446b663edea354594773508708982aee037fd34a4105",
        does="systemap.toml, or [tool.systemap] in pyproject.toml, resolved with defaults: package roots, test directories and test-file patterns, source-language settings discovered, judgement answers kept with their reasons. Unknown keys, ignores and answers without a reason are refused.",
        interface="load(root) -> Config; load_model(path) -> (MODEL, MEANING); discover_typescript_roots(root)",
        implemented_by=(
            "systemap.config",
            "systemap.language_config",
            "systemap.typescript_config",
        ),
        entry="load",
        kind="store",
        region="operate",
        x=460,
        y=212,
    ),
    # ---- gather: the mechanical truth ----
    Component(
        id="FactsExtractor",
        source_review="09b3695891733ae83c65ae937d8a3ac30ab9faeeda156bec38fde9674423c890",
        does="Walks the package's syntax tree and writes the facts: every module, its public surface and every public name, what it imports inside and outside the package, the tests that import it, and where a run can start. TypeScript syntax it cannot parse or classify is marked unknown. Nothing anyone writes changes what it finds; systemap facts reads them back one view at a time.",
        interface="build(cfg) -> facts; drift(fresh, stored) -> what no longer matches",
        implemented_by=(
            "systemap.extract",
            "systemap.facts",
            "systemap.language",
            "systemap.typescript",
            "systemap.typescript_surface",
            "systemap.ways_in",
        ),
        entry="build",
        region="gather",
        x=698,
        y=120,
    ),
    Component(
        id="ChangeDetector",
        source_review="784ffcff55a3c60971de58884f43d3b741f4a9b7fa0c206603c774656a02a07a",
        does="Compares source revisions in the map's terms: changed modules and public names, renamed modules, and parts that directly import changed modules. systemap delta compares facts at two commits and reports findings with their fixes. systemap history compares commits through time and reports structural changes.",
        interface="compute(cfg, model, base, facts, head) -> change; delta.compute(cfg, model, meaning, base facts, head facts) -> Delta",
        implemented_by=(
            "systemap.change",
            "systemap.delta",
            "systemap.delta_report",
            "systemap.moves",
            "systemap.history",
            "systemap.trend",
        ),
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
        source_review="5e19b3def93c484ab3f9c6e0fe33557b97e315e821e8904e34eac6f2fdec6ece",
        does="The schema a map is written in, and the file the agent writes in it: containers, regions, components, flows, invariants, and the meaning tables. Checks that the meaning names only what the model has, classifies flow evidence as observed, structural, external or declared, binds card reviews to source and claims, and loads the tree of maps when a card opens a map of its own.",
        interface="Model(canvas, containers, regions, components, flows, flow_kinds, invariants) and Meaning(plain, layers, relations, journeys, verbs), exported by map/model.py as MODEL and MEANING",
        implemented_by=(
            "systemap.model",
            "systemap.card_review",
            "systemap",
            "systemap.evidence",
            "systemap.nest",
            "systemap.graph",
        ),
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
        source_review="3442a43dd10a79378d4919935e61836daf36566360e26dee7674578190c19b2f",
        does="Draws the SVG: cards marked by kind, routes coloured by layer, and the interaction script that lights a clicked component's neighbours, switches readings, shows selected journey steps, pans and zooms. The theme is one table of tokens.",
        interface="render(model, meaning, theme, facts) -> (svg, detail JSON)",
        implemented_by=(
            "systemap.schematic",
            "systemap.schematic_cards",
            "systemap.schematic_style",
            "systemap.schematic_script",
            "systemap.schematic_relations",
            "systemap.theme",
        ),
        entry="render",
        region="draw",
        x=888,
        y=452,
    ),
    Component(
        id="Page",
        source_review="e29173cf261b4bd6b6186d74db201f9d3f4153b037d373d7bfb0de0668f6ce0e",
        does="Builds the self-contained map page. The authored drawing, exact relationships, journeys and source records share one inspector. A reading view lists the same parts and flows. Recorded judgement reasons and revision comparisons support review. No fonts, scripts or images are fetched.",
        interface="build(cfg, model, meaning, theme, facts, change) -> html",
        implemented_by=(
            "systemap.page",
            "systemap.page_data",
            "systemap.page_assets",
            "systemap.page_script",
            "systemap.page_atlas",
        ),
        entry="build",
        region="draw",
        x=888,
        y=360,
    ),
    Component(
        id="Figures",
        source_review="70db73470d3a70648bdcde0d4cd47d015d78f8944d32bddcd77ccd363387d494",
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
        source_review="279ea7508383928d578d3faeb28c9e6c9e30bf65430114ab7540ac106c93aff1",
        does="Checks coverage, entry, interface, unknown TypeScript surface, placement, routes, labels, card text, type size, meaning, wheels and stale outputs. It reports the findings together and exits 1 when any remain.",
        interface="run(model, meaning, theme, facts, ignores) -> Result; stale(cfg, tree, fresh=None) -> lines",
        implemented_by=("systemap.check",),
        entry="run",
        region="keep",
        x=270,
        y=692,
    ),
    Component(
        id="Judgement",
        source_review="d6fcd831272f078df209b4318c560fe06ac8817640cc29c117a8fba3499c59ca",
        does="The list the agent acts on and the maintainer confirms: single-module components, odd folds, flows without a sentence, thin layers, entry points without a journey, imports across a boundary with no flow, model SDK imports outside an agent, and unknown TypeScript surface. Accepted exact answers and explicit family policies suppress lines and are counted. A report; a gate only with --strict. Before any of it, systemap suggest proposes a first grouping from the facts, to argue with.",
        interface="run(model, meaning, facts, sdks) -> lines; exit 1 with --strict while a line is open",
        implemented_by=(
            "systemap.judgement",
            "systemap.judgement_evidence",
            "systemap.journey_coverage",
            "systemap.suggest",
            "systemap.explain",
        ),
        entry="run",
        region="keep",
        x=270,
        y=600,
    ),
    Component(
        id="SecondOpinion",
        source_review="da68992ee1ab16f9eaed3e3c9320ac4ac69393d74a6e5e71f1623bdc5eef45e4",
        does="Help from outside this process, asked one narrow question at a time and cached: the Jev model for what judgement cannot read from names and imports (a module that reads like another card, a card for an unclaimed module, a sentence that may not describe its modules, a flow the code may not carry, an invariant that may govern a card it does not name, the cards an issue will change), and a coding agent named in the configuration for prose only a reader of the code can write. Opt-in; never a gate.",
        interface="run(tree, facts, cfg, jev) -> lines; commands return 1 when an optional request fails",
        implemented_by=(
            "systemap.audit",
            "systemap.jev_cli",
            "systemap.jev",
            "systemap.agent",
            "systemap.journeys",
            "systemap.model_write",
            "systemap.plan",
        ),
        entry="run",
        region="keep",
        x=460,
        y=600,
    ),
    Component(
        id="Describe",
        source_review="5b9f13776fb71c418d524b72c7af8fa9a809454f180949443949277d95fb471b",
        does="What a look at the picture would tell an agent that cannot look: cards per region, bends and length per edge worst first, seats used per gutter, cards and edges per reading. A description, never a rule.",
        interface="run(model, meaning, theme, facts) -> lines; describe returns 1 when the model cannot be drawn",
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
# Current source snapshots and exact semantic claim digests for reviewed flows.
# A changed source or sentence reopens its flow for judgement.
# fmt: off
_SOURCE_SHA = {
    'systemap.audit': '8c2c6974b91df12b47d3a334b092211d1255a958537dde216f027ca8bd47b0bf',
    'systemap.card_review': 'e477ddde264e26d5fc00120f5e6de127e7fc47616f5dea8c33927ea3e29a0661',
    'systemap.change': '7685b91de903c3cbba0644216abb7af3ed185cb003420020e5dbfa1c6eadbd90',
    'systemap.check': '40bf80cd5e1c6b1fe7949ece80b2867d3ebc0072f141d8088e3e6fc3cb0867de',
    'systemap.cli': '6de716af24260bde416c8cfd76c836afa9ee6fec3815f58c2427fefb3b07ea53',
    'systemap.config': 'd2c3051747c67b4c9faee6dcbc94b50e5d964fba20901cdd97059b3cff39c349',
    'systemap.delta': '4c06f00460270a5ba39913f3240d7be00f6e533bc8fd8f6a9baa80b49fb475f7',
    'systemap.delta_report': 'eb5fc9017a13448bd219188311cb393d2b3484f3d3cc6f046e73d8c067ad3a0d',
    'systemap.describe': '196deff594790817ba54d1991cd84a42e107ea40d6b9585656469bb58630121c',
    'systemap.evidence': 'f9f3368ff30ae1f79d3cea3c778ca3b7ae0b6d0bb238f37236621e9f9e4bb5f3',
    'systemap.explain': '26b83bedab12025d416497e50d1c37eddf117680ec6263de78be167a75f6e7cd',
    'systemap.extract': '5468e4325d42fe4cb04c2e271ddf257b0eed9f887a9d58ca858789af241935d6',
    'systemap.facts': '7fc8aea937a2c023beb4eae2b73f0861e0a9581da6a1c7d55fcd5c6aacd5f78d',
    'systemap.figure': 'bc7ddac9e176f75223a5eb20a46b8a149ddc22f28b4928ef841ff0d87e2ee9fc',
    'systemap.jev_cli': '663bcbb6075bafedf9d44569b2b564151b7e7f518b4503c697cb79b899ef8e83',
    'systemap.journey_coverage': '45a2eaec9f26ccc46a6a24ac30db2b52aab219ece8f101ed0e7ed80f335991e0',
    'systemap.journeys': 'a6d377d8a65346a916e58b5bb141c870db2718c6c20ce7273a8a7b18c37cc0e5',
    'systemap.judgement_evidence': '26baca328b93b1776b31a979e92c998a13f786e5c69554e46175b1dc4f9787bc',
    'systemap.judgement': '4acbe559dd098ab0b1d85cb659091c6d8986602e8a71f03673742d20d1be08f6',
    'systemap.model': '84fedf8cd3bc8ea1d25488013bc4091cec6a5ba3f8e9edd0bef1593a39765dc0',
    'systemap.nest': '937fc07562507dbdf771033894d9840d72df27b084cff0c6700038de28ecba7c',
    'systemap.page': 'b7ba31d18e34c5e2d38c661de7db5035b03303e0c53513c62d24d43419872bff',
    'systemap.place': '753ad42b2d53f0bc814581c85f0b3a6b151f2362ba31ef109422e7bba409f9a2',
    'systemap.route': 'cec265419b277416b9da9344d963ce2e6da054792bac4a46964a6f85b993014f',
    'systemap.scaffold': '9c6991a29fe6622c8296df838e89ad2021d75873fff2cd01f451a4ea7b7641a4',
    'systemap.schematic': 'ab5e4fd08a2437768580b571d2016c82b3cb473717890f14b2718172da78850b',
    'systemap.skill': '499a59f3682005638afa2d38aa63b69e5f0aeaaad6c922e8445d7b2b2698d8e5',
    'systemap.page_data': '88d998342e1a3b3f88db5345991359a3373aa187eb4659531186e97546b02a1a',
}

_FLOW_REVIEWS = {
    'CLI -> Scaffold': ('systemap.cli systemap.scaffold', 'd69eb93579f4a8e8d708548623da2b2b9e1116304733ebe113cf5b802baaa50f'),
    'CLI -> Placer': ('systemap.cli systemap.place', '995dd35aa8d3bb068d49f43d18128e45c3617eaa4cdf9bc894bdba1e9226bbe6'),
    'CLI -> Skill': ('systemap.cli systemap.skill', '7dab29d464fadc20b7badc548de5bd100cced6060aa8da75260b37829838337c'),
    'CLI -> FactsExtractor': ('systemap.cli systemap.extract systemap.facts', '2ce65d96fc8c1fb53283ae3697fc8159d422cfa26301bcbf21236bd7d73a5f6b'),
    'CLI -> ChangeDetector': ('systemap.cli systemap.change systemap.delta systemap.delta_report systemap.figure', 'b7f6b8c2e60243418c3080a6e6412ab98648178ef3815c2dc8d6ccf34ceb48ea'),
    'CLI -> Check': ('systemap.cli systemap.check', '122cb016193aaa95bd743206d5bfb79f87e9b85d45d5bf061e6f0f7b462e878c'),
    'CLI -> Page': ('systemap.cli systemap.page', '1e5179ea9fc21a2e5c2e892dcf64076b0cff24a4d1e12821cd639abbcbcbc548'),
    'CLI -> Figures': ('systemap.cli systemap.figure', '38f93fa42cc3652ff718b91dd681afe8ab3738802d446d4b626a24a0b0017972'),
    'CLI -> Judgement': ('systemap.cli systemap.judgement', '45a01299fe5d5d00423f9bddf292770e2ea4f610d53c32df2b164951486c4444'),
    'CLI -> Describe': ('systemap.cli systemap.describe', '41fb78ae3033dd6c8b25d6e1ae3bfe5431b4b98c3f1262dbc872cb02cc0cd57b'),
    'CLI -> SecondOpinion': ('systemap.cli systemap.jev_cli', '53e319d6c2e79990db523dd46d222a94f4c019341c7aef42f76a8d0257bcd122'),
    'Check -> Page': ('systemap.check systemap.page', '8ef310c6b315a6a1c12cbab9f386222a31f64c551e748c76f2ff93cef1474e0d'),
    'Check -> Figures': ('systemap.check systemap.figure', 'c1bc08ce9093edbac14a611fbc89636176d4fc17ff26087289cce814379c3af9'),
    'Check -> ChangeDetector': ('systemap.check systemap.delta', '6cce24aa5d5eae1f2c17426c0b722bd6ba85a4d55e7db8ed43444ab6c35d74f3'),
    'Config -> CLI': ('systemap.config systemap.cli', 'dcfa6a328a0536027170ef1126b968d1020abae1c25ca29d77ed30422c598133'),
    'Config -> FactsExtractor': ('systemap.config systemap.extract', '9267b1ff08c5514418ae60ab7cb3aa98bff3a3a765d0ed4fd3f10aceb34daa55'),
    'Config -> ChangeDetector': ('systemap.config systemap.change', '24a1b1131f04a8af1d9d66f31221c88ca47dcc5d2a506edd0291057270548f4e'),
    'Config -> Page': ('systemap.config systemap.page', 'aac2ae34a244c0962a5fd26500827644d51fb6c88dabc1d6856ff2a5ffb13ba1'),
    'Config -> Figures': ('systemap.config systemap.figure systemap.cli', '825992e329547ee45a040980be6d3eb58a7f768ba371ae4c09bd8da29ed9146c'),
    'Config -> Check': ('systemap.config systemap.check systemap.cli', '8a150a1624bb33d0a306abff17daaaf8e29d014c2f13917c12f988a049635a9d'),
    'Config -> Judgement': ('systemap.config systemap.judgement systemap.judgement_evidence systemap.cli', '49945b6716ba48ab5476e503ef0a9e83a0a50b7094a9b496af09181a4169a544'),
    'Config -> SecondOpinion': ('systemap.config systemap.jev_cli systemap.audit', 'a58c2233b6429362e80facabf4bff86872b891b549831741bfef79346f50697d'),
    'FactsExtractor -> SecondOpinion': ('systemap.jev_cli systemap.audit', '6d1e64932828cd751159ffd02f8e5b6632191a22a69200cb285db7adc2fb94cc'),
    'SecondOpinion -> ChangeDetector': ('systemap.jev_cli systemap.cli systemap.delta', '75fafe32a725f0cf5a916e3c123fde99f9c4c6243e85b7576ac7b1f4a302b1a2'),
    'Judgement -> SecondOpinion': ('systemap.journey_coverage systemap.journeys', '2dcbd12fc22491ba1500366323cdbeedbd5a79b2402665bafd9dc2d45b850f61'),
    'SecondOpinion -> Describe': ('systemap.journeys systemap.describe', 'db9df73a98e8008668626d57ce8e549d359a8e9f89ba84e77681e56a687d851f'),
    'FactsExtractor -> Describe': ('systemap.extract systemap.describe', '73f9422f2aa0b57b5d57ba01b210be7a4b3251d8c5a3bc15862cdd59528d7828'),
    'Scaffold -> Model': ('systemap.scaffold systemap.cli', '6c904305c3506de60838589165ab2f35f28de6e3be86250d2a82a2377e8358db'),
    'FactsExtractor -> Check': ('systemap.extract systemap.check', '2519575b8d32c417794beb0fed8914a95a9c9e077cf6679ea43b856c00897740'),
    'FactsExtractor -> Schematic': ('systemap.extract systemap.schematic systemap.evidence', '319fb1e9192f6472586a635284ce066c7176277883dec8cb06f528155bd4d58e'),
    'FactsExtractor -> Judgement': ('systemap.judgement systemap.journey_coverage', 'c9f835888d25733ebd20c8bae1dda9153dfb2ba5a3b170e18fa3e1347b7c5231'),
    'FactsExtractor -> ChangeDetector': ('systemap.extract systemap.change', 'b7b99b569790feda9040714cc0c5393ce76fdbee283926dc872ad3a5a6bc2867'),
    'ChangeDetector -> Page': ('systemap.change systemap.cli systemap.page', 'fa3e5953cb42c7d1d72ac66e4bad6dc029712bdf88d7ffed92b4738d75138fd5'),
    'ChangeDetector -> Figures': ('systemap.change systemap.figure', '47cf6b5287234dc82a88249b05fd294abd0937b7645d04d3ef746ef3a8e16952'),
    'Model -> Placer': ('systemap.model systemap.place', 'f26fd830df40bce6a649389ad6dee626c8e3c08f04b4f58eea68b1a2df150291'),
    'Placer -> Model': ('systemap.place', '3a88def8f0aeab3e8477e8a33eb24e226b9d6fe53041f2a8521ff31d26a933fa'),
    'Model -> FactsExtractor': ('systemap.model systemap.extract', '48a9f4a4ee9c83cb45b7bf66b6294dbe2472aedba4dcbe3f76b348245b874ac1'),
    'Model -> ChangeDetector': ('systemap.model systemap.card_review systemap.change systemap.delta', '1c34991097a893911ddffa699040f12f929cde1eed6d45caafd5f73abe25a5d5'),
    'Model -> Schematic': ('systemap.model systemap.schematic', '452e787fb91022f66f3035a2ec3f8823d7b4c015069d65c7b92169db81ca4073'),
    'Model -> Check': ('systemap.model systemap.check', 'e0c41a068acc1a0275328bec0b7885576df9d51714f62cc2eaada0a71955714d'),
    'Model -> CLI': ('systemap.model systemap.nest systemap.cli', '20688cabac944689993f8a9406a4747b689d82004e6079b21730571712319848'),
    'Config -> Model': ('systemap.config systemap.nest', '5840c70445e25a1e08338f35586acbd9072e5e0da868ba4fe8ee427b7dd013bf'),
    'Model -> Page': ('systemap.model systemap.page', '14b4f61c0ae5be2cd6613e2c0fbe5564ea618ddfef6adaf4402c4fdd01309155'),
    'Model -> Figures': ('systemap.model systemap.figure', '7bb3e7ff57099336f92e7c6af6cd5ea2d0a98f9944e9fa2222d4c48bf2a5b8b2'),
    'Model -> Describe': ('systemap.model systemap.describe', '59029a86cd59f23e039b0bf69b8eb84f6847842af02140eb4d54a002de7a80b7'),
    'Router -> Schematic': ('systemap.route systemap.schematic', '4a06b4078df346c5dc4e0b9f0dd7f65ccdd428767ebd45046f5b21c48b89ce5f'),
    'Router -> Describe': ('systemap.route systemap.describe', '8473fe7df6574586ece17acf8875fc132d245f7021e87e4b01c055d30b0fb74c'),
    'Router -> Placer': ('systemap.route systemap.place', '9625622426e864ec8a0fd0290deff8e3a97d2dfe9f435471ddd00bd2c7aa2291'),
    'Schematic -> Placer': ('systemap.schematic systemap.place', 'ff43fa256b316dc5f10fb1bf44a69e856622539bdd3eed33dbf884f77880b738'),
    'Placer -> Describe': ('systemap.place systemap.describe', '128c0ebc204acb2ebc7360ffaa91416f4f459581047b5bf3820473c0d0b85349'),
    'Schematic -> Page': ('systemap.schematic systemap.page', 'e35e5aa708990b6491b4d9c2e6838e8a18d42536c44b269b1f2c7065661e2dc3'),
    'Schematic -> Figures': ('systemap.schematic systemap.figure', '5f268b0564b1252faf387726d8d9e86afe4d0cdda0396e12978866a76fe7d286'),
    'Schematic -> Check': ('systemap.schematic systemap.check', '8643467390f169b6ecc8b742b86ffa344de85c773a878111ffc4fdd706043f3e'),
    'Schematic -> Describe': ('systemap.schematic systemap.describe', '1fac0cc5ba46abc152ab0eba2eedb008ad02671266db56e518336275ddedda23'),
    'Model -> Judgement': ('systemap.model systemap.judgement', '7048e11fed1d5b427660afd54151cfc27f0d56d7005144d5298d599e22784e19'),
    'Judgement -> Check': ('systemap.explain systemap.check', 'ffbc6d172459e4cee94b98346666857ffaabbfb90a92ba281ce95626a23c3a6b'),
    'Model -> SecondOpinion': ('systemap.model systemap.audit', 'd9a2f798126ed0062d8a428488ae1f1a0a8c4e05cdc9163a2f372a457a0275bb'),
    'Judgement -> ChangeDetector': ('systemap.judgement systemap.explain systemap.delta systemap.delta_report', '8e013ba1c8d6cd208afb256ffcbae56d08249cda7215a3e983253b1b89ca9c82'),
    'FactsExtractor -> Page': ('systemap.extract systemap.page_data', '8a2ca99b466241881e352baa8039c75ee74064657a180c4a9d872b6a215b57ec'),
    'Judgement -> Page': ('systemap.judgement systemap.page_data', 'fdfe2a116db62d3154ef699c32fb9b703df1e2f3abe45812f87d1c3c0fef87ec'),
}
# fmt: on


def _reviewed(flow: Flow) -> Flow:
    record = _FLOW_REVIEWS.get(f"{flow.src} -> {flow.dst}")
    if record is None:
        return flow
    modules, digest = record
    refs = tuple(f"{module}@{_SOURCE_SHA[module]}" for module in modules.split())
    return replace(flow, source_refs=refs, review_digest=digest)


FLOWS = tuple(
    _reviewed(flow)
    for flow in (
        # control: who drives whom
        Flow("Agent", "CLI", "commands", "control"),
        Flow("CI", "CLI", "check", "control"),
        Flow("CLI", "Scaffold", "init", "control"),
        Flow("CLI", "Placer", "place", "control"),
        Flow("CLI", "Skill", "init, skill", "control"),
        Flow("CLI", "FactsExtractor", "extract, facts", "control"),
        Flow("CLI", "Check", "check", "control"),
        Flow("CLI", "ChangeDetector", "--base, delta", "control"),
        Flow("CLI", "Page", "render", "control"),
        Flow("CLI", "Figures", "figure", "control"),
        Flow("CLI", "Judgement", "judgement", "control"),
        Flow("CLI", "Describe", "describe", "control"),
        Flow("CLI", "SecondOpinion", "audit, journeys, plan, triage, --jev", "control"),
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
        Flow("Config", "SecondOpinion", "answers, model, cache", "data"),
        Flow("FactsExtractor", "SecondOpinion", "map.json", "data"),
        Flow("SecondOpinion", "TypeSafe", "questions", "data"),
        Flow("TypeSafe", "SecondOpinion", "typed answers", "data"),
        Flow("SecondOpinion", "ChangeDetector", "moves Jev read", "data"),
        Flow("Judgement", "SecondOpinion", "the ways in with no walk", "data"),
        Flow("SecondOpinion", "Describe", "the ways in with no walk", "data"),
        Flow("FactsExtractor", "Describe", "entry points", "data"),
        Flow("Scaffold", "Model", "starter", "data"),
        Flow("FactsExtractor", "Check", "map.json", "data"),
        Flow("FactsExtractor", "Schematic", "map.json", "data"),
        Flow("FactsExtractor", "Judgement", "entry points", "data"),
        Flow("FactsExtractor", "ChangeDetector", "surfaces", "data"),
        Flow("FactsExtractor", "Page", "source records", "data"),
        Flow("ChangeDetector", "Page", "change map", "data"),
        Flow("ChangeDetector", "Figures", "change", "data"),
        Flow("Model", "Placer", "cards, flows", "data"),
        Flow("Placer", "Model", "positions", "data"),
        Flow("Model", "FactsExtractor", "claims", "data"),
        Flow("Model", "ChangeDetector", "claims", "data"),
        Flow("Model", "Schematic", "topology, meaning", "data"),
        Flow("Model", "Check", "model", "data"),
        Flow("Model", "CLI", "loaded map", "data"),
        Flow("Config", "Model", "model path, loaded map", "data"),
        Flow("Model", "Page", "layers", "data"),
        Flow("Model", "Figures", "layers", "data"),
        Flow("Model", "Describe", "readings", "data"),
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
        Flow("ChangeDetector", "Agent", "what moved, and when", "data"),
        Flow("Check", "CI", "verdict", "data"),
        Flow("Judgement", "ChangeDetector", "crossing rules, answers, lessons", "data"),
        # judge: where the meaning comes from, and who confirms it
        Flow("Skill", "Agent", "procedure", "judge"),
        Flow("Agent", "Model", "map/model.py", "judge"),
        Flow("Maintainer", "Model", "corrections", "judge"),
        Flow("Model", "Judgement", "model", "judge"),
        Flow("Judgement", "Check", "the teaching under each line", "judge"),
        Flow("Judgement", "Page", "findings and reasons", "judge"),
        Flow("Judgement", "Agent", "second-pass list", "judge"),
        Flow("Judgement", "Maintainer", "judgement answers", "judge"),
        Flow("Model", "SecondOpinion", "cards, sentences", "judge"),
        Flow("SecondOpinion", "Agent", "jev lines", "judge"),
    )
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
        governs=("Model", "Placer", "Router", "Check", "Schematic"),
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
    Invariant(
        11,
        "check and judgement never reach the network; asking Jev is a separate command that sends nothing without a key (src/systemap/jev_cli.py, docstring).",
        governs=("Check", "Judgement", "SecondOpinion"),
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
    "ChangeDetector": "Compares source revisions",
    "Skill": "the procedure the agent follows",
    "Model": "the map as written",
    "Router": "what finds the routes",
    "Schematic": "what draws the map",
    "Page": "Builds the map page",
    "Figures": "a picture for a document",
    "Check": "what refuses",
    "Judgement": "what asks",
    "Describe": "what the picture shows",
    "SecondOpinion": "what asks for a second opinion",
    "TypeSafe": "the model asked",
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

# One sentence per flow, keyed "from -> to".
_RELATIONS = {
    "Agent -> CLI": "The agent drives everything through the commands; it never imports the package.",
    "CI -> CLI": "The workflow init writes runs the check on every push and pull request.",
    "CLI -> Scaffold": "init hands the scaffold the project's name and package roots; the scaffold writes what does not exist yet.",
    "CLI -> Skill": "init installs the bundled skill directory beside the project. The skill command reinstalls it when requested.",
    "CLI -> Placer": "place computes a position for every card without one, or with --all for every card not pinned, and writes it into the model; describe places them for one look without writing.",
    "Router -> Placer": "The placer routes every shortlisted region order with the router and the label pass, and keeps the order with the fewest label collisions, refused routes, bends and length.",
    "Schematic -> Placer": "The placer scores a candidate layout on the drawing's own geometry (the card boxes, the headers and empty containers as walls, what a label may not sit on) and reads the header measurements so a box it lays out holds its header.",
    "Placer -> Describe": "Describe reads the region order off the map as placed and the score of the drawing under it, and says how many orders place tried when it chose the order for the look.",
    "CLI -> FactsExtractor": "extract and the first step of refresh build facts over the configured package roots. facts reads the stored result by module or view.",
    "CLI -> ChangeDetector": "render --base and figure --base ask the change detector what a git range moved; delta asks it what a change did to the map, from the facts at two commits.",
    "CLI -> Check": "check runs every rule and prints each failure with its fix; refresh runs the same rules before it renders.",
    "CLI -> Page": "render, and refresh, build the page from the facts and the model.",
    "CLI -> Figures": "figure draws one figure to a file; refresh draws every figure the configuration lists.",
    "CLI -> Judgement": "judgement prints the list to act on or answer; with --strict it exits 1 while a line is open.",
    "CLI -> Describe": "describe draws the map the way the page does and prints what the drawing shows, in numbers.",
    "Check -> Page": "The stale rule renders the page from the stored facts and compares it with the committed one.",
    "Check -> Figures": "The stale rule renders every configured figure and compares it with the committed one.",
    "Check -> ChangeDetector": "delta judges an interface name that vanished by the check's own interface rule, so the two cannot disagree about what a line may start with.",
    "Config -> CLI": "The configuration tells the commands where the packages, the model and the output are.",
    "Config -> FactsExtractor": "The package roots and the tests directory say what the extractor walks.",
    "Config -> ChangeDetector": "The package roots and the tests directory say which changed files are modules and which are tests.",
    "Config -> Page": "The page takes its title, its footer paths and the label for actors outside every region from the configuration.",
    "Config -> Figures": "The [[figures]] table says which figures refresh regenerates, in which mode, to which file.",
    "Config -> Check": "An ignore with a reason takes a module out of the coverage rule, on record.",
    "Config -> Judgement": "Judgement applies configured reasons when their evidence or explicit policy is accepted. The [facts] model_sdks list extends or reduces the SDK names it checks.",
    "Scaffold -> Model": "init writes an empty starter model with regions but no cards. The agent adds cards from the facts before check can pass.",
    "FactsExtractor -> Check": "The facts are what the check judges coverage, entry and staleness against.",
    "FactsExtractor -> Schematic": "The schematic uses extracted facts to show each card's code state and entry module, and to show whether a flow has source or structural evidence.",
    "FactsExtractor -> Judgement": "The entry points in the facts are what the judgement asks journeys for; the imports are what it walks for crossing edges.",
    "FactsExtractor -> ChangeDetector": "The change detector reads a module's public surface with the extractor's parser, on both sides of the diff, so the two cannot disagree about what a module exports.",
    "ChangeDetector -> Page": "With --base, the page carries a source comparison: what changed and which parts directly import changed modules. This adjacency does not prove execution or impact.",
    "ChangeDetector -> Figures": "For a git range, the change detector supplies the changed and adjacent cards to the figure. A plan reach figure gets its card ids directly and does not use the change detector.",
    "Model -> Placer": "The placer reads the cards, their regions and the flows between them; a card with x and y is kept, and with --all only a pinned card is.",
    "Placer -> Model": "The placer writes the positions, the boxes and the canvas into map/model.py in place; the rest of the file is kept byte for byte.",
    "Model -> FactsExtractor": "The extractor reads the model's claims to warn about a module the tree no longer has.",
    "Model -> ChangeDetector": "The change detector attributes changed modules to their cards and compares each card's recorded source review with the digest of its current source and claims.",
    "Model -> Schematic": "The model is the topology the schematic draws and the meaning it prints on the wheel.",
    "Model -> Check": "The check reads the model's contradictions before drawing. It still checks coverage, entries and interfaces when the model has a contradiction.",
    "Model -> CLI": "The commands load the model and its meaning through the map tree. They check model contradictions before rendering and use the model for other commands.",
    "Config -> Model": "The map tree uses the configured model path and the loader's MODEL and MEANING values. The loader checks their schema before returning them.",
    "Model -> Page": "The page reads components, layers, journeys and invariants from the model and meaning to build its controls and text.",
    "Model -> Figures": "The figure reads components and layers from the model and meaning to choose the drawing and its caption.",
    "Model -> Describe": "Describe reads components, flows, regions and layer readings from the model and meaning to explain the drawn geometry.",
    "Router -> Schematic": "The router hands back the routes and the seated labels, and reports what could not be placed cleanly, with the fix that applies.",
    "Router -> Describe": "The router's gutters and seat counts are what describe reports per gutter.",
    "Schematic -> Page": "The page embeds the SVG and the detail JSON the interaction script reads.",
    "FactsExtractor -> Page": "The page presents stored source records for a selected part. Imports show connections, not proof of the authored explanation.",
    "Judgement -> Page": "The page retains the judgement's exact finding identifiers and recorded reasons accepted under its evidence and policy rules.",
    "Schematic -> Figures": "A figure is the same SVG in a figure element, or bare for an image.",
    "Schematic -> Check": "The check renders once and reads the geometry back: routes, labels, type size, wheels.",
    "Schematic -> Describe": "describe renders once and reads the geometry back as a description: regions, edges, gutters, readings.",
    "Describe -> Agent": "An agent that cannot open the page reads the picture in numbers after every refresh.",
    "Page -> Maintainer": "The maintainer opens the page: readings, click, journeys, pan and zoom.",
    "Check -> Agent": "Every failure names its fix; the agent edits until coverage is complete and the layout is clean.",
    "Check -> CI": "Exit 1 fails the pull request; the message says what to run.",
    "Skill -> Agent": "The skill gives the agent the loop, the schema, a worked example, the second pass, and what to hand back.",
    "Agent -> Model": "The agent writes map/model.py: the groupings, the flows, the sentences, the journeys, the invariants.",
    "Maintainer -> Model": "The maintainer corrects the calls they disagree with; the model is theirs once reviewed.",
    "Model -> Judgement": "The judgement reads the model for the calls that could have gone another way.",
    "Judgement -> SecondOpinion": "Which ways into the system a journey walks from is one rule, and it lives in the judgement; the writer of journeys asks it what is left, so the two cannot disagree about what is covered.",
    "Judgement -> ChangeDetector": "Delta reuses judgement's answer matching and crossing-import grouping for changed imports. Its report renderer reads the explanation for each kind of finding.",
    "SecondOpinion -> Describe": "Describe asks the writer of journeys how many ways into the system have no walk from them, and names the first few.",
    "FactsExtractor -> Describe": "Describe names each way in the way a person would name it, which the extractor decides.",
    "ChangeDetector -> Agent": "delta hands back what a change did to the map, one line per thing with its fix; history hands back what moved over a year, the largest windows first with the commits that wrote them.",
    "Judgement -> Check": "The lesson under each kind of line lives with the judgement, because that is where most kinds come from; the check reads it to say why a failing rule matters and what to do.",
    "Judgement -> Agent": "In the second pass the agent walks every crossing import and every entry point without a journey, and changes the model or answers the line.",
    "Judgement -> Maintainer": "The maintainer reads the agent's answers, line by line; the list is mechanical to produce, so the review cannot be skipped.",
    "CLI -> SecondOpinion": "audit, journeys, plan, triage and the --jev flags run second-opinion commands. check and judgement do not call those services.",
    "Config -> SecondOpinion": "The configuration names the model, where its answers are cached, and the answers that suppress a jev line.",
    "FactsExtractor -> SecondOpinion": "The facts give each question its state: a module's docstring, names and imports, and the lines where two cards meet.",
    "SecondOpinion -> TypeSafe": "One typed question at a time goes over HTTPS with the maintainer's key; nothing goes without it.",
    "TypeSafe -> SecondOpinion": "Jev sends back a probability or a choice with its distribution, which is cached by model release and question.",
    "SecondOpinion -> ChangeDetector": "For delta --jev, the modules delta's own rules left unpaired go to Jev, and the new module it reads each as becomes one more move in delta's report.",
    "Model -> SecondOpinion": "The model's cards, sentences, flows and invariants are what the questions ask about.",
    "SecondOpinion -> Agent": "The agent gets a jev line where the answer disagrees with the map, to act on or answer like a judgement line; when the configuration names an agent command, it is also asked the questions whose answer is prose.",
}
RELATIONS = {(k.split(" -> ")[0], k.split(" -> ")[1]): v for k, v in _RELATIONS.items()}

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

JOURNEYS = journeys.JOURNEYS

MEANING = Meaning(
    plain=PLAIN,
    layers=LAYERS,
    layer_of_kind=LAYER_OF_KIND,
    relations=RELATIONS,
    journeys=JOURNEYS,
    verbs=VERBS,
    verb_overrides=VERB_OVERRIDES,
)
