"""A workspace-shaped map fixture: two packages, 144 modules, 27 cards, four agents.

Anonymised from a real repository's first map: the package and the ids
are renamed by one uniform word substitution, so every word-sharing
relation between ids, prose and module paths is the one the real map
had. The mis-fold heuristic is measured on it: the last-segment rule of
0.4.1 fired 112 times here; the 0.5.0 rule is asserted in
tests/test_judgement.py.

`MODULES` is the module list `systemap extract` read; `facts()` wraps it
as the minimal facts the judgement reads (module names only).
"""

from __future__ import annotations

from typing import Any

from systemap import (
    Component,
    Container,
    Flow,
    Invariant,
    Journey,
    Meaning,
    Model,
    Region,
    Step,
)

MODULES: tuple[str, ...] = (
    "wharf_contracts",
    "wharf_contracts.__main__",
    "wharf_contracts.components",
    "wharf_contracts.frame_identity",
    "wharf_contracts.gateway",
    "wharf_contracts.geometry",
    "wharf_contracts.limits",
    "wharf_contracts.ops",
    "wharf_contracts.page_model",
    "wharf_contracts.registries",
    "wharf_contracts.reports",
    "wharf_contracts.sources",
    "wharf_contracts.styleguide",
    "wharf_contracts.validators",
    "wharf_contracts.wire",
    "wharf_server",
    "wharf_server.artifacts",
    "wharf_server.artifacts.disk_store",
    "wharf_server.artifacts.registry",
    "wharf_server.component_generator",
    "wharf_server.component_generator.library",
    "wharf_server.config",
    "wharf_server.config.governance",
    "wharf_server.config.models",
    "wharf_server.config.provisional",
    "wharf_server.content",
    "wharf_server.content.document_tuning",
    "wharf_server.content.documents",
    "wharf_server.content.extraction_provider",
    "wharf_server.content.plan_eval",
    "wharf_server.content.planner",
    "wharf_server.content.refusal",
    "wharf_server.content.tabular",
    "wharf_server.content.tieouts",
    "wharf_server.content.tuning",
    "wharf_server.edit",
    "wharf_server.gateway",
    "wharf_server.gateway.__main__",
    "wharf_server.gateway.app",
    "wharf_server.gateway.errors",
    "wharf_server.gateway.extraction_run",
    "wharf_server.gateway.jobs",
    "wharf_server.gateway.routes",
    "wharf_server.gateway.store",
    "wharf_server.gateway.stub_run",
    "wharf_server.hashing",
    "wharf_server.layout",
    "wharf_server.layout.precheck",
    "wharf_server.layout.registry",
    "wharf_server.layout.solver",
    "wharf_server.layout.spacing",
    "wharf_server.layout.typestyles",
    "wharf_server.layout.validation",
    "wharf_server.lineage",
    "wharf_server.lineage.datasets",
    "wharf_server.lineage.errors",
    "wharf_server.lineage.source_line",
    "wharf_server.measure",
    "wharf_server.measure.api",
    "wharf_server.measure.decided",
    "wharf_server.measure.faces",
    "wharf_server.measure.text",
    "wharf_server.measure.tolerance",
    "wharf_server.mirror",
    "wharf_server.orchestration",
    "wharf_server.orchestration.agents",
    "wharf_server.orchestration.agents.wharf",
    "wharf_server.orchestration.agents.wharf.agent",
    "wharf_server.orchestration.import_boundary",
    "wharf_server.orchestration.ledger",
    "wharf_server.orchestration.prompts",
    "wharf_server.orchestration.roster_client",
    "wharf_server.orchestration.single_shot",
    "wharf_server.orchestration.telemetry",
    "wharf_server.prompts",
    "wharf_server.prompts.compose",
    "wharf_server.prompts.design_skills",
    "wharf_server.prompts.extraction_schemas",
    "wharf_server.prompts.loader",
    "wharf_server.quality",
    "wharf_server.render",
    "wharf_server.render.__main__",
    "wharf_server.render.app",
    "wharf_server.render.cpu",
    "wharf_server.render.deadline",
    "wharf_server.render.emit",
    "wharf_server.render.emit.annotation",
    "wharf_server.render.emit.assembler",
    "wharf_server.render.emit.chart",
    "wharf_server.render.emit.chart_plan",
    "wharf_server.render.emit.chart_surgery",
    "wharf_server.render.emit.context",
    "wharf_server.render.emit.decor",
    "wharf_server.render.emit.domains",
    "wharf_server.render.emit.errors",
    "wharf_server.render.emit.frame",
    "wharf_server.render.emit.group",
    "wharf_server.render.emit.image",
    "wharf_server.render.emit.master",
    "wharf_server.render.emit.opc",
    "wharf_server.render.emit.oxml",
    "wharf_server.render.emit.package",
    "wharf_server.render.emit.page",
    "wharf_server.render.emit.shape",
    "wharf_server.render.emit.styles",
    "wharf_server.render.emit.table",
    "wharf_server.render.emit.text",
    "wharf_server.render.emit.text_plan",
    "wharf_server.render.emit.validators",
    "wharf_server.render.fonts",
    "wharf_server.render.jobs",
    "wharf_server.render.pool",
    "wharf_server.render.profiles",
    "wharf_server.render.raster",
    "wharf_server.render.service",
    "wharf_server.render.suite",
    "wharf_server.render.tuning",
    "wharf_server.sandbox",
    "wharf_server.sandbox.container",
    "wharf_server.sandbox.errors",
    "wharf_server.sandbox.runner",
    "wharf_server.sandbox.tuning",
    "wharf_server.style",
    "wharf_server.style.cache",
    "wharf_server.style.compiler",
    "wharf_server.style.completer",
    "wharf_server.style.completion_eval",
    "wharf_server.style.drawml",
    "wharf_server.style.gallery",
    "wharf_server.style.hardening",
    "wharf_server.style.inheritance",
    "wharf_server.style.inspect",
    "wharf_server.style.invalidation",
    "wharf_server.style.measurements",
    "wharf_server.style.pointers",
    "wharf_server.style.recompile",
    "wharf_server.style.records",
    "wharf_server.style.review_packet",
    "wharf_server.style.schema",
    "wharf_server.style.selection",
    "wharf_server.style.shapes",
    "wharf_server.style.tokens",
    "wharf_server.style.tuning",
    "wharf_server.style.walker",
)


