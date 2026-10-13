"""Run commands that call Jev or a configured coding agent.

These commands are outside cli.py to keep the CLI module small.
`systemap.delta_jev` holds the Jev questions of `systemap delta`.
Jev calls must have `TYPESAFE_API_KEY` and print usage.
Completed semantic reports exit 0. Request errors exit 1.
Plan comparison can exit 1 for changes outside the recorded plan.

The questions and the answers use the provider records in `systemap.decision`.
`systemap.providers` selects the provider: Jev by default, or OpenAI when the user
selects it. A question type without a measured value for the selected provider is not
sent. A refusal from the decision provider stops triage and plan with exit 1.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from systemap import (
    agent,
    audit,
    config,
    decision,
    decision_kinds,
    delta,
    evidence,
    extract,
    extraction,
    history,
    jev,
    journeys,
    model_write,
    nest,
    providers,
    source_facts,
)
from systemap import plan as plan_mod
from systemap.decision import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionError,
    DecisionProvider,
    PredicateQuestion,
)

OK, STALE = 0, 1

# A hint says what a Jev feature does for the reader and how to stop the hint.
# Measurements are for maintainers: bench/jev/README.md records them, with the
# prompts and the repositories of each run.
#
# Where the report text is cut: the measured issues were a title and 1,500
# characters of body; past this the numbers in bench/jev do not apply.
REPORT_CAP = 2000
# The `suggest --decide` limit for one part is `same_at` in `systemap.decision.THRESHOLDS`.

TRIAGE_Q = "`report` is an issue for this system. Which component will the fix probably change?"
SAME_Q = (
    "Do `module_a` and `module_b` have the same system function and belong to one "
    "component? Components that only call each other or share types stay different."
)


def _client(cfg: config.Config, send: jev.Send | None = None) -> providers.Metered:
    return providers.select(cfg, send)


def _one(provider: DecisionProvider, question: decision.Question, label: str) -> ChoiceAnswer:
    """Give the choice answer to one question. A refusal raises DecisionError."""
    answer = provider.decide([question])[0]
    if isinstance(answer, decision.Refusal):
        raise DecisionError(f"the decision provider gave a refusal: {jev.printable(answer.reason)}")
    if not isinstance(answer, ChoiceAnswer):
        raise DecisionError(f"the answer to {label} does not select an option")
    return answer


def _facts(cfg: config.Config) -> dict[str, Any] | None:
    facts = extract.read_facts(cfg.facts_path)
    if not facts:
        print(f"No facts are available at {cfg.rel(cfg.facts_path)}\nrun: systemap extract")
        return None
    return facts


# ---- when a command asks Jev on its own, and what it says when it cannot ---------

# What Jev can add, for a command that sends no Jev request.
JUDGEMENT_HINT = (
    "hint: Set TYPESAFE_API_KEY to use systemap audit. Then Jev reads each module and "
    "its component. It gives a list of the modules that are probably in an incorrect "
    "component. Set [jev] enabled = false in systemap.toml to stop this hint."
)
DELTA_HINT = (
    "hint: To receive suggestions from the decision provider for moved modules and for "
    "modules without a component, give --decide or set [jev] enabled = true in "
    "systemap.toml. Jev must have TYPESAFE_API_KEY. OpenAI must have OPENAI_API_KEY. "
    "The suggestions do not change the delta result. "
    "Set [jev] enabled = false in systemap.toml to stop this hint."
)


def uses_jev(cfg: config.Config, flag: bool | None) -> bool:
    """Use an explicit flag, or an explicit `[jev] enabled = true` and an API key.

    A key alone does not select Jev. Thus a key in the environment sends no source.
    The key must be the key of the selected provider.
    """
    if flag is not None:
        return flag
    return cfg.jev_enabled is True and providers.has_key(cfg)


def hint(cfg: config.Config, text: str) -> None:
    """Print a Jev hint to stderr without an API key, unless `[jev] enabled = false`."""
    if cfg.jev_enabled is not False and not jev.has_key():
        print(text, file=sys.stderr)


def delta_hint(cfg: config.Config) -> None:
    """Print the delta hint to stderr, with or without a key, unless `[jev] enabled = false`."""
    if cfg.jev_enabled is not False:
        print(DELTA_HINT, file=sys.stderr)


# ---- audit -------------------------------------------------------------------------


def cmd_audit(args: argparse.Namespace, send: jev.Send | None = None) -> int:
    """Give the provider findings with exit 0, or exit 1 if the request cannot complete."""
    cfg = providers.chosen(config.load(args.root_path), getattr(args, "provider", None))
    facts = _facts(cfg)
    if facts is None:
        return STALE
    tree = nest.load(cfg)
    for line in decision_kinds.warnings(cfg.judgement_answered):
        print(line, file=sys.stderr)
    kinds = _measured_kinds(cfg, _kinds(args.kind) if args.kind else audit.DEFAULT_KINDS)
    if not kinds:
        return STALE
    plan = audit.make_plan(tree, facts, cfg, kinds)
    if args.dry_run:
        return _dry_run(cfg, plan, send)
    try:
        client = _client(cfg, send)
        answers = client.decide(plan.questions)
        found = audit.lines(plan, answers, decision.thresholds(client.name))
    except DecisionError as exc:
        print(f"audit: {exc}")
        return STALE
    texts = [line.text for line in found]
    current_evidence = audit.evidence(tree, facts, cfg.root, texts)
    result = audit.apply_reviewed(found, cfg.judgement_answered, current_evidence, kinds)
    open_lines = [x for x in result.open if decision_kinds.kind_of(x.text) in kinds]
    print(
        *audit.report(
            open_lines,
            result.answered,
            result.stale,
            client.usage.line(),
            not args.brief,
            result.pending,
            result.policies,
            plan.unasked,
            decision.refused(plan.questions, answers),
            plan.unknown,
        ),
        sep="\n",
    )
    return OK


def _kinds(given: list[str]) -> tuple[str, ...]:
    """Give the current kind names. Print a warning for each previous name."""
    for name in dict.fromkeys(k for k in given if k in decision_kinds.PREVIOUS):
        print(decision_kinds.option_warning(name), file=sys.stderr)
    return tuple(dict.fromkeys(decision_kinds.current(k) for k in given))


def _measured_kinds(cfg: config.Config, kinds: tuple[str, ...]) -> tuple[str, ...]:
    """Give the question types with a measured value. Print the reason for each other type."""
    skipped = providers.missing(cfg, kinds)
    for kind in skipped:
        print(f"audit: {decision.unmeasured(cfg.decision_provider, kind)}")
    return tuple(k for k in kinds if k not in skipped)


def _dry_run(cfg: config.Config, plan: audit.Plan, send: jev.Send | None) -> int:
    """Count the questions. With a key, get only the model list to count cached answers."""
    pending: int | str | None = None
    chars = providers.chars(cfg, plan.questions)
    if send is not None or providers.has_key(cfg):
        try:
            pending = _client(cfg, send).pending(plan.questions)
        except DecisionError as exc:
            print(*audit.dry_run(plan, f"unknown: {exc}", chars), sep="\n")
            return STALE
    print(*audit.dry_run(plan, pending, chars), sep="\n")
    return OK


# ---- triage ------------------------------------------------------------------------


def _neighbours(model: Any, cid: str) -> str:
    into = sorted({f.src for f in model.flows if f.dst == cid})
    out = sorted({f.dst for f in model.flows if f.src == cid})
    return f"flows from {', '.join(into) or 'nothing'}. Flows to {', '.join(out) or 'nothing'}"


def cmd_triage(args: argparse.Namespace, send: jev.Send | None = None) -> int:
    """Predict the three components an issue fix will probably change."""
    cfg = providers.chosen(config.load(args.root_path), getattr(args, "provider", None))
    facts = _facts(cfg)
    if facts is None:
        return STALE
    text = sys.stdin.read() if args.text == "-" else args.text
    if not text.strip():
        print("triage: give the issue text, or - to read it from stdin")
        return STALE
    top = nest.load(cfg).top
    try:
        providers.require_triage(cfg)
        client = _client(cfg, send)
        answer = _one(client, triage_question(cfg, top, text), "triage")
        spread = decision.spread(answer)
    except DecisionError as exc:
        print(f"triage: {exc}")
        return STALE
    by = audit.modules_by_card(top.model, facts)
    cut = " (the command used only the first 2,000 characters)" if len(text) > REPORT_CAP else ""
    sure = "no confidence" if answer.confidence is None else f"confidence {answer.confidence:.2f}"
    print(f"triage: {sure}{cut}")
    for cid, p in audit._top(spread, 3):
        if cid == audit.NONE:
            print(f"  {p:.2f}  none of the components")
            continue
        mods = by.get(cid, [])
        more = f" and {len(mods) - 5} more" if len(mods) > 5 else ""
        print(f"  {p:.2f}  {cid}: {', '.join(mods[:5]) or 'no modules'}{more}")
        print(f"        on the map: {_neighbours(top.model, cid)}")
    print(client.usage.line())
    return OK


def triage_question(cfg: config.Config, top: nest.Map, text: str) -> ChoiceQuestion:
    """Make the triage question for one issue text."""
    state = {"system": cfg.name, "report": text[:REPORT_CAP]}
    options = audit.owner_criteria(top.model, top.meaning)
    return ChoiceQuestion("triage", "where", TRIAGE_Q, state, options)


# ---- journeys: a walk written for a way in nothing walks from yet ------------------

# How many walks one run writes without being asked for more: a maintainer
# reads what comes back, and a dozen drafts at once is not reading.
JOURNEY_CAP = 3


def cmd_journeys(args: argparse.Namespace, run_command: agent.Run | None = None) -> int:
    """Write sequences for entry points without examined sequence coverage."""
    cfg = config.load(args.root_path)
    facts = _facts(cfg)
    if facts is None:
        return STALE
    tree = nest.load(cfg)
    from systemap.journey_coverage import reviewed_entries
    from systemap.model import claimed

    covered = reviewed_entries(m.meaning for m in tree.maps)
    components = facts.get("components", {})
    left: list[tuple[nest.Map, journeys.Group]] = []
    for current in tree.maps:
        owned = set(evidence.owners(current.model, facts))
        opened = {module for card in current.model.opening for module in claimed(card, components)}
        groups = journeys.gather(
            current.model,
            current.meaning,
            facts,
            modules=owned - opened,
            covered=covered,
        )
        left.extend((current, group) for group in groups)
    if not left:
        print("journeys: every entry point has an examined sequence")
        return OK
    if args.dry_run or not agent.has_agent(cfg):
        print(*_would_write(left, cfg), sep="\n")
        return OK
    return _write_journeys(cfg, facts, left[: args.limit], run_command)


def _would_write(left: list[tuple[nest.Map, journeys.Group]], cfg: config.Config) -> list[str]:
    """List proposed sequences without file changes.

    An entry-point group of one type in one component counts as one proposed sequence.
    Judgement uses the same grouping for its findings.
    """
    total = sum(len(group.ways_in) for _map, group in left)
    ways, them = ("entry point", "it") if total == 1 else ("entry points", "them")
    head = f"journeys: {total} {ways} without a sequence for {them}"
    if len(left) < total:
        walks = "sequence" if len(left) == 1 else "sequences"
        head += f", {len(left)} {walks} to write: one for each component group"
    out = [head + ":"]
    out += [f"  {current.prefix}{group.label} ({current.rel})" for current, group in left[:20]]
    if len(left) > 20:
        out.append(f"  and {len(left) - 20} more")
    if not agent.has_agent(cfg):
        out.append(f"  {agent.NO_AGENT}")
    return out


def _write_journeys(
    cfg: config.Config,
    facts: dict[str, Any],
    take: list[tuple[nest.Map, journeys.Group]],
    run_command: agent.Run | None,
) -> int:
    """Get agent sequences, examine map consistency, and write accepted sequences."""
    try:
        writer = agent.from_cfg(cfg, run_command)
    except agent.AgentError as exc:
        print(f"journeys: {exc}")
        return STALE
    sources: dict[Path, str] = {}
    written: dict[Path, list[str]] = {}
    out: list[str] = []
    for current, group in take:
        try:
            taken = written.get(current.path, ())
            draft = journeys.write_one(writer, current.model, current.meaning, facts, group, taken)
        except agent.AgentError as exc:
            out.append(f"journeys: {exc}")
            break
        _record_journey(current, group, draft, sources, written, out)
    if written and not _commit_journeys(cfg, sources, written, out):
        return STALE
    print(*out, sep="\n")
    writer_usage(writer)
    return _written_code(take, written)


def _written_code(
    take: list[tuple[nest.Map, journeys.Group]], written: dict[Path, list[str]]
) -> int:
    """The command fails when it had sequences to write and wrote none."""
    return OK if written or not take else STALE


def _record_journey(
    current: nest.Map,
    group: journeys.Group,
    draft: journeys.Draft,
    sources: dict[Path, str],
    written: dict[Path, list[str]],
    out: list[str],
) -> None:
    if draft.journey is None:
        out.append(f"journeys: no sequence written for {group.label}")
        out += [f"      {p}" for p in draft.problems]
        return
    source = sources.get(current.path)
    if source is None:
        source = current.path.read_text(encoding="utf-8-sig")
    grown = journeys.add_to_source(source, draft.journey)
    if grown is None:
        out.append(f"journeys: {current.rel} has no journeys list. Add this source:")
        out += journeys.as_source(draft.journey)
        return
    sources[current.path] = grown
    written.setdefault(current.path, []).append(draft.journey.id)
    out.append(
        f"journeys: wrote {draft.journey.id} ({draft.journey.label}) "
        f"for {current.prefix}{group.label}"
    )
    out += [f"      {p}" for p in draft.problems]


def _commit_journeys(
    cfg: config.Config,
    sources: dict[Path, str],
    written: dict[Path, list[str]],
    out: list[str],
) -> bool:
    """Validate proposed source before writing any sequence files."""
    try:
        model_write.write_models(sources)
    except (SyntaxError, OSError) as exc:
        print(f"journeys: the command could not write the proposed model: {exc}")
        return False
    for path, ids in written.items():
        out.append(f"  {len(ids)} written into {cfg.rel(path)}, each marked drafted=True")
    out.append("  compare each sequence with the source. Then remove its drafted line")
    out.append("  run: systemap check && systemap judgement")
    return True


def _atomic_model_write(path: Path, source: str) -> None:
    """Validate full source, then replace the model in one operation."""
    model_write.write_models({path: source})


def writer_usage(writer: agent.Agent) -> None:
    if writer.usage.called or writer.usage.cached:
        print(writer.usage.line(), file=sys.stderr)


# ---- suggest --decide: groups from the provider answers about module pairs --------


def pair_candidates(facts: dict[str, Any], mods: list[str]) -> list[tuple[str, str]]:
    """Get import-connected pairs and adjacent module names within each package."""
    known = set(mods)
    by_package: dict[str, list[str]] = {}
    for m in mods:
        by_package.setdefault(source_facts.package_of(m, facts["components"]), []).append(m)
    pairs = {(a, b) for ms in by_package.values() for a, b in zip(ms, ms[1:], strict=False)}
    for a in mods:
        for b in facts["components"][a].get("imports", []):
            if b in known and b != a:
                pairs.add((a, b) if a < b else (b, a))
    return sorted(pairs)


def groups(mods: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Get connected groups from accepted module pairs, with the largest first."""
    parent = {m: m for m in mods}

    def find(m: str) -> str:
        while parent[m] != m:
            parent[m] = parent[parent[m]]
            m = parent[m]
        return m

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    out: dict[str, list[str]] = {}
    for m in mods:
        out.setdefault(find(m), []).append(m)
    return sorted(out.values(), key=lambda g: (-len(g), g[0]))


