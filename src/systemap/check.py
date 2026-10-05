"""The mechanical checks compare map geometry, map meaning, and source facts.

The checks include component positions, routes, labels, text size, and relationship
wheels. They also include module coverage, nested maps, entries, and interfaces. The
stale-output checks compare facts, pages, and figures with fresh generated output.

Each source module must have one component claim, unless an ignore reason or empty
package marker lets the map omit the module. A nested map must contain the same modules
as its parent component. Its actors must be other parent components. The CLI gives
diagnostic lines and actions. Any check error gives exit code 1.
"""

from __future__ import annotations

import difflib
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from systemap import explain, extract, figure, nest, page
from systemap.config import Config, Ignore
from systemap.model import (
    Component,
    Layer,
    Meaning,
    Model,
    all_layers,
    claimed,
    defines_entry,
    is_symbol,
    module_matches,
    public_names,
    symbol_claims,
)
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
    """This function finds label and header overlaps from the reported drawing boxes."""
    out = list(meta.get("collisions", []))
    labels: list[dict[str, Any]] = meta.get("labels", [])
    cards: dict[str, list[float]] = meta.get("cards", {})
    for header in meta.get("headers", []):
        hb = _box(header["box"])
        for cid, cb in cards.items():
            if _overlap(hb, _box(cb)):
                out.append(f"header of {header['kind']} {header['id']} touches component {cid}")
    for k, lab in enumerate(labels):
        lb = _box(lab["box"])
        for cid, cb in cards.items():
            if _overlap(lb, _box(cb)):
                out.append(f"label '{lab['artifact']}' touches component {cid}")
        for other in labels[k + 1 :]:
            if _overlap(lb, _box(other["box"])):
                out.append(f"label '{lab['artifact']}' touches label '{other['artifact']}'")
    return out