def facts() -> dict[str, Any]:
    """Minimal facts: one empty record per module, keyed by name."""
    return {
        "packages": ["wharf_contracts", "wharf_server"],
        "entry_points": [],
        "components": {
            m: {"functions": [], "classes": [], "errors": [], "constants": [], "uses": {}}
            for m in MODULES
        },
    }


# The grid: card columns 190 apart (150 card, 40 gutter), rows 92 apart
# (56 card, 36 gutter). Cards on the grid leave straight corridors for edges.
COL = {f"c{i + 1}": 270 + 190 * i for i in range(8)}
ROW = {"r1": 90, "r2": 270, "r3": 362, "r4": 454}

CONTAINERS = (
    Container(
        id="client",
        label="CLIENT",
        sub="the office sidebar, TypeScript, outside these packages",
        box=(16, 16, 196, 164),
        tone="client",
    ),
    Container(
        id="server",
        label="SERVER",
        sub="one gateway process: FastAPI with AgentKit embedded",
        box=(230, 16, 1560, 520),
        tone="server",
    ),
    Container(
        id="outside",
        label="OUTSIDE",
        sub="providers, behind the roster",
        box=(630, 580, 190, 110),
        tone="host",
    ),
    Container(
        id="render",
        label="RENDER CONTAINER",
        sub="the pinned Linux image; the only place OfficeSuite runs",
        box=(1010, 580, 570, 110),
        tone="isolated",
    ),
)

REGIONS = (
    Region(id="gateway", label="GATEWAY", box=(250, 50, 1520, 130), container="server"),
    Region(id="contracts", label="CONTRACTS", box=(250, 230, 190, 282), container="server"),
    Region(id="content", label="CONTENT", box=(440, 230, 190, 282), container="server"),
    Region(
        id="orchestration",
        label="ORCHESTRATION",
        box=(630, 230, 380, 282),
        container="server",
    ),
    Region(id="style", label="STYLE", box=(1010, 230, 380, 282), container="server"),
    Region(
        id="layout",
        label="LAYOUT AND EMIT",
        box=(1390, 230, 380, 282),
        container="server",
    ),
)

