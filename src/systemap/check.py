"""Check the map geometry and the meaning tables mechanically.

The map is hand-placed (positions) and hand-authored (relations), so two
kinds of quiet lie are possible: a card drawn where the model does not claim
it, or a sentence that names a flow the model no longer has. Both fail here
instead of shipping.

What is checked, in order:

    placement ..... every card inside its band, no two cards overlapping,
                    every flow naming known components (the model)
    routes ........ every edge an orthogonal path that passes through no
                    card it does not connect and crosses no region box it
                    neither starts nor ends in (both counted, each offender
                    listed with the router's reason)
    labels ........ every edge label seated without touching a card, a
                    header or another label (the schematic's collision pass,
                    re-verified from the boxes it reports)
    type size ..... nothing in the figure set below 11px
    meaning ....... every flow has a layer and a sentence, every component a
                    plain word, every journey step a real edge and real ids,
                    every verb override a real edge
    wheel ......... for every component, the relationship wheel's name labels
                    stay inside the drawing and off each other and the centre
    coverage ...... every module in the facts is claimed by exactly one
                    component, unless the configuration ignores it with a
                    reason; an incomplete map fails
    entry ......... a component whose modules exist names an entry, and one
                    of those modules defines it; the build state is derived
                    from that name, so a name the code does not have would
                    draw a part as built or part built on a lie
    tracker ....... a planned component (none of its modules exist) names
                    the tracker item that will build it
    stale ......... the facts file describes the tree, the page is what the
                    renderer draws from the facts and the model, and every
                    configured figure is what the generator draws; the
                    same comparisons `extract --check` and `render --check`
                    make, run in one place

The CLI prints one line per problem, the fix under each group, and exits
1 when any is found.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from systemap import extract, figure, page
from systemap.config import Config, Ignore
from systemap.model import Meaning, Model, build_state, claimed, module_matches
from systemap.model import problems as model_problems
from systemap.schematic import TEXT_PX
from systemap.schematic import render as render_schematic

Box = tuple[float, float, float, float]


def _overlap(a: Box, b: Box) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _box(values: list[float]) -> Box:
    return float(values[0]), float(values[1]), float(values[2]), float(values[3])


def check_labels(meta: dict[str, Any]) -> list[str]:
    out = [f"label collision: {line}" for line in meta.get("collisions", [])]
    labels: list[dict[str, Any]] = meta.get("labels", [])
    cards: dict[str, list[float]] = meta.get("cards", {})
    for k, lab in enumerate(labels):
        lb = _box(lab["box"])
        for cid, cb in cards.items():
            if _overlap(lb, _box(cb)):
                out.append(f"label '{lab['artifact']}' touches card {cid}")
        for other in labels[k + 1 :]:
            if _overlap(lb, _box(other["box"])):
                out.append(f"label '{lab['artifact']}' touches label '{other['artifact']}'")
    return out


def _seg_hits(a: list[float], b: list[float], box: Box) -> bool:
    """Does the axis-aligned segment a-b cross the interior of box?"""
    bx, by, bw, bh = box
    (x0, y0), (x1, y1) = a, b
    if abs(y0 - y1) < 1e-6:
        if not (by < y0 < by + bh):
            return False
        return min(x0, x1) < bx + bw and max(x0, x1) > bx
    if not (bx < x0 < bx + bw):
        return False
    return min(y0, y1) < by + bh and max(y0, y1) > by


def check_routes(meta: dict[str, Any], model: Model) -> tuple[list[str], int, int]:
    """(problems, edges through a foreign card, edges across a foreign region).

    A segment is judged against the exact card box (the router keeps a
    margin, so a touch here is a real pass-through) and against every
    region box other than the two the edge belongs to. An edge is counted
    once per offence, and listed with the router's own reason when it had
    to fall back.
    """
    out: list[str] = []
    paths: dict[Any, list[list[float]]] = meta.get("paths", {})
    cards: dict[str, list[float]] = meta.get("cards", {})
    notes: list[str] = meta.get("notes", [])
    region_of = {c.id: c.region or "" for c in model.components}
    regions = {r.id: _box(list(r.box)) for r in model.regions}
    through = 0
    across = 0
    for i, f in enumerate(model.flows):
        src, dst, art = f.src, f.dst, f.artifact
        pts = paths.get(str(i)) or paths.get(i)
        if not pts:
            out.append(f"route: {src} -> {dst} ('{art}') has no path")
            continue
        segs = list(zip(pts, pts[1:], strict=False))
        hit_cards = sorted(
            cid
            for cid, box in cards.items()
            if cid not in (src, dst) and any(_seg_hits(a, b, _box(box)) for a, b in segs)
        )
        hit_regions = sorted(
            rid
            for rid, box in regions.items()
            if rid not in (region_of[src], region_of[dst])
            and any(_seg_hits(a, b, box) for a, b in segs)
        )
        why = next((n for n in notes if n.startswith(f"{src} -> {dst}:")), "")
        reason = f" ({why.split(': ', 1)[1]})" if why else ""
        if hit_cards:
            through += 1
            out.append(f"route: {src} -> {dst} passes through {', '.join(hit_cards)}{reason}")
        if hit_regions:
            across += 1
            out.append(f"route: {src} -> {dst} crosses region {', '.join(hit_regions)}{reason}")
    return out, through, across


def check_type_size(svg: str) -> list[str]:
    small = sorted(
        {float(m) for m in re.findall(r"font-size:\s*([0-9.]+)px", svg) if float(m) < TEXT_PX}
    )
    return [f"text set at {s}px, below {TEXT_PX}px" for s in small]


# ---- the wheel, mirrored from schematic._INTERACTIVE_JS ----------------------
# The page lays the wheel out in the browser; this is the same arithmetic in
# Python so the label geometry can be checked without one. Keep the two in
# step: a change to one is a change to both.

W, H, CX, CY, R = 400.0, 400.0, 200.0, 200.0, 118.0
MONO_CHAR_W = 6.6
NAME_LINE_H = 13.0


def wrap_name(cid: str) -> list[str]:
    parts = re.findall(r"[A-Z]+[a-z0-9]*|[a-z0-9]+", cid) or [cid]
    lines: list[str] = []
    cur = ""
    for p in parts:
        if cur and len(cur + p) > 10:
            lines.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        lines.append(cur)
    return lines[:3]


def wheel_boxes(
    cid: str, edges: list[dict[str, str]], meaning: Meaning
) -> tuple[Box, list[tuple[str, Box]]]:
    order = {layer.id: i for i, layer in enumerate(meaning.layers)}
    idx = sorted(
        (i for i, e in enumerate(edges) if cid in (e["from"], e["to"])),
        key=lambda i: (order[edges[i]["layer"]], i),
    )
    groups = 0
    prev: str | None = None
    for i in idx:
        if edges[i]["layer"] != prev:
            groups += 1
            prev = edges[i]["layer"]
    gap = 0.5 if groups > 1 else 0.0
    step = 360.0 / (len(idx) + gap * groups) if idx else 360.0
    hw, hh = max(34.0, len(cid) * 3.7 + 12), 15.0
    centre: Box = (CX - hw, CY - hh, 2 * hw, 2 * hh)
    boxes: list[tuple[str, Box]] = []
    a = -90.0
    prev = None
    for i in idx:
        e = edges[i]
        if prev is not None and e["layer"] != prev:
            a += gap * step
        prev = e["layer"]
        th = math.radians(a)
        a += step
        ux, uy = math.cos(th), math.sin(th)
        other = e["to"] if e["from"] == cid else e["from"]
        lines = wrap_name(other)
        n = len(lines)
        lw = max(len(line) for line in lines) * MONO_CHAR_W
        ex, ey = CX + (R + 9) * ux, CY + (R + 9) * uy
        if abs(ux) < 0.35:
            first = ey - 4 - (n - 1) * NAME_LINE_H if uy < 0 else ey + 12
            left = ex - lw / 2
        else:
            first = ey + 4 - (n - 1) * 6.5
            left = ex + 2 if ux > 0 else ex - 2 - lw
        top = first - 10
        boxes.append((other, (left, top, lw, (n - 1) * NAME_LINE_H + NAME_LINE_H)))
    return centre, boxes


def check_wheels(edges: list[dict[str, str]], model: Model, meaning: Meaning) -> list[str]:
    out: list[str] = []
    for c in model.components:
        cid = c.id
        centre, boxes = wheel_boxes(cid, edges, meaning)
        for k, (name, box) in enumerate(boxes):
            x, y, w, h = box
            if x < 0 or y < 0 or x + w > W or y + h > H:
                out.append(f"wheel of {cid}: label {name} leaves the drawing")
            if _overlap(box, centre):
                out.append(f"wheel of {cid}: label {name} touches the centre")
            for other, ob in boxes[k + 1 :]:
                if _overlap(box, ob):
                    out.append(f"wheel of {cid}: labels {name} and {other} touch")
    return out


# ---- coverage: every module claimed once --------------------------------------


@dataclass(frozen=True)
class Coverage:
    """What the coverage rule found.

    `checked` is false when there were no facts to check against, which is
    itself a failure: a map cannot be called complete against nothing.
    `total` counts the modules the rule applies to (the facts minus the
    ignored ones) and `mapped` how many of those exactly one component
    claims.
    """

    checked: bool
    mapped: int
    total: int
    ignored: int
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.checked and not self.problems


def check_coverage(model: Model, facts: dict[str, Any], ignores: Iterable[Ignore]) -> Coverage:
    """Every module in the facts is claimed by exactly one component.

    A module no component claims is a hole in the map: the reader cannot
    find that code on the page. A module two components claim is a lie in
    the other direction: the page says one thing does it and another thing
    also does it. An ignore in the configuration takes a module out of the
    first rule, with its reason on record; it never excuses the second. An
    ignore that matches nothing in the facts is reported too, so a stale
    entry cannot quietly outlive the module it named.
    """
    if not facts:
        return Coverage(False, 0, 0, 0, ("no facts to check coverage against",))
    modules = sorted(facts.get("components", {}))
    ignore_list = list(ignores)
    problems: list[str] = []
    for ignore in ignore_list:
        if not any(module_matches(ignore.module, m) for m in modules):
            problems.append(f"ignore names a module the facts do not have: {ignore.module}")
    ignored = {m for m in modules if any(module_matches(i.module, m) for i in ignore_list)}
    mapped = 0
    for m in modules:
        owners = [
            c.id for c in model.components if any(module_matches(p, m) for p in c.implemented_by)
        ]
        if len(owners) > 1:
            times = "twice" if len(owners) == 2 else f"{len(owners)} times"
            problems.append(f"claimed {times}: {m} ({', '.join(owners)})")
        elif m in ignored:
            continue
        elif not owners:
            problems.append(f"unmapped: {m} (no component claims it)")
        else:
            mapped += 1
    return Coverage(True, mapped, len(modules) - len(ignored), len(ignored), tuple(problems))


# ---- entry and tracker: build state cannot rest on a name that is not there ----


def check_entry(model: Model, facts: dict[str, Any]) -> list[str]:
    """Every component whose modules exist names an entry its modules define.

    Build state is derived by looking `entry` up in the claimed modules. A
    name that is not there would leave the card at "part built" for ever,
    and an empty name would do the same, so both are refused. A component
    with a tracker is exempt: it is planned until the entry lands, and the
    ghost says so. Actors claim no code and are never checked.
    """
    components = facts.get("components", {})
    if not components:
        return []
    out: list[str] = []
    for c in model.components:
        if c.kind == "actor" or c.tracker:
            continue
        modules = claimed(c, components)
        if not modules:
            continue
        if not c.entry:
            out.append(f"{c.id} names no entry; its modules are {', '.join(modules)}")
            continue
        defined = any(
            c.entry in [f["name"] for f in components[m]["functions"]]
            or c.entry in [k["name"] for k in components[m]["classes"]]
            for m in modules
        )
        if not defined:
            out.append(
                f"{c.id} names entry {c.entry}, which none of its modules define "
                f"({', '.join(modules)})"
            )
    return out


def check_tracker(model: Model, facts: dict[str, Any]) -> list[str]:
    """Every planned component names the tracker item that will build it."""
    if not facts.get("components"):
        return []
    return [
        f"{c.id} is planned (none of its modules exist) and names no tracker"
        for c in model.components
        if c.kind != "actor" and not c.tracker and build_state(c, facts) == "planned"
    ]


# ---- stale: the outputs are what the tree and the model say ----------------------


def stale_facts(
    fresh: dict[str, Any], stored: dict[str, Any], model: Model, prefixes: set[str]
) -> list[str]:
    """Ways the stored facts no longer describe the tree, plus claims of
    modules the tree does not have. The rule `extract --check` runs."""
    problems = extract.drift(fresh, stored) + extract.mapping_drift(fresh, model, prefixes)
    if not stored:
        problems.insert(0, "no facts have been built yet")
    return problems


def stale(
    cfg: Config,
    model: Model,
    meaning: Meaning,
    t: dict[str, Any],
    fresh: dict[str, Any] | None = None,
) -> list[str]:
    """Every output that is older than the tree or the model.

    The facts are compared against a fresh extraction, the page against a
    fresh render from the stored facts (the committed page must match the
    committed facts, whatever the tree has since done), and each configured
    figure against the generator. A model that contradicts itself cannot
    be rendered honestly, so only the facts are compared then; the
    placement and meaning rules report the rest.
    """
    fresh = fresh if fresh is not None else extract.build(cfg)
    stored = extract.read_facts(cfg.facts_path)
    if not stored:
        return ["no facts have been built yet"]
    out = [f"facts: {line}" for line in stale_facts(fresh, stored, model, cfg.prefixes)]
    if model_problems(model, meaning):
        return out
    out += _stale_file(
        cfg, cfg.page_path, page.build(cfg, model, meaning, t, stored, {"has_change": False})
    )
    for fig in cfg.figures:
        html, _collisions = figure.configured(cfg, model, meaning, t, stored, fig)
        out += _stale_file(cfg, cfg.out_path / fig.out, html)
    return out


def _stale_file(cfg: Config, path: Path, expected: str) -> list[str]:
    rel = cfg.rel(path)
    if not path.is_file():
        return [f"{rel} has not been rendered"]
    if path.read_text(encoding="utf-8") != expected:
        return [f"{rel} differs from what systemap renders"]
    return []


# ---- one run -------------------------------------------------------------------


@dataclass(frozen=True)
class Result:
    """Everything one check run found.

    `problems` are the placement, meaning, route, label, type-size and
    wheel findings; `coverage` is the module rule; `entry` and `tracker`
    are the build-state rules; `stale` is filled in by the CLI, which has
    the configuration the comparison needs; `through` and `across` count
    edges through a foreign card and across a foreign region.
    """

    problems: list[str]
    notes: list[str]
    through: int
    across: int
    coverage: Coverage
    entry: list[str] = field(default_factory=list)
    tracker: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            not self.problems
            and self.coverage.ok
            and not self.entry
            and not self.tracker
            and not self.stale
        )


def run(
    model: Model,
    meaning: Meaning,
    t: dict[str, Any],
    facts: dict[str, Any],
    issue_url: str = "",
    ignores: Iterable[Ignore] = (),
) -> Result:
    """Check the model against the facts.

    Placement and meaning are checked first; the drawing is only attempted
    once those are clean, since a model that contradicts itself cannot be
    drawn honestly. Coverage is checked regardless, because it reads the
    facts and the claims only, never the drawing.
    """
    problems = model_problems(model, meaning)
    through = across = 0
    notes: list[str] = []
    if not problems:
        svg, detail = render_schematic(model, meaning, t, facts, issue_url=issue_url)
        meta = json.loads(detail)["_meta"]
        route_problems, through, across = check_routes(meta, model)
        problems += route_problems
        problems += check_labels(meta)
        problems += check_type_size(svg)
        problems += check_wheels(meta["edges"], model, meaning)
        notes = [n for n in meta.get("notes", []) if "shorter segment" in n]
    coverage = check_coverage(model, facts, ignores)
    return Result(
        problems,
        notes,
        through,
        across,
        coverage,
        entry=check_entry(model, facts),
        tracker=check_tracker(model, facts),
    )


def with_stale(result: Result, lines: list[str]) -> Result:
    return replace(result, stale=lines)


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'s' if n != 1 else ''}"


def report(model: Model, result: Result, model_file: str = "the model") -> list[str]:
    """The lines the CLI prints for one check run: each failing rule with
    its findings and the fix under them."""
    through, across = result.through, result.across
    out = [
        f"map routes: {through} edge{'s' if through != 1 else ''} through a card "
        f"they do not connect, {across} across a region they neither start nor end in"
    ]
    out += [f"  note: {line}" for line in result.notes]
    cov = result.coverage
    if cov.checked:
        ignored = f", {cov.ignored} ignored" if cov.ignored else ""
        out.append(f"coverage: {cov.mapped}/{cov.total} modules mapped{ignored}")
        out += [f"  {line}" for line in cov.problems]
        if cov.problems:
            out.append(
                f"  fix: map every module in {model_file}, or ignore it with a reason "
                "under [coverage] in the configuration"
            )
    else:
        out.append("coverage: not checked, there are no facts; run: systemap extract")
    if result.entry:
        out.append(f"entry: {_plural(len(result.entry), 'problem')}")
        out += [f"  {line}" for line in result.entry]
        out.append(
            f"  fix: in {model_file}, set entry to a public function or class the "
            "component's modules define, or give the component a tracker"
        )
    if result.tracker:
        out.append(f"tracker: {_plural(len(result.tracker), 'problem')}")
        out += [f"  {line}" for line in result.tracker]
        out.append(
            f"  fix: in {model_file}, set tracker to the item that will build it, "
            "or name the modules that are it"
        )
    problems = result.problems
    if problems:
        out.append(f"map layout: {_plural(len(problems), 'problem')}")
        out += [f"  {line}" for line in problems]
        out.append(f"  fix: edit {model_file}, then run: systemap check")
    else:
        n = len(model.components)
        out.append(
            f"map layout: clean ({n} cards, {len(model.flows)} orthogonal labelled "
            f"edges, {n} wheels, nothing below {TEXT_PX:g}px)"
        )
    if result.stale:
        out.append(f"stale: {_plural(len(result.stale), 'problem')}")
        out += [f"  {line}" for line in result.stale]
        out.append("  fix: run: systemap refresh, then commit the output directory")
    return out