def same_question(cfg: config.Config, facts: dict[str, Any], a: str, b: str) -> PredicateQuestion:
    """Make the question that asks if two modules are in one component."""
    state = {
        "system": cfg.name,
        "module_a": audit.module_state(facts, a, names_cap=25),
        "module_b": audit.module_state(facts, b, names_cap=25),
    }
    return PredicateQuestion(f"{a}|{b}", "same", SAME_Q, state)


def suggest_groups(
    cfg: config.Config, facts: dict[str, Any], provider: DecisionProvider
) -> list[str]:
    """Give the module groups. A refusal gives no pair. The output gives the count of refusals."""
    comps = facts["components"]
    mods = sorted(m for m in comps if not source_facts.is_empty_marker(comps[m]))
    questions = [same_question(cfg, facts, a, b) for a, b in pair_candidates(facts, mods)]
    same_at = decision.value(decision.thresholds(provider.name), "same_at")
    answers = provider.decide(questions)
    edges = []
    for q, answer in zip(questions, answers, strict=True):
        p = decision.probability(answer, q.key)
        if p is not None and p >= same_at:
            edges.append((q.key.split("|")[0], q.key.split("|")[1]))
    found = groups(mods, edges)
    out = [
        f"{SUGGEST}: {len(found)} groups from {len(questions)} questions about module pairs. "
        f"A pair is in one component if P >= {same_at}. Examine these proposed groups. "
        "On two of five development maps, the accuracy was lower than with one component "
        "for each package",
    ]
    refused = decision.refused(questions, answers)
    if refused:
        count = len(refused)
        out.append(f"  no answer: the decision provider gave a refusal for {count} pair questions")
    for k, g in enumerate(found, 1):
        out.append(f"  group {k} ({len(g)} modules): {', '.join(g)}")
    return out


