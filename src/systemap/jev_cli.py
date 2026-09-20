"""The commands that ask Jev: `audit`, `triage`, and the `--jev` of `delta` and `suggest`.

They live apart from cli.py so the offline commands never import a network
path, and so cli.py does not grow. Every one of them sends nothing without
`TYPESAFE_API_KEY`, prints what a run cost, and exits 0 unless it could not
run at all: none of them is a gate.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from typing import Any

from systemap import agent, audit, config, extract, jev, journeys, moves, nest
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

TRIAGE_Q = (
    "`report` is an issue filed against this system. Which component will "
    "the fix most likely have to change?"
)
BECAME_Q = (
    "In one commit `old_module` disappeared and the modules in the options "
    "appeared. Which new module is the old one, moved or renamed and perhaps "
    "edited? If it was deleted, say so."
)
NOT_MOVED = "not moved: deleted"
# How many new modules the question offers: the measured cap.
MOVE_OPTIONS = 250
SAME_Q = (
    "Do `module_a` and `module_b` belong to the same component of "
    "this system: one part with one job that a reader would point at "
    "and name? Two parts that merely call each other or share types "
    "are two components."
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
    "hint: with a TypeSafe key in TYPESAFE_API_KEY, systemap audit adds Jev's second "
    "opinion on meaning: it caught 95% of modules moved into a neighbouring card, where "
    "the word rule behind possible mis-fold caught 32% (bench/jev). "
    "[jev] enabled = false in systemap.toml silences this."
)
DELTA_HINT = (
    "hint: with a TypeSafe key in TYPESAFE_API_KEY, delta also asks Jev which new module "
    "each removed one became: on renames in five repositories that found 82 where delta "
    "alone found 66, 16 of its 17 additions right (bench/jev). "
    "[jev] enabled = false in systemap.toml silences this."
)


def uses_jev(cfg: config.Config, flag: bool | None) -> bool:
    """`--jev` or `--no-jev` when given; else Jev when a key is set and `[jev]` allows it."""
    if flag is not None:
        return flag
    return cfg.jev_enabled and jev.has_key()


def usage_to_stderr(client: jev.Jev) -> None:
    """What the run cost, on stderr, so the report and the pull-request comment
    stay the report; nothing when no question was asked."""
    if client.usage.sent or client.usage.cached:
        print(client.usage.line(), file=sys.stderr)


def hint(cfg: config.Config, text: str) -> None:
    """What Jev would add, on stderr, when no key is set and `[jev]` allows it."""
    if cfg.jev_enabled and not jev.has_key():
        print(text, file=sys.stderr)


# ---- audit -------------------------------------------------------------------------


def cmd_audit(args: argparse.Namespace, send: jev.Send | None = None) -> int:
    """A second opinion on the map from Jev. A report: exit 0, or 1 when it could not run."""
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
    open_lines, answered, stale = audit.apply(found, cfg.judgement_answered, kinds)
    open_lines = [x for x in open_lines if audit._bare(x.text).split(": ", 1)[0] in kinds]
    print(*audit.report(open_lines, answered, stale, client.usage.line()), sep="\n")
    return OK


# ---- triage ------------------------------------------------------------------------


def _neighbours(model: Any, cid: str) -> str:
    into = sorted({f.src for f in model.flows if f.dst == cid})
    out = sorted({f.dst for f in model.flows if f.src == cid})
    return f"from {', '.join(into) or 'nothing'}; to {', '.join(out) or 'nothing'}"


def cmd_triage(args: argparse.Namespace, send: jev.Send | None = None) -> int:
    """Which card an issue's fix will most likely change: the top three, with where to read."""
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
            print(f"  {p:.2f}  none of the cards")
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
    """One line per unclaimed module: the card Jev reads it as, or the closest three."""
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
    """Write a journey for a way into the system that no journey walks from."""
    cfg = config.load(args.root_path)
    facts = _facts(cfg)
    if facts is None:
        return STALE
    top = nest.load(cfg).top
    left = journeys.uncovered(top.meaning, facts)
    if not left:
        print("journeys: every way into the system already has a walk from it")
        return OK
    if args.dry_run or not agent.has_agent(cfg):
        print(*_would_write(left, cfg), sep="\n")
        return OK
    return _write_journeys(cfg, top, facts, left[: args.limit], run_command)


def _would_write(left: list[dict[str, str]], cfg: config.Config) -> list[str]:
    """What there is to write, and what it would take, without writing it."""
    ways = "way" if len(left) == 1 else "ways"
    out = [f"journeys: {len(left)} {ways} into the system with no walk from them:"]
    out += [f"  {extract.entry_label(p)}" for p in left[:20]]
    if len(left) > 20:
        out.append(f"  and {len(left) - 20} more")
    if not agent.has_agent(cfg):
        out.append(f"  {agent.NO_AGENT}")
    return out


