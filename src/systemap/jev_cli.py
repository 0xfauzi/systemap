"""Run commands that call Jev or a configured coding agent.

These commands are outside cli.py to keep the CLI module small.
Jev calls must have `TYPESAFE_API_KEY` and print usage.
Completed semantic reports exit 0. Request errors exit 1.
Plan comparison can exit 1 for changes outside the recorded plan.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from systemap import (
    agent,
    audit,
    config,
    delta,
    evidence,
    extract,
    history,
    jev,
    journeys,
    judgement,
    model_write,
    moves,
    nest,
)
from systemap import plan as plan_mod
from systemap.jev import Ask, JevError

OK, STALE = 0, 1

# Where the report text is cut: the measured issues were a title and 1,500
# characters of body; past this the numbers in bench/jev do not apply.
REPORT_CAP = 2000
# A module that disappeared is paired with Jev's pick at this confidence or
# more, when delta's own three questions left it unpaired: on the renames in
# five repositories this found 82 real renames against delta's 66, and 16 of
# the 17 pairings it added were right (labelled blind from the commits).
MOVE_AT = 0.8
# Pairs at or above this are one part, for `suggest --jev`: with the threshold
# chosen on four development maps and scored on the fifth, pairwise F1 beat one
# card per package by 0.18 on average, and lost on two maps of five.
SAME_AT = 0.4

TRIAGE_Q = "`report` is an issue for this system. Which component will the fix probably change?"
BECAME_Q = (
    "The commit removed `old_module` and added the option modules. Which "
    "new module is the removed module after a move, rename, or edit? If no option "
    "continues the removed module, select the deleted option."
)
NOT_MOVED = "not moved: deleted"
# How many new modules the question offers: the measured cap.
MOVE_OPTIONS = 250
SAME_Q = (
    "Do `module_a` and `module_b` have the same system function and belong to one "
    "component? Components that only call each other or share types stay different."
)


def _client(cfg: config.Config, send: jev.Send | None = None) -> jev.Jev:
    return jev.from_env(cfg.jev_model, cfg.jev_cache_path, send)


def _facts(cfg: config.Config) -> dict[str, Any] | None:
    facts = extract.read_facts(cfg.facts_path)
    if not facts:
        print(f"no facts at {cfg.rel(cfg.facts_path)}\nrun: systemap extract")
        return None
    return facts


# ---- when a command asks Jev on its own, and what it says when it cannot ---------

# What the commands that stay offline say Jev would add, when no key is set.
# Each figure is measured (bench/jev) and quoted as measured.
JUDGEMENT_HINT = (
    "hint: TYPESAFE_API_KEY enables systemap audit. It found 95% of planted assignments to "
    "an adjacent component. The possible mis-fold word rule found 32% (bench/jev). "
    "Set [jev] enabled = false in systemap.toml to stop this hint."
)
DELTA_HINT = (
    "hint: TYPESAFE_API_KEY enables Jev rename questions. Across five repositories, "
    "Jev and delta found 82 renames; delta found 66. Sixteen of 17 added pairs were "
    "correct (bench/jev). Set [jev] enabled = false in systemap.toml to stop this "
    "hint."
)


def uses_jev(cfg: config.Config, flag: bool | None) -> bool:
    """Use an explicit flag, or the configured Jev policy and available API key."""
    if flag is not None:
        return flag
    return cfg.jev_enabled and jev.has_key()


def usage_to_stderr(client: jev.Jev) -> None:
    """Print usage to stderr when a run used Jev or its cache."""
    if client.usage.sent or client.usage.cached:
        print(client.usage.line(), file=sys.stderr)


def hint(cfg: config.Config, text: str) -> None:
    """Print a Jev hint to stderr when enabled without an API key."""
    if cfg.jev_enabled and not jev.has_key():
        print(text, file=sys.stderr)


# ---- audit -------------------------------------------------------------------------


def cmd_audit(args: argparse.Namespace, send: jev.Send | None = None) -> int:
    """Give Jev findings with exit 0, or exit 1 if the request cannot complete."""
    cfg = config.load(args.root_path)
    facts = _facts(cfg)
    if facts is None:
        return STALE
    tree = nest.load(cfg)
    kinds = tuple(args.kind) if args.kind else audit.DEFAULT_KINDS
    plan = audit.make_plan(tree, facts, cfg, kinds)
    if args.dry_run:
        pending = None
        if send is not None or jev.has_key():
            pending = len(_client(cfg, send).pending(plan.asks))
        print(*audit.dry_run(plan, pending), sep="\n")
        return OK
    try:
        client = _client(cfg, send)
        found = audit.lines(plan, client.ask(plan.asks))
    except JevError as exc:
        print(f"audit: {exc}")
        return STALE
    texts = [line.text for line in found]
    current_evidence = judgement.evidence_for_tree(tree, facts, cfg.root, texts)
    result = audit.apply_reviewed(found, cfg.judgement_answered, current_evidence, kinds)
    open_lines = [x for x in result.open if audit._bare(x.text).split(": ", 1)[0] in kinds]
    print(
        *audit.report(
            open_lines,
            result.answered,
            result.stale,
            client.usage.line(),
            not args.brief,
            result.pending,
            result.policies,
        ),
        sep="\n",
    )
    return OK


# ---- triage ------------------------------------------------------------------------


def _neighbours(model: Any, cid: str) -> str:
    into = sorted({f.src for f in model.flows if f.dst == cid})
    out = sorted({f.dst for f in model.flows if f.src == cid})
    return f"from {', '.join(into) or 'nothing'}; to {', '.join(out) or 'nothing'}"


def cmd_triage(args: argparse.Namespace, send: jev.Send | None = None) -> int:
    """Predict the three components an issue fix will probably change."""
    cfg = config.load(args.root_path)
    facts = _facts(cfg)
    if facts is None:
        return STALE
    text = sys.stdin.read() if args.text == "-" else args.text
    if not text.strip():
        print("triage: give the issue's text, or - to read it from stdin")
        return STALE
    top = nest.load(cfg).top
    state = {"system": cfg.name, "report": text[:REPORT_CAP]}
    question = {
        "where": {
            "type": "choice",
            "instructions": TRIAGE_Q,
            "criteria": audit.owner_criteria(top.model, top.meaning),
        }
    }
    try:
        client = _client(cfg, send)
        answer = client.ask([Ask("triage", state, question)])["triage"]["where"]
    except JevError as exc:
        print(f"triage: {exc}")
        return STALE
    by = audit.modules_by_card(top.model, facts)
    cut = " (the text was cut at 2,000 characters)" if len(text) > REPORT_CAP else ""
    print(f"triage: confidence {answer.get('confidence', 0):.2f}{cut}")
    for cid, p in audit._top(answer.get("probabilities", {}), 3):
        if cid == audit.NONE:
            print(f"  {p:.2f}  none of the components")
            continue
        mods = by.get(cid, [])
        more = f" and {len(mods) - 5} more" if len(mods) > 5 else ""
        print(f"  {p:.2f}  {cid}: {', '.join(mods[:5]) or 'no modules'}{more}")
        print(f"        on the map: {_neighbours(top.model, cid)}")
    print(client.usage.line())
    return OK


# ---- delta --jev: a card for every module no card claims ---------------------------

UNCLAIMED = (
    re.compile(r"^(?:\S+: )?added: (\S+), claimed by no card"),
    re.compile(r"^(?:\S+: )?moved: \S+ -> (\S+) \(.*\); no card claims"),
)


def unclaimed_in(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        for pattern in UNCLAIMED:
            found = pattern.match(line)
            if found:
                out.append(found[1])
    return out


def owner_suggestions(
    cfg: config.Config, tree: nest.Tree, head: dict[str, Any], modules: list[str], client: jev.Jev
) -> list[str]:
    """Give one owner prediction or three candidates per unclaimed module."""
    if not modules:
        return []
    plan = audit.Plan()
    audit.plan_owner(plan, tree.top, head, modules, cfg.name, placed_too=False)
    answered = client.ask(plan.asks)
    out = []
    for ask in plan.asks:
        line = audit.owner_line(plan.reads[ask.key], answered[ask.key])
        if line is not None:
            out.append(f"{line.text} ({'; '.join(line.detail)})")
    return out


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
        head += f", {len(left)} {walks} to write: one per component group"
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
            draft = journeys.write_one(writer, current.model, current.meaning, facts, group)
        except agent.AgentError as exc:
            out.append(f"journeys: {exc}")
            break
        _record_journey(current, group, draft, sources, written, out)
    if written and not _commit_journeys(cfg, sources, written, out):
        return STALE
    print(*out, sep="\n")
    writer_usage(writer)
    return OK


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
        source = current.path.read_text(encoding="utf-8")
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
        print(f"journeys: proposed model could not be written: {exc}")
        return False
    for path, ids in written.items():
        out.append(f"  {len(ids)} written into {cfg.rel(path)}, each marked drafted=True")
    out.append("  examine each sequence against source. Then remove its drafted line")
    out.append("  run: systemap check && systemap judgement")
    return True


def _atomic_model_write(path: Path, source: str) -> None:
    """Validate full source, then replace the model in one operation."""
    model_write.write_models({path: source})


def writer_usage(writer: agent.Agent) -> None:
    if writer.usage.called or writer.usage.cached:
        print(writer.usage.line(), file=sys.stderr)


# ---- delta --jev: which new module a module that disappeared became ---------------


def _first_sentence(text: str, cap: int) -> str:
    text = " ".join((text or "").split())
    for end in (". ", ".\n"):
        i = text.find(end)
        if i != -1:
            text = text[: i + 1]
            break
    return text[:cap]


def _brief(record: dict[str, Any]) -> str:
    names = ", ".join(n["name"] for n in record.get("names", [])[:12])
    doc = _first_sentence(record.get("docstring") or "", 160)
    return f"{record.get('file')}: {doc} Names: {names}"


def _move_ask(base: dict[str, Any], old: str, criteria: dict[str, str]) -> Ask:
    record = base[old]
    state = {
        "old_module": {
            "module": old,
            "file": record.get("file"),
            "docstring": record.get("docstring"),
            "names": [n["name"] for n in record.get("names", [])][:40],
        }
    }
    question = {"type": "choice", "instructions": BECAME_Q, "criteria": criteria}
    return Ask(old, state, {"became": question})


def jev_moves(
    base: dict[str, Any], head: dict[str, Any], client: jev.Jev
) -> dict[str, tuple[str, str]]:
    """Pair removed modules with new modules at confidence MOVE_AT or more.

    Delta's rules first remove known pairs. Jev selects from the unpaired candidates.
    """
    b, h = base.get("components", {}), head.get("components", {})
    gone = sorted(set(b) - set(h))
    new = sorted(set(h) - set(b))
    found = moves.find(b, h, gone, new)
    left = [m for m in gone if m not in found and not extract.is_empty_marker(b[m])]
    options = [m for m in new if not extract.is_empty_marker(h[m])]
    if not left or not options:
        return {}
    criteria = {m: _brief(h[m]) for m in options[:MOVE_OPTIONS]}
    criteria[NOT_MOVED] = "The removed module was deleted. No new module continues its function."
    asks = [_move_ask(b, old, criteria) for old in left]
    answered = client.ask(asks)
    picks = sorted(
        ((answered[a.key]["became"], a.key) for a in asks),
        key=lambda p: (-p[0].get("confidence", 0.0), p[1]),
    )
    return {
        old: (a["choice"], f"read as the same module by Jev, confidence {a['confidence']:.2f}")
        for a, old in picks
        if a.get("choice") not in (None, NOT_MOVED) and a.get("confidence", 0.0) >= MOVE_AT
    }


# ---- suggest --jev: groups from Jev's answers about module pairs -------------------


def pair_candidates(facts: dict[str, Any], mods: list[str]) -> list[tuple[str, str]]:
    """Get import-connected pairs and adjacent module names within each package."""
    known = set(mods)
    by_package: dict[str, list[str]] = {}
    for m in mods:
        by_package.setdefault(m.rsplit(".", 1)[0], []).append(m)
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


def suggest_groups(cfg: config.Config, facts: dict[str, Any], client: jev.Jev) -> list[str]:
    comps = facts["components"]
    mods = sorted(m for m in comps if not extract.is_empty_marker(comps[m]))
    asks = [
        Ask(
            f"{a}|{b}",
            {
                "system": cfg.name,
                "module_a": audit.module_state(facts, a, names_cap=25),
                "module_b": audit.module_state(facts, b, names_cap=25),
            },
            {"same": {"type": "noul", "instructions": SAME_Q}},
        )
        for a, b in pair_candidates(facts, mods)
    ]
    answered = client.ask(asks)
    edges = [
        (a.key.split("|")[0], a.key.split("|")[1])
        for a in asks
        if answered[a.key]["same"]["noul"] >= SAME_AT
    ]
    found = groups(mods, edges)
    out = [
        f"suggest --jev: {len(found)} groups from {len(asks)} questions about module pairs; "
        f"a pair forms one component at P >= {SAME_AT}. Examine these proposed groups. "
        "On two of five "
        "development maps, accuracy was lower than one component per package",
    ]
    for k, g in enumerate(found, 1):
        out.append(f"  group {k} ({len(g)} modules): {', '.join(g)}")
    return out


def run_or_explain(fn: Callable[[], list[str]], label: str) -> tuple[list[str], int]:
    try:
        return fn(), OK
    except JevError as exc:
        return [f"{label}: {exc}"], STALE


# ---- plan: the work projected onto the map, then checked against what happened ------


def cmd_plan(args: argparse.Namespace, send: jev.Send | None = None) -> int:
    """Predict changed components and give their adjacent flows, sequences, and rules."""
    cfg = config.load(args.root_path)
    if args.check:
        return _check_plan(cfg, args)
    text = sys.stdin.read() if args.task == "-" else (args.task or "")
    if not text.strip():
        print("plan: give the task in your own words, or - to read it from stdin")
        return STALE
    top = nest.load(cfg).top
    try:
        client = _client(cfg, send)
        answer = client.ask([Ask("plan", _plan_state(cfg, text), _plan_question(top))])
    except JevError as exc:
        print(f"plan: {exc}")
        return STALE
    spread = answer["plan"]["where"].get("probabilities", {})
    made = plan_mod.project(top.model, top.meaning, text.strip(), spread)
    # A projection that names nothing is not written down: there would be
    # nothing to check it against later.
    where = plan_mod.save(cfg, made) if made.cards else None
    print(*_plan_lines(made, cfg, where), sep="\n")
    usage_to_stderr(client)
    return OK


def _plan_state(cfg: config.Config, text: str) -> dict[str, Any]:
    return {"system": cfg.name, "task": text[: plan_mod.TEXT_CAP]}


def _plan_question(top: nest.Map) -> dict[str, Any]:
    return {
        "where": {
            "type": "choice",
            "instructions": plan_mod.PLAN_Q,
            "criteria": audit.owner_criteria(top.model, top.meaning),
        }
    }


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
    out.append(f"  written to {cfg.rel(where)}" if where else "  not written down")
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
        print(f"plan: no plan named {args.check} (written here: {known})")
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
    return history.facts_at(cfg, sha), extract.build(cfg)


def _check_lines(
    found: dict[str, Any], changed: set[str], missed: list[str], untouched: list[str], base: str
) -> list[str]:
    out = [
        f"plan {found.get('id', '')} against the code since {base}: "
        f"{len(changed)} components changed, {len(found.get('cards', []))} were projected"
    ]
    for cid in missed:
        out.append(f"  not in the plan: {cid} changed and the plan did not name it")
    out += [f"  in the plan, untouched: {cid}" for cid in untouched]
    if missed:
        out.append("  examine each component: the work changed a part absent from the plan")
    elif not untouched:
        out.append("  the changed components agree with the plan")
    return out


# ---- the parsers -------------------------------------------------------------------


def add_parsers(sub: Any, add_root: Callable[[argparse.ArgumentParser], None]) -> None:
    s = sub.add_parser(
        "audit",
        help="get Jev's second opinion on semantic map claims",
        description="Jev examines module ownership, component sentences, flow claims, and "
        "invariants. "
        "It can propose owners for unclaimed modules and identify claims that "
        "disagree with source. "
        "The command sends facts and model text to the API. Set TYPESAFE_API_KEY before use.",
    )
    add_root(s)
    s.add_argument(
        "--dry-run", action="store_true", help="count proposed questions without sending data"
    )
    s.add_argument(
        "--kind",
        action="append",
        default=[],
        choices=config.AUDIT_KINDS,
        metavar="KIND",
        help="select this question type. Use the flag again for more types (one of: "
        + ", ".join(f'"{k}"' for k in config.AUDIT_KINDS)
        + '). The default excludes "jev flow", which did not meet the holdout threshold',
    )
    s.add_argument(
        "--brief",
        action="store_true",
        help=(
            "print findings without explanation rows. systemap explain KIND gives the "
            "full explanation"
        ),
    )
    s.set_defaults(func=lambda args: cmd_audit(_rooted(args)))

    s = sub.add_parser(
        "journeys",
        help="write a sequence for an entry point without examined sequence coverage",
        description="An entry point without a sequence has no authored account of its operation. "
        "The configured [agent] command reads source and gives component steps with sentences. "
        "systemap compares the steps with map flows and writes accepted sequences as drafts. "
        "Examine each draft against source before acceptance.",
    )
    add_root(s)
    s.add_argument(
        "--limit",
        type=int,
        default=JOURNEY_CAP,
        help=f"maximum sequences per run (default {JOURNEY_CAP})",
    )
    s.add_argument(
        "--dry-run", action="store_true", help="list proposed sequences without file changes"
    )
    s.set_defaults(func=lambda args: cmd_journeys(_rooted(args)))

    s = sub.add_parser(
        "plan",
        help="predict changed components, then compare the plan with the changes",
        description="Jev compares a task with each component's function. "
        "The output gives predicted components with their flows, sequences, and rules. "
        "The saved projection lets --check compare the plan with changed code. "
        "Set TYPESAFE_API_KEY before use.",
    )
    add_root(s)
    s.add_argument("task", nargs="?", help="give the task, or - to read stdin")
    s.add_argument("--check", metavar="ID", help="compare a saved plan with changed components")
    s.add_argument(
        "--base",
        default="origin/main",
        help="select the base revision for --check (default origin/main)",
    )
    s.set_defaults(func=lambda args: cmd_plan(_rooted(args)))

    s = sub.add_parser(
        "triage",
        help="predict the three components that an issue fix will probably change",
        description="Jev compares the issue with each component's function. "
        "It predicts three changed components with their modules and neighbours. "
        "Give the text as an argument, or - to read stdin. Set TYPESAFE_API_KEY before use.",
    )
    add_root(s)
    s.add_argument("text", help="give the issue title and body, or - to read stdin")
    s.set_defaults(func=lambda args: cmd_triage(_rooted(args)))


def _rooted(args: argparse.Namespace) -> argparse.Namespace:
    from systemap.cli import _root

    args.root_path = _root(args)
    return args