def _seg_hits(a: list[float], b: list[float], box: Box) -> bool:
    """This function finds whether segment a-b crosses the box interior."""
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
    """This function finds routes across components other than its endpoints or regions.

    It uses exact component boxes and excludes the endpoint regions. Each edge counts
    once for each error type. Router notices supply the reason for a fallback route.
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
    return [f"text set at {s}px, less than {TEXT_PX}px" for s in small]


# ---- the wheel, mirrored from schematic._INTERACTIVE_JS ----------------------
# The page lays the wheel out in the browser; this is the same arithmetic in
# Python so the label geometry can be checked without one. Keep the two in
# step: a change to one is a change to both.

CX, CY, R = 200.0, 200.0, 118.0
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
    cid: str, edges: list[dict[str, str]], layers: tuple[Layer, ...]
) -> tuple[Box, list[tuple[str, Box]]]:
    order = {layer.id: i for i, layer in enumerate(layers)}
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
    """This function finds wheel labels that touch the center or another label.

    The page adjusts the viewBox to contain all labels, so no drawing-boundary check is
    necessary.
    """
    out: list[str] = []
    layers = all_layers(model, meaning)
    for c in model.components:
        cid = c.id
        centre, boxes = wheel_boxes(cid, edges, layers)
        for k, (name, box) in enumerate(boxes):
            if _overlap(box, centre):
                out.append(f"wheel of {cid}: label {name} touches the centre")
            for other, ob in boxes[k + 1 :]:
                if _overlap(box, ob):
                    out.append(f"wheel of {cid}: labels {name} and {other} touch")
    return out


# ---- coverage: every module claimed once --------------------------------------


@dataclass(frozen=True)
class Coverage:
    """This record gives the module coverage result.

    Without facts, `checked` is false. The `total` field counts all source modules. The
    `mapped` count includes unique claims, ignored modules, and empty package markers.
    Nested maps have `counted=False`, because their parent component supplies the
    top-level coverage count.
    """

    checked: bool
    mapped: int
    total: int
    ignored: int
    problems: tuple[str, ...]
    markers: int = 0
    counted: bool = True

    @property
    def ok(self) -> bool:
        return self.checked and not self.problems


def check_coverage(model: Model, facts: dict[str, Any], ignores: Iterable[Ignore]) -> Coverage:
    """This function validates one component claim for each source module.

    An ignore reason lets a module have no claim, but not multiple claims. An empty
    package marker can have no component claim. An ignore without a source match, or
    with only empty markers, gives a diagnostic.
    """
    if not facts:
        return Coverage(False, 0, 0, 0, ("No facts are available for the coverage check.",))
    components = facts.get("components", {})
    modules = sorted(components)
    markers = {m for m in modules if extract.is_empty_marker(components[m])}
    ignore_list = list(ignores)
    problems: list[str] = []
    for ignore in ignore_list:
        matched = [m for m in modules if module_matches(ignore.module, m)]
        if not matched:
            problems.append(f"ignore specifies a module missing from the facts: {ignore.module}")
        elif all(m in markers for m in matched):
            problems.append(
                f"ignore is not necessary: {ignore.module} is an empty package marker. The "
                f"coverage rule omits it automatically. Remove the ignore entry."
            )
    ignored = {m for m in modules if any(module_matches(i.module, m) for i in ignore_list)}
    mapped = n_ignored = n_markers = 0
    for m in modules:
        owners = [
            c.id for c in model.components if any(module_matches(p, m) for p in c.implemented_by)
        ]
        if len(owners) > 1:
            times = "twice" if len(owners) == 2 else f"{len(owners)} times"
            problems.append(f"claimed {times}: {m} ({', '.join(owners)})")
        elif owners:
            mapped += 1
        elif m in markers:
            mapped += 1
            n_markers += 1
        elif m in ignored:
            mapped += 1
            n_ignored += 1
        else:
            problems.append(f"unmapped: {m} (no component has this module claim)")
    return Coverage(True, mapped, len(modules), n_ignored, tuple(problems), n_markers)


# The coverage of a map inside a card: nothing, on record.
NOT_COUNTED = Coverage(True, 0, 0, 0, (), counted=False)


# ---- nesting: the map inside a card is that card and nothing else --------------


def check_nesting(
    parent: Model, card: Component, sub: Model, facts: dict[str, Any], sub_label: str
) -> list[str]:
    """This function compares nested-map module claims with the parent component claims.

    Each applicable module must have one nested component claim. Empty package markers
    and symbol claims do not add module requirements. The nested actors must be other
    parent components. Without facts, only actor checks run.
    """
    where = f"the map inside {card.id} ({sub_label})"
    out: list[str] = []
    for c in sub.components:
        if c.kind != "actor":
            continue
        if c.id == card.id:
            out.append(f"{where} has actor {c.id}, the component that contains the map.")
        elif c.id not in parent.ids:
            out.append(
                f"{where} has actor {c.id}, which is not a component of the parent map. "
                f"Nested-map actors are other parent components."
            )
    components = facts.get("components", {})
    if not components:
        return out
    markers = {m for m in components if extract.is_empty_marker(components[m])}
    wanted = [m for m in claimed(card, components) if m not in markers]
    have: dict[str, list[str]] = {}
    for c in sub.components:
        if c.kind == "actor":
            continue
        for m in claimed(c, components):
            if m not in markers:
                have.setdefault(m, []).append(c.id)
    for m, owners in have.items():
        if len(owners) > 1:
            out.append(f"{where} has a claim for {m} {len(owners)} times ({', '.join(owners)})")
    for m in sorted(set(have) - set(wanted)):
        out.append(
            f"{where} has a claim for {m}, but {card.id} has no claim for it "
            f"({', '.join(have[m])})."
        )
    for m in wanted:
        if m not in have:
            out.append(f"{where} has no claim for {m}, but {card.id} has a claim for it.")
    return out


# ---- entry: a card is code that exists today ----------------------------------

# The kinds whose card may be a namespace with no way in: state is what
# they are, and their modules alone say they exist.
ENTRY_OPTIONAL = ("store", "context")


def check_entry(model: Model, facts: dict[str, Any]) -> list[str]:
    """This function validates component modules, symbol claims, and entries against the
    facts.

    A symbol claim must have a public symbol and a module owner. An actor has no
    source-code checks. A store or context component can have an empty entry. Other
    components must have a defined public entry.
    """
    components = facts.get("components", {})
    if not components:
        return []
    owned = {m for c in model.components for m in claimed(c, components)}
    out: list[str] = []
    for c in model.components:
        if c.kind == "actor":
            continue
        for pattern in c.implemented_by:
            if is_symbol(pattern):
                continue
            if not any(module_matches(pattern, m) for m in components):
                out.append(
                    f"{c.id} has a module claim for {pattern}, which is missing from the facts."
                )
        symbols: list[str] = []
        for module, name in symbol_claims(c):
            symbol = f"{module}:{name}"
            if module not in components:
                out.append(
                    f"{c.id} has a symbol claim for {symbol} in a module missing from the facts."
                )
                continue
            if name not in public_names(components[module]):
                out.append(
                    f"{c.id} has a symbol claim for {symbol}, but {module} does not define it."
                )
                continue
            if module not in owned:
                out.append(
                    f"{c.id} has a symbol claim for {symbol} in a module with no owner. A symbol "
                    f"claim must have a module owner on the map."
                )
                continue
            symbols.append(symbol)
        modules = claimed(c, components)
        if not modules and not symbols:
            if not c.implemented_by:
                out.append(f"{c.id} has no module claim. A component shows source code.")
            continue
        held = ", ".join(modules + symbols)
        if not c.entry:
            if c.kind not in ENTRY_OPTIONAL:
                out.append(f"{c.id} has no entry. Its modules are {held}")
            continue
        if not defines_entry(c, facts):
            out.append(
                f"{c.id} has entry {c.entry}, but its modules do not define this entry ({held})."
            )
    return out


# ---- interface: the signature names something the modules define ------------------

# The leading identifier of an interface line, and the method after a dot
# when the line reads `Class.method`. The token ends at `(`, `.`, `->`,
# whitespace or anything else that is not part of a name.
INTERFACE_HEAD = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z_][A-Za-z0-9_]*))?")


def interface_head(text: str) -> tuple[str, str] | None:
    """This function reads the initial interface identifier and optional method name, or
    gives `None` if there is no identifier.
    """
    found = INTERFACE_HEAD.match(text)
    if found is None:
        return None
    return found.group(1), found.group(2) or ""


def method_names(record: Mapping[str, Any], class_name: str) -> set[str]:
    """This function gives public class methods from recorded signatures."""
    out: set[str] = set()
    for group in ("classes", "errors"):
        for cls in record.get(group, []):
            if cls.get("name") != class_name:
                continue
            for sig in cls.get("methods", []):
                found = re.match(r"(?:async )?def (\w+)\(", sig)
                if found:
                    out.add(found.group(1))
    return out


def _reexport_sources(record: Mapping[str, Any], name: str) -> list[str]:
    """This function finds the source modules for re-exported public names."""
    return [
        str(n["reexport_of"])
        for n in record.get("names", [])
        if n.get("name") == name and n.get("reexport_of")
    ]


def _closest(name: str, candidates: Iterable[str]) -> str:
    matches = difflib.get_close_matches(name, sorted(set(candidates)), n=1, cutoff=0.0)
    return matches[0] if matches else ""


def check_interface(model: Model, facts: dict[str, Any]) -> list[str]:
    """This function validates interface names against the component modules.

    A method name must have a public class and a public method. Re-exports can supply
    these names.
    """
    components = facts.get("components", {})
    if not components:
        return []
    out: list[str] = []
    for c in model.components:
        problem = interface_problem(c, components)
        if problem:
            out.append(problem)
    return out


def interface_problem(c: Component, components: Mapping[str, Any]) -> str:
    """This function gives the interface diagnostic for one component, or an empty string
    if the interface is correct.
    """
    if c.kind == "actor" or not c.interface.strip():
        return ""
    modules = claimed(c, components)
    symbols = symbol_claims(c)
    names: set[str] = set()
    for m in modules:
        names |= public_names(components[m])
    names |= {name for _module, name in symbols}
    held = ", ".join(modules + [f"{m}:{n}" for m, n in symbols])
    head = interface_head(c.interface)
    if head is None:
        return (
            f"{c.id} interface '{c.interface}' does not start with a name. Start it with a "
            f"public name from its modules ({held})"
        )
    name, method = head
    if name not in names:
        closest = _closest(name, names)
        hint = f". The nearest name is {closest}" if closest else ""
        return (
            f"{c.id} interface starts with {name}, but none of its modules defines this "
            f"name ({held}){hint}"
        )
    if not method:
        return ""
    methods = _interface_methods(modules, symbols, components, name)
    if method not in methods:
        # The class's own methods first: a wrong method is usually a
        # misspelt one, not a module-level name.
        closest = _closest(method, methods) or _closest(method, names)
        hint = f". The nearest name is {closest}" if closest else ""
        return (
            f"{c.id} interface contains {name}.{method}, but {name} has no public method "
            f"{method} ({held}){hint}"
        )
    return ""


def _interface_methods(
    modules: list[str], symbols: list[tuple[str, str]], components: Mapping[str, Any], name: str
) -> set[str]:
    """This function gives public methods from a class claim and its re-exports."""
    methods: set[str] = set()
    for m in modules:
        methods |= method_names(components[m], name)
        # A class re-exported by a package __init__ keeps its methods in
        # the module that defines it.
        methods |= _reexport_methods(components[m], components, name)
    for m, n in symbols:
        if n == name and m in components:
            methods |= method_names(components[m], name)
    return methods


def _reexport_methods(
    record: Mapping[str, Any], components: Mapping[str, Any], name: str
) -> set[str]:
    methods: set[str] = set()
    for source in _reexport_sources(record, name):
        if source not in components:
            continue
        methods |= method_names(components[source], name)
        if any(
            entry.get("name") == name
            and entry.get("kind") == "module"
            and entry.get("reexport_of") == source
            for entry in record.get("names", [])
        ):
            methods |= public_names(components[source])
    return methods


# ---- stale: the outputs are what the tree and the model say ----------------------


def stale_facts(
    fresh: dict[str, Any], stored: dict[str, Any], model: Model, prefixes: set[str]
) -> list[str]:
    """This function compares stored facts with fresh facts and finds claims for missing
    source modules.
    """
    problems = (
        extract.drift(fresh, stored)
        + extract.mapping_drift(fresh, model, prefixes)
        + extract.inventory_issue_lines(fresh)
    )
    if not stored:
        problems.insert(0, "No extracted facts are available.")
    return problems


def stale(
    cfg: Config,
    tree: nest.Tree,
    fresh: dict[str, Any] | None = None,
) -> list[str]:
    """This function compares saved facts, pages, and configured figures with fresh
    generated output.
    """
    fresh = fresh if fresh is not None else extract.build(cfg)
    stored = extract.read_facts(cfg.facts_path)
    if not stored:
        return ["No extracted facts are available."]
    # Only the drift is stale here: a claim of a module the tree does not
    # have is the entry rule's finding, and a placement problem is the
    # placement rule's, so neither is reported twice.
    out = [f"facts: {line}" for line in extract.drift(fresh, stored)]
    for m in tree.maps:
        if model_problems(m.model, m.meaning):
            continue
        html = page.build(
            cfg,
            m.model,
            m.meaning,
            m.theme,
            stored,
            {"has_change": False},
            nesting=page.nesting_of(cfg, tree, m, stored),
        )
        out += _stale_file(cfg, m.page_path(cfg), html)
    for fig in cfg.figures:
        if not tree.has(fig.map):
            raise nest.unknown_map(tree, fig.map)
        m = tree.get(fig.map)
        if model_problems(m.model, m.meaning):
            continue
        html, _collisions = figure.configured(cfg, tree, m, stored, fig)
        out += _stale_file(cfg, cfg.out_path / fig.out, html)
    return out


def _stale_file(cfg: Config, path: Path, expected: str) -> list[str]:
    rel = cfg.rel(path)
    if not path.is_file():
        return [f"{rel} has no rendered output."]
    if path.read_text(encoding="utf-8") != expected:
        return [f"{rel} differs from the rendered output."]
    return []


# ---- one run -------------------------------------------------------------------


@dataclass(frozen=True)
class Result:
    """This record contains geometry, meaning, coverage, entry, interface, and nested-map
    check results.
    """

    problems: list[str]
    through: int
    across: int
    coverage: Coverage
    entry: list[str] = field(default_factory=list)
    interface: list[str] = field(default_factory=list)
    nesting: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    unknown_surface: list[str] = field(default_factory=list)
    inventory_issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            not self.problems
            and self.coverage.ok
            and not self.entry
            and not self.interface
            and not self.nesting
            and not self.stale
            and not self.inventory_issues
        )


def run(
    model: Model,
    meaning: Meaning,
    t: dict[str, Any],
    facts: dict[str, Any],
    ignores: Iterable[Ignore] = (),
    observed_by: Iterable[str] = (),
    *,
    coverage: bool = True,
) -> Result:
    """This function does the checks for one map.

    Model contradictions prevent rendering. Other checks compare the model with source
    facts.
    """
    problems = model_problems(model, meaning)
    through = across = 0
    if not problems:
        svg, detail = render_schematic(model, meaning, t, facts, observed_by=observed_by)
        meta = json.loads(detail)["_meta"]
        route_problems, through, across = check_routes(meta, model)
        problems += route_problems
        problems += check_labels(meta)
        problems += check_type_size(svg)
        problems += check_wheels(meta["edges"], model, meaning)
    counted = check_coverage(model, facts, ignores) if coverage else NOT_COUNTED
    return Result(
        problems,
        through,
        across,
        counted,
        entry=check_entry(model, facts),
        interface=check_interface(model, facts),
        unknown_surface=extract.unknown_fact_lines(facts) if coverage else [],
        inventory_issues=extract.inventory_issue_lines(facts) if coverage else [],
    )


def run_tree(
    tree: nest.Tree,
    facts: dict[str, Any],
    ignores: Iterable[Ignore] = (),
    observed_by: Iterable[str] = (),
) -> dict[str, Result]:
    """This function does the checks for all maps. Coverage counts on the top map.
    module-set checks run on nested maps.
    """
    out: dict[str, Result] = {}
    for m in tree.maps:
        result = run(m.model, m.meaning, m.theme, facts, ignores, observed_by, coverage=m.top)
        card = tree.opening_card(m)
        if card is not None:
            parent = tree.get(m.parent or "")
            nesting = check_nesting(parent.model, card, m.model, facts, m.rel)
            result = replace(result, nesting=nesting)
        out[m.id] = result
    return out


def tree_ok(results: Mapping[str, Result]) -> bool:
    return all(result.ok for result in results.values())


def with_stale(result: Result, lines: list[str]) -> Result:
    return replace(result, stale=lines)


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'s' if n != 1 else ''}"


def coverage_line(cov: Coverage) -> str:
    """This function formats the coverage counts, including ignored modules and empty
    package markers.
    """
    line = f"coverage: {cov.mapped} of {cov.total} modules mapped"
    if cov.ignored:
        line += f", {cov.ignored} ignored with a reason"
    if cov.markers:
        noun = "an empty package marker" if cov.markers == 1 else "empty package markers"
        line += f", {cov.markers} {noun}"
    return line


def report(
    model: Model,
    result: Result,
    model_file: str = "the model",
    prefix: str = "",
    teach: bool = True,
) -> list[str]:
    """This function gives the CLI report for one map.

    The report includes diagnostic groups and necessary actions. The optional prefix
    identifies a nested map. The `teach` option adds an explanation for each diagnostic
    group.
    """
    lines = _report(model, result, model_file)
    return [prefix + line for line in (_taught(lines) if teach else lines)]


def _taught(lines: list[str]) -> list[str]:
    """This function adds an explanation to each diagnostic group with errors."""
    out: list[str] = []
    for k, line in enumerate(lines):
        out.append(line)
        failed = k + 1 < len(lines) and lines[k + 1].startswith(" ")
        if failed:
            out += explain.rows(line.split(":")[0])
    return out


def report_stale(lines: list[str], teach: bool = True) -> list[str]:
    """This function gives one stale-output report for the full map tree."""
    if not lines:
        return []
    return [
        f"stale: {_plural(len(lines), 'problem')}",
        *(explain.rows("stale") if teach else []),
        *(f"  {line}" for line in lines),
        "  fix: Use systemap refresh. Then commit the output directory.",
    ]


def _report(model: Model, result: Result, model_file: str) -> list[str]:
    through, across = result.through, result.across
    out = [
        (
            f"map routes: {through} edge{('s' if through != 1 else '')} across components "
            f"other than its endpoints, {across} across regions other than its endpoint "
            f"regions."
        )
    ]
    cov = result.coverage
    if not cov.counted:
        pass
    elif cov.checked:
        out.append(coverage_line(cov))
        out += [f"  {line}" for line in cov.problems]
        if cov.problems:
            out.append(
                f"  fix: Give each module a component in {model_file}, or give a reason to "
                f"ignore it in [coverage] in the configuration."
            )
    else:
        out.append("coverage: No facts are available for the check. Use systemap extract.")
    if result.nesting:
        out.append(f"nesting: {_plural(len(result.nesting), 'problem')}")
        out += [f"  {line}" for line in result.nesting]
        out.append(
            f"  fix: In {model_file}, give each module of the parent component one claim. "
            f"Use other parent components as actors."
        )
    if result.entry:
        out.append(f"entry: {_plural(len(result.entry), 'problem')}")
        out += [f"  {line}" for line in result.entry]
        out.append(
            "  fix: The map shows code in the facts. "
            f"In {model_file}, use modules from the facts. Set entry to a public "
            f"name that one of these modules defines."
        )
    if result.interface:
        out.append(f"interface: {_plural(len(result.interface), 'problem')}")
        out += [f"  {line}" for line in result.interface]
        out.append(
            f"  fix: In {model_file}, start interface with a public name from the "
            f"component modules (Class.method for a method), or leave it empty."
        )
    out.extend(_unknown_surface_report(result.unknown_surface))
    problems = result.problems
    if problems:
        out.append(f"map layout: {_plural(len(problems), 'problem')}")
        out += [f"  {line}" for line in problems]
        out.append(f"  fix: Change {model_file}. Then use systemap check.")
    else:
        n = len(model.components)
        out.append(
            f"map layout: has no errors ({n} components, {len(model.flows)} orthogonal "
            f"labeled edges, {n} wheels, no text size less than {TEXT_PX:g}px)"
        )
    out += report_stale(result.stale)
    return out


def _unknown_surface_report(findings: list[str]) -> list[str]:
    if not findings:
        return []
    return [
        f"unknown surface: {_plural(len(findings), 'finding')}",
        *(f"  {line.removeprefix('unknown surface: ')}" for line in findings),
        (
            "  fix: Add parser support for this TypeScript syntax, or restore the missing "
            "source mapping."
        ),
    ]