COMPONENTS = (
    # ---- actors -----------------------------------------------------------
    Component(
        id="Sidebar",
        does="The office add-in a person works in; sends briefs, references and edits, shows progress.",
        kind="actor",
        container="client",
        x=36,
        y=ROW["r1"],
    ),
    Component(
        id="ModelProvider",
        does="A frontier model behind the proxy or AgentKit's registry; every call reaches it through the roster.",
        kind="actor",
        container="outside",
        x=650,
        y=616,
    ),
    Component(
        id="OfficeSuite",
        does="The headless suite process the renderer drives over the bridge.",
        kind="actor",
        container="render",
        x=1220,
        y=616,
    ),
    # ---- gateway ----------------------------------------------------------
    Component(
        id="Gateway",
        region="gateway",
        does="The HTTP and WebSocket surface: sessions, uploads, guide compile, corrections, "
        "extraction, text metrics and durable jobs, on AgentKit's FastAPI embedding.",
        interface="create_app() -> FastAPI",
        implemented_by=(
            "wharf_server.gateway",
            "wharf_server.gateway.__main__",
            "wharf_server.gateway.app",
            "wharf_server.gateway.errors",
            "wharf_server.gateway.extraction_run",
            "wharf_server.gateway.jobs",
            "wharf_server.gateway.routes",
            "wharf_server.gateway.stub_run",
        ),
        entry="create_app",
        x=COL["c2"],
        y=ROW["r1"],
    ),
    Component(
        id="GatewayStore",
        region="gateway",
        does="The gateway's durable state: sessions, uploads, jobs and the event log, in SQLite.",
        interface="GatewayStore",
        implemented_by=("wharf_server.gateway.store",),
        entry="GatewayStore",
        kind="store",
        x=COL["c4"],
        y=ROW["r1"],
    ),
    Component(
        id="ArtifactStore",
        region="gateway",
        does="Where bytes live: a disk-backed AgentKit artifact service; session state carries URIs.",
        interface="DiskArtifactService",
        implemented_by=("wharf_server.artifacts.*",),
        entry="DiskArtifactService",
        kind="store",
        x=COL["c5"],
        y=ROW["r1"],
    ),
    # ---- contracts --------------------------------------------------------
    Component(
        id="PageModel",
        region="contracts",
        does="The thin waist: the PageModel tree, its components, geometry, limits, "
        "validators and the flattened wire form every provider sees.",
        interface="PageModel / ResolvedPageModel",
        implemented_by=(
            "wharf_contracts",
            "wharf_contracts.__main__",
            "wharf_contracts.page_model",
            "wharf_contracts.components",
            "wharf_contracts.geometry",
            "wharf_contracts.limits",
            "wharf_contracts.validators",
            "wharf_contracts.wire",
            "wharf_contracts.frame_identity",
            "wharf_contracts.registries",
            "wharf_contracts.sources",
        ),
        entry="PageModel",
        x=COL["c1"],
        y=ROW["r2"],
    ),
    Component(
        id="StyleGuide",
        region="contracts",
        does="The one place literal values legitimately live: typography, colour, spacing, "
        "frame, composition grammar, each member with its provenance.",
        interface="StyleGuide / StyleGuideDraft",
        implemented_by=("wharf_contracts.styleguide",),
        entry="StyleGuide",
        x=COL["c1"],
        y=ROW["r3"],
    ),
    Component(
        id="WireContracts",
        region="contracts",
        does="What crosses to the client: route payloads, the WSS event union, durable jobs, "
        "the closed typed-op schema and the reports.",
        interface="GenerateRequest / OpsProgram / Report",
        implemented_by=(
            "wharf_contracts.gateway",
            "wharf_contracts.ops",
            "wharf_contracts.reports",
        ),
        entry="GenerateRequest",
        x=COL["c1"],
        y=ROW["r4"],
    ),
    # ---- content ----------------------------------------------------------
    Component(
        id="SourceExtractor",
        region="content",
        does="Turns attached XLSX, CSV, PDF, DOCX and page images into cited Datasets: "
        "tabular files deterministically, documents through a metered TextExtract call.",
        interface="ingest(file) -> SourceRecord; extract(source, need) -> [Dataset]",
        implemented_by=(
            "wharf_server.content",
            "wharf_server.content.documents",
            "wharf_server.content.document_tuning",
            "wharf_server.content.extraction_provider",
            "wharf_server.content.refusal",
            "wharf_server.content.tabular",
            "wharf_server.content.tieouts",
            "wharf_server.content.tuning",
        ),
        entry="ingest",
        kind="agent",
        x=COL["c2"],
        y=ROW["r2"],
    ),
    Component(
        id="FolioPlanner",
        region="content",
        does="One structured call: brief plus data plus guide to an ordered list of "
        "PageGoals, then deterministic density and repetition verdicts.",
        interface="plan(brief, data, guide) -> [PageGoal]",
        implemented_by=(
            "wharf_server.content.planner",
            "wharf_server.content.plan_eval",
        ),
        entry="plan",
        kind="agent",
        x=COL["c2"],
        y=ROW["r3"],
    ),
    # ---- orchestration ----------------------------------------------------
    Component(
        id="Orchestrator",
        region="orchestration",
        does="The root LlmAgent in AgentKit's loadable layout: the only loop that runs with "
        "the user. Today a skeleton with one echo tool.",
        interface="app (AgentKit App) with the ledger and telemetry plugins",
        implemented_by=("wharf_server.orchestration.agents.*",),
        entry="echo",
        kind="agent",
        x=COL["c3"],
        y=ROW["r2"],
    ),
    Component(
        id="RosterClient",
        region="orchestration",
        does="The only way to reach a provider: the single-shot call template, the roster "
        "client, the telemetry plugins and the import-boundary lint that enforces it.",
        interface="run_single_shot(...) -> structured output",
        implemented_by=(
            "wharf_server.orchestration",
            "wharf_server.orchestration.single_shot",
            "wharf_server.orchestration.roster_client",
            "wharf_server.orchestration.telemetry",
            "wharf_server.orchestration.import_boundary",
        ),
        entry="run_single_shot",
        x=COL["c3"],
        y=ROW["r3"],
    ),
    Component(
        id="PromptTemplates",
        region="orchestration",
        does="Versioned XML prompt templates, design-skill packages and extraction schemas, "
        "rendered into the cacheable system prefix and the payload of each call.",
        interface="render_prompt(name, version, vars) -> str",
        implemented_by=(
            "wharf_server.prompts",
            "wharf_server.prompts.compose",
            "wharf_server.prompts.design_skills",
            "wharf_server.prompts.extraction_schemas",
            "wharf_server.prompts.loader",
            "wharf_server.orchestration.prompts",
        ),
        entry="render_prompt",
        kind="context",
        x=COL["c4"],
        y=ROW["r4"],
    ),
    Component(
        id="BudgetLedger",
        region="orchestration",
        does="The Runner plugin every model call passes: multi-dimensional budgets counted "
        "atomically, a typed budget error at the invocation boundary.",
        interface="BudgetLedgerPlugin",
        implemented_by=("wharf_server.orchestration.ledger",),
        entry="BudgetLedger",
        x=COL["c4"],
        y=ROW["r3"],
    ),
    Component(
        id="Config",
        region="orchestration",
        does="The model roster pinned exactly, the routing guard and telemetry scrub, and "
        "every constant that ships before its measurement exists.",
        interface="build_roster() / route_check() / provisional constants",
        implemented_by=(
            "wharf_server.config",
            "wharf_server.config.models",
            "wharf_server.config.governance",
            "wharf_server.config.provisional",
        ),
        entry="build_roster",
        x=COL["c4"],
        y=ROW["r2"],
    ),
    # ---- style ------------------------------------------------------------
    Component(
        id="GuideCache",
        region="style",
        does="Final guides by content hash, their retention and the user overlay; the "
        "one content digest every producer shares.",
        interface="GuideCache",
        implemented_by=("wharf_server.style.cache", "wharf_server.hashing"),
        entry="GuideCache",
        kind="store",
        x=COL["c5"],
        y=ROW["r2"],
    ),
    Component(
        id="StyleCompiler",
        region="style",
        does="Walks a reference folio's XML through the untrusted-input boundary, compiles "
        "observations into a StyleGuideDraft, and recompiles with corrections applied.",
        interface="extract(ofx_bytes) -> StyleGuideDraft",
        implemented_by=(
            "wharf_server.style",
            "wharf_server.style.compiler",
            "wharf_server.style.walker",
            "wharf_server.style.tokens",
            "wharf_server.style.drawml",
            "wharf_server.style.inheritance",
            "wharf_server.style.schema",
            "wharf_server.style.hardening",
            "wharf_server.style.records",
            "wharf_server.style.shapes",
            "wharf_server.style.tuning",
            "wharf_server.style.recompile",
            "wharf_server.style.invalidation",
            "wharf_server.style.pointers",
            "wharf_server.style.inspect",
            "wharf_server.style.selection",
        ),
        entry="extract",
        x=COL["c5"],
        y=ROW["r3"],
    ),
    Component(
        id="StyleCompleter",
        region="style",
        does="One joint multimodal completion call over the draft's unresolved paths, "
        "then a deterministic finalizer that refuses what it cannot validate.",
        interface="complete(draft, renders) -> CompletedGuide",
        implemented_by=(
            "wharf_server.style.completer",
            "wharf_server.style.completion_eval",
            "wharf_server.style.measurements",
            "wharf_server.style.review_packet",
        ),
        entry="complete",
        kind="agent",
        x=COL["c6"],
        y=ROW["r3"],
    ),
    Component(
        id="ComponentGallery",
        region="style",
        does="Which of a reference folio's components are interesting, rendered and cropped "
        "into the images the completer sees.",
        interface="build_gallery(...) -> GalleryBuild",
        implemented_by=("wharf_server.style.gallery",),
        entry="build_gallery",
        kind="context",
        x=COL["c6"],
        y=ROW["r4"],
    ),
    # ---- layout and emit --------------------------------------------------
    Component(
        id="TextMeasurer",
        region="layout",
        does="Server-side text measurement: whole runs shaped with the shaper, integer EMU, "
        "the client-server tolerance and the fit margin derived from it.",
        interface="measure_text(...) -> Measurement",
        implemented_by=("wharf_server.measure.*",),
        entry="measure_text",
        x=COL["c7"],
        y=ROW["r2"],
    ),
    Component(
        id="LayoutEngine",
        region="layout",
        does="The geometry core: a PageModel tree to integer-EMU boxes at scale s, the "
        "open kind registry, the fixed-element precheck and the hard predicates.",
        interface="solve(model, guide, scale) -> ResolvedPageModel",
        implemented_by=("wharf_server.layout.*",),
        entry="solve",
        x=COL["c7"],
        y=ROW["r3"],
    ),
    Component(
        id="Sandbox",
        region="layout",
        does="The only place generated code runs: AgentKit's container executor plus the limits "
        "it does not set, verified at start.",
        interface="SandboxRunner.run(code, inputs) -> tree | TypedSandboxError",
        implemented_by=("wharf_server.sandbox.*",),
        entry="SandboxRunner",
        x=COL["c7"],
        y=ROW["r4"],
    ),
    Component(
        id="ComponentLibrary",
        region="layout",
        does="Admitted components, their versions and embeddings, in SQLite. Nothing in "
        "the tree fills it yet.",
        interface="ComponentLibrary.search(need)",
        implemented_by=("wharf_server.component_generator.*",),
        entry="ComponentLibrary",
        kind="store",
        note="no caller in the tree: the ComponentGenerator is not written",
        x=COL["c8"],
        y=ROW["r2"],
    ),
    Component(
        id="SourceLineage",
        region="layout",
        does="Where a rendered figure's claim to a source is computed, read and refused; "
        "builds the page's source line from its citations.",
        interface="build_source_line(...) / resolve_cells(...)",
        implemented_by=("wharf_server.lineage.*",),
        entry="build_source_line",
        x=COL["c8"],
        y=ROW["r3"],
    ),
    Component(
        id="OfxEmitter",
        region="layout",
        does="ResolvedPageModel to byte-valid OFX: text, tables, native charts, images, "
        "frame, master reuse, assembly, and validators that fail the emit.",
        interface="emit_folio([ResolvedPageModel], guide) -> bytes",
        implemented_by=("wharf_server.render.emit.*",),
        entry="emit_folio",
        x=COL["c8"],
        y=ROW["r4"],
    ),
    # ---- render container -------------------------------------------------
    Component(
        id="Renderer",
        region=None,
        container="render",
        does="The OfficeSuite worker pool, font provisioning and substitution detection, "
        "the PNG and PDF API, and the worker's HTTP surface inside the container.",
        interface="RenderService.png(bytes, scope) / pdf(bytes)",
        implemented_by=(
            "wharf_server.render",
            "wharf_server.render.__main__",
            "wharf_server.render.app",
            "wharf_server.render.cpu",
            "wharf_server.render.deadline",
            "wharf_server.render.fonts",
            "wharf_server.render.jobs",
            "wharf_server.render.pool",
            "wharf_server.render.profiles",
            "wharf_server.render.raster",
            "wharf_server.render.service",
            "wharf_server.render.suite",
            "wharf_server.render.tuning",
        ),
        entry="RenderService",
        x=1030,
        y=616,
    ),
)

