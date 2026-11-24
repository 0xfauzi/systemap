"""The command `systemap claims`: the map claims about one component or one module.

`systemap claims NAME` reads the model and the stored facts. NAME is a component ID, a
module name, or the path of a source file. For a module or a file, the command gives the
component that contains it. For each map with that component, the output has:

- the function, the interface, and the modules of the component;
- the invariants that apply to it;
- the import rules that name it, each with its current result;
- the flows to it and from it, each with its relation sentence;
- the sequences that name it.

A coding agent reads this output before it changes a module. The command sends no data
out, calls no decision provider, and writes no file. `--json` writes one JSON object.
If no map has the name, the command gives the nearest names and exit code 1.
"""

from __future__ import annotations

import argparse
import difflib
import json
from collections.abc import Callable
from typing import Any

from systemap import card_review, config, facts_file, flow_ids, import_rules, nest
from systemap.evidence import owners
from systemap.model import Component, ImportRule, claimed

OK, FAILED = 0, 1

HELP = "Print the map claims about one component or one module."
DESCRIPTION = (
    "NAME is a component ID, a module name, or the path of a source file. The output "
    "gives the function, the modules, the invariants, the import rules, the flows, and "
    "the sequences of the component. A coding agent reads it before it changes a module. "
    "The command reads the model and the stored facts. It sends no data out and writes "
    "no file."
)


def module_of(name: str, components: dict[str, Any]) -> str:
    """Give the module that a module name or a file path identifies, or an empty string."""
    if name in components:
        return name
    path = name.replace("\\", "/").removeprefix("./")
    for module, record in components.items():
        if isinstance(record, dict) and record.get("file") == path:
            return str(module)
    return ""


def _cards(m: nest.Map, name: str, module: str, facts: dict[str, Any]) -> list[Component]:
    """Give the component with this ID, or the component that contains the module."""
    wanted = {name}
    if module:
        wanted.add(owners(m.model, facts).get(module, ""))
    return [card for card in m.model.components if card.id in wanted]


def _rule_text(rule: ImportRule, card_id: str) -> str:
    """Give the sentence that tells the effect of a rule on one component, or an empty
    string if the rule gives this component no limit."""
    src = ", ".join(rule.src)
    dst = ", ".join(rule.dst)
    if rule.kind == "forbid_cycle" and (not rule.src or card_id in rule.src):
        return f"must not be in an import cycle of {src or 'the components'}"
    if card_id in rule.src and rule.kind == "forbid_import":
        return f"must not import {dst}"
    if card_id in rule.src and rule.kind == "allow_imports":
        return (
            f"can import only its own modules and {dst}"
            if dst
            else "can import only its own modules"
        )
    if card_id in rule.dst and rule.kind == "forbid_import":
        return f"{src} must not import this component"
    return ""