def _write_journeys(
    cfg: config.Config,
    top: nest.Map,
    facts: dict[str, Any],
    take: list[dict[str, str]],
    run_command: agent.Run | None,
) -> int:
    """Ask the agent for each walk, check it, and write the ones that hold."""
    try:
        writer = agent.from_cfg(cfg, run_command)
    except agent.AgentError as exc:
        print(f"journeys: {exc}")
        return STALE
    source = top.path.read_text(encoding="utf-8")
    written: list[str] = []
    out: list[str] = []
    for point in take:
        try:
            draft = journeys.write_one(writer, top.model, top.meaning, facts, point)
        except agent.AgentError as exc:
            out.append(f"journeys: {exc}")
            break
        label = extract.entry_label(point)
        if draft.journey is None:
            out.append(f"journeys: no walk written for {label}")
            out += [f"      {p}" for p in draft.problems]
            continue
        grown = journeys.add_to_source(source, draft.journey)
        if grown is None:
            out.append(f"journeys: {cfg.rel(top.path)} has no journeys to add to; paste this in:")
            out += journeys.as_source(draft.journey)
            continue
        source = grown
        written.append(draft.journey.id)
        out.append(f"journeys: wrote {draft.journey.id} ({draft.journey.label}) for {label}")
        out += [f"      {p}" for p in draft.problems]
    if written:
        top.path.write_text(source, encoding="utf-8")
        out.append(f"  {len(written)} written into {cfg.rel(top.path)}, each marked drafted=True")
        out.append("  read each one against the code, then remove the drafted line")
        out.append("  run: systemap check && systemap judgement")
    print(*out, sep="\n")
    writer_usage(writer)
    return OK


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
    """old module -> (new module, how), for the modules that disappeared and that
    delta's own questions left unpaired, where Jev names one at MOVE_AT or more."""
    b, h = base.get("components", {}), head.get("components", {})
    gone = sorted(set(b) - set(h))
    new = sorted(set(h) - set(b))
    found = moves.find(b, h, gone, new)
    left = [m for m in gone if m not in found and not extract.is_empty_marker(b[m])]
    options = [m for m in new if not extract.is_empty_marker(h[m])]
    if not left or not options:
        return {}
    criteria = {m: _brief(h[m]) for m in options[:MOVE_OPTIONS]}
    criteria[NOT_MOVED] = "The old module was deleted; none of the new modules continues it."
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
    """Import-joined pairs, and neighbours in name order within one package."""
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
    """Connected components of the pairs called one part, largest first."""
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
        f"a pair is one part at P >= {SAME_AT}. A grouping to argue with: on two of five "
        "development maps it did worse than one card per package",
    ]
    for k, g in enumerate(found, 1):
        out.append(f"  group {k} ({len(g)} modules): {', '.join(g)}")
    return out


def run_or_explain(fn: Callable[[], list[str]], label: str) -> tuple[list[str], int]:
    try:
        return fn(), OK
    except JevError as exc:
        return [f"{label}: {exc}"], STALE


# ---- the parsers -------------------------------------------------------------------


def add_parsers(sub: Any, add_root: Callable[[argparse.ArgumentParser], None]) -> None:
    s = sub.add_parser(
        "audit",
        help="a second opinion from TypeSafe's Jev on the map's judgement calls: modules "
        "that read like another card, a card for each unclaimed module, card sentences that "
        "may not describe their modules, flows the code may not carry, invariants that may "
        "govern a card they do not name; sends the facts and model text to the API, needs "
        "TYPESAFE_API_KEY, caches every answer; a report, exit 0",
    )
    add_root(s)
    s.add_argument(
        "--dry-run", action="store_true", help="count what would be sent, and send nothing"
    )
    s.add_argument(
        "--kind",
        action="append",
        default=[],
        choices=config.AUDIT_KINDS,
        metavar="KIND",
        help="ask and print only this kind; repeat for more (one of: "
        + ", ".join(f'"{k}"' for k in config.AUDIT_KINDS)
        + '); without it, every kind but "jev flow", which fell short on maps its '
        "threshold was not chosen on",
    )
    s.set_defaults(func=lambda args: cmd_audit(_rooted(args)))

    s = sub.add_parser(
        "journeys",
        help="write a walk through the system for a way in that has none: the agent named "
        "under [agent] reads the code from that way in and answers with the cards a run "
        "passes through and a sentence each; the walk is checked against the map and written "
        "into the model as a draft for you to confirm",
    )
    add_root(s)
    s.add_argument(
        "--limit",
        type=int,
        default=JOURNEY_CAP,
        help=f"how many walks to write in one run (default {JOURNEY_CAP})",
    )
    s.add_argument(
        "--dry-run", action="store_true", help="list the ways in that have no walk, and write none"
    )
    s.set_defaults(func=lambda args: cmd_journeys(_rooted(args)))

    s = sub.add_parser(
        "triage",
        help="which card an issue's fix will most likely change, by Jev: the top three "
        "cards with their modules and neighbours; the text as an argument, or - for stdin; "
        "needs TYPESAFE_API_KEY",
    )
    add_root(s)
    s.add_argument("text", help="the issue's title and body, or - to read them from stdin")
    s.set_defaults(func=lambda args: cmd_triage(_rooted(args)))


def _rooted(args: argparse.Namespace) -> argparse.Namespace:
    from systemap.cli import _root

    args.root_path = _root(args)
    return args