# (from, to, the artifact carried, the kind).
FLOWS = (
    Flow("Sidebar", "Gateway", "request", "data"),
    Flow("Gateway", "Sidebar", "progress events", "data"),
    Flow("Gateway", "GatewayStore", "job record", "data"),
    Flow("Gateway", "ArtifactStore", "service registration", "control"),
    Flow("Gateway", "SourceExtractor", "attached source", "data"),
    Flow("SourceExtractor", "Gateway", "cited Datasets", "data"),
    Flow("Gateway", "GuideCache", "reference bytes", "data"),
    Flow("Gateway", "StyleCompiler", "correction", "data"),
    Flow("Gateway", "TextMeasurer", "text run", "data"),
    Flow("Orchestrator", "RosterClient", "model binding", "control"),
    Flow("Orchestrator", "BudgetLedger", "plugin registration", "control"),
    Flow("Gateway", "BudgetLedger", "open budget", "control"),
    Flow("Gateway", "Orchestrator", "run", "control"),
    Flow("RosterClient", "BudgetLedger", "call usage", "data"),
    Flow("Config", "RosterClient", "roster", "data"),
    Flow("Config", "BudgetLedger", "call caps", "data"),
    Flow("RosterClient", "ModelProvider", "request", "data"),
    Flow("ModelProvider", "RosterClient", "response", "data"),
    Flow("PromptTemplates", "Orchestrator", "system prompt", "context"),
    Flow("PromptTemplates", "FolioPlanner", "planner template", "context"),
    Flow("PromptTemplates", "SourceExtractor", "extraction schema", "context"),
    Flow("PromptTemplates", "StyleCompleter", "completion template", "context"),
    Flow("FolioPlanner", "RosterClient", "plan call", "control"),
    Flow("SourceExtractor", "RosterClient", "extraction call", "control"),
    Flow("StyleCompleter", "RosterClient", "completion call", "control"),
    Flow("GuideCache", "StyleCompiler", "compile on miss", "control"),
    Flow("StyleCompiler", "StyleCompleter", "StyleGuideDraft", "data"),
    Flow("StyleCompleter", "GuideCache", "CompletedGuide", "data"),
    Flow("StyleCompiler", "ComponentGallery", "walk observations", "data"),
    Flow("ComponentGallery", "StyleCompleter", "gallery crops", "context"),
    Flow("ComponentGallery", "Renderer", "render job", "control"),
    Flow("Renderer", "ComponentGallery", "PNG pages", "data"),
    Flow("Renderer", "OfficeSuite", "conversion", "control"),
    Flow("OfficeSuite", "Renderer", "PDF", "data"),
    Flow("SourceLineage", "LayoutEngine", "installed source line", "data"),
    Flow("SourceLineage", "OfxEmitter", "source line", "data"),
    Flow("LayoutEngine", "OfxEmitter", "ResolvedPageModel", "data"),
    Flow("LayoutEngine", "Sandbox", "expand call", "control"),
)

