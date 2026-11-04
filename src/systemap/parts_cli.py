"""The command `systemap parts`: the part plan, the stubs, and the result files.

- `systemap parts` writes the plan of the nested parts of the top map to
  `parts/plan.json` beside the top model, and prints one line for each part.
- `systemap parts --map ID` reads the plan that has the map ID as a part, and gives the
  record of that part. If the plan is stale, the command stops. If the map ID has nested
  maps, the command also writes the plan of these nested parts.
- `systemap parts --stub CARD` writes the stub of a new nested part for a component of
  the top map, or of the map that `--map` selects.
- `systemap parts --results` examines the result file of each part of the plan.

`--json` writes one JSON object. The command reads the stored facts. It sends no data
out. A write holds the write lock `.systemap/write.lock`.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Any

from systemap import (
    config,
    facts_file,
    file_write,
    nest,
    parts,
    parts_plan,
    parts_result,
    parts_stub,
)
from systemap.config import Config, ConfigError

OK, FAILED = 0, 1


class StemError(ConfigError):
    """A nested map of the model has a stem that the plan refuses."""


class PlanError(Exception):
    """The stored plan is missing, cannot be read, or is stale. The message gives the
    action. The command gives the message and exit code 1."""


def _say(*lines: str) -> None:
    from systemap.cli import say

    say(*lines)


def cmd_parts(args: argparse.Namespace) -> int:
    from systemap.cli import _root

    cfg = config.load(_root(args))
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    if not facts:
        _say(f"No facts are available at {cfg.rel(cfg.facts_path)}", "run: systemap extract")
        return FAILED
    tree = nest.load(cfg, args.only)
    selected = tree.get(tree.selected or "")
    if args.stub:
        return _stub(cfg, tree, selected, args.stub, facts)
    try:
        if args.results:
            return _results(cfg, tree, selected, bool(args.json))
        if selected.id:
            return _part(cfg, tree, selected, facts, bool(args.json))
    except PlanError as exc:
        from systemap.cli import warn

        warn(f"systemap: {exc}")
        return FAILED
    return _plan(cfg, tree, selected, facts, bool(args.json))


def _written(
    cfg: Config, tree: nest.Tree, m: nest.Map, facts: dict[str, Any]
) -> dict[str, Any] | None:
    """Make and write the plan of the nested parts of `m`. A map without nested maps gives
    None and no file."""
    found = parts_plan.problems(tree, m)
    if found:
        raise StemError("The plan refuses these map IDs:\n" + "\n".join(found))
    if not tree.children(m):
        return None
    plan = parts_plan.build(cfg, tree, m, facts)
    with file_write.exclusive(cfg.root):
        parts_plan.write(cfg, plan)
    return plan


def _plan(cfg: Config, tree: nest.Tree, m: nest.Map, facts: dict[str, Any], as_json: bool) -> int:
    plan = _written(cfg, tree, m, facts)
    if as_json:
        # A map without nested maps gives a plan with no parts, and no file.
        shown = plan or parts_plan.build(cfg, tree, m, facts)
        _say(parts_plan.text(shown).rstrip("\n"))
        return OK
    if plan is None:
        _say("parts: The map has no component that opens a nested map. systemap wrote no plan.")
        return OK
    rel = cfg.rel(parts.plan_path(cfg.model_path, m.id))
    _say(f"parts: The plan has {len(plan['parts'])} nested parts. systemap wrote {rel}.")
    _say(*parts_plan.summary(plan))
    return OK


def stored(cfg: Config, tree: nest.Tree, m: nest.Map) -> dict[str, Any]:
    """Read the plan of the nested parts of `m`. A missing or stale plan gives PlanError."""
    rel = cfg.rel(parts.plan_path(cfg.model_path, m.id))
    command = f"systemap parts --map {m.id}" if m.id else "systemap parts"
    try:
        plan = parts_plan.read(cfg, m.id)
    except ValueError as exc:
        raise PlanError(
            f"systemap cannot read the plan file {rel}: {exc}. Do {command} again."
        ) from exc
    if plan is None:
        raise PlanError(f"No plan is at {rel}. Do {command} first.")
    if parts_plan.is_stale(cfg, plan, m):
        raise PlanError(f"{parts_plan.STALE} The plan file is {rel}. Do {command}.")
    return plan


def _part(cfg: Config, tree: nest.Tree, m: nest.Map, facts: dict[str, Any], as_json: bool) -> int:
    """Give the record of the part `m` from the plan of its parent map."""
    parent = tree.get(m.parent or "")
    plan = stored(cfg, tree, parent)
    found = next((r for r in plan["parts"] if r["map"] == m.id), None)
    if found is None:
        raise PlanError(
            f"The plan of {parent.id or 'the top map'} has no part {m.id}. Do systemap parts again."
        )
    nested = _written(cfg, tree, m, facts)
    if as_json:
        keep = ("base_commit", "facts_digest", "contract_digest", "vocabulary", "shared_files")
        obj = {"map": m.id, "plan_file": cfg.rel(parts.plan_path(cfg.model_path, parent.id))}
        obj.update({key: plan[key] for key in keep})
        _say(
            json.dumps({**obj, "part": found, "nested_plan": nested}, indent=2, ensure_ascii=False)
        )
        return OK
    _say(f"parts: The part {m.id} of the plan of {parent.id or 'the top map'}:")
    _say(*parts_plan.summary({"parts": [found], "order": [m.id]}))
    if nested is not None:
        rel = cfg.rel(parts.plan_path(cfg.model_path, m.id))
        _say(f"parts: {m.id} has {len(nested['parts'])} nested parts. systemap wrote {rel}.")
        _say(*parts_plan.summary(nested))
    return OK


def _stub(cfg: Config, tree: nest.Tree, m: nest.Map, card: str, facts: dict[str, Any]) -> int:
    with file_write.exclusive(cfg.root):
        path = parts_stub.write(cfg, tree, m, card, facts)
    where = cfg.rel(m.path)
    _say(
        f"parts: systemap wrote the stub {cfg.rel(path)}.",
        f'  Set map="{path.name}" on {card} in {where}.',
        "  Then do systemap refresh and systemap check.",
    )
    return OK


def _results(cfg: Config, tree: nest.Tree, m: nest.Map, as_json: bool) -> int:
    plan = stored(cfg, tree, m)
    found = parts_result.examine(cfg, plan)
    ok = not any(found.values())
    if as_json:
        _say(json.dumps({"map": m.id, "ok": ok, "problems": found}, indent=2, ensure_ascii=False))
        return OK if ok else FAILED
    for map_id, lines in found.items():
        _say(f"result {map_id}: " + ("correct" if not lines else f"{len(lines)} problems"))
        _say(*(f"  {line}" for line in lines))
    return OK if ok else FAILED


def add_parser(
    sub: Any, add_root: Callable[[argparse.ArgumentParser], None], map_help: str
) -> None:
    s = sub.add_parser(
        "parts",
        help="Write the part plan of the nested maps, or the stub of a new nested map.",
        description=(
            "This command gives the facts for each nested map of one map: its modules, its "
            "module groups, its adjacent components, the flows and the imports across its "
            "boundary, and its entry points. It writes the plan to parts/plan.json beside "
            "the top model. It does not select the boundaries of the nested maps."
        ),
    )
    add_root(s)
    s.add_argument("--map", dest="only", default=None, metavar="ID", help=map_help)
    s.add_argument("--json", action="store_true", help="Write one JSON object.")
    s.add_argument(
        "--stub",
        default="",
        metavar="CARD",
        help=(
            "Write the stub of a new nested map for the component CARD. The stub has one "
            "component for each module group, the actors, and positions. The command does "
            "not write over a file."
        ),
    )
    s.add_argument(
        "--results",
        action="store_true",
        help="Examine the result file of each nested part of the plan against the plan.",
    )
    s.set_defaults(func=cmd_parts)
