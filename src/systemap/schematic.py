"""Render the map as an SVG figure with inspector data.

A card shows one component, its identifier and its plain text name.
Dashed card borders identify actors outside the source code. Flow lines
show artifacts and use the color of their flow kind. Selection shows connections
and shows their explanation in the inspector. Nodes carry `data-id`
and kind values. Flow lines carry artifact labels and `data-layer`.
The groups of the drawing use `data-part`, not `data-layer`. Thus a layer ID cannot
have the same attribute value as a group.

Flow evidence states come from evidence.py. `observed` means that source
references resolve and the source review digest agrees with the claim.
The reader text for `observed` is "current source review".
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

from systemap import assurance, evidence, flow_ids
from systemap.model import (
    DERIVED_LAYERS,
    Meaning,
    Model,
    Step,
    all_layers,
    build_state,
    entry_module,
    reading,
)
from systemap.route import Placed, Route, path_d, place_labels, route_all
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
    RADIUS,
    card_lines,
    card_sizes,
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
from systemap.schematic_change import (
    change_card,
    change_defs,
    change_flow,
    change_marks,
    change_meta,
    change_style,
    change_tag,
)
from systemap.schematic_script import interactive_script as interactive_script
from systemap.schematic_script import line_safe as line_safe
from systemap.schematic_style import _defs, _svg_style, layer_marker
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
    tests_only: set[str] | None = None,
) -> tuple[str, str]:
    """Give the SVG figure and detail JSON.

    `changed` identifies changed components or components in a plan.
    `changed_modules` identifies changed source modules. `hot_artifacts`
    identifies flow labels whose source module changed its public surface.
    `tests_only` identifies changed components with changed tests and no
    changed source. The change detector supplies these values. A change map
    with changed modules or a `tests_only` set shows a revision comparison.
    Without them, it shows the components of a plan. `gained` gives the
    counts of new public names and tests that the detail JSON records.

    `layer` selects the flows that `model.reading` supplies. All cards
    stay. Flow lines keep the color of their kind in each layer. The subject
    cards of a layer use the layer color for their borders. A derived layer
    has a neutral color. Other unconnected cards have lower
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

    T = t
    P = Palette(t, variables)
    COMPONENTS = model.components
    FLOWS = [(f.src, f.dst, f.artifact, f.kind) for f in model.flows]
    CANVAS = model.canvas
    INK, INK_3 = P["ink"], P["ink_3"]
    # Text halos and the region number ring have the map color, so a label
    # hides the lines under it and shows the map ground.
    HALO = P["map"]
    LAYER_COLOUR: dict[str, str] = {lid: P.layer(lid) for lid in T["layers"]}
    MARKS: dict[str, str] = T.get("marks") or {}
    LAYERS = all_layers(model, meaning)
    # Which edges and which cards each reading shows, decided once here and
    # read by the page's script out of the detail JSON.
    readings = {lay.id: reading(model, meaning, lay.id) for lay in LAYERS}
    if layer and layer not in readings:
        raise ValueError(f"unknown layer id: {layer}")
    shown: set[int] | None = set(readings[layer][0]) if layer else None
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
    # The level and the freshness of each claim, for the inspector (`assurance`).
    claims = assurance.of_model(model, meaning, facts)
    marks = change_marks(model, backed, mode, changed, adjacent, tests_only, changed_modules)

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
    # The ground is neutral and has the same colors in every view: a container
    # is a 1 px solid frame (`line_2`) with no fill, and a region is a 1 px
    # dashed `region` border with a number ring. The strokes keep their screen
    # width at each zoom, as the borders of the design boards do.
    fixed = ' vector-effect="non-scaling-stroke"'
    for box in model.containers:
        x, y, w, h = box.box
        stroke, fill = P.container(box.tone)
        _header, sub_lines, _unfit = container_header(box)
        # The header text is one group, so the page can scale it about the
        # container corner when the map is small (`data-at`: x, y and width).
        floor.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1"{fixed}/>'
            f'<g class="box__h" data-at="{x} {y} {w}">'
            + L(x + 13, y + 19, box.label, TEXT_PX, INK_3, "600", True, "start", ".08em")
            + "".join(
                L(x + 13, y + 33 + 12 * k, line, TEXT_PX, INK_3, "400", False, "start")
                for k, line in enumerate(sub_lines)
            )
            + "</g>"
        )

    # A region header grows about the middle of its number ring (`data-at`).
    zones: list[str] = []
    for i, region in enumerate(model.regions, start=1):
        x, y, w, h = region.box
        zones.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="none" '
            f'stroke="{P["region"]}" stroke-width="1" stroke-dasharray="3 3"{fixed}/>'
            f'<g class="zone__h" data-zone="{esc(region.id)}" data-at="{x} {y + 16} {w}">'
            f'<circle cx="{x + 17:.0f}" cy="{y + 16:.0f}" r="9" fill="{HALO}" '
            f'stroke="{P["region"]}" stroke-width="1"{fixed}/>'
            + L(x + 17, y + 20, str(i), TEXT_PX, P["ink_2"], "600", True)
            + L(x + 31, y + 20, region.label, TEXT_PX, P["ink_2"], "600", True, "start", ".08em")
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
    label_names = {i: f"label '{f.artifact}' ({f.name})" for i, f in enumerate(model.flows)}
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
        own = meaning.layer_for(model.flows[i], kind)
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
            notes.append(f"{model.flows[i].name}: {route.fallback}")
        # A line keeps the color of its kind in every layer. A derived layer
        # (structure, system, agents) selects lines and does not color them.
        colour, marker = LAYER_COLOUR[own], layer_marker(own)
        look = change_flow(P, marks, i, colour, marker, artifact in hot_artifacts)
        fid = f"{svg_id}-f{i}"
        ev = backed.of(model.flows[i])
        evidence_label = {evidence.OBSERVED: evidence.READER_TEXT[evidence.OBSERVED]}.get(
            ev.state, ev.state
        )
        # A declared edge is dashed: the map says so and the code does not.
        dashed = {
            evidence.DECLARED: ' stroke-dasharray="7 5"',
            evidence.STRUCTURAL: ' stroke-dasharray="3 4"',
        }.get(ev.state, "")
        flow_parts.append(
            f'<path id="{fid}" class="flow" data-edge="{i}" data-from="{esc(src)}" '
            f'data-to="{esc(dst)}" data-art="{esc(artifact)}" '
            f'data-kind="{esc(kind)}" data-layer="{esc(own)}" data-evidence="{ev.state}" '
            f'role="button" tabindex="0" aria-pressed="false" '
            f'aria-label="Examine {esc(artifact)}: {esc(src)} to {esc(dst)}, '
            f'{esc(own)}, {esc(evidence_label)}" '
            f'd="{path_d(route.points)}" '
            f'fill="none" stroke="{look.stroke}"{look.attrs} '
            f'stroke-width="{look.width}" stroke-linecap="round"{dashed} '
            f'marker-end="url(#{svg_id}-m-{look.marker})"/>'
        )
        if seat.cost > 0:
            # The line names what the seat touches and, from the router's
            # own seat counts, which fix applies: the gutter is full, or
            # the label is wider than any seat its path offers.
            fix = f"; {seat.fix}" if seat.fix else ""
            collisions.append(
                f"label collision: '{artifact}' ({model.flows[i].name}) overlaps "
                f"{', '.join(seat.hits[:3])}{fix}"
            )
        lx, ly = lbox[0] + lbox[2] / 2, lbox[1] + LABEL_H - 3
        label_parts[i] = (
            f'<g class="flowlbl" data-edge="{i}" '
            f'data-from="{esc(src)}" data-to="{esc(dst)}" data-layer="{esc(own)}"'
            f"{look.shown} "
            f'role="button" tabindex="-1" aria-pressed="false" '
            f'aria-label="Examine {esc(artifact)}: {esc(src)} to {esc(dst)}, '
            f'{esc(own)}, {esc(evidence_label)}">'
            f'<rect class="flowlbl__hit" x="{lbox[0]}" y="{lbox[1] - 6}" '
            f'width="{lbox[2]}" height="{LABEL_H + 12}" rx="3" fill="transparent"/>'
            + L(lx, ly, artifact, LABEL_PX, look.label, "500", False, "middle", "", True)
            + "</g>"
        )

    # ---- cards ------------------------------------------------------------
    # Cards are written in reading order, row by row and left to right,
    # so Tab moves across the map the way the eye does, and the detail
    # lists them the same way; no two overlap, so paint order is free.
    detail: dict[str, Any] = {}
    cards: list[str] = []
    sizes = card_sizes([(c.kind, c.id, meaning.plain.get(c.id, "")) for c in COMPONENTS])
    for c in sorted(COMPONENTS, key=lambda c: (boxes[c.id][1], boxes[c.id][0])):
        cid = c.id
        kind = c.kind
        state = states[cid]
        fill, stroke, state_label = P.state(state)
        if kind == "actor":
            fill, stroke = P.actor()
            state_label = "outside"
        moved = cid in changed
        subject = marks_reading and cid in subjects
        quiet = marks_reading and not subject and cid not in reached
        if subject and layer:
            stroke = LAYER_COLOUR[layer]
        x, y, w, h = boxes[cid]
        state_class = state if kind != "actor" else "actor"
        plain = meaning.plain.get(cid, "")

        # The kind's mark, from the theme: an actor is dashed (outside the
        # code); an agent, a tool and a context card carry the mark the
        # theme's `marks` table gives their kind. Never a colour.
        mark = MARKS.get(kind, "")
        dashes = ' stroke-dasharray="4 3"' if kind == "actor" else ""
        if mark == "dotted":
            dashes = ' stroke-dasharray="1.5 2.5"'
        change = marks.cards.get(cid, "")
        marked = change_card(P, change, stroke, dashes, state_label)
        g: list[str] = [
            f'<g class="node {state_class}'
            f'{" subject" if subject else ""}{" quiet" if quiet else ""}" '
            f'data-id="{esc(cid)}" data-kind="{esc(kind)}" data-state="{state}" '
            f'data-region="{esc(c.home)}"{marked.attrs} '
            f'role="button" '
            f'tabindex="0" aria-label="{esc(cid)}, {esc(plain)}, {esc(marked.label)}">'
        ]
        # A card that opens a map stands on a second card, offset down and
        # right: the mark that says there is a map inside, on the page and
        # in every figure. The panel names the map and links to it.
        if c.opens:
            g.append(
                f'<g class="node__map" aria-label="Opens a map"><title>opens a map</title>'
                f'<rect x="{x + MAP_OFFSET}" y="{y + MAP_OFFSET}" width="{w}" height="{h}" '
                f'rx="{RADIUS}" fill="{fill}" stroke="{stroke}" stroke-width="1.1"{dashes}/></g>'
            )
        g.append(
            f'<rect class="node__box" x="{x}" y="{y}" width="{w}" height="{h}" '
            f'rx="{RADIUS}" fill="{fill}" stroke="{marked.stroke}" '
            f'stroke-width="{marked.width}"'
            f"{marked.dashes}/>"
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
        collisions += card_text(kind, cid, plain)[2]
        name_rows, plain_rows = card_lines(kind, cid, plain, sizes) or ([], [])
        for dy, line in name_rows:
            g.append(L(x + 10, y + dy, line, sizes[0], INK, "600", True, "start"))
        # A card with a note carries a dot in its top corner, on the map and
        # in every figure; the panel shows the note itself, and a figure file
        # shows it as the dot's title. The page legend names the dot.
        if c.note:
            g.append(
                f'<g class="node__note" aria-label="Note: {esc(c.note)}">'
                f"<title>Note: {esc(c.note)}</title>"
                f'<circle cx="{x + w - 6}" cy="{y + 6}" r="2.5" fill="{INK_3}"/></g>'
            )
        # A store is the same card with a double base line: flat convention
        # for a thing that holds rows rather than does work. A context card is
        # a store too: its rows enter an agent's window.
        ruled = kind in ("store", "context")
        if ruled:
            g.append(
                f'<line class="node__base" x1="{x + 1}" y1="{y + h - 3}" x2="{x + w - 1}" '
                f'y2="{y + h - 3}" stroke="{stroke}" stroke-width="1"/>'
            )
        # The plain word under the code name. The name and the plain word
        # are centred in the card.
        g.append(
            '<g data-part="job">'
            + "".join(
                L(x + 10 + inset, y + dy, line, sizes[1], P["ink_2"], "400", False, "start")
                for dy, inset, line in plain_rows
            )
            + "</g>"
        )

        g.append(change_tag(P, L, change, (x, y, w, h)))
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
            "lives": lives_in(list(c.implemented_by), facts.get("components", {})),
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
            "gained": gained.get(cid, {}),
            "rules": model.rules_of(cid),
            **assurance.panel_field(claims, assurance.COMPONENT, cid),
            "edges": [
                i
                for i, (a, b, _art, _k) in enumerate(FLOWS)
                if cid in (a, b) and (shown is None or i in shown)
            ],
        }

    edges_meta = []
    for i, (src, dst, artifact, kind) in enumerate(FLOWS):
        own = layers_of[i]
        flow = model.flows[i]
        ev = backed.of(flow)
        edges_meta.append(
            {
                # The flow identifier: the id, or SRC->DST for a flow without an id.
                "id": flow.key,
                "from": src,
                "to": dst,
                "art": artifact,
                "kind": kind,
                "layer": own,
                "out": meaning.verb_for(flow, own, True),
                "in": meaning.verb_for(flow, own, False),
                "say": meaning.relation(flow),
                # The evidence state and the line the panel prints for it,
                # worded here so the page and a figure say the same thing.
                "evidence": ev.state,
                "mechanism": ev.mechanism,
                "import_present": ev.import_present,
                "shared_module": ev.shared,
                "source_refs": list(ev.source_refs),
                "unresolved_refs": list(ev.unresolved_refs),
                "claim_changed": ev.claim_changed,
                "review_digest": flow.review_digest,
                "evidence_says": ev.says,
                **assurance.panel_field(claims, assurance.FLOW, flow.key),
            }
        )
    edge_index = {f.key: i for i, f in enumerate(model.flows)}
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
                    "edge": _step_index(s, model, edge_index),
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
            "assurance_text": assurance.texts(claims),
            "rules": [
                {
                    "n": inv.n,
                    "text": inv.text,
                    "ids": sorted(inv.governs),
                    **assurance.panel_field(claims, assurance.INVARIANT, str(inv.n)),
                }
                for inv in sorted(model.invariants, key=lambda i: i.n)
            ],
            "kinds": list(model.flow_kinds),
            "states": {s: sum(1 for v in states.values() if v == s) for s in states.values()},
            "evidence": {
                state: sum(1 for ev in backed.values() if ev.state == state)
                for state in evidence.STATES
            },
            **change_meta(marks),
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
            "the flow kind."
        )
    p: list[str] = [
        f'<svg id="{svg_id}" class="scene" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{-pad} {-pad} {width + pad * 2} {height + pad * 2}" '
        f"{view_data(model, boxes, routes, seats, sizes)}"
        f'preserveAspectRatio="xMidYMid meet" tabindex="0" role="application" '
        f'aria-label="{esc(what)}">'
        f"<title>{esc(title)}</title>",
        _defs(svg_id, P) + change_defs(svg_id, P, marks),
        _svg_style(svg_id, P) + change_style(svg_id, marks),
    ]
    # Everything drawn sits in one group the script pans and zooms with a
    # transform; the viewBox never changes, so every coordinate read back from
    # the figure (card boxes, edge paths) stays in drawing units.
    p.append('<g class="view">')
    p.extend(floor)
    p.append(f'<g data-part="zones">{"".join(zones)}</g>')
    p.append(f'<g data-part="flow">{"".join(flow_parts)}</g>')
    p.extend(cards)
    p.append('<g data-part="flow">' + "".join(label_parts[i] for i in sorted(label_parts)) + "</g>")
    p.append('<g data-part="tags"></g>')
    p.append("</g>")
    # Text classes are known only once everything is drawn, so their style
    # block goes in last; the renderer does not care where a style sits.
    p.append(text_css())
    p.append("</svg>")
    return "".join(p), json.dumps({**detail, **meta}, ensure_ascii=False)