FLOW_KINDS = ()

INVARIANTS = (
    Invariant(
        1,
        "The PageModel is the only interchange between content, layout and style; LLM "
        "output carries token roles and constraints, never literal colours, sizes or "
        "coordinates (AGENTS.md, Architecture invariants, 2).",
        governs=("PageModel", "FolioPlanner", "LayoutEngine", "StyleGuide"),
    ),
    Invariant(
        2,
        "An agent needs a reason: only the Orchestrator and the ComponentGenerator clear "
        "the bar; everything else is a single-shot structured call with pre-fetched "
        "context and no fetch tools (AGENTS.md, Architecture invariants, 3).",
        governs=("Orchestrator", "FolioPlanner", "StyleCompleter", "SourceExtractor"),
    ),
    Invariant(
        3,
        "Generated code runs only in the sandbox: no network, no filesystem, resource "
        "caps, and no unsandboxed fallback path anywhere (AGENTS.md, Architecture "
        "invariants, 5).",
        governs=("Sandbox", "LayoutEngine"),
    ),
    Invariant(
        4,
        "Text fit is measured, never estimated; whole runs, never summed fragments "
        "(AGENTS.md, Architecture invariants, 6).",
        governs=("TextMeasurer", "LayoutEngine"),
    ),
    Invariant(
        5,
        "Bytes live in the artifact store; session state carries URIs and small typed "
        "values, written only through tracked paths (AGENTS.md, Architecture "
        "invariants, 9).",
        governs=("ArtifactStore", "GatewayStore"),
    ),
    Invariant(
        6,
        "Every model call passes the BudgetLedger plugin; every budget, cap and "
        "threshold comes from measurement on this system (AGENTS.md, Architecture "
        "invariants, 10).",
        governs=("BudgetLedger", "RosterClient", "Config"),
    ),
    Invariant(
        7,
        "Prompts are versioned XML template files; a template change ships with its "
        "eval delta (AGENTS.md, Architecture invariants, 11).",
        governs=("PromptTemplates",),
    ),
    Invariant(
        8,
        "Uploaded reference files are untrusted input: XML entity resolution disabled, "
        "zip-bomb caps enforced (AGENTS.md, Architecture invariants, 14).",
        governs=("StyleCompiler", "SourceExtractor"),
    ),
    Invariant(
        9,
        "The renderer runs only in the pinned Linux container image, never native "
        "OfficeSuite; dev and prod use the same image (AGENTS.md, Architecture "
        "invariants, 16).",
        governs=("Renderer",),
    ),
    Invariant(
        10,
        "House style is all or nothing: reference mode imports zero house values, and "
        "persistent completion failure requests user direction (AGENTS.md, "
        "Architecture invariants, 19).",
        governs=("StyleCompleter", "StyleCompiler"),
    ),
    Invariant(
        11,
        "The flow is the only way to reach a provider: no module outside the roster "
        "client imports a provider SDK (orchestration/import_boundary.py, module "
        "docstring).",
        governs=("RosterClient",),
    ),
)

