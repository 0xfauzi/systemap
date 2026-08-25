"""The system map of kstrl: what the parts are and what they are to each other.

Components, the artifacts that flow between them, the regions they sit in and
the invariants that govern them are transcribed from kstrl's ARCHITECTURE.md,
CLAUDE.md and docs/control-loop-design.md. Those documents are the authority
for what the system is meant to be; this file is only their machine-readable
form, plus the mapping from each logical component to the modules that
implement it, and the meaning: the plain word per component, the seven layers,
one sentence per flow, the four journeys, and the verb each spoke prints.

Build state is DERIVED, never declared: a component is built when the modules
named in `implemented_by` exist and carry the entry point named in `entry`.
A component that carries a `tracker` (a roadmap item) is planned until that
entry appears, so the map cannot claim something is finished before the code
lands, and cannot keep calling it planned after it does.

Positions are hand-placed because this is a topology, not a chart: a box's
place carries meaning (which boundary it sits inside, where it is on the path
from an issue to a merged pull request). A fixed layout also means the same
system always draws the same picture, so a change in the map is a change in
the system. `systemap check` checks the placement mechanically.

Nothing in the meaning tables is derived from code. It is the hand-authored
meaning of the system, and it is wrong the moment the code disagrees with it:
keep it short, keep it checked.
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

CANVAS = (2278, 978)

# The canvas is a grid of card columns 190 apart (150 card, 40 gutter) and
# card rows 92 apart (56 card, 36 gutter). Every card sits on it, so every
# gutter is a straight corridor an orthogonal edge can run down, and a lane
# in one gutter lines up with the same gutter one band lower. The forward
# path reads left to right across the upper band; the bands that govern,
# remember and observe it sit in a lower band; the agent's own process and
# tree sit below the factory, under BUILD, so the adapter's two edges drop
# straight down to them.
COL: dict[str, int] = {
    "c0": 32,  # github, outside the factory
    "c1": 254,
    "c2": 444,
    "c3": 654,
    "c4": 864,
    "c5": 1054,
    "c6": 1264,
    "c7": 1474,
    "c8": 1664,
    "c9": 1854,
    "c10": 2096,  # operator, outside the factory
}
ROW: dict[str, int] = {
    "r1": 110,
    "r2": 202,
    "r3": 294,
    "r4": 386,
    "r5": 478,
    "l1": 650,
    "l2": 742,
}

# Hard boundaries. Nesting is by containment in the coordinates, not a tree.
CONTAINERS = (
    Container(
        id="github",
        label="GITHUB",
        sub="issues in, pull requests out, polled never pushed",
        box=(16, 16, 182, 172),
        tone="host",
    ),
    Container(
        id="factory",
        label="FACTORY PROCESS",
        sub="one process; every decision is code",
        box=(216, 16, 1846, 814),
        tone="server",
    ),
    Container(
        id="operator",
        label="OPERATOR",
        sub="one person, on the loop",
        box=(2080, 16, 182, 116),
        tone="host",
    ),
    Container(
        id="control_dir",
        label="CONTROL DIRECTORY",
        sub="XDG state outside the tree; the governor the agent cannot edit",
        box=(2080, 616, 182, 100),
        tone="isolated",
    ),
    Container(
        id="agent_cli",
        label="AGENT CLI",
        sub="subprocess in its own process group; killed on deadline",
        box=(848, 846, 182, 116),
        tone="isolated",
    ),
    Container(
        id="worktree",
        label="WORKTREE",
        sub="the only tree the agent may write",
        box=(1046, 846, 178, 116),
        tone="isolated",
    ),
)

# Soft bands inside the factory. The upper band reads left to right as the
# path one unit of work takes, DECIDE between BUILD and MEASURE because the
# pipeline is the hub both sides report to. The lower band holds the bands
# that govern, remember and observe that path. Each box is 20 wider than its
# cards on each side and 34 taller above them: room for a lane past a card
# inside its own band.
REGIONS = (
    Region(id="intake", label="INTAKE", box=(234, 76, 380, 380), container="factory"),
    Region(id="plan", label="PLAN", box=(634, 76, 190, 288), container="factory"),
    Region(id="build", label="BUILD", box=(844, 76, 380, 380), container="factory"),
    Region(id="decide", label="DECIDE", box=(1244, 168, 190, 196), container="factory"),
    Region(id="measure", label="MEASURE", box=(1454, 76, 380, 472), container="factory"),
    Region(id="ship", label="SHIP", box=(1854, 76, 190, 472), container="factory"),
    Region(id="observe", label="OBSERVE", box=(234, 616, 570, 196), container="factory"),
    Region(id="learn", label="LEARN", box=(1034, 616, 380, 196), container="factory"),
    Region(id="trust", label="TRUST", box=(1454, 616, 570, 196), container="factory"),
)

_TUI_MODULES = (
    "kstrl.tui",
    "kstrl.tui.app",
    "kstrl.tui.bridge",
    "kstrl.tui.dispatch",
    "kstrl.tui.embed",
    "kstrl.tui.home",
    "kstrl.tui.home_data",
    "kstrl.tui.messages",
    "kstrl.tui.runcontext",
    "kstrl.tui.runs",
    "kstrl.tui.screens",
    "kstrl.tui.screens.checkpoint",
    "kstrl.tui.screens.component",
    "kstrl.tui.screens.config",
    "kstrl.tui.screens.decompose",
    "kstrl.tui.screens.evolve",
    "kstrl.tui.screens.home",
    "kstrl.tui.screens.inbox",
    "kstrl.tui.screens.init_wizard",
    "kstrl.tui.screens.launch",
    "kstrl.tui.screens.options",
    "kstrl.tui.screens.overview",
    "kstrl.tui.screens.quit",
    "kstrl.tui.screens.retry",
    "kstrl.tui.session",
    "kstrl.tui.state",
    "kstrl.tui.tail",
    "kstrl.tui.theme",
    "kstrl.tui.widgets",
    "kstrl.tui.widgets.activity",
    "kstrl.tui.widgets.component_table",
    "kstrl.tui.widgets.context_bar",
    "kstrl.tui.widgets.cost_meter",
    "kstrl.tui.widgets.dag_table",
    "kstrl.tui.widgets.evidence",
    "kstrl.tui.widgets.findings_table",
    "kstrl.tui.widgets.form",
    "kstrl.tui.widgets.header",
    "kstrl.tui.widgets.phase_timeline",
    "kstrl.tui.widgets.run_table",
    "kstrl.tui.widgets.transcript",
)

_AGENT_MODULES = (
    "kstrl.agents",
    "kstrl.agents.base",
    "kstrl.agents.claude_code",
    "kstrl.agents.claude_sdk",
    "kstrl.agents.codex",
    "kstrl.agents.custom",
    "kstrl.agents.logging",
    "kstrl.agents.proc",
    "kstrl.agents.sdk_runner",
)

# Each card: its region (or, for an actor, its container), what it does, its
# interface, the modules that implement it and the entry point that makes it
# built. `tracker` marks a roadmap item whose code has not landed; `note` is
# a caveat the reader should see. Positions are grid cells.
COMPONENTS = (
    # ---- INTAKE ----------------------------------------------------------------
    Component(
        id="ServeDaemon",
        region="intake",
        does="Polls every minute, runs the admission gates in a fixed order, claims exactly one item, launches a run.",
        interface="serve_cycle(root, ...) -> CycleResult",
        implemented_by=("kstrl.serve",),
        entry="serve_cycle",
        x=COL["c2"],
        y=ROW["r1"],
    ),
    Component(
        id="GitHubIntake",
        region="intake",
        does="Turns a labelled issue into a queue item after checking the label was applied before the body was last edited.",
        interface="sync(queue, config, root) -> SyncResult",
        implemented_by=("kstrl.intake_github",),
        entry="sync",
        x=COL["c1"],
        y=ROW["r2"],
    ),
    Component(
        id="WorkQueue",
        region="intake",
        does="Maildir-style queue with leases, a reaper and backoff; one item per cycle.",
        interface="Queue.next_ready / lease / start / transition",
        implemented_by=("kstrl.workqueue",),
        entry="Queue",
        kind="store",
        x=COL["c1"],
        y=ROW["r1"],
    ),
    Component(
        id="SpendLedger",
        region="intake",
        does="Daily spend and consecutive-poison counts, rewritten whole under the control lock.",
        interface="SpendLedger.read_state / record_terminal",
        implemented_by=("kstrl.serve",),
        entry="SpendLedger",
        kind="store",
        x=COL["c1"],
        y=ROW["r3"],
    ),
    Component(
        id="Inbox",
        region="intake",
        does="Everything awaiting a human decision, with a cap consulted before admission.",
        interface="Inbox.add / open_items",
        implemented_by=("kstrl.inbox",),
        entry="Inbox",
        kind="store",
        x=COL["c2"],
        y=ROW["r2"],
    ),
    Component(
        id="FlowControl",
        region="intake",
        does="R10.7 #228: refuse admission while max_open_prs kstrl PRs are open.",
        interface="check_open_pr_bound",
        implemented_by=("kstrl.serve",),
        entry="check_open_pr_bound",
        x=COL["c2"],
        y=ROW["r3"],
        tracker="R10.7 #228",
    ),
    Component(
        id="Steering",
        region="intake",
        does="R10.10 #231: /memory and /iterate comments on kstrl PRs, polled.",
        interface="poll_steering",
        implemented_by=("kstrl.intake_github",),
        entry="poll_steering",
        x=COL["c1"],
        y=ROW["r4"],
        tracker="R10.10 #231",
    ),
    # ---- PLAN ------------------------------------------------------------------
    Component(
        id="Architect",
        region="plan",
        does="Red-teams the spec (halts on blockers) and decomposes it into a component DAG with per-component PRDs.",
        interface="decompose_spec(...) -> Manifest",
        implemented_by=("kstrl.decompose",),
        entry="decompose_spec",
        x=COL["c3"],
        y=ROW["r2"],
    ),
    Component(
        id="Manifest",
        region="plan",
        does="The component DAG, per-component status, PR pointers, policy hash; the resumable source of truth.",
        interface="Manifest.load / save / get_ready_components",
        implemented_by=("kstrl.manifest",),
        entry="Manifest",
        kind="store",
        x=COL["c3"],
        y=ROW["r1"],
    ),
    Component(
        id="PRD",
        region="plan",
        does="Per-component user stories with acceptance criteria and the passes flag the engineer sets.",
        interface="PRD.load / save",
        implemented_by=("kstrl.prd",),
        entry="PRD",
        kind="store",
        x=COL["c3"],
        y=ROW["r3"],
    ),
    # ---- BUILD -----------------------------------------------------------------
    Component(
        id="Feedforward",
        region="build",
        does="Computes module map, public interfaces, import graph and conventions from the tree, no model call.",
        interface="build_feedforward_context(path, config) -> str",
        implemented_by=("kstrl.feedforward",),
        entry="build_feedforward_context",
        x=COL["c4"],
        y=ROW["r1"],
    ),
    Component(
        id="KnowledgeInjector",
        region="build",
        does="Selects distilled facts (core, dependency, sibling tiers) for this component's prompt under token caps.",
        interface="build_knowledge_context(...) -> str",
        implemented_by=("kstrl.knowledge",),
        entry="build_knowledge_context",
        x=COL["c4"],
        y=ROW["r2"],
    ),
    Component(
        id="RetryContext",
        region="build",
        does="The failures handed to the next attempt; append-only today, level-triggered after R10.2.",
        interface="IterationContext.format_for_prompt",
        implemented_by=("kstrl.context",),
        entry="IterationContext",
        kind="store",
        x=COL["c5"],
        y=ROW["r2"],
    ),
    Component(
        id="EngineerLoop",
        region="build",
        does="Builds the prompt once, runs the agent up to max_iterations, watches for the completion marker, enforces allowed paths, trips the breaker.",
        interface="run_loop(config, agent, ...) -> LoopResult",
        implemented_by=("kstrl.loop",),
        entry="run_loop",
        x=COL["c5"],
        y=ROW["r3"],
    ),
    Component(
        id="AgentAdapter",
        region="build",
        does="Runs the coding agent's CLI, its SDK or a custom command as a subprocess through a deadline streamer; scrapes usage.",
        interface="Agent.run(prompt, cwd, timeout) -> Iterator[str]",
        implemented_by=_AGENT_MODULES,
        entry="Agent",
        x=COL["c4"],
        y=ROW["r4"],
    ),
    Component(
        id="Breaker",
        region="build",
        does="Halts a component after N iterations with an unchanged diff hash and test signature.",
        interface="NoProgressBreaker.record_iteration",
        implemented_by=("kstrl.breaker",),
        entry="NoProgressBreaker",
        x=COL["c5"],
        y=ROW["r4"],
    ),
    Component(
        id="PathGuard",
        region="build",
        does="Reverts or fails changes outside allowedPaths before the completion marker is honoured.",
        interface="enforce_allowed_paths(...)",
        implemented_by=("kstrl.guards",),
        entry="enforce_allowed_paths",
        x=COL["c4"],
        y=ROW["r3"],
    ),
    Component(
        id="OperatorContext",
        region="build",
        does="R10.8 #229 and R10.9 #230: golden patterns and the memory file loaded into the prefix.",
        interface="load_operator_file",
        implemented_by=("kstrl.operator_context",),
        entry="load_operator_file",
        x=COL["c5"],
        y=ROW["r1"],
        tracker="R10.8 #229, R10.9 #230",
    ),
    # ---- MEASURE ---------------------------------------------------------------
    Component(
        id="MechanicalVerifier",
        region="measure",
        does="Tests, typecheck, lint, diff scope, bad patterns, plus opt-in policy, adequacy, dead code, mutation, fixtures; all checks run even if earlier ones fail.",
        interface="run_mechanical_verification(...) -> VerificationResult",
        implemented_by=("kstrl.verify",),
        entry="run_mechanical_verification",
        x=COL["c7"],
        y=ROW["r3"],
    ),
    Component(
        id="Reviewer",
        region="measure",
        does="Independent LLM verdict per acceptance criterion plus concerns; cross-family by default; fails closed on empty or partial output.",
        interface="run_review(...) -> ReviewResult",
        implemented_by=("kstrl.review",),
        entry="run_review",
        x=COL["c7"],
        y=ROW["r2"],
    ),
    Component(
        id="SecurityReviewer",
        region="measure",
        does="OWASP/CWE-mapped LLM review; off by default; hard mode fails at the severity threshold.",
        interface="run_security_review(...) -> SecurityResult",
        implemented_by=("kstrl.security",),
        entry="run_security_review",
        x=COL["c7"],
        y=ROW["r1"],
    ),
    Component(
        id="ContractTester",
        region="measure",
        does="Integration tests on merged tiers; attributes a failure to the most recently merged component.",
        interface="run_contract_testing(...)",
        implemented_by=("kstrl.contract",),
        entry="run_contract_testing",
        x=COL["c8"],
        y=ROW["r1"],
    ),
    Component(
        id="FixturesOracle",
        region="measure",
        does="Approved input/output pairs run sandboxed outside the agent-writable tree; snapshot regression.",
        interface="check_fixtures_from_prd",
        implemented_by=("kstrl.fixtures", "kstrl.sandbox"),
        entry="check_fixtures_from_prd",
        x=COL["c8"],
        y=ROW["r4"],
    ),
    Component(
        id="AdequacyGate",
        region="measure",
        does="Reads the diff for deleted tests, added skips, lost assertions, and new tests with no strong oracle.",
        interface="lint_test_source / analyze_test_diff",
        implemented_by=("kstrl.adequacy",),
        entry="analyze_test_diff",
        x=COL["c7"],
        y=ROW["r4"],
    ),
    Component(
        id="PolicyEnvelope",
        region="measure",
        does="Declarative merge guardrails on the diff and lockfile; enforcement-machinery paths halt at every level.",
        interface="evaluate_policy(...) -> PolicyEvaluation",
        implemented_by=("kstrl.policy",),
        entry="evaluate_policy",
        x=COL["c8"],
        y=ROW["r5"],
    ),
    Component(
        id="Findings",
        region="measure",
        does="The typed error signal every sensor emits; infrastructure_error and phase_skipped make an empty list a safe success.",
        interface="Finding",
        implemented_by=("kstrl.findings",),
        entry="Finding",
        kind="store",
        x=COL["c8"],
        y=ROW["r3"],
    ),
    Component(
        id="Calibration",
        region="measure",
        does="Runs the adversarial roles against planted bugs and compares detection rates to a saved baseline; the sensor pointed at the sensors.",
        interface="compare_baselines(old, new) -> Comparison",
        implemented_by=("kstrl.calibration",),
        entry="compare_baselines",
        x=COL["c7"],
        y=ROW["r5"],
    ),
    Component(
        id="Sense",
        region="measure",
        does="R10.1 #222: every mechanical sensor run by hand against any tree with --json.",
        interface="ks sense",
        implemented_by=("kstrl.cli",),
        entry="sense",
        x=COL["c8"],
        y=ROW["r2"],
        tracker="R10.1 #222",
    ),
    # ---- DECIDE ----------------------------------------------------------------
    Component(
        id="Pipeline",
        region="decide",
        does="Per-component phase chain: verify, diff, review, security, distill, checkpoint, PR; decides retry, fail, or complete; owns the adversarial budget.",
        interface="ComponentPipeline.process_result",
        implemented_by=("kstrl.pipeline",),
        entry="ComponentPipeline",
        x=COL["c6"],
        y=ROW["r3"],
    ),
    Component(
        id="Scheduler",
        region="decide",
        does="Schedules ready components into worktrees under max_parallel, runs contract testing, resets breakers, records autonomy outcomes.",
        interface="run_factory(...) -> FactoryResult",
        implemented_by=("kstrl.factory",),
        entry="run_factory",
        x=COL["c6"],
        y=ROW["r2"],
    ),
    # ---- SHIP ------------------------------------------------------------------
    Component(
        id="Worktrees",
        region="ship",
        does="Isolated per-component worktrees cut from origin/<base>, flocked, recreated fresh after timeouts and conflicts.",
        interface="fetch_base_branch / resolve_base_ref; factory._setup_worktree drives them",
        implemented_by=("kstrl.git",),
        entry="fetch_base_branch",
        x=COL["c9"],
        y=ROW["r3"],
        note="The worktree command itself is a private function in kstrl.factory; kstrl.git holds the public base-branch primitives it is built on, so this entry tracks those.",
    ),
    Component(
        id="PullRequests",
        region="ship",
        does="Push, create, merge and wait; completion is merge-gated; MERGE_PENDING parks a component.",
        interface="push_create_and_merge_pr(...) -> PrOutcome",
        implemented_by=("kstrl.pr",),
        entry="push_create_and_merge_pr",
        x=COL["c9"],
        y=ROW["r1"],
    ),
    Component(
        id="Distiller",
        region="ship",
        does="Writes durable facts about the built artifact to disk before the PR merges.",
        interface="distill_facts(...)",
        implemented_by=("kstrl.knowledge",),
        entry="distill_facts",
        x=COL["c9"],
        y=ROW["r2"],
    ),
    Component(
        id="Dampener",
        region="ship",
        does="R10.6 #227: baseline in version control plus a per-PR regression report.",
        interface="ks sense --compare-baseline",
        implemented_by=("kstrl.cli",),
        entry="compare_baseline",
        x=COL["c9"],
        y=ROW["r4"],
        tracker="R10.6 #227",
        note="Entry name is provisional: R10.6 adds a flag to ks sense, so the helper that flag calls must be named compare_baseline, or this entry updated, for the state to derive.",
    ),
    Component(
        id="ReleaseStage",
        region="ship",
        does="R8.7 #154: deploy drivers, verification ladder, rollback doctrine.",
        interface="(Phase 4)",
        implemented_by=("kstrl.release",),
        entry="run_release",
        x=COL["c9"],
        y=ROW["r5"],
        tracker="R8.7 #154",
        note="Entry name is provisional until R8.7 names its module.",
    ),
    # ---- TRUST -----------------------------------------------------------------
    Component(
        id="AutonomyLadder",
        region="trust",
        does="L1 to L4; promotion needs evidence plus a human ack; demotion is automatic; the flag bundle is derived at run start and can only withhold.",
        interface="AutonomyState / resolve_runtime_level / flag_bundle_for",
        implemented_by=("kstrl.autonomy",),
        entry="AutonomyState",
        x=COL["c7"],
        y=ROW["l1"],
    ),
    Component(
        id="Replay",
        region="trust",
        does="Replays the ladder's thresholds over recorded history and reports, never decides.",
        interface="replay_file(...)",
        implemented_by=("kstrl.autonomy_replay",),
        entry="replay_file",
        x=COL["c8"],
        y=ROW["l1"],
    ),
    Component(
        id="StateDir",
        region="trust",
        does="Resolves the control directory outside the tree and refuses to trust it when it is inside, symlinked or unreadable.",
        interface="control_file / control_untrusted_reason / control_lock",
        implemented_by=("kstrl.statedir",),
        entry="control_untrusted_reason",
        kind="store",
        x=COL["c7"],
        y=ROW["l2"],
    ),
    Component(
        id="SafeMode",
        region="trust",
        does="R10.4 #225: one predicate over the four degraded states.",
        interface="safe_mode_reasons(root)",
        implemented_by=("kstrl.safemode",),
        entry="safe_mode_reasons",
        x=COL["c9"],
        y=ROW["l1"],
        tracker="R10.4 #225",
    ),
    Component(
        id="HealthTrending",
        region="trust",
        does="R8.4 #151: control-chart rules over run metrics; the HEALTH_BREACH sensor.",
        interface="health_breaches",
        implemented_by=("kstrl.health",),
        entry="health_breaches",
        x=COL["c8"],
        y=ROW["l2"],
        tracker="R8.4 #151",
    ),
    # ---- LEARN -----------------------------------------------------------------
    Component(
        id="EvolutionJournal",
        region="learn",
        does="Append-only record of every component outcome, failure signature, cost and finding summary.",
        interface="EvolutionJournal.record_run",
        implemented_by=("kstrl.evolution",),
        entry="EvolutionJournal",
        kind="store",
        x=COL["c6"],
        y=ROW["l1"],
    ),
    Component(
        id="Proposals",
        region="learn",
        does="Turns recurring journal patterns into markdown proposals; applies only convention proposals, behind a prompt.",
        interface="list_proposals / apply_proposal",
        implemented_by=("kstrl.proposals",),
        entry="apply_proposal",
        x=COL["c5"],
        y=ROW["l1"],
        note="Pattern detection and proposal writing live on EvolutionJournal.propose_improvements; this module reads and applies the files it writes.",
    ),
    Component(
        id="Playbook",
        region="learn",
        does="R9 #217: global playbook of attributed lessons under the XDG state home.",
        interface="(store)",
        implemented_by=("kstrl.playbook",),
        entry="Playbook",
        kind="store",
        x=COL["c5"],
        y=ROW["l2"],
        tracker="R9 #217",
        note="Entry name is provisional until R9 names its module.",
    ),
    Component(
        id="RuntimeSignals",
        region="learn",
        does="R8.8 #155: error and health signals polled into the queue with a reproducing-test rule.",
        interface="ks signals poll",
        implemented_by=("kstrl.signals",),
        entry="poll_signals",
        x=COL["c6"],
        y=ROW["l2"],
        tracker="R8.8 #155",
        note="Entry name is provisional until R8.8 names its module.",
    ),
    # ---- OBSERVE ---------------------------------------------------------------
    Component(
        id="EventBus",
        region="observe",
        does="Typed, schema-versioned events fanned out to sinks; sinks are observability, never control flow.",
        interface="EventBus.emit",
        implemented_by=("kstrl.events",),
        entry="EventBus",
        x=COL["c3"],
        y=ROW["l1"],
    ),
    Component(
        id="Reducer",
        region="observe",
        does="Folds an event stream into the renderable run state every surface shows.",
        interface="load_run_state(...) -> RunState",
        implemented_by=("kstrl.reducer",),
        entry="load_run_state",
        x=COL["c2"],
        y=ROW["l1"],
    ),
    Component(
        id="Dashboard",
        region="observe",
        does="The Textual TUI: home shell, run board, component detail, checkpoint modal; a view, never the record.",
        interface="KstrlTuiApp",
        implemented_by=_TUI_MODULES,
        entry="KstrlTuiApp",
        x=COL["c1"],
        y=ROW["l1"],
    ),
    Component(
        id="ProgressLog",
        region="observe",
        does="The v1 append-only JSONL log kept byte-compatible for existing consumers.",
        interface="ProgressLog.emit",
        implemented_by=("kstrl.observability",),
        entry="ProgressLog",
        kind="store",
        x=COL["c1"],
        y=ROW["l2"],
    ),
    Component(
        id="LinearMirror",
        region="observe",
        does="One-way outbound mirror of component status to the issue tracker; warns and degrades, never fails a run.",
        interface="LinearSink",
        implemented_by=("kstrl.linear",),
        entry="LinearSink",
        x=COL["c3"],
        y=ROW["l2"],
    ),
    Component(
        id="CLI",
        region="observe",
        does="The ks command tree: run, factory, decompose, serve, status, dash, autonomy, inbox, queue, evolve.",
        interface="cli",
        implemented_by=("kstrl.cli",),
        entry="cli",
        x=COL["c2"],
        y=ROW["l2"],
    ),
    # ---- actors, outside the factory -------------------------------------------
    Component(
        id="Operator",
        container="operator",
        does="Labels issues, edits specs and prompts, approves checkpoints, promotes autonomy, reads the inbox and the dashboard.",
        interface="external",
        implemented_by=(),
        entry="",
        kind="actor",
        x=2096,
        y=74,
    ),
    Component(
        id="GitHubIssues",
        container="github",
        does="The remote inbox: an issue plus a label is a request.",
        interface="external",
        implemented_by=(),
        entry="",
        kind="actor",
        x=32,
        y=74,
    ),
    Component(
        id="GitHubPRs",
        container="github",
        does="The output: one pull request per component, merge-gated.",
        interface="external",
        implemented_by=(),
        entry="",
        kind="actor",
        x=32,
        y=130,
    ),
    Component(
        id="CodingAgent",
        container="agent_cli",
        does="Whichever coding agent the project configures, or a custom command.",
        interface="external",
        implemented_by=(),
        entry="",
        kind="actor",
        x=864,
        y=904,
    ),
)

# (from, to, artifact carried, dataflow kind)
FLOWS = (
    Flow("GitHubIssues", "GitHubIntake", "labelled issue", "intake"),
    Flow("GitHubIntake", "WorkQueue", "queue item", "intake"),
    Flow("WorkQueue", "ServeDaemon", "next ready item", "intake"),
    Flow("SpendLedger", "ServeDaemon", "admission verdict", "intake"),
    Flow("Inbox", "ServeDaemon", "open-item cap", "intake"),
    Flow("ServeDaemon", "Scheduler", "factory run", "intake"),
    Flow("Operator", "Architect", "spec", "plan"),
    Flow("Architect", "Manifest", "component DAG", "plan"),
    Flow("Architect", "PRD", "stories + criteria", "plan"),
    Flow("Manifest", "Scheduler", "ready components", "decide"),
    Flow("Scheduler", "Worktrees", "worktree per component", "ship"),
    Flow("Feedforward", "EngineerLoop", "computed context", "build"),
    Flow("KnowledgeInjector", "EngineerLoop", "facts", "build"),
    Flow("RetryContext", "EngineerLoop", "failures from last attempt", "build"),
    Flow("EngineerLoop", "AgentAdapter", "prompt", "build"),
    Flow("AgentAdapter", "CodingAgent", "stdin prompt", "build"),
    Flow("CodingAgent", "AgentAdapter", "stream + COMPLETE marker", "build"),
    Flow("PRD", "EngineerLoop", "next failing story", "build"),
    Flow("EngineerLoop", "PRD", "passes flag (a claim)", "build"),
    Flow("Breaker", "EngineerLoop", "stall verdict", "build"),
    Flow("PathGuard", "EngineerLoop", "scope verdict", "build"),
    Flow("EngineerLoop", "Pipeline", "LoopResult", "decide"),
    Flow("Pipeline", "MechanicalVerifier", "worktree + PRD", "measure"),
    Flow("Pipeline", "Reviewer", "diff + criteria", "measure"),
    Flow("Pipeline", "SecurityReviewer", "diff", "measure"),
    Flow("PolicyEnvelope", "MechanicalVerifier", "envelope verdict", "measure"),
    Flow("AdequacyGate", "MechanicalVerifier", "adequacy findings", "measure"),
    Flow("FixturesOracle", "MechanicalVerifier", "fixture results", "measure"),
    Flow("MechanicalVerifier", "Findings", "check results", "measure"),
    Flow("Reviewer", "Findings", "criterion verdicts + concerns", "measure"),
    Flow("SecurityReviewer", "Findings", "vulnerability findings", "measure"),
    Flow("Findings", "Pipeline", "the error signal", "decide"),
    Flow("Pipeline", "RetryContext", "retry", "decide"),
    Flow("Pipeline", "Distiller", "passed diff", "ship"),
    Flow("Distiller", "KnowledgeInjector", "durable facts", "learn"),
    Flow("Pipeline", "PullRequests", "merge", "ship"),
    Flow("PullRequests", "GitHubPRs", "pull request", "ship"),
    Flow("PullRequests", "ContractTester", "merged tiers", "measure"),
    Flow("ContractTester", "Scheduler", "breaker component to reset", "decide"),
    Flow("Pipeline", "Inbox", "checkpoint / policy exception / budget overrun", "trust"),
    Flow("Scheduler", "AutonomyLadder", "run outcome", "trust"),
    Flow("AutonomyLadder", "Pipeline", "flag bundle (withhold only)", "trust"),
    Flow("PolicyEnvelope", "AutonomyLadder", "violation -> demotion", "trust"),
    Flow("Calibration", "AutonomyLadder", "regression (R10.11)", "trust"),
    Flow("AutonomyLadder", "StateDir", "autonomy.json", "trust"),
    Flow("SpendLedger", "StateDir", "spend.json", "trust"),
    Flow("Inbox", "StateDir", "inbox.jsonl", "trust"),
    Flow("Scheduler", "EvolutionJournal", "component outcomes + signatures", "learn"),
    Flow("EvolutionJournal", "Proposals", "recurring patterns", "learn"),
    Flow("EvolutionJournal", "Replay", "experiments.tsv", "trust"),
    Flow("Pipeline", "EventBus", "typed events", "observe"),
    Flow("Scheduler", "EventBus", "typed events", "observe"),
    Flow("EventBus", "ProgressLog", "v1 mirror", "observe"),
    Flow("EventBus", "Reducer", "events.jsonl", "observe"),
    Flow("Reducer", "Dashboard", "RunState", "observe"),
    Flow("Reducer", "CLI", "ks status", "observe"),
    Flow("EventBus", "LinearMirror", "failures, budget halts", "observe"),
    Flow("Dashboard", "Operator", "board, checkpoint modal", "observe"),
    Flow("Operator", "Inbox", "approve / reject / snooze", "trust"),
    Flow("Operator", "AutonomyLadder", "promote with ack", "trust"),
)

# The dataflows a reader can trace one at a time, in reading order.
FLOW_KINDS = ("intake", "plan", "build", "measure", "decide", "ship", "trust", "learn", "observe")

# The load-bearing rules of this system, from CLAUDE.md (H1 to H4), the
# roadmap doctrine, and docs/control-loop-design.md. They say WHY a part is
# shaped the way it is, which is the one thing the code cannot tell you.
# Each names the components it directly governs.
INVARIANTS = (
    Invariant(
        1,
        "H1: AI-generated code is never gated by AI self-review.",
        governs=("Reviewer",),
    ),
    Invariant(
        2,
        "H2: any adversarial prompt-body change re-runs calibration and records the delta.",
        governs=("Calibration", "Reviewer", "SecurityReviewer"),
    ),
    Invariant(
        3,
        "H3: prompt version and snapshot hash move together in one diff.",
        governs=("Reviewer", "SecurityReviewer"),
    ),
    Invariant(
        4,
        "H4: every done claim states what was tested versus assumed.",
        governs=(),
    ),
    Invariant(
        5,
        "Doctrine: integrate at the edges, build only thin middles.",
        governs=(),
    ),
    Invariant(
        6,
        "Doctrine: enforcement reads artifacts, never agent self-report.",
        governs=(
            "AdequacyGate",
            "Distiller",
            "FixturesOracle",
            "MechanicalVerifier",
            "PolicyEnvelope",
            "Reviewer",
            "SecurityReviewer",
        ),
    ),
    Invariant(
        7,
        "Doctrine: autonomy is earned, bounded, revocable; the bundle may only withhold.",
        governs=("AutonomyLadder", "PolicyEnvelope"),
    ),
    Invariant(
        8,
        "Doctrine: no assumed numbers; advisory first, graduate on the operator's judgement.",
        governs=(
            "AdequacyGate",
            "AutonomyLadder",
            "Calibration",
            "Dampener",
            "FlowControl",
            "HealthTrending",
            "Proposals",
            "ServeDaemon",
        ),
    ),
    Invariant(
        9,
        "Doctrine: the human is a role, not a bottleneck; boundary conditions route to the inbox.",
        governs=("FlowControl", "Inbox", "OperatorContext", "SafeMode", "ServeDaemon", "Steering"),
    ),
    Invariant(
        10,
        "Doctrine: the first-class phase count is frozen; new evaluators land inside a phase.",
        governs=("Pipeline", "Scheduler"),
    ),
    Invariant(
        11,
        "Doctrine: new outcome surfaces reuse the shared disposition; existing enums are not retrofitted.",
        governs=("Pipeline", "Scheduler"),
    ),
    Invariant(
        12,
        "Loop rule: what acts never measures its own result (a measurement written by the actuator is not a measurement).",
        governs=(
            "Dampener",
            "EngineerLoop",
            "MechanicalVerifier",
            "PRD",
            "Pipeline",
            "RetryContext",
            "Reviewer",
            "SecurityReviewer",
        ),
    ),
    Invariant(
        13,
        "Loop rule: every component runs by hand first; a sensor reachable only through a factory run cannot be tuned.",
        governs=("EngineerLoop", "MechanicalVerifier", "Sense"),
    ),
    Invariant(
        14,
        "Record rule: the filesystem is the event bus; sinks are observability, never control flow; the dashboard is a view.",
        governs=("Dashboard", "EventBus", "ProgressLog", "Reducer"),
    ),
    Invariant(
        15,
        "Trust boundary: control state lives outside the agent-reachable tree; unreadable control state fails closed.",
        governs=("AutonomyLadder", "SafeMode", "ServeDaemon", "SpendLedger", "StateDir"),
    ),
)

MODEL = Model(
    canvas=CANVAS,
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=FLOWS,
    flow_kinds=FLOW_KINDS,
    invariants=INVARIANTS,
)

# Model-call budget per unit of work, and where the documents define each
# component. systemap does not read these two tables; they are kstrl's own
# notes, kept beside the model they annotate.
CALL_BUDGET: dict[str, str] = {
    "Architect": "1 decompose call per spec",
    "EngineerLoop": "up to max_iterations agent calls per attempt",
    "Reviewer": "1 call per component per attempt (chunked: 1 per chunk)",
    "SecurityReviewer": "1 call per component per attempt when enabled",
    "Distiller": "1 call per completed component",
    "Calibration": "3 runs per fixture per role, opt-in",
}

SPEC_ANCHOR: dict[str, str] = {
    "ServeDaemon": "ARCHITECTURE.md: Runtime state layout",
    "GitHubIntake": "docs/continuous-intake.md",
    "WorkQueue": "docs/continuous-intake.md",
    "SpendLedger": "ARCHITECTURE.md: Runtime state layout",
    "Inbox": "ARCHITECTURE.md: Runtime state layout",
    "FlowControl": "control-loop-design 5.6",
    "Steering": "control-loop-design 5.8",
    "Architect": "ARCHITECTURE.md: Factory mode",
    "Manifest": "ARCHITECTURE.md: Factory mode",
    "PRD": "ARCHITECTURE.md: The iteration loop",
    "Feedforward": "ARCHITECTURE.md: The iteration loop",
    "KnowledgeInjector": "ARCHITECTURE.md: The iteration loop",
    "RetryContext": "control-loop-design 5.3",
    "EngineerLoop": "ARCHITECTURE.md: The iteration loop",
    "AgentAdapter": "ARCHITECTURE.md: The iteration loop",
    "Breaker": "ARCHITECTURE.md: The iteration loop",
    "PathGuard": "ARCHITECTURE.md: The iteration loop",
    "OperatorContext": "control-loop-design 5.4, 5.7",
    "MechanicalVerifier": "ARCHITECTURE.md: The pipeline",
    "Reviewer": "ARCHITECTURE.md: The pipeline",
    "SecurityReviewer": "ARCHITECTURE.md: The pipeline",
    "ContractTester": "ARCHITECTURE.md: Factory mode",
    "FixturesOracle": "ARCHITECTURE.md: The fixtures sandbox",
    "AdequacyGate": "ARCHITECTURE.md: The pipeline",
    "PolicyEnvelope": "ARCHITECTURE.md: The pipeline",
    "Findings": "ARCHITECTURE.md: The pipeline",
    "Calibration": "docs/adversarial-design.md",
    "Sense": "control-loop-design 5.1",
    "Pipeline": "ARCHITECTURE.md: The pipeline",
    "Scheduler": "ARCHITECTURE.md: Factory mode",
    "Worktrees": "ARCHITECTURE.md: Factory mode",
    "PullRequests": "ARCHITECTURE.md: The pipeline",
    "Distiller": "ARCHITECTURE.md: The pipeline",
    "Dampener": "control-loop-design 5.5",
    "ReleaseStage": "docs/dark-factory-roadmap.md R8.7",
    "AutonomyLadder": "ARCHITECTURE.md: Runtime state layout",
    "Replay": "ARCHITECTURE.md: Runtime state layout",
    "StateDir": "ARCHITECTURE.md: Runtime state layout",
    "SafeMode": "control-loop-design 5.9",
    "HealthTrending": "control-loop-design 5.11",
    "EvolutionJournal": "ARCHITECTURE.md: The learning loop",
    "Proposals": "ARCHITECTURE.md: The learning loop",
    "Playbook": "docs/continuous-learning-design.md",
    "RuntimeSignals": "docs/dark-factory-roadmap.md R8.8",
    "EventBus": "ARCHITECTURE.md: The event-stream substrate",
    "Reducer": "ARCHITECTURE.md: The event-stream substrate",
    "Dashboard": "ARCHITECTURE.md: The event-stream substrate",
    "ProgressLog": "ARCHITECTURE.md: The event-stream substrate",
    "LinearMirror": "docs/linear-integration.md",
    "CLI": "ARCHITECTURE.md: The event-stream substrate",
}

# ---------------------------------------------------------------------------
# Meaning. Plain words: the map shows the code's name; the panel leads with
# the plain word and gives the code's name once, so a reader who does not
# know the codebase can still follow.
# ---------------------------------------------------------------------------

PLAIN: dict[str, str] = {
    "ServeDaemon": "the daemon that admits work",
    "GitHubIntake": "the issue reader",
    "WorkQueue": "the queue",
    "SpendLedger": "the spend ledger",
    "Inbox": "the decisions waiting for you",
    "FlowControl": "the open-PR bound",
    "Steering": "your PR comments, read back",
    "Architect": "the planner that attacks the spec",
    "Manifest": "the component graph",
    "PRD": "what done means, per story",
    "Feedforward": "what the agent is told before it starts",
    "KnowledgeInjector": "facts from earlier components",
    "RetryContext": "what failed last time",
    "EngineerLoop": "the inner loop around the agent",
    "AgentAdapter": "the wrapper around the coding agent",
    "Breaker": "the stall detector",
    "PathGuard": "the scope fence",
    "OperatorContext": "your standing instructions",
    "MechanicalVerifier": "the checks that need no model",
    "Reviewer": "the second opinion",
    "SecurityReviewer": "the security opinion",
    "ContractTester": "the integration check",
    "FixturesOracle": "the answers the agent cannot rewrite",
    "AdequacyGate": "the check on the tests themselves",
    "PolicyEnvelope": "the written rules for a merge",
    "Findings": "the error signal",
    "Calibration": "the check on the checkers",
    "Sense": "run any check by hand",
    "Pipeline": "the decision per component",
    "Scheduler": "the decision per run",
    "Worktrees": "one working copy per component",
    "PullRequests": "the merge",
    "Distiller": "what was learned about the artifact",
    "Dampener": "the regression guard on every PR",
    "ReleaseStage": "the deploy",
    "AutonomyLadder": "how much the factory may do alone",
    "Replay": "what the ladder would have done",
    "StateDir": "the governor's own files, out of reach",
    "SafeMode": "is the factory degraded, and why",
    "HealthTrending": "is the factory getting worse",
    "EvolutionJournal": "the record of every outcome",
    "Proposals": "suggested harness changes",
    "Playbook": "lessons shared across projects",
    "RuntimeSignals": "what production says",
    "EventBus": "the event stream",
    "Reducer": "the current state, rebuilt from events",
    "Dashboard": "the live view",
    "ProgressLog": "the older event log, kept compatible",
    "LinearMirror": "the tracker mirror",
    "CLI": "the ks command",
    "Operator": "you",
    "GitHubIssues": "issues, the way in",
    "GitHubPRs": "pull requests, the way out",
    "CodingAgent": "the coding agent itself",
}

# Layers. One map, several readings. Each flow kind maps to one layer; a
# reader switches layers and the map shows only that layer's edges with the
# rest of the system dimmed but present. The order here is the order the
# layer switch shows them, and the first is on by default.
LAYERS = (
    Layer(
        id="work",
        label="Work",
        question="How does a spec become a merged pull request?",
        sub="intake, plan, build, ship: the forward path",
    ),
    Layer(
        id="measure",
        label="Measurement",
        question="Who checks what, and who is never allowed to check their own work?",
        sub="every sensor and what it reads",
    ),
    Layer(
        id="feedback",
        label="Feedback",
        question="What comes back to the agent, and from where?",
        sub="the gap between done and measured, fed forward",
    ),
    Layer(
        id="operator",
        label="You",
        question="Where do you stand, and what reaches you?",
        sub="every channel between the operator and the factory",
    ),
    Layer(
        id="trust",
        label="Trust",
        question="How does the factory earn and lose the right to act alone?",
        sub="the ladder, the envelope, the governor's files",
    ),
    Layer(
        id="learn",
        label="Learning",
        question="What carries from one run to the next?",
        sub="facts, journal, playbook",
    ),
    Layer(
        id="record",
        label="Record",
        question="How do you see what happened, live or after the fact?",
        sub="events in, views out; never control flow",
    ),
)

# Flow kind -> layer id. A flow whose meaning belongs to a different layer
# than its kind suggests is overridden below by (from, to).
LAYER_OF_KIND: dict[str, str] = {
    "intake": "work",
    "plan": "work",
    "build": "work",
    "decide": "work",
    "ship": "work",
    "measure": "measure",
    "trust": "trust",
    "learn": "learn",
    "observe": "record",
}

LAYER_OVERRIDES: dict[tuple[str, str], str] = {
    ("RetryContext", "EngineerLoop"): "feedback",
    ("PRD", "EngineerLoop"): "feedback",
    ("EngineerLoop", "PRD"): "feedback",
    ("Breaker", "EngineerLoop"): "feedback",
    ("PathGuard", "EngineerLoop"): "feedback",
    ("Findings", "Pipeline"): "feedback",
    ("Pipeline", "RetryContext"): "feedback",
    ("ContractTester", "Scheduler"): "feedback",
    ("Distiller", "KnowledgeInjector"): "learn",
    ("Operator", "Architect"): "operator",
    ("Operator", "Inbox"): "operator",
    ("Operator", "AutonomyLadder"): "operator",
    ("Dashboard", "Operator"): "operator",
    ("Pipeline", "Inbox"): "operator",
    ("Inbox", "ServeDaemon"): "operator",
    ("GitHubIssues", "GitHubIntake"): "operator",
    ("PullRequests", "GitHubPRs"): "operator",
}

# Relationships. Keyed by (from, to), matching FLOWS. Each is one sentence
# that reads from the FROM side. The panel shows it under the clicked
# component in both directions, so write the sentence to read either way.
RELATIONS: dict[tuple[str, str], str] = {
    (
        "GitHubIssues",
        "GitHubIntake",
    ): "An issue carrying the trigger label is a request to spend money; the reader refuses it if the body was edited after the label was applied.",
    (
        "GitHubIntake",
        "WorkQueue",
    ): "An admitted issue becomes one queue item with the issue text as its spec and a source reference so the verdict can be posted back.",
    (
        "WorkQueue",
        "ServeDaemon",
    ): "The daemon takes exactly one ready item per cycle, under a lease, so two runs can never touch the same repository at once.",
    (
        "SpendLedger",
        "ServeDaemon",
    ): "Before claiming anything the daemon asks the ledger whether today's budget, cost coverage and poison count allow another run.",
    (
        "Inbox",
        "ServeDaemon",
    ): "The daemon admits no new work while more decisions wait for you than the cap allows; unread decisions are a reason to stop, not to continue.",
    (
        "ServeDaemon",
        "Scheduler",
    ): "One admitted item becomes one factory run, launched as a subprocess the daemon can kill on a deadline.",
    (
        "Operator",
        "Architect",
    ): "You hand the planner a spec; it is the only input you must write, and everything below measures against what it says.",
    (
        "Architect",
        "Manifest",
    ): "The planner splits the spec into components with dependencies and allowed paths, and halts instead of guessing when the spec has a blocker.",
    (
        "Architect",
        "PRD",
    ): "For each component the planner writes the stories and acceptance criteria that every later check will measure against: the set point.",
    (
        "Manifest",
        "Scheduler",
    ): "The graph tells the scheduler which components are ready: those whose dependencies have actually merged, not merely finished.",
    (
        "Scheduler",
        "Worktrees",
    ): "Each component gets its own working copy cut from the base branch, so parallel builds cannot see or damage each other.",
    (
        "Feedforward",
        "EngineerLoop",
    ): "Before the agent writes a line, it is told the module map, public interfaces, import graph and conventions, computed from the tree with no model call.",
    (
        "KnowledgeInjector",
        "EngineerLoop",
    ): "Facts distilled from components built earlier are placed in the prompt so the agent inherits what was already learned instead of rediscovering it.",
    (
        "RetryContext",
        "EngineerLoop",
    ): "What failed on the last attempt is handed to the agent as parsed failures with file, line and a fix hint; after R10.2, only what is failing now.",
    (
        "EngineerLoop",
        "AgentAdapter",
    ): "The loop assembles one prompt and sends it to the agent through the adapter, once per iteration, up to the iteration cap.",
    (
        "AgentAdapter",
        "CodingAgent",
    ): "The adapter runs the agent as a subprocess in its own process group, on a deadline, and feeds the prompt on stdin.",
    (
        "CodingAgent",
        "AgentAdapter",
    ): "The agent streams its output back; the adapter watches for the completion marker and scrapes token and cost figures from what the CLI reports.",
    (
        "PRD",
        "EngineerLoop",
    ): "The loop points the agent at the highest-priority story not yet marked done.",
    (
        "EngineerLoop",
        "PRD",
    ): "The agent marks a story done by setting its flag; that flag is a claim, and after R10.3 the reviewer must confirm it before it counts.",
    (
        "Breaker",
        "EngineerLoop",
    ): "If several iterations in a row change nothing (same diff, same test signature), the breaker halts the loop instead of spending the remaining budget.",
    (
        "PathGuard",
        "EngineerLoop",
    ): "Anything the agent changed outside its allowed paths is reverted or failed before the completion marker is honoured, so a claim of done cannot smuggle out-of-scope edits.",
    (
        "EngineerLoop",
        "Pipeline",
    ): "When the loop ends, by completion, cap, breaker or timeout, its result goes to the pipeline, which decides what the measurement says.",
    (
        "Pipeline",
        "MechanicalVerifier",
    ): "The pipeline hands the finished working copy and its PRD to the checks that need no model: tests, typecheck, lint, scope, bad patterns.",
    (
        "Pipeline",
        "Reviewer",
    ): "After the mechanical checks pass, the diff and the acceptance criteria go to an independent reviewer, by default from a different model family than the engineer.",
    (
        "Pipeline",
        "SecurityReviewer",
    ): "The same diff goes to a security reviewer working from a threat taxonomy; off by default, blocking at a severity threshold in hard mode.",
    (
        "PolicyEnvelope",
        "MechanicalVerifier",
    ): "The written merge rules (denied paths, size caps, dependency and licence rules, secret patterns) are checked on the diff and lockfile as one of the mechanical checks.",
    (
        "AdequacyGate",
        "MechanicalVerifier",
    ): "The tests themselves are checked: deleted tests, added skips, lost assertions, and new test files that assert nothing falsifiable.",
    (
        "FixturesOracle",
        "MechanicalVerifier",
    ): "Input and output pairs approved in the PRD are run sandboxed, outside the tree the agent can write, so a gamed test file cannot deselect them.",
    (
        "MechanicalVerifier",
        "Findings",
    ): "Every failed check becomes a typed finding with a file, a line and a fix hint; a check that could not run leaves a finding saying so.",
    (
        "Reviewer",
        "Findings",
    ): "Each acceptance criterion gets a verdict, and each concern beyond the criteria (scope creep, weak tests, dead code) becomes a finding.",
    (
        "SecurityReviewer",
        "Findings",
    ): "Each vulnerability found becomes a finding mapped to an OWASP category, with severity.",
    (
        "Findings",
        "Pipeline",
    ): "The findings are the error signal: the pipeline reads them, not the agent's summary, to decide whether the component passed.",
    (
        "Pipeline",
        "RetryContext",
    ): "When a gate fails and retries remain, the pipeline writes the findings into the context the next attempt will receive.",
    (
        "Pipeline",
        "Distiller",
    ): "Once every gate has passed and before the merge, the diff goes to the distiller so what was learned is captured while it is still the true delta.",
    (
        "Distiller",
        "KnowledgeInjector",
    ): "Durable facts about the built artifact are written to disk and picked up by later components' prompts; how often they are used is measured.",
    (
        "Pipeline",
        "PullRequests",
    ): "A component that passed every gate is pushed, opened as a pull request and merged; it counts as complete only when the merge is confirmed.",
    (
        "PullRequests",
        "GitHubPRs",
    ): "One pull request per component, with the findings in its body, is the factory's output; a human can read every decision there.",
    (
        "PullRequests",
        "ContractTester",
    ): "After components merge, the integration tests run on the merged tiers of the dependency graph.",
    (
        "ContractTester",
        "Scheduler",
    ): "A failing tier is attributed to the most recently merged component, which the scheduler resets and re-runs against the fresh base.",
    (
        "Pipeline",
        "Inbox",
    ): "A merge you asked to approve, a policy exception, a budget overrun: the pipeline parks the decision for you instead of taking it.",
    (
        "Scheduler",
        "AutonomyLadder",
    ): "After a run, its outcome (decisive or not, merged components, violations) is folded into the evidence the ladder promotes or demotes on.",
    (
        "AutonomyLadder",
        "Pipeline",
    ): "At run start the ladder derives the permission bundle for the current level; the bundle can only withhold, never grant, so a hand-edited flag cannot exceed it.",
    (
        "PolicyEnvelope",
        "AutonomyLadder",
    ): "A policy violation demotes the factory one level automatically; there is no appeal at run time.",
    (
        "Calibration",
        "AutonomyLadder",
    ): "A regression in the reviewers' measured detection rate opens a decision for you and, behind a switch, demotes (R10.11).",
    (
        "AutonomyLadder",
        "StateDir",
    ): "The level and its history live in the control directory outside the repository, so the agent it governs cannot edit its own governor.",
    (
        "SpendLedger",
        "StateDir",
    ): "Daily spend is kept outside the tree too, rewritten whole under a lock, and refused rather than guessed when unreadable.",
    (
        "Inbox",
        "StateDir",
    ): "The decisions waiting for you are stored outside the tree; an inbox the agent could edit would not be yours.",
    (
        "Scheduler",
        "EvolutionJournal",
    ): "Every component's outcome, failure signature, cost and finding summary is appended to the journal after the run.",
    (
        "EvolutionJournal",
        "Proposals",
    ): "Patterns that recur across runs become proposals written for you to read; today nothing reads a proposal back into a run.",
    (
        "EvolutionJournal",
        "Replay",
    ): "The recorded runs are what the replay tool feeds through the ladder's thresholds to say what would have fired, without changing anything.",
    (
        "Pipeline",
        "EventBus",
    ): "Every phase start, verdict, retry and finding is emitted as a typed event; the event is the record, and sinks may not change control flow.",
    (
        "Scheduler",
        "EventBus",
    ): "Run start, component scheduling, budget and completion are emitted as typed events alongside the pipeline's.",
    (
        "EventBus",
        "ProgressLog",
    ): "The older progress log is still written, byte-compatible, for anything that reads it.",
    (
        "EventBus",
        "Reducer",
    ): "The reducer folds the event file into the current state of the run; anything shown anywhere can be rebuilt from that file.",
    (
        "Reducer",
        "Dashboard",
    ): "The terminal dashboard renders the reduced state live, attaches to a run from another terminal, and replays a finished one.",
    (
        "Reducer",
        "CLI",
    ): "ks status prints the same reduced state for scripts and CI, with lower-bound markers wherever a cost figure is unreported.",
    (
        "EventBus",
        "LinearMirror",
    ): "Failures and budget halts are mirrored to the tracker as comments; the mirror is outbound only and can never fail a run.",
    (
        "Dashboard",
        "Operator",
    ): "You watch the board, open a component, read the findings and the transcript, and approve or reject at a checkpoint.",
    (
        "Operator",
        "Inbox",
    ): "You approve, reject, retry or snooze each waiting decision from the command line; nothing proceeds past a parked decision without you.",
    (
        "Operator",
        "AutonomyLadder",
    ): "Only you can promote, and only with the evidence in place and a recorded acknowledgement; demotion never needs you.",
}

# Verbs. The relationship wheel prints one short verb on each spoke, read
# from the clicked component outward. Defaults by layer (verb when the
# clicked component is FROM, verb when it is TO); overrides where the default
# would mislead.
VERBS: dict[str, tuple[str, str]] = {
    "work": ("hands to", "receives from"),
    "measure": ("measures", "is measured by"),
    "feedback": ("feeds back to", "is fed by"),
    "operator": ("asks", "is steered by"),
    "trust": ("governs", "is governed by"),
    "learn": ("teaches", "learns from"),
    "record": ("records to", "is rebuilt from"),
}

VERB_OVERRIDES: dict[tuple[str, str], tuple[str, str]] = {
    ("Pipeline", "MechanicalVerifier"): ("submits to", "measures for"),
    ("Pipeline", "Reviewer"): ("submits to", "measures for"),
    ("Pipeline", "SecurityReviewer"): ("submits to", "measures for"),
    ("Findings", "Pipeline"): ("decides", "reads"),
    ("EngineerLoop", "PRD"): ("claims done in", "is claimed by"),
    ("PRD", "EngineerLoop"): ("points", "targets"),
    ("PathGuard", "EngineerLoop"): ("fences", "is fenced by"),
    ("Breaker", "EngineerLoop"): ("halts", "is halted by"),
    ("AutonomyLadder", "Pipeline"): ("withholds from", "is limited by"),
    ("PolicyEnvelope", "AutonomyLadder"): ("demotes", "is demoted by"),
    ("Calibration", "AutonomyLadder"): ("can demote", "watches"),
    ("Operator", "AutonomyLadder"): ("promotes", "is promoted by"),
    ("Operator", "Inbox"): ("decides in", "waits for"),
    ("Pipeline", "Inbox"): ("parks in", "holds for"),
    ("Dashboard", "Operator"): ("shows", "watches"),
    ("Operator", "Architect"): ("gives the spec to", "plans for"),
    ("ContractTester", "Scheduler"): ("resets via", "re-runs for"),
    ("Distiller", "KnowledgeInjector"): ("writes facts for", "reads facts from"),
    ("AutonomyLadder", "StateDir"): ("is kept in", "keeps"),
    ("SpendLedger", "StateDir"): ("is kept in", "keeps"),
    ("Inbox", "StateDir"): ("is kept in", "keeps"),
    ("EventBus", "Reducer"): ("is folded by", "folds"),
    ("Reducer", "Dashboard"): ("drives", "renders"),
    ("EventBus", "LinearMirror"): ("mirrors to", "mirrors"),
}

# Journeys. A reader steps through one at a time; each step names the
# components to light and the edge to trace, with one sentence. `acts` is
# who does the step; `measures` is who checks it (empty when nothing does,
# which is itself the lesson).
JOURNEYS = (
    Journey(
        id="spec-to-merge",
        label="A spec becomes a merged pull request",
        steps=(
            Step(
                acts=("GitHubIssues", "GitHubIntake"),
                measures=("GitHubIntake",),
                edge=("GitHubIssues", "GitHubIntake"),
                say="You label an issue. The reader checks the label came before the last edit, then admits it as a queue item.",
            ),
            Step(
                acts=("ServeDaemon",),
                measures=("SpendLedger", "Inbox"),
                edge=("WorkQueue", "ServeDaemon"),
                say="The daemon runs its admission gates in a fixed order and claims one item only if every gate allows it.",
            ),
            Step(
                acts=("Architect",),
                measures=("Architect",),
                edge=("Architect", "PRD"),
                say="The planner attacks the spec for ambiguity and missing failure modes, halts on a blocker, and otherwise writes the components and their acceptance criteria.",
            ),
            Step(
                acts=("Scheduler", "Worktrees"),
                measures=(),
                edge=("Scheduler", "Worktrees"),
                say="Each ready component gets its own working copy; nothing is measured yet.",
            ),
            Step(
                acts=("Feedforward", "KnowledgeInjector"),
                measures=(),
                edge=("Feedforward", "EngineerLoop"),
                say="The agent is told what the codebase looks like and what earlier components learned, before it acts.",
            ),
            Step(
                acts=("EngineerLoop", "AgentAdapter", "CodingAgent"),
                measures=("Breaker", "PathGuard"),
                edge=("EngineerLoop", "AgentAdapter"),
                say="The agent works one story at a time and says when it is done. Only the stall detector and the scope fence watch this loop; neither reads the code.",
            ),
            Step(
                acts=("Pipeline",),
                measures=("MechanicalVerifier", "PolicyEnvelope", "AdequacyGate", "FixturesOracle"),
                edge=("Pipeline", "MechanicalVerifier"),
                say="The checks that need no model run first: tests, types, lint, scope, the merge rules, the tests' own quality, the approved fixtures.",
            ),
            Step(
                acts=("Pipeline",),
                measures=("Reviewer", "SecurityReviewer"),
                edge=("Pipeline", "Reviewer"),
                say="A reviewer from another model family judges every acceptance criterion; a security reviewer hunts vulnerabilities.",
            ),
            Step(
                acts=("Findings", "Pipeline"),
                measures=("Findings",),
                edge=("Findings", "Pipeline"),
                say="The findings, not the agent's summary, decide: pass, or write them into the next attempt's context and retry.",
            ),
            Step(
                acts=("Distiller",),
                measures=(),
                edge=("Pipeline", "Distiller"),
                say="What was learned about the artifact is written down while the diff is still the true delta.",
            ),
            Step(
                acts=("PullRequests", "GitHubPRs"),
                measures=("PullRequests",),
                edge=("Pipeline", "PullRequests"),
                say="The component is pushed, opened and merged; it is complete only when the merge is confirmed.",
            ),
            Step(
                acts=("ContractTester",),
                measures=("ContractTester",),
                edge=("PullRequests", "ContractTester"),
                say="Integration tests run on the merged tiers; a failure is attributed to the last component merged, which re-runs against the fresh base.",
            ),
            Step(
                acts=("Scheduler",),
                measures=("AutonomyLadder", "EvolutionJournal"),
                edge=("Scheduler", "AutonomyLadder"),
                say="The run's outcome is folded into the ladder's evidence and appended to the journal.",
            ),
        ),
    ),
    Journey(
        id="failure-to-retry",
        label="A failure becomes the next attempt",
        steps=(
            Step(
                acts=("MechanicalVerifier",),
                measures=("MechanicalVerifier",),
                edge=("MechanicalVerifier", "Findings"),
                say="A check fails. Its output is parsed into a finding with the file, the line, the source context and a hint.",
            ),
            Step(
                acts=("Findings", "Pipeline"),
                measures=(),
                edge=("Findings", "Pipeline"),
                say="The pipeline reads the finding and, with retries left, decides to try again.",
            ),
            Step(
                acts=("Pipeline", "RetryContext"),
                measures=(),
                edge=("Pipeline", "RetryContext"),
                say="The finding is written into the retry context. Today that context only grows; after R10.2 it shows what is failing now and omits what was fixed.",
            ),
            Step(
                acts=("RetryContext", "EngineerLoop"),
                measures=(),
                edge=("RetryContext", "EngineerLoop"),
                say="The next attempt starts with that context in front of the agent, after the codebase context and before your standing instructions.",
            ),
            Step(
                acts=("EngineerLoop",),
                measures=("Breaker",),
                edge=("Breaker", "EngineerLoop"),
                say="If the attempt changes nothing, the stall detector halts it rather than spending the rest of the budget.",
            ),
        ),
    ),
    Journey(
        id="operator-steers",
        label="You steer the factory",
        steps=(
            Step(
                acts=("Operator", "Architect"),
                measures=(),
                edge=("Operator", "Architect"),
                say="You write the spec and, when the planner halts on a blocker, you fix the spec; there is no override flag.",
            ),
            Step(
                acts=("Dashboard", "Operator"),
                measures=(),
                edge=("Dashboard", "Operator"),
                say="You watch the board, drill into a component, and read the findings beside the transcript.",
            ),
            Step(
                acts=("Pipeline", "Inbox", "Operator"),
                measures=(),
                edge=("Operator", "Inbox"),
                say="Decisions the factory may not take alone wait for you in one place; you approve, reject, retry or snooze.",
            ),
            Step(
                acts=("Operator", "AutonomyLadder"),
                measures=(),
                edge=("Operator", "AutonomyLadder"),
                say="You promote the factory only with evidence and an acknowledgement; it demotes itself without asking.",
            ),
            Step(
                acts=("OperatorContext", "Steering"),
                measures=(),
                edge=("Feedforward", "EngineerLoop"),
                say="Planned: your golden patterns and standing corrections are read on every run, and a comment on a pull request appends to them (R10.8 to R10.10).",
            ),
        ),
    ),
    Journey(
        id="trust-earned-lost",
        label="The factory earns and loses autonomy",
        steps=(
            Step(
                acts=("Scheduler", "AutonomyLadder"),
                measures=(),
                edge=("Scheduler", "AutonomyLadder"),
                say="Every decisive run adds evidence at the current level: merged components, clean merges, violations.",
            ),
            Step(
                acts=("Operator", "AutonomyLadder"),
                measures=(),
                edge=("Operator", "AutonomyLadder"),
                say="When the evidence meets the level's entry criteria, you promote with an acknowledgement; the ladder never promotes itself.",
            ),
            Step(
                acts=("AutonomyLadder", "Pipeline"),
                measures=(),
                edge=("AutonomyLadder", "Pipeline"),
                say="At the next run start the level becomes a permission bundle that can only withhold: a higher level removes a gate, never adds a power the level does not carry.",
            ),
            Step(
                acts=("PolicyEnvelope", "AutonomyLadder"),
                measures=("PolicyEnvelope",),
                edge=("PolicyEnvelope", "AutonomyLadder"),
                say="One policy violation demotes one level, immediately, with a cooldown before re-promotion.",
            ),
            Step(
                acts=("Calibration", "HealthTrending", "AutonomyLadder"),
                measures=("Calibration", "HealthTrending"),
                edge=("Calibration", "AutonomyLadder"),
                say="Planned: a measured regression in the reviewers, or a health breach in the run metrics, opens a decision for you and can demote (R10.11, R8.4).",
            ),
            Step(
                acts=("AutonomyLadder", "StateDir"),
                measures=("StateDir",),
                edge=("AutonomyLadder", "StateDir"),
                say="All of this lives outside the repository. If the control directory is unreadable or inside the tree, the factory falls back to the lowest level.",
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
    layer_overrides=LAYER_OVERRIDES,
    verbs=VERBS,
    verb_overrides=VERB_OVERRIDES,
)