SUGGEST = "suggest --decide"


def cmd_suggest_jev(cfg: config.Config, facts: dict[str, Any]) -> int:
    """Print the module groups from the provider answers, or the reason for no groups."""
    try:
        providers.require(cfg, "same_at")
        client = _client(cfg)
    except DecisionError as exc:
        print(f"{SUGGEST}: {exc}")
        return STALE
    try:
        lines, code = suggest_groups(cfg, facts, client), OK
    except DecisionError as exc:
        lines, code = [f"{SUGGEST}: {exc}"], STALE
    print(*lines, client.usage.line(), sep="\n")
    return code


# ---- plan: the work projected onto the map, then checked against what happened ------


def cmd_plan(args: argparse.Namespace, send: jev.Send | None = None) -> int:
    """Predict changed components and give their adjacent flows, sequences, and rules."""
    cfg = providers.chosen(config.load(args.root_path), getattr(args, "provider", None))
    if args.check:
        return _check_plan(cfg, args)
    text = sys.stdin.read() if args.task == "-" else (args.task or "")
    if not text.strip():
        print("plan: give the task in your own words, or - to read it from stdin")
        return STALE
    top = nest.load(cfg).top
    try:
        cut = providers.require(cfg, "plan_cut")
        client = _client(cfg, send)
        spread = decision.spread(_one(client, plan_question(cfg, top, text), "plan"))
    except DecisionError as exc:
        print(f"plan: {exc}")
        return STALE
    made = plan_mod.project(top.model, top.meaning, text.strip(), spread, cut=cut)
    # A projection that names nothing is not written down: there would be
    # nothing to check it against later.
    where = plan_mod.save(cfg, made) if made.cards else None
    print(*_plan_lines(made, cfg, where), sep="\n")
    providers.usage_to_stderr(client)
    return OK