MODEL = Model(
    canvas=(1800, 720),
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=FLOWS,
    flow_kinds=FLOW_KINDS,
    invariants=INVARIANTS,
)

# ---- meaning: the plain words, the layers, one sentence per flow ---------

PLAIN = {
    "Sidebar": "the add-in the person types into",
    "ModelProvider": "the model on the other end of the wire",
    "OfficeSuite": "the office suite that turns pages into pages",
    "Gateway": "the front door of the server",
    "GatewayStore": "the server's memory of sessions and jobs",
    "ArtifactStore": "where the bytes are kept",
    "PageModel": "the one shape every page is described in",
    "StyleGuide": "the record of what a reference folio looks like",
    "WireContracts": "the shapes that cross to the client",
    "SourceExtractor": "the part that reads attached files into numbers with sources",
    "FolioPlanner": "the part that decides what each page says",
    "Orchestrator": "the agent that talks with the user",
    "RosterClient": "the one road to a model",
    "PromptTemplates": "the words each model call is given",
    "BudgetLedger": "the meter on every model call",
    "Config": "the pinned model list and the provisional numbers",
    "GuideCache": "the shelf of finished style guides",
    "StyleCompiler": "the part that reads a reference folio's style",
    "StyleCompleter": "the part that fills in what reading could not settle",
    "ComponentGallery": "the pictures of a reference folio's parts",
    "TextMeasurer": "the ruler for text",
    "LayoutEngine": "the part that places things on the page",
    "Sandbox": "the locked room where generated code runs",
    "ComponentLibrary": "the shelf of admitted components",
    "SourceLineage": "the trail from a figure back to its source",
    "OfxEmitter": "the part that writes the office file",
    "Renderer": "the part that turns a folio into pictures",
}

# The page derives Structure, System context, Data flow, Control flow, and
# (because the model has agents) Agents, Context and Tools.
LAYERS = ()

LAYER_OF_KIND = {}

RELATIONS = {
    (
        "Sidebar",
        "Gateway",
    ): "The sidebar opens a session, uploads a reference or a source, and asks for a generate or an edit; it never reaches past the gateway.",
    (
        "Gateway",
        "Sidebar",
    ): "The gateway streams stage, narration and preview events over the WebSocket, and replays them on reconnect.",
    (
        "Gateway",
        "GatewayStore",
    ): "The gateway records every session, upload and job in the store so a restart resumes or cleanly reports, never orphans.",
    (
        "Gateway",
        "ArtifactStore",
    ): "The gateway registers the disk artifact service through AgentKit's own seam so bytes land on disk and state carries URIs.",
    (
        "Gateway",
        "Orchestrator",
    ): "AgentKit's FastAPI embedding loads the wharf agent app from its directory; the gateway runs it and relays its events.",
    (
        "Gateway",
        "SourceExtractor",
    ): "The gateway hands an uploaded source to the extractor as a durable stage of the job.",
    (
        "SourceExtractor",
        "Gateway",
    ): "The extractor returns cited datasets and typed refusals; the gateway records them against the upload.",
    (
        "Gateway",
        "GuideCache",
    ): "The gateway asks the cache for the guide of a reference by content hash; a miss compiles, a hit returns.",
    (
        "Gateway",
        "StyleCompiler",
    ): "The gateway loads the house style at startup and passes each user correction to the compiler, which recompiles the reference with it applied and says which guide heads it invalidates.",
    (
        "Gateway",
        "TextMeasurer",
    ): "The gateway's text-metrics route measures a run for the client so the two rulers can be compared.",
    (
        "Gateway",
        "BudgetLedger",
    ): "The gateway opens a budget and run config for each generate or edit job, and classifies a typed budget error into the job's failed state.",
    (
        "Orchestrator",
        "RosterClient",
    ): "The orchestrator's root agent is bound to the roster's model through the client; it never names a provider.",
    (
        "Orchestrator",
        "BudgetLedger",
    ): "The agent app registers the ledger plugin at assembly so every call the orchestrator makes is counted.",
    (
        "RosterClient",
        "BudgetLedger",
    ): "Every call the client constructs reports its usage and cache tokens to the ledger before it runs.",
    (
        "Config",
        "RosterClient",
    ): "The roster tells the client which pinned model each role may use and the routing guard refuses the rest.",
    (
        "Config",
        "BudgetLedger",
    ): "The ledger's dimensions and per-job call caps are read from the provisional table, where every unmeasured constant is on record.",
    (
        "RosterClient",
        "ModelProvider",
    ): "The client sends one request per logical call, with a stable cacheable prefix.",
    (
        "ModelProvider",
        "RosterClient",
    ): "The provider returns the structured reply the call's output schema demanded, or a refusal the client types.",
    (
        "PromptTemplates",
        "Orchestrator",
    ): "The orchestrator's instruction is loaded from a versioned template.",
    (
        "PromptTemplates",
        "FolioPlanner",
    ): "The planner's call prompt is composed from its versioned template and the planner's design skills.",
    (
        "PromptTemplates",
        "SourceExtractor",
    ): "The extractor loads a per-document-class extraction schema as a versioned prompt asset.",
    (
        "PromptTemplates",
        "StyleCompleter",
    ): "The completer's call prompt is composed from its versioned template and the completer's design skills.",
    (
        "FolioPlanner",
        "RosterClient",
    ): "The planner makes exactly one structured call per folio through the single-shot template.",
    (
        "SourceExtractor",
        "RosterClient",
    ): "Document extraction routes TextExtract's calls through the roster and the ledger; tabular files make no call.",
    (
        "StyleCompleter",
        "RosterClient",
    ): "The completer makes one joint completion call per reference through the single-shot template.",
    (
        "GuideCache",
        "StyleCompiler",
    ): "On a miss the cache runs the compiler it was built with on the reference bytes.",
    (
        "StyleCompiler",
        "StyleCompleter",
    ): "The compiler hands the completer a draft whose unresolved paths are listed.",
    (
        "StyleCompleter",
        "GuideCache",
    ): "The completed guide, with its draft and completion patch, is what the cache keeps by content hash.",
    (
        "StyleCompiler",
        "ComponentGallery",
    ): "The gallery selects components from the walker's observations and leaf shapes; it never re-reads the folio.",
    (
        "ComponentGallery",
        "StyleCompleter",
    ): "The gallery's crops and exemplar pages are the images in the completer's window.",
    (
        "ComponentGallery",
        "Renderer",
    ): "The gallery asks the renderer for PNG pages of the reference folio to crop.",
    (
        "Renderer",
        "ComponentGallery",
    ): "The renderer returns the pages at the requested scale, with any font substitution reported.",
    (
        "Renderer",
        "OfficeSuite",
    ): "The pool drives one long-lived suite per worker over the bridge, one conversion at a time.",
    (
        "OfficeSuite",
        "Renderer",
    ): "suite returns the PDF the renderer rasterises into pages.",
    (
        "SourceLineage",
        "LayoutEngine",
    ): "Lineage installs the page's source line before the registry expands and solves.",
    (
        "SourceLineage",
        "OfxEmitter",
    ): "The emitter writes the source line lineage built from the page's citations, and refuses uncited numerics.",
    (
        "LayoutEngine",
        "OfxEmitter",
    ): "The emitter takes a solved tree with every box in integer EMU; nothing is re-solved at emit time.",
    (
        "LayoutEngine",
        "Sandbox",
    ): "The kind registry runs a component's expand code in the sandbox and validates the returned tree.",
}

