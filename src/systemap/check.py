"""The mechanical checks compare map geometry, map meaning, and source facts.

The checks include component positions, routes, labels, and text size.
They also include module coverage, nested maps, entries, and interfaces. The
stale-output checks compare facts, pages, and figures with fresh generated output.

Each source module must have one component claim, unless an ignore reason or empty
package marker lets the map omit the module. A nested map must contain the same modules
as its parent component. Its actors must be other parent components. The CLI gives
diagnostic lines and actions. Any check error gives exit code 1.
"""

from __future__ import annotations

import difflib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from systemap import (
    extraction,
    facts_file,
    figure,
    file_write,
    identifier,
    nest,
    out_paths,
    page,
    reexports,
    source_facts,
    unknown_causes,
)
from systemap import language as languages
from systemap.check_report import coverage_line as coverage_line
from systemap.check_report import report as report
from systemap.check_report import report_stale as report_stale
from systemap.config import Config, Ignore
from systemap.entry_names import missing_entry
from systemap.model import (
    Component,
    Meaning,
    Model,
    claimed,
    covers,
    defines_entry,
    is_symbol,
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
        src, dst, art, name = f.src, f.dst, f.artifact, f.name
        pts = paths.get(str(i)) or paths.get(i)
        if not pts:
            out.append(f"route: {name} ('{art}') has no path")
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
        why = next((n for n in notes if n.startswith(f"{name}:")), "")
        reason = f" ({why.split(': ', 1)[1]})" if why else ""
        if hit_cards:
            through += 1
            out.append(f"route: {name} passes through {', '.join(hit_cards)}{reason}")
        if hit_regions:
            across += 1
            out.append(f"route: {name} crosses region {', '.join(hit_regions)}{reason}")
    return out, through, across


def check_type_size(svg: str) -> list[str]:
    small = sorted(
        {float(m) for m in re.findall(r"font-size:\s*([0-9.]+)px", svg) if float(m) < TEXT_PX}
    )
    return [f"text set at {s}px, less than {TEXT_PX}px" for s in small]


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
    markers = {m for m in modules if source_facts.is_empty_marker(components[m])}
    ignore_list = list(ignores)
    problems: list[str] = []
    for ignore in ignore_list:
        matched = [m for m in modules if covers(ignore.module, m, components)]
        if not matched:
            problems.append(f"ignore specifies a module missing from the facts: {ignore.module}")
        elif all(m in markers for m in matched):
            problems.append(
                f"ignore is not necessary: {ignore.module} is an empty package marker. The "
                f"coverage rule omits it automatically. Remove the ignore entry."
            )
    problems += _claimed_ignores(model, components, markers, ignore_list)
    ignored = {m for m in modules if any(covers(i.module, m, components) for i in ignore_list)}
    mapped = n_ignored = n_markers = 0
    for m in modules:
        owners = [
            c.id
            for c in model.components
            if any(covers(p, m, components) for p in c.implemented_by)
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


def _claimed_ignores(
    model: Model, modules: Mapping[str, Any], markers: set[str], ignores: list[Ignore]
) -> list[str]:
    """This function finds an ignore entry whose modules all have a component claim."""
    claims = [p for c in model.components for p in c.implemented_by]
    out = []
    for ignore in ignores:
        matched = [m for m in modules if covers(ignore.module, m, modules) and m not in markers]
        if matched and all(any(covers(p, m, modules) for p in claims) for m in matched):
            out.append(
                f"ignore is not necessary: {ignore.module} has a component claim. "
                f"Remove the ignore entry."
            )
    return out


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
    markers = {m for m in components if source_facts.is_empty_marker(components[m])}
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


def _no_modules(model: Model, components: Mapping[str, Any]) -> list[str]:
    """This function finds facts without modules for a model with source components."""
    if components or all(c.kind == "actor" for c in model.components):
        return []
    return [
        "The facts contain no source modules. Make sure that [package_roots] in the "
        "configuration gives the directories that contain the source files."
    ]


def names_not_known(c: Component, components: Mapping[str, Any]) -> bool:
    """Tell if the public names of the component are not known.

    A claimed module, or the module of a symbol claim, that the extractor could not read
    or parse has names that are not known. A module with an unknown record of the cause
    `reexport` also has names that are not known. Then a name that the facts do not give
    is not known: it is not a pass and not a failure. The `source inventory unresolved`
    group or the `unknown surface` group gives the module."""
    modules = [*claimed(c, components), *(m for m, _name in symbol_claims(c))]
    return any(m in components and _names_unknown(components[m]) for m in modules)


def _names_unknown(record: Mapping[str, Any]) -> bool:
    """Tell if the adapter could not read or parse all of the module, or if the names of a
    re-export of the module are not known.

    A record without a `completeness` record keeps the earlier check result."""
    state = record.get("completeness")
    if isinstance(state, Mapping) and state.get("parsed") is False:
        return True
    unknown = record.get("unknown") or []
    return any(unknown_causes.of(item) == unknown_causes.REEXPORT for item in unknown)


def _symbol_problem(
    c: Component, module: str, name: str, components: Mapping[str, Any], owned: set[str]
) -> str | None:
    """Give the problem of one symbol claim, or None for a correct claim.

    An empty string tells that the claim is not known: the names of the module are not
    known (`_names_unknown`), and the facts do not give the name. The claim then gives no line.
    The module owner is known also when the name is not known. Thus a module without an
    owner gives its line."""
    symbol = f"{module}:{name}"
    if module not in components:
        return f"{c.id} has a symbol claim for {symbol} in a module missing from the facts."
    if name not in public_names(components[module]):
        if not _names_unknown(components[module]):
            return f"{c.id} has a symbol claim for {symbol}, but {module} does not define it."
        if module in owned:
            return ""
    if module not in owned:
        return (
            f"{c.id} has a symbol claim for {symbol} in a module with no owner. A symbol "
            f"claim must have a module owner on the map."
        )
    return None


def check_entry(model: Model, facts: dict[str, Any]) -> list[str]:
    """This function validates component modules, symbol claims, and entries against the
    facts.

    A symbol claim must have a public symbol and a module owner. An actor has no
    source-code checks. A store or context component can have an empty entry. Other
    components must have a defined entry (`systemap.entry_names` gives the forms). Facts
    without modules do not agree with a model that has source components.
    """
    components = facts.get("components", {})
    if not facts:
        return []
    owned = {m for c in model.components for m in claimed(c, components)}
    out = _no_modules(model, components)
    for c in model.components:
        if c.kind == "actor":
            continue
        for pattern in c.implemented_by:
            if is_symbol(pattern):
                continue
            if not any(covers(pattern, m, components) for m in components):
                out.append(
                    f"{c.id} has a module claim for {pattern}, which is missing from the facts."
                )
        symbols: list[str] = []
        for module, name in symbol_claims(c):
            problem = _symbol_problem(c, module, name, components, owned)
            if problem is None:
                symbols.append(f"{module}:{name}")
            elif problem:
                out.append(problem)
        modules = claimed(c, components)
        if not modules and not symbols:
            if not c.implemented_by:
                out.append(f"{c.id} has no module claim. A component shows source code.")
            continue
        held = ", ".join(modules + symbols)
        if not c.entry:
            if c.kind not in ENTRY_OPTIONAL:
                out.extend(missing_entry(c.id, modules, symbols, facts))
            continue
        if not defines_entry(c, facts) and not names_not_known(c, components):
            out.append(
                f"{c.id} has entry {c.entry}, but its modules do not define this entry ({held})."
            )
    return out


# ---- interface: the signature names something the modules define ------------------


def interface_head(text: str) -> tuple[str, str] | None:
    """This function reads the initial interface identifier and the method name after a
    dot (`Class.method`), or gives `None`. An identifier can contain Unicode letters.
    """
    start = len(text) - len(text.lstrip())
    name = identifier.read(text, start)
    if not name:
        return None
    after = start + len(name)
    method = identifier.read(text, after + 1) if text[after : after + 1] == "." else ""
    return name, method


def method_names(record: Mapping[str, Any], class_name: str) -> set[str]:
    """This function gives public class methods from recorded signatures.

    The first language adapter that reads a name from the signature gives the name."""
    signatures = [
        sig
        for group in ("classes", "errors", "types")
        for cls in record.get(group, [])
        if cls.get("name") == class_name
        for sig in cls.get("methods", [])
    ]
    return {name for name in map(_method_name, signatures) if name}


def _method_name(signature: str) -> str:
    adapters = (languages.repository(name) for name in languages.names())
    return next((found for a in adapters if (found := a.method_name(signature))), "")


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
    if the interface is correct or not known.
    """
    if c.kind == "actor" or not c.interface.strip() or names_not_known(c, components):
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
        hint = _name_hint(name, names, [components[m] for m in modules])
        return (
            f"{c.id} interface starts with {name}, but none of its modules defines this "
            f"name ({held}){hint}"
        )
    if not method:
        return ""
    holders = _holders(modules, symbols, components, name)
    methods = _interface_methods(holders, components, name)
    if method in methods or _methods_not_known(holders, components, name):
        return ""
    # The class's own methods first: a wrong method is usually a
    # misspelt one, not a module-level name.
    closest = _closest(method, methods) or _closest(method, names)
    hint = f". The nearest name is {closest}" if closest else ""
    return (
        f"{c.id} interface contains {name}.{method}, but {name} has no public method "
        f"{method} ({held}){hint}"
    )


def _name_hint(name: str, names: set[str], records: list[Mapping[str, Any]]) -> str:
    """Give the hint for an interface name that is not a public name.

    A public name with the defining symbol `name` (`defined_as`) comes first, for example
    the public name `default` of a module that exports the symbol `ky`. If there is no
    such name, the hint gives the nearest spelling."""
    given = sorted(
        {
            entry["name"]
            for record in records
            for entry in record.get("names") or []
            if entry.get("defined_as") == name and entry.get("name") != name
        }
    )
    if given:
        return f". The public name for the symbol {name} is {', '.join(given)}"
    closest = _closest(name, names)
    return f". The nearest name is {closest}" if closest else ""


def _holders(
    modules: list[str], symbols: list[tuple[str, str]], components: Mapping[str, Any], name: str
) -> list[str]:
    """Give the claimed modules and the modules of the symbol claims of the name."""
    return [*modules, *(m for m, n in symbols if n == name and m in components)]


def _methods_not_known(holders: list[str], components: Mapping[str, Any], name: str) -> bool:
    """Tell if the methods of the name are not known.

    They are not known if a module gives the name with an unknown definition. They are
    also not known if a module of a definition is missing from the facts or its names are not known.
    Then a method that the facts do not give is not known: it is not a pass and not a
    failure. The `source inventory unresolved` group or the `unknown surface` group gives
    the cause."""
    for holder in holders:
        record = components[holder]
        if _unknown_definition(record, name):
            return True
        for module, _symbol in reexports.definitions(record, holder, name):
            if module not in components or _names_unknown(components[module]):
                return True
    return False


def _unknown_definition(record: Mapping[str, Any], name: str) -> bool:
    """Tell if the module gives the name with an unknown defining module or symbol."""
    return any(
        entry.get("defined_in") is None or entry.get("defined_as") is None
        for entry in record.get("names") or []
        if entry.get("name") == name and "defined_in" in entry
    )


def _interface_methods(holders: list[str], components: Mapping[str, Any], name: str) -> set[str]:
    """This function gives the public methods of each definition of the name.

    A re-export gives the module and the symbol of its definition. A name that refers to
    a full module gives the public names of that module."""
    methods: set[str] = set()
    for holder in holders:
        for module, symbol in reexports.definitions(components[holder], holder, name):
            if module not in components:
                continue
            if symbol == source_facts.WHOLE_MODULE:
                methods |= public_names(components[module])
            else:
                methods |= method_names(components[module], symbol)
    return methods


# ---- stale: the outputs are what the tree and the model say ----------------------


def stale_facts(
    fresh: dict[str, Any], stored: dict[str, Any], model: Model, prefixes: set[str]
) -> list[str]:
    """This function compares stored facts with fresh facts and finds claims for missing
    source modules.
    """
    problems = extraction.drift(fresh, stored) + extraction.mapping_drift(fresh, model, prefixes)
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
    fresh = fresh if fresh is not None else extraction.build(cfg)
    stored = facts_file.read_facts(cfg.facts_path, cfg.root)
    if not stored:
        return ["No extracted facts are available."]
    # Only the drift is stale here: a claim of a module the tree does not
    # have is the entry rule's finding, and a placement problem is the
    # placement rule's, so neither is reported twice.
    out = [f"facts: {line}" for line in extraction.drift(fresh, stored)]
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
    """Compare an output file with its rendered text.

    The file must be in the output directory (`out_paths`). A link out of the repository,
    a FIFO, and a device give `file_write.RefusedFile` with the cause. A file that is not
    UTF-8 text is different from the rendered output. A refresh replaces it.
    """
    rel = cfg.rel(path)
    try:
        text = file_write.read_text(cfg.root, out_paths.checked(cfg, path))
    except UnicodeError:
        return [f"{rel} differs from the rendered output. The file is not UTF-8 text."]
    if text is None:
        return [f"{rel} has no rendered output."]
    if text != expected:
        return [f"{rel} differs from the rendered output."]
    return []


def output_text(root: Path, path: Path) -> str:
    """Give the text of an output file, or an empty string if it is missing.

    A file that is not UTF-8 text also gives an empty string: it is different from each
    rendered output."""
    try:
        return file_write.read_text(root, path) or ""
    except UnicodeError:
        return ""


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
    # The modules that the extractor could not read or parse. They do not reject the map.
    inventory_issues: tuple[str, ...] = ()
    # The causes of the `unknown_surface` lines and the `inventory_issues` lines, for
    # their fix lines.
    unknown_causes: tuple[str, ...] = ()
    # The source rows below each `unknown_surface` line (`source_facts.source_rows`).
    unknown_rows: Mapping[str, list[str]] = field(default_factory=dict)
    inventory_causes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return (
            not self.problems
            and self.coverage.ok
            and not self.entry
            and not self.interface
            and not self.nesting
            and not self.stale
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
    counted = check_coverage(model, facts, ignores) if coverage else NOT_COUNTED
    unknown = source_facts.unknown_fact_causes(facts) if coverage else []
    unread = source_facts.inventory_issue_causes(facts) if coverage else []
    return Result(
        problems,
        through,
        across,
        counted,
        entry=check_entry(model, facts),
        interface=check_interface(model, facts),
        unknown_surface=[line for line, _cause in unknown],
        inventory_issues=tuple(line for line, _cause in unread),
        unknown_causes=tuple(dict.fromkeys(cause for _line, cause in unknown)),
        unknown_rows=source_facts.unknown_rows(facts) if coverage else {},
        inventory_causes=tuple(dict.fromkeys(cause for _line, cause in unread)),
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
