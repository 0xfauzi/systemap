"""Render the map as an SVG figure with inspector data.

A card shows one component, its identifier and its plain text name.
Dashed card borders identify actors outside the source code. Flow lines
show artifacts and use layer colors. Selection shows connections
and shows their explanation in the inspector. Nodes carry `data-id`
and kind values. Flow lines carry artifact labels and `data-layer`.

Flow evidence states come from evidence.py. `observed` means that source
references resolve and the source review digest agrees with the claim.
`structural` means that an import, shared module or configured mechanism
supports a possible connection. `external` means that an endpoint is
an actor. `declared` means that no structural evidence supports the flow.
Structural evidence does not prove direction or artifact.

route.py makes horizontal and vertical paths between cards. Paths avoid
other cards and unrelated regions. Labels use path segments or space
beside a short segment. Header subtitles can use two lines. The detail
JSON records placement errors in `_meta.collisions` and routing reasons
in `_meta.notes`. Map checks reject placement errors.

Card positions and flow explanations come from the model. Every figure
uses these same positions. The minimum figure text size is 11px."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from systemap import evidence
from systemap.model import (
    DERIVED_LAYERS,
    Meaning,
    Model,
    all_layers,
    build_state,
    entry_module,
    reading,
)
from systemap.route import path_d, place_labels, route_all
from systemap.schematic_cards import (
    CARD_W as CARD_W,
)
from systemap.schematic_cards import (
    HEADER_LINES as HEADER_LINES,
)
from systemap.schematic_cards import (
    LABEL_CHAR as LABEL_CHAR,
)
from systemap.schematic_cards import (
    LABEL_CHAR_W as LABEL_CHAR_W,
)
from systemap.schematic_cards import (
    LABEL_GAP as LABEL_GAP,
)
from systemap.schematic_cards import (
    LABEL_H as LABEL_H,
)
from systemap.schematic_cards import (
    LABEL_PX,
    MAP_OFFSET,
    NAME_LINE_H,
    NAME_PX,
    RADIUS,
    container_header,
    esc,
)
from systemap.schematic_cards import (
    SUB_CHAR as SUB_CHAR,
)
from systemap.schematic_cards import (
    TEXT_PX as TEXT_PX,
)
from systemap.schematic_cards import (
    Geometry as Geometry,
)
from systemap.schematic_cards import (
    card_text as card_text,
)
from systemap.schematic_cards import geometry as geometry
from systemap.schematic_cards import (
    kind_rows as kind_rows,
)
from systemap.schematic_cards import (
    layer_rows as layer_rows,
)
from systemap.schematic_cards import (
    legend_rows as legend_rows,
)
from systemap.schematic_cards import (
    lives_in as lives_in,
)
from systemap.schematic_cards import region_header as region_header
from systemap.schematic_cards import (
    wrap_all as wrap_all,
)
from systemap.schematic_cards import (
    wrap_id as wrap_id,
)
from systemap.schematic_script import interactive_script as interactive_script
from systemap.schematic_style import _defs, _svg_style
from systemap.schematic_style import panel_css as panel_css
from systemap.theme import Palette


def render(
    model: Model,
    meaning: Meaning,
    t: dict[str, Any],
    facts: dict[str, Any],
    *,
    changed: set[str] | None = None,
    changed_modules: set[str] | None = None,
    adjacent: set[str] | None = None,
    mode: str = "system",
    svg_id: str = "schematic",
    gained: dict[str, dict[str, int]] | None = None,
    hot_artifacts: set[str] | None = None,
    layer: str = "",
    observed_by: Iterable[str] = (),
    opens: Mapping[str, Mapping[str, Any]] | None = None,
    variables: bool = False,
) -> tuple[str, str]:
    """Give the SVG figure and detail JSON.

    `changed` identifies changed components or components in a plan.
    `changed_modules` identifies changed source modules. `hot_artifacts`
    identifies flow labels whose source module changed its public surface.
    The change detector supplies these values.

    `layer` selects the flows that `model.reading` supplies. All cards
    stay. A derived layer uses its specified color. Cards for the layer
    use this color for their borders. Other unconnected cards have lower
    contrast. Card positions, paths and label positions stay the same.
    An unknown layer identifier raises ValueError.

    `observed_by` contains configured mechanisms that support structural
    connections. These mechanisms do not prove flow direction or artifact.
    `opens` contains child map names, page paths, card counts and preview
    diagrams. A child map with a page path has a button in the inspector.
    Without a page path, the inspector gives only the child map name.

    With `variables`, colors use CSS tokens. The page supplies the palette
    tables. Separate figures use literal color values.

    Detail JSON contains one record for each component. `_meta` contains
    layers, flows, verbs, explanations, rules, regions and label errors."""
    changed = changed or set()
    changed_modules = changed_modules or set()
    adjacent = adjacent or set()
    gained = gained or {}
    hot_artifacts = hot_artifacts or set()
    opens = opens or {}
    change_mode = mode == "change"

    T = t
    P = Palette(t, variables)
    COMPONENTS = model.components
    FLOWS = [(f.src, f.dst, f.artifact, f.kind) for f in model.flows]
    CANVAS = model.canvas
    INK, INK_3 = P["ink"], P["ink_3"]
    HALO = P["bg"]
    GHOST_FILL, GHOST_STROKE = P.ghost()
    LAYER_COLOUR: dict[str, str] = {lid: P.layer(lid) for lid in T["layers"]}
    MARKS: dict[str, str] = T.get("marks") or {}
    LAYERS = all_layers(model, meaning)
    # Which edges and which cards each reading shows, decided once here and
    # read by the page's script out of the detail JSON.
    readings = {lay.id: reading(model, meaning, lay.id) for lay in LAYERS}
    if layer and layer not in readings:
        raise ValueError(f"unknown layer id: {layer}")
    shown: set[int] | None = set(readings[layer][0]) if layer else None
    reading_hue = layer if layer in DERIVED_LAYERS else ""
    # The cards a reading is about and the cards its edges reach; the rest
    # are dimmed in a figure of that reading. Structure is about every card
    # and dims none.
    subjects: set[str] = set(readings[layer][1]) if layer else set()
    reached: set[str] = set()
    if shown is not None:
        for i in shown:
            reached.update((model.flows[i].src, model.flows[i].dst))
    marks_reading = bool(layer) and layer != "structure"

    # Text styling is deduplicated into classes: 240 text elements each
    # carrying a full font stack tripled the size of the figure for no
    # information. A lesson embeds this whole.
    text_styles: dict[tuple[float, str, str, bool, str, str, bool], str] = {}

    def L(
        px: float,
        py: float,
        text: str,
        size: float,
        colour: str,
        weight: str = "500",
        mono: bool = False,
        anchor: str = "middle",
        spacing: str = "",
        halo: bool = False,
    ) -> str:
        assert size >= TEXT_PX, f"text below {TEXT_PX}px: {text!r} at {size}"
        key = (size, colour, weight, mono, anchor, spacing, halo)
        cls = text_styles.setdefault(key, f"t{len(text_styles)}")
        return f'<text x="{px:.1f}" y="{py:.1f}" class="{cls}">{esc(text)}</text>'

    def text_css() -> str:
        rules: list[str] = []
        for (size, colour, weight, mono, anchor, spacing, halo), cls in text_styles.items():
            family = P["font_mono"] if mono else P["font_ui"]
            rule = (
                f"font-family:{family};font-size:{size}px;font-weight:{weight};"
                f"fill:{colour};text-anchor:{anchor}"
            )
            if spacing:
                rule += f";letter-spacing:{spacing}"
            if halo:
                rule += f";paint-order:stroke;stroke:{HALO};stroke-width:4;stroke-linejoin:round"
            rules.append(f"#{svg_id} .{cls}{{{rule}}}")
        return "<style>" + "".join(rules) + "</style>"

    states = {c.id: build_state(c, facts) for c in COMPONENTS}
    backed = evidence.of_model(model, meaning, facts, observed_by)

    # The geometry the router and the label pass read: the card boxes, the
    # headers and the empty containers as walls, every obstacle named for
    # the collision report, and the headers a box cannot hold. The same
    # function scores a layout for `systemap place`.
    geo = geometry(model)
    boxes = geo.boxes

    # ---- ground: boundaries, then the bands -------------------------------
    # Boxes are integers in the model and floats once routed; the drawing
    # prints each as it was given, so an integer corner stays "16", never
    # "16.0", and the SVG is stable across the two.
    x: float
    y: float
    w: float
    h: float
    floor: list[str] = []
    obstacles = geo.obstacles
    blocks = geo.blocks
    headers = geo.headers
    collisions = list(geo.collisions)
    for box in model.containers:
        x, y, w, h = box.box
        stroke, fill = P.container(box.tone)
        if change_mode:
            stroke, fill = P["line"], P["bg"]
        _header, sub_lines, _unfit = container_header(box)
        floor.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
            + L(x + 13, y + 19, box.label, TEXT_PX, INK_3, "600", True, "start", ".13em")
            + "".join(
                L(x + 13, y + 33 + 12 * k, line, TEXT_PX, INK_3, "400", False, "start")
                for k, line in enumerate(sub_lines)
            )
        )

    zones: list[str] = []
    for i, region in enumerate(model.regions, start=1):
        x, y, w, h = region.box
        zones.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="none" '
            f'stroke="{P["region"]}" stroke-opacity=".28" stroke-width="1" '
            f'stroke-dasharray="3 4"/>'
            f'<g class="zone__h" data-zone="{esc(region.id)}">'
            f'<circle cx="{x + 17:.0f}" cy="{y + 16:.0f}" r="8.5" fill="{HALO}" '
            f'stroke="{P["region"]}" stroke-opacity=".5"/>'
            + L(x + 17, y + 20, str(i), TEXT_PX, P["region"], "600", True)
            + L(x + 31, y + 20, region.label, TEXT_PX, P["region"], "600", True, "start", ".13em")
            + "</g>"
        )

    # ---- flows ------------------------------------------------------------
    # Every flow is a Manhattan path through the gutters, routed by route.py
    # against the card boxes, the headers and the region boxes; the drawing
    # here only paints what the router returns and reports what it could
    # not do.
    actor_ids, region_of, region_boxes = geo.actors, geo.region_of, geo.region_boxes
    edges = [(src, dst) for src, dst, _art, _k in FLOWS]
    routes = route_all(edges, boxes, actor_ids, blocks, region_boxes, region_of, CANVAS)
    widths = {i: len(FLOWS[i][2]) * LABEL_CHAR_W + 6 for i in routes}
    # A collision names both labels: the one that could not be seated and
    # the one it landed on, each by its artifact and its edge.
    label_names = {
        i: f"label '{art}' ({src} -> {dst})" for i, (src, dst, art, _k) in enumerate(FLOWS)
    }
    seats = place_labels(
        routes,
        widths,
        LABEL_H,
        obstacles,
        CANVAS,
        names=label_names,
        cards=boxes,
        region_of=region_of,
    )

    flow_parts: list[str] = []
    label_parts: dict[int, str] = {}
    notes: list[str] = []
    label_boxes: list[dict[str, Any]] = []
    layers_of: dict[int, str] = {}
    paths: dict[int, list[list[float]]] = {}
    for i, (src, dst, artifact, kind) in enumerate(FLOWS):
        own = meaning.layer_for((src, dst), kind)
        layers_of[i] = own
        route = routes[i]
        paths[i] = [[round(x, 1), round(y, 1)] for x, y in route.points]
        seat = seats[i]
        lbox = seat.box
        label_boxes.append(
            {
                "from": src,
                "to": dst,
                "artifact": artifact,
                "box": [round(v, 1) for v in lbox],
                "segment": seat.segment,
            }
        )
        # An edge outside the reading is left out whole: no path, no label,
        # and nothing reported about a seat nobody sees.
        if shown is not None and i not in shown:
            continue
        if route.fallback:
            notes.append(f"{src} -> {dst}: {route.fallback}")
        art_hot = artifact in hot_artifacts
        colour, marker = LAYER_COLOUR[own], own
        if reading_hue:
            colour, marker = LAYER_COLOUR[reading_hue], reading_hue
        if art_hot:
            colour, marker = P["change"], "change"
        fid = f"{svg_id}-f{i}"
        ev = backed[(src, dst)]
        evidence_label = {evidence.OBSERVED: "source review recorded"}.get(ev.state, ev.state)
        # A declared edge is dashed: the map says so and the code does not.
        dashed = {
            evidence.DECLARED: ' stroke-dasharray="7 5"',
            evidence.STRUCTURAL: ' stroke-dasharray="3 4"',
        }.get(ev.state, "")
        flow_parts.append(
            f'<path id="{fid}" class="flow {kind}" data-edge="{i}" data-from="{esc(src)}" '
            f'data-to="{esc(dst)}" data-art="{esc(artifact)}" '
            f'data-kind="{esc(kind)}" data-layer="{own}" data-evidence="{ev.state}" '
            f'role="button" tabindex="0" aria-pressed="false" '
            f'aria-label="Examine {esc(artifact)}: {esc(src)} to {esc(dst)}, '
            f'{esc(own)}, {esc(evidence_label)}" '
            f'd="{path_d(route.points)}" '
            f'fill="none" stroke="{colour}" stroke-opacity="{0.95 if art_hot else 0.82}" '
            f'stroke-width="{1.8 if art_hot else 1.2}" stroke-linecap="round"{dashed} '
            f'marker-end="url(#{svg_id}-m-{marker})"/>'
        )
        if seat.cost > 0:
            # The line names what the seat touches and, from the router's
            # own seat counts, which fix applies: the gutter is full, or
            # the label is wider than any seat its path offers.
            fix = f"; {seat.fix}" if seat.fix else ""
            collisions.append(
                f"label collision: '{artifact}' ({src} -> {dst}) overlaps "
                f"{', '.join(seat.hits[:3])}{fix}"
            )
        lx, ly = lbox[0] + lbox[2] / 2, lbox[1] + LABEL_H - 3
        label_parts[i] = (
            f'<g class="flowlbl {kind}" data-edge="{i}" '
            f'data-from="{esc(src)}" data-to="{esc(dst)}" data-layer="{own}" '
            f'role="button" tabindex="-1" aria-pressed="false" '
            f'aria-label="Examine {esc(artifact)}: {esc(src)} to {esc(dst)}, '
            f'{esc(own)}, {esc(evidence_label)}">'
            f'<rect class="flowlbl__hit" x="{lbox[0]}" y="{lbox[1] - 6}" '
            f'width="{lbox[2]}" height="{LABEL_H + 12}" rx="3" fill="transparent"/>'
            + L(lx, ly, artifact, LABEL_PX, colour, "500", False, "middle", "", True)
            + "</g>"
        )

    # ---- cards ------------------------------------------------------------
    # Cards are written in reading order, row by row and left to right,
    # so Tab moves across the map the way the eye does, and the detail
    # lists them the same way; no two overlap, so paint order is free.
    detail: dict[str, Any] = {}
    cards: list[str] = []
    for c in sorted(COMPONENTS, key=lambda c: (boxes[c.id][1], boxes[c.id][0])):
        cid = c.id
        kind = c.kind
        state = states[cid]
        fill, stroke, state_label = P.state(state)
        if kind == "actor":
            fill, stroke = P.actor()
            state_label = "outside"
        moved, near = cid in changed, cid in adjacent
        tier = "moved" if moved else ("near" if near else "far")
        if change_mode and tier == "far":
            fill, stroke = GHOST_FILL, GHOST_STROKE
        if change_mode and moved:
            stroke = P["change"]
        elif change_mode and near:
            stroke = P["reach"]
        subject = marks_reading and cid in subjects
        quiet = marks_reading and not subject and cid not in reached
        if subject and layer:
            stroke = LAYER_COLOUR[layer]
        x, y, w, h = boxes[cid]
        state_class = state if kind != "actor" else "actor"
        plain = meaning.plain.get(cid, "")

        g: list[str] = [
            f'<g class="node {state_class}'
            f"{f' node--{tier}' if change_mode else ''}"
            f'{" subject" if subject else ""}{" quiet" if quiet else ""}" '
            f'data-id="{esc(cid)}" data-kind="{kind}" data-state="{state}" '
            f'data-region="{esc(c.home)}" '
            f'role="button" '
            f'tabindex="0" aria-label="{esc(cid)}, {esc(plain)}, {esc(state_label)}">'
        ]
        # The kind's mark, from the theme: an actor is dashed (outside the
        # code); an agent, a tool and a context card carry the mark the
        # theme's `marks` table gives their kind. Never a colour.
        mark = MARKS.get(kind, "")
        dashes = ' stroke-dasharray="4 3"' if kind == "actor" else ""
        if mark == "dotted":
            dashes = ' stroke-dasharray="1.5 2.5"'
        # A card that opens a map stands on a second card, offset down and
        # right: the mark that says there is a map inside, on the page and
        # in every figure. The panel names the map and links to it.
        if c.opens:
            g.append(
                f'<g class="node__map"><title>opens a map</title>'
                f'<rect x="{x + MAP_OFFSET}" y="{y + MAP_OFFSET}" width="{w}" height="{h}" '
                f'rx="{RADIUS}" fill="{fill}" stroke="{stroke}" stroke-width="1.1"{dashes}/></g>'
            )
        g.append(
            f'<rect class="node__box" x="{x}" y="{y}" width="{w}" height="{h}" '
            f'rx="{RADIUS}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{1.6 if change_mode and (moved or near) else 1.1}"'
            f"{dashes}/>"
            f'<rect class="node__ring" x="{x + 3}" y="{y + 3}" width="{w - 6}" '
            f'height="{h - 6}" rx="{RADIUS - 1}"/>'
            f'<rect class="node__selection" x="{x + 5}" y="{y + 7}" '
            f'width="1" height="{h - 14}" fill="{P["accent"]}"/>'
        )
        if mark == "ring":
            g.append(
                f'<rect class="node__mark" x="{x + 5}" y="{y + 5}" width="{w - 10}" '
                f'height="{h - 10}" rx="{RADIUS - 2}" fill="none" stroke="{stroke}" '
                f'stroke-opacity=".7" stroke-width="1"/>'
            )
        elif mark == "notch":
            g.append(
                f'<path class="node__mark" d="M{x + 3},{y + 3} h9 l-9,9 z" fill="{stroke}" '
                f'fill-opacity=".85"/>'
            )
        # The name and the plain word, within the card's budget; what does
        # not fit is reported for the check, never cut short.
        name_lines, plain_lines, unfit = card_text(kind, cid, plain)
        collisions += unfit
        for k, line in enumerate(name_lines):
            g.append(L(x + 10, y + 17 + NAME_LINE_H * k, line, NAME_PX, INK, "600", True, "start"))
        # A card with a note carries a dot in its top corner, on the map and
        # in every figure; the panel shows the note itself, and the dot's
        # title does when hovered.
        if c.note:
            g.append(
                f'<g class="node__note" aria-label="Note: {esc(c.note)}">'
                f"<title>Note: {esc(c.note)}</title>"
                f'<circle cx="{x + w - 6}" cy="{y + 6}" r="2.5" fill="{INK_3}"/></g>'
            )
        # A store is the same card with a rule under its head: flat convention
        # for a thing that holds rows rather than does work. A context card is
        # a store too: its rows enter an agent's window.
        ruled = kind in ("store", "context")
        if ruled:
            g.append(
                f'<line x1="{x + 1}" y1="{y + 23}" x2="{x + w - 1}" y2="{y + 23}" '
                f'stroke="{stroke}" stroke-opacity=".45" stroke-width="1"/>'
            )
        # The plain word under the code name, on the lines the card has
        # left under it.
        first = y + (36 if ruled else 32) + NAME_LINE_H * (len(name_lines) - 1)
        g.append(
            '<g data-layer="job">'
            + "".join(
                L(x + 10, first + k * 12, line, TEXT_PX, INK_3, "400", False, "start")
                for k, line in enumerate(plain_lines)
            )
            + "</g>"
        )

        delta = gained.get(cid, {}) if change_mode and moved else {}
        if delta:
            total = sum(delta.values()) or 1
            pos = 0.0
            for key in ("operations", "types", "refusals", "tests"):
                n = delta.get(key, 0)
                if not n:
                    continue
                seg = (w - 2) * n / total
                g.append(
                    f'<rect x="{x + 1 + pos:.1f}" y="{y + 1}" '
                    f'width="{seg:.1f}" height="2.5" fill="{P.delta(key)}"/>'
                )
                pos += seg
            g.append(
                f'<circle cx="{x + 12}" cy="{y - 1}" r="10" fill="{P["change"]}"/>'
                + L(x + 12, y + 3, f"+{sum(delta.values())}", TEXT_PX, HALO, "600", True)
            )
        elif change_mode and moved:
            g.append(
                L(
                    x + w / 2,
                    y - 5,
                    "IN REACH" if not changed_modules else "CHANGED INSIDE",
                    TEXT_PX,
                    P["change"],
                    "600",
                    True,
                    "middle",
                    ".1em",
                )
            )
        g.append("</g>")
        cards.append("".join(g))

        detail[cid] = {
            "id": cid,
            "kind": kind,
            "region": c.home,
            "plain": plain,
            "does": c.does,
            "state": state if kind != "actor" else "actor",
            "state_label": state_label if kind != "actor" else "outside",
            "lives": lives_in(list(c.implemented_by)),
            "modules": list(c.implemented_by),
            # The three fields the panel prints beside the plain word: the
            # one-line signature, the entry with the module that defines
            # it, and the caveat.
            "interface": c.interface,
            "entry": c.entry,
            "entry_module": entry_module(c, facts),
            "note": c.note,
            "calls_model": c.calls_model,
            "map": (
                opens.get(cid, {"name": cid, "href": "", "cards": 0, "preview": ""})
                if c.opens
                else None
            ),
            "moved": moved,
            "rules": model.rules_of(cid),
            "edges": [
                i
                for i, (a, b, _art, _k) in enumerate(FLOWS)
                if cid in (a, b) and (shown is None or i in shown)
            ],
        }

    edges_meta = []
    for i, (src, dst, artifact, kind) in enumerate(FLOWS):
        own = layers_of[i]
        ev = backed[(src, dst)]
        edges_meta.append(
            {
                "from": src,
                "to": dst,
                "art": artifact,
                "kind": kind,
                "layer": own,
                "out": meaning.verb_for((src, dst), own, True),
                "in": meaning.verb_for((src, dst), own, False),
                "say": meaning.relations.get((src, dst), ""),
                # The evidence state and the line the panel prints for it,
                # worded here so the page and a figure say the same thing.
                "evidence": ev.state,
                "mechanism": ev.mechanism,
                "import_present": ev.import_present,
                "shared_module": ev.shared,
                "source_refs": list(ev.source_refs),
                "unresolved_refs": list(ev.unresolved_refs),
                "claim_changed": ev.claim_changed,
                "review_digest": model.flows[i].review_digest,
                "evidence_says": ev.says,
            }
        )
    edge_index = {(a, b): i for i, (a, b, _art, _k) in enumerate(FLOWS)}
    journeys_meta = [
        {
            "id": j.id,
            "label": j.label,
            # Where the walk begins, as the facts name that way in, and
            # whether it is still a draft nobody has read against the code.
            "starts": j.starts,
            "drafted": j.drafted,
            "steps": [
                {
                    "acts": list(s.acts),
                    "measures": list(s.measures),
                    "edge": edge_index.get(s.edge, -1),
                    "say": s.say,
                }
                for s in j.steps
            ],
        }
        for j in meaning.journeys
    ]

    meta = {
        "_meta": {
            "layers": [
                {
                    "id": lay.id,
                    "label": lay.label,
                    "question": lay.question,
                    "sub": lay.sub,
                    "colour": LAYER_COLOUR[lay.id],
                    "tag": P.tag(lay.id),
                    "derived": lay.id in DERIVED_LAYERS,
                }
                for lay in LAYERS
            ],
            "readings": {
                lid: {"edges": edges, "subjects": subjects}
                for lid, (edges, subjects) in readings.items()
            },
            "reading": layer,
            "edges": edges_meta,
            "journeys": journeys_meta,
            "regions": [
                {
                    "id": r.id,
                    "label": r.label,
                    "box": [float(v) for v in r.box],
                    "ids": [c.id for c in COMPONENTS if c.region == r.id],
                }
                for r in model.regions
            ],
            "rules": [
                {"n": inv.n, "text": inv.text, "ids": sorted(inv.governs)}
                for inv in sorted(model.invariants, key=lambda i: i.n)
            ],
            "kinds": list(model.flow_kinds),
            "states": {s: sum(1 for v in states.values() if v == s) for s in states.values()},
            "evidence": {
                state: sum(1 for ev in backed.values() if ev.state == state)
                for state in evidence.STATES
            },
            "collisions": collisions,
            "notes": notes,
            "labels": label_boxes,
            "headers": headers,
            "cards": {cid: list(box) for cid, box in boxes.items()},
            "paths": paths,
        }
    }

    pad = 26
    width, height = CANVAS
    # The drawing's title is the reading's question when it draws one
    # reading, so an image of the control flow says what it answers.
    if layer:
        lay = next(lay for lay in LAYERS if lay.id == layer)
        title = f"{lay.label}: {lay.question}" if lay.question else lay.label
        what = (
            f"{title} All component cards and only the flows of the {lay.label} layer. "
            "Each flow label gives its artifact."
        )
    else:
        title = "System map"
        what = (
            "System map. Fill shows source state. Flow labels give artifacts. Line color shows "
            "the layer."
        )
    p: list[str] = [
        f'<svg id="{svg_id}" class="scene" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{-pad} {-pad} {width + pad * 2} {height + pad * 2}" '
        f'preserveAspectRatio="xMidYMid meet" tabindex="0" role="application" '
        f'aria-label="{esc(what)}">'
        f"<title>{esc(title)}</title>",
        _defs(svg_id, P),
        _svg_style(svg_id, P),
    ]
    # Everything drawn sits in one group the script pans and zooms with a
    # transform; the viewBox never changes, so every coordinate read back from
    # the figure (card boxes, edge paths) stays in drawing units.
    p.append('<g class="view">')
    p.extend(floor)
    p.append(f'<g data-layer="zones">{"".join(zones)}</g>')
    p.append(f'<g data-layer="flow">{"".join(flow_parts)}</g>')
    p.extend(cards)
    p.append(
        '<g data-layer="flow">' + "".join(label_parts[i] for i in sorted(label_parts)) + "</g>"
    )
    p.append('<g data-layer="tags"></g>')
    p.append("</g>")
    # Text classes are known only once everything is drawn, so their style
    # block goes in last; the renderer does not care where a style sits.
    p.append(text_css())
    p.append("</svg>")
    return "".join(p), json.dumps({**detail, **meta}, ensure_ascii=False)