VERBS = {"data": ("hands to", "receives from")}
VERB_OVERRIDES = {("Orchestrator", "BudgetLedger"): ("registers", "counts")}

JOURNEYS = (
    Journey(
        id="generate-job",
        label="python -m wharf_server.gateway: a request becomes a durable job",
        steps=(
            Step(
                acts=("Sidebar",),
                measures=(),
                edge=("Sidebar", "Gateway"),
                say="`main` starts uvicorn; the sidebar opens a session and posts a generate request.",
            ),
            Step(
                acts=("Gateway",),
                measures=(),
                edge=("Gateway", "GatewayStore"),
                say="The gateway records the job and its stage checkpoints so a restart resumes rather than orphans.",
            ),
            Step(
                acts=("Gateway",),
                measures=("BudgetLedger",),
                edge=("Gateway", "BudgetLedger"),
                say="The gateway opens the job's budget; today the generate run is a scripted stub that walks the stages.",
            ),
            Step(
                acts=("Gateway",),
                measures=(),
                edge=("Gateway", "Sidebar"),
                say="Stage and narration events stream to the sidebar and replay on reconnect.",
            ),
        ),
    ),
    Journey(
        id="orchestrator-turn",
        label="An orchestrator turn",
        steps=(
            Step(
                acts=("Gateway",),
                measures=(),
                edge=("Gateway", "Orchestrator"),
                say="AgentKit's embedding runs the wharf agent app for a user message.",
            ),
            Step(
                acts=("PromptTemplates",),
                measures=(),
                edge=("PromptTemplates", "Orchestrator"),
                say="The orchestrator's instruction enters its window from a versioned template.",
            ),
            Step(
                acts=("Orchestrator",),
                measures=("BudgetLedger",),
                edge=("Orchestrator", "RosterClient"),
                say="The root agent's model is the roster's; the ledger plugin counts the call.",
            ),
            Step(
                acts=("RosterClient",),
                measures=("BudgetLedger",),
                edge=("RosterClient", "ModelProvider"),
                say="The call goes to the provider with a stable prefix.",
            ),
            Step(
                acts=("ModelProvider",),
                measures=(),
                edge=("ModelProvider", "RosterClient"),
                say="The reply comes back; today the only tool the agent can invoke is echo.",
            ),
        ),
    ),
    Journey(
        id="reference-to-guide",
        label="A reference folio becomes a guide",
        steps=(
            Step(
                acts=("Gateway",),
                measures=(),
                edge=("Gateway", "GuideCache"),
                say="An uploaded reference is looked up by content hash.",
            ),
            Step(
                acts=("GuideCache",),
                measures=(),
                edge=("GuideCache", "StyleCompiler"),
                say="On a miss the cache runs the compiler.",
            ),
            Step(
                acts=("StyleCompiler",),
                measures=(),
                edge=("StyleCompiler", "StyleCompleter"),
                say="The walker reads every page, layout, master and theme through the hardening boundary; tokens compile the draft and list what stays unresolved.",
            ),
            Step(
                acts=("ComponentGallery",),
                measures=(),
                edge=("ComponentGallery", "Renderer"),
                say="The gallery renders the reference to pages.",
            ),
            Step(
                acts=("Renderer",),
                measures=(),
                edge=("Renderer", "OfficeSuite"),
                say="A pooled suite converts the folio; font substitution is detected.",
            ),
            Step(
                acts=("OfficeSuite",),
                measures=(),
                edge=("OfficeSuite", "Renderer"),
                say="The PDF comes back and is rasterised.",
            ),
            Step(
                acts=("Renderer",),
                measures=(),
                edge=("Renderer", "ComponentGallery"),
                say="Pages return; the gallery crops the interesting components.",
            ),
            Step(
                acts=("ComponentGallery",),
                measures=(),
                edge=("ComponentGallery", "StyleCompleter"),
                say="Crops and exemplars enter the completer's window.",
            ),
            Step(
                acts=("PromptTemplates",),
                measures=(),
                edge=("PromptTemplates", "StyleCompleter"),
                say="The completion template and design skills enter the window.",
            ),
            Step(
                acts=("StyleCompleter",),
                measures=("BudgetLedger",),
                edge=("StyleCompleter", "RosterClient"),
                say="One joint completion call over the unresolved groups.",
            ),
            Step(
                acts=("RosterClient",),
                measures=("BudgetLedger",),
                edge=("RosterClient", "ModelProvider"),
                say="The call reaches the provider.",
            ),
            Step(
                acts=("StyleCompleter",),
                measures=(),
                edge=("StyleCompleter", "GuideCache"),
                say="The finalizer validates the patch deterministically; the completed guide is cached.",
            ),
        ),
    ),
    Journey(
        id="source-to-datasets",
        label="An attached source becomes cited datasets",
        steps=(
            Step(
                acts=("Gateway",),
                measures=(),
                edge=("Gateway", "SourceExtractor"),
                say="Extraction runs as a durable stage over the uploaded source.",
            ),
            Step(
                acts=("PromptTemplates",),
                measures=(),
                edge=("PromptTemplates", "SourceExtractor"),
                say="For a document, the extraction schema for its class enters the window; a tabular file skips the model entirely.",
            ),
            Step(
                acts=("SourceExtractor",),
                measures=("BudgetLedger",),
                edge=("SourceExtractor", "RosterClient"),
                say="TextExtract's calls are metered through the roster.",
            ),
            Step(
                acts=("RosterClient",),
                measures=("BudgetLedger",),
                edge=("RosterClient", "ModelProvider"),
                say="The extraction call reaches the provider.",
            ),
            Step(
                acts=("SourceExtractor",),
                measures=(),
                edge=("SourceExtractor", "Gateway"),
                say="Datasets with citation chains, or a typed refusal, return to the job.",
            ),
        ),
    ),
    Journey(
        id="plan-call",
        label="A folio plan call",
        steps=(
            Step(
                acts=("PromptTemplates",),
                measures=(),
                edge=("PromptTemplates", "FolioPlanner"),
                say="The planner template and its skills enter the window with the brief, data summaries and style description.",
            ),
            Step(
                acts=("FolioPlanner",),
                measures=("BudgetLedger",),
                edge=("FolioPlanner", "RosterClient"),
                say="One structured call per folio; today only the eval script calls plan, the gateway does not yet.",
            ),
            Step(
                acts=("RosterClient",),
                measures=("BudgetLedger",),
                edge=("RosterClient", "ModelProvider"),
                say="The call reaches the provider; the reply's density and repetition are judged deterministically.",
            ),
        ),
    ),
    Journey(
        id="render-job",
        label="python -m wharf_server.render: a folio becomes pages",
        steps=(
            Step(
                acts=("ComponentGallery",),
                measures=(),
                edge=("ComponentGallery", "Renderer"),
                say="A render job enters the priority queue; `main` serves the worker's HTTP surface inside the container.",
            ),
            Step(
                acts=("Renderer",),
                measures=(),
                edge=("Renderer", "OfficeSuite"),
                say="Fonts are provisioned, then one pooled suite converts.",
            ),
            Step(
                acts=("OfficeSuite",),
                measures=(),
                edge=("OfficeSuite", "Renderer"),
                say="The PDF returns within the render deadline.",
            ),
            Step(
                acts=("Renderer",),
                measures=(),
                edge=("Renderer", "ComponentGallery"),
                say="Pages are rasterised and returned with the substitution report.",
            ),
        ),
    ),
    Journey(
        id="solve-and-emit",
        label="A solved page becomes OFX bytes",
        steps=(
            Step(
                acts=("SourceLineage",),
                measures=(),
                edge=("SourceLineage", "LayoutEngine"),
                say="The source line is installed from the page's citations before solving.",
            ),
            Step(
                acts=("LayoutEngine",),
                measures=("Sandbox",),
                edge=("LayoutEngine", "Sandbox"),
                say="Registered component kinds expand in the sandbox; the returned tree is validated.",
            ),
            Step(
                acts=("LayoutEngine",),
                measures=(),
                edge=("LayoutEngine", "OfxEmitter"),
                say="Every box is solved in integer EMU and validated before emission.",
            ),
            Step(
                acts=("OfxEmitter",),
                measures=("SourceLineage",),
                edge=("SourceLineage", "OfxEmitter"),
                say="The emitter writes the folio and its validators fail the emit on any uncited numeric.",
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