def view_data(
    model: Model,
    boxes: Mapping[str, tuple[float, float, float, float]],
    routes: Mapping[int, Route],
    seats: Mapping[int, Placed],
    sizes: tuple[float, float],
) -> str:
    """Give the SVG attributes that the page camera and the label sizes use.

    `data-fit` gives the drawn bounds: the containers, the regions, the cards,
    the flow paths and the label boxes. Fit shows these bounds, not the empty
    margin of the viewBox. `data-grow` gives the largest scale of a flow label,
    a region label and a container label: the card description size divided by
    the label size. `data-read` gives the smallest zoom at which card names
    show at 12 px and card descriptions at 11 px. The values do not change
    the layout."""
    rects: list[tuple[float, float, float, float]] = [c.box for c in model.containers]
    rects += [r.box for r in model.regions]
    rects += [(x, y, w + MAP_OFFSET, h + MAP_OFFSET) for x, y, w, h in boxes.values()]
    rects += [seat.box for seat in seats.values()]
    rects += [(x, y, 0.0, 0.0) for route in routes.values() for x, y in route.points]
    if not rects:
        return ""
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[0] + r[2] for r in rects)
    y1 = max(r[1] + r[3] for r in rects)
    grow = max(1.0, sizes[1] / LABEL_PX)
    read = max(12 / sizes[0], 11 / sizes[1])
    return (
        f'data-fit="{x0:g} {y0:g} {round(x1 - x0, 1):g} {round(y1 - y0, 1):g}" '
        f'data-grow="{grow:.3f}" data-read="{read:.3f}" '
    )


def _step_index(step: Step, model: Model, edge_index: dict[str, int]) -> int:
    """Give the index of the flow of a sequence step, or -1 if the step names no one flow."""
    found = flow_ids.step_flow(step, model.flows)[0]
    return -1 if found is None else edge_index[found.key]