def _rules(m: nest.Map, card: Component, facts: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for outcome in import_rules.evaluate(m.model, facts):
        text = _rule_text(outcome.rule, card.id)
        if text:
            rule = outcome.rule
            out.append(
                {
                    "id": rule.id,
                    "kind": rule.kind,
                    "result": outcome.result,
                    "effect": text,
                    "reason": rule.reason,
                }
            )
    return out


def _flows(m: nest.Map, card: Component, end: int) -> list[dict[str, str]]:
    """Give the flows that have the component at one end: 0 is the source, 1 the target."""
    return [
        {
            "id": flow.id,
            "src": flow.src,
            "dst": flow.dst,
            "artifact": flow.artifact,
            "kind": flow.kind,
            "relation": m.meaning.relation(flow),
        }
        for flow in m.model.flows
        if flow.edge[end] == card.id
    ]


def record(m: nest.Map, card: Component, facts: dict[str, Any]) -> dict[str, Any]:
    """Give the map claims about one component of one map."""
    meaning = flow_ids.resolve(m.model, m.meaning)
    return {
        "map": m.id or nest.TOP_ID,
        "component": card.id,
        "name": m.meaning.plain.get(card.id, ""),
        "kind": card.kind,
        "region": card.region or "",
        "does": card.does,
        "interface": card.interface,
        "entry": card.entry,
        "opens_map": card.map or "",
        "modules": sorted(claimed(card, facts.get("components", {}))),
        "invariants": [
            {"n": inv.n, "text": inv.text}
            for inv in m.model.invariants
            if not inv.governs or card.id in inv.governs
        ],
        "import_rules": _rules(m, card, facts),
        "flows_in": _flows(m, card, 1),
        "flows_out": _flows(m, card, 0),
        "sequences": [
            {"id": journey.id, "label": journey.label}
            for journey in meaning.journeys
            if card_review.touches(journey, card.id)
        ],
    }


def find(tree: nest.Tree, facts: dict[str, Any], name: str) -> list[dict[str, Any]]:
    """Give one record for each reported map that has the component or the module."""
    module = module_of(name, facts.get("components", {}))
    return [
        record(m, card, facts) for m in tree.reported for card in _cards(m, name, module, facts)
    ]


def near(tree: nest.Tree, facts: dict[str, Any], name: str) -> list[str]:
    """Give the component IDs and the module names that are nearest to an unknown name."""
    known = {card.id for m in tree.reported for card in m.model.components}
    known.update(facts.get("components", {}))
    return difflib.get_close_matches(name, sorted(known), n=5, cutoff=0.5)


def _flow_line(flow: dict[str, str]) -> str:
    head = f"  {flow['src']} -> {flow['dst']} ('{flow['artifact']}', {flow['kind']})"
    return f"{head}: {flow['relation']}" if flow["relation"] else head


def _head(found: dict[str, Any]) -> list[str]:
    name = f" ({found['name']})" if found["name"] else ""
    place = f", region {found['region']}" if found["region"] else ""
    out = [f"{found['component']}{name}: {found['kind']} in the map {found['map']}{place}"]
    for key in ("does", "interface", "entry"):
        if found[key]:
            out.append(f"{key}: {found[key]}")
    if found["opens_map"]:
        out.append(f"nested map: {found['opens_map']}")
    return out


def lines(found: dict[str, Any]) -> list[str]:
    """Give the text of one record for a person or an agent."""
    out = _head(found)
    out.append(f"modules ({len(found['modules'])}): {', '.join(found['modules'])}")
    out.append(f"invariants ({len(found['invariants'])}):")
    out += [f"  {inv['n']}. {inv['text']}" for inv in found["invariants"]]
    out.append(f"import rules ({len(found['import_rules'])}):")
    out += [
        f"  {rule['id']} ({rule['kind']}, {rule['result']}): {rule['effect']}. {rule['reason']}"
        for rule in found["import_rules"]
    ]
    out.append(f"flows to this component ({len(found['flows_in'])}):")
    out += [_flow_line(flow) for flow in found["flows_in"]]
    out.append(f"flows from this component ({len(found['flows_out'])}):")
    out += [_flow_line(flow) for flow in found["flows_out"]]
    out.append(f"sequences ({len(found['sequences'])}):")
    out += [f"  {seq['id']}: {seq['label']}" for seq in found["sequences"]]
    return out


def cmd_claims(args: argparse.Namespace) -> int:
    from systemap import cli, cli_scope

    cfg = config.load(cli._root(args))
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    if not facts:
        cli.warn(f"No facts are available at {cfg.rel(cfg.facts_path)}", "run: systemap extract")
        return FAILED
    tree = cli_scope.load(cfg, args)
    found = find(tree, facts, args.name)
    cli.warn(*cli_scope.notes(tree))
    if not found:
        names = near(tree, facts, args.name)
        hint = f"The nearest names are {', '.join(names)}." if names else "No name is near it."
        cli.warn(f"No component and no module has the name {args.name}. {hint}")
        return FAILED
    if args.json:
        cli.say(json.dumps(cli_scope.payload({"query": args.name, "found": found}, tree), indent=2))
        return OK
    for at, one in enumerate(found):
        cli.say(*([""] if at else []), *lines(one))
    return OK


def add_parser(sub: Any, add_root: Callable[[argparse.ArgumentParser], None]) -> None:
    s = sub.add_parser("claims", help=HELP, description=DESCRIPTION)
    add_root(s)
    s.add_argument(
        "name", metavar="NAME", help="Give a component ID, a module name, or a file path."
    )
    s.add_argument("--json", action="store_true", help="Write one JSON object.")
    s.set_defaults(func=cmd_claims)