def plan_question(cfg: config.Config, top: nest.Map, text: str) -> ChoiceQuestion:
    """Make the plan question for one task text."""
    state = {"system": cfg.name, "task": text[: plan_mod.TEXT_CAP]}
    options = audit.owner_criteria(top.model, top.meaning)
    return ChoiceQuestion("plan", "where", plan_mod.PLAN_Q, state, options)


def _plan_lines(made: plan_mod.Projection, cfg: config.Config, where: Path | None) -> list[str]:
    """Give each predicted component and its adjacent map context."""
    if not made.cards:
        return [
            "plan: no component is a clear candidate for this work",
            "  give the task in the system's terms, or run: systemap triage",
        ]
    out = [f"plan {made.id}: {len(made.cards)} components this work will probably change"]
    for one in made.around:
        out.append(f"  {one.card} ({made.weights.get(one.card, 0):.2f})")
        out += _some("flow", one.flows)
        out += _some("sequence", one.journeys)
        out += _some("rule", one.rules)
    out.append(f"  written to {cfg.rel(where)}" if where else "  not written")
    out.append(f"  after the work: systemap plan --check {made.id} --base <ref>")
    return out


# How much of a card's surroundings one plan prints. A hub card sits on a
# dozen flows, and a list that long is read as noise rather than as context.
AROUND_CAP = 6


def _some(word: str, found: tuple[str, ...]) -> list[str]:
    """Give adjacent map context up to the display limit."""
    out = [f"      {word}: {x}" for x in found[:AROUND_CAP]]
    if len(found) > AROUND_CAP:
        out.append(f"      {word}: and {len(found) - AROUND_CAP} more")
    return out


def _check_plan(cfg: config.Config, args: argparse.Namespace) -> int:
    """Compare projected components with changed components."""
    found = plan_mod.load(cfg, args.check)
    if found is None:
        known = ", ".join(plan_mod.saved(cfg)) or "none yet"
        print(f"plan: no plan has the ID {args.check} (saved plans: {known})")
        return STALE
    try:
        base_facts, head_facts = _plan_facts(cfg, args.base)
    except delta.DeltaError as exc:
        print(f"plan: {exc}")
        return STALE
    top = nest.load(cfg).top
    owner = evidence.owners(top.model, head_facts)
    changed = plan_mod.touched(base_facts, head_facts, owner)
    missed, untouched = plan_mod.check(list(found.get("cards", [])), changed)
    print(*_check_lines(found, changed, missed, untouched, args.base), sep="\n")
    return STALE if missed else OK


def _plan_facts(cfg: config.Config, base: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Get base facts and working-tree facts for plan comparison."""
    sha = delta.merge_base(cfg.root, base, "HEAD")
    return history.facts_at(cfg, sha), extraction.build(cfg)


def _check_lines(
    found: dict[str, Any], changed: set[str], missed: list[str], untouched: list[str], base: str
) -> list[str]:
    out = [
        f"plan {found.get('id', '')} against the code since {base}: "
        f"{len(changed)} components changed, {len(found.get('cards', []))} were projected"
    ]
    for cid in missed:
        out.append(f"  not in the plan: {cid} changed and the plan did not name it")
    out += [f"  in the plan, not changed: {cid}" for cid in untouched]
    if missed:
        out.append("  examine each component. The work changed a component that is not in the plan")
    elif not untouched:
        out.append("  the changed components agree with the plan")
    return out


# ---- the parsers -------------------------------------------------------------------


def add_parsers(sub: Any, add_root: Callable[[argparse.ArgumentParser], None]) -> None:
    s = sub.add_parser(
        "audit",
        help="Ask the decision provider to examine the map claims.",
        description="The decision provider (Jev or OpenAI) examines module ownership, "
        "component sentences, flow claims, and invariants. "
        "It can give possible owners for modules without a component. It can identify claims "
        "that do not agree with the source. "
        "The command sends facts and model text to the API of the decision provider. "
        "Set TYPESAFE_API_KEY (Jev) or OPENAI_API_KEY (OpenAI) before use.",
    )
    add_root(s)
    providers.add_option(s)
    s.add_argument(
        "--dry-run",
        action="store_true",
        help="Count the proposed questions. Send no map data. With a key, the command reads "
        "only the model list from the API, to count the cached answers.",
    )
    s.add_argument(
        "--kind",
        action="append",
        default=[],
        choices=decision_kinds.AUDIT_NAMES,
        metavar="KIND",
        help="Select this question type. Use the option again for more types (one of: "
        + ", ".join(f'"{k}"' for k in config.AUDIT_KINDS)
        + f'). The default does not include "{decision_kinds.FLOW}". Its holdout result was '
        'less than the threshold. The previous names, such as "jev flow", stay correct for '
        "one release.",
    )
    s.add_argument(
        "--brief",
        action="store_true",
        help=(
            "Print the findings without explanation rows. Use systemap explain KIND for the "
            "full explanation."
        ),
    )
    s.set_defaults(func=lambda args: cmd_audit(_rooted(args)))

    s = sub.add_parser(
        "journeys",
        help="Write sequences for entry points without an examined sequence.",
        description="For an entry point without a sequence, the map does not give the steps "
        "of its operation. "
        "The configured [agent] command reads source and gives component steps with sentences. "
        "systemap compares the steps with map flows and writes accepted sequences as drafts. "
        "Before you accept a draft, compare it with the source.",
    )
    add_root(s)
    s.add_argument(
        "--limit",
        type=int,
        default=JOURNEY_CAP,
        help=f"Set the maximum number of sequences for each run. The default is {JOURNEY_CAP}.",
    )
    s.add_argument(
        "--dry-run", action="store_true", help="Give the proposed sequences. Change no files."
    )
    s.set_defaults(func=lambda args: cmd_journeys(_rooted(args)))

    s = sub.add_parser(
        "plan",
        help="Give the components that a task will probably change. Then compare the plan with "
        "the changes.",
        description="The decision provider compares a task with the purpose of each component. "
        "The output gives the probable components with their flows, sequences, and rules. "
        "The --check option compares the saved plan projection with the changed code. "
        "Set TYPESAFE_API_KEY (Jev) or OPENAI_API_KEY (OpenAI) before use.",
    )
    add_root(s)
    providers.add_option(s)
    s.add_argument("task", nargs="?", help="Give the task, or - to read stdin.")
    s.add_argument("--check", metavar="ID", help="Compare a saved plan with changed components.")
    s.add_argument(
        "--base",
        default="origin/main",
        help="Set the base revision for --check. The default is origin/main.",
    )
    s.set_defaults(func=lambda args: cmd_plan(_rooted(args)))

    s = sub.add_parser(
        "triage",
        help="Give the three components that an issue fix will probably change.",
        description="The decision provider compares the issue with the purpose of each "
        "component. "
        "It gives the three components that the fix will probably change. It also gives their "
        "modules and their flows on the map. "
        "Give the text as an argument, or - to read stdin. "
        "Set TYPESAFE_API_KEY (Jev) or OPENAI_API_KEY (OpenAI) before use.",
    )
    add_root(s)
    providers.add_option(s)
    s.add_argument("text", help="Give the issue title and text, or - to read stdin.")
    s.set_defaults(func=lambda args: cmd_triage(_rooted(args)))


def _rooted(args: argparse.Namespace) -> argparse.Namespace:
    from systemap.cli import _root

    args.root_path = _root(args)
    return args
