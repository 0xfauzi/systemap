"""The figure generator uses the same source facts and map renderer as the page.

A system figure shows the map. A change figure uses explicit Git refs or component IDs
from a plan. A layer selection shows that layer and all components. An interactive
figure includes component selection, a flow list, and zoom controls without external
libraries.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from systemap import change as change_mod
from systemap import nest
from systemap.config import Config, ConfigError, Figure
from systemap.model import Layer, Meaning, Model, all_layers
from systemap.schematic import interactive_script, kind_rows, layer_rows, legend_rows, panel_css
from systemap.schematic import render as render_schematic

GENERATOR = "systemap"


class FigureError(Exception):
    """The program cannot make the requested figure. The message gives the reason."""


def bare_svg(svg: str, t: dict[str, Any]) -> str:
    """This function gives the SVG drawing with a background rectangle for use as an image.

    It keeps the drawing geometry, style, and text size.
    """
    match = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"', svg)
    if match is None:
        return svg
    x, y, w, h = match.groups()
    end = svg.index(">") + 1
    ground = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{t["bg"]}"/>'
    return svg[:end] + ground + svg[end:] + "\n"


MARK_STYLE = {
    "ring": "box-shadow:inset 0 0 0 1.5px {bg},inset 0 0 0 2.5px {ink}",
    "notch": "background-image:linear-gradient(135deg,{ink} 0 38%,transparent 38%)",
    "dotted": "border-style:dotted",
    # A card that opens a map stands on a second card.
    "map": "box-shadow:2px 2px 0 0 {ink}",
}


def figure(
    t: dict[str, Any],
    model: Model,
    meaning: Meaning,
    svg: str,
    caption: str,
    legend: list[tuple[str, str, str]],
    svg_id: str,
    detail_json: str | None,
    layer: str = "",
) -> str:
    """This function makes the figure element. Detail JSON permits interaction; a layer ID
    selects the legend contents.
    """
    swatches = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:.4em;'
        f'margin-right:1.1em;white-space:nowrap">'
        f'<span style="width:.75em;height:.75em;border-radius:2px;'
        f"background:{fill};border:1px solid {stroke};"
        f'display:inline-block"></span>{label}</span>'
        for fill, stroke, label in legend
    )
    swatches += "".join(
        f'<span style="display:inline-flex;align-items:center;gap:.4em;'
        f'margin-right:1.1em;white-space:nowrap">'
        f'<span style="width:.75em;height:.75em;border-radius:2px;'
        f"background:{t['state']['built'][0]};border:1px solid {t['state']['built'][1]};"
        f"{MARK_STYLE[mark].format(bg=t['state']['built'][0], ink=t['state']['built'][1])};"
        f'display:inline-block"></span>{kind}</span>'
        for kind, mark in kind_rows(t, model)
    )
    if model.opening:
        swatches += (
            '<span style="display:inline-flex;align-items:center;gap:.4em;margin-right:'
            '1.1em;white-space:nowrap"><span style="width:.75em;height:.75em;border-rad'
            "ius:2px;background:"
            f"{t['state']['built'][0]}"
            ";border:1px solid "
            f"{t['state']['built'][1]}"
            ";"
            f"{MARK_STYLE['map'].format(bg=t['state']['built'][0], ink=t['state']['built'][1])}"
            ';display:inline-block"></span>nested map</span>'
        )
    swatches += "".join(
        f'<span style="display:inline-flex;align-items:center;gap:.4em;'
        f'margin-right:1.1em;white-space:nowrap">'
        f'<span style="width:1em;height:3px;border-radius:2px;background:{colour};'
        f'display:inline-block"></span>{label}</span>'
        for lid, colour, label in layer_rows(t, model, meaning)
        if not layer or lid == layer
    )
    if layer != "structure":
        swatches += (
            '<span style="display:inline-flex;align-items:center;gap:.4em;margin-right:'
            '1.1em;white-space:nowrap"><span style="width:1em;height:0;border-top:2px '
            "dashed "
            f"{t['ink_3']}"
            ';display:inline-block"></span>flow without source review</span>'
        )
    controls = ""
    panel = ""
    script = ""
    hint = ""
    if detail_json is not None:
        panel_id = f"{svg_id}-panel"
        btn = (
            'style="font:inherit;color:inherit;background:none;border:1px solid '
            f"{t['line']};border-radius:4px;min-height:24px;min-width:2.2em;"
            'padding:0 .5em;cursor:pointer"'
        )
        controls = (
            '<span style="display:inline-flex;gap:.3em;margin-left:1em;white-space:nowr'
            'ap"><button type="button" data-zoom="fit" data-for="'
            f"{svg_id}"
            '" '
            f"{btn}"
            '>Show all</button><button type="button" data-zoom="actual" data-for="'
            f"{svg_id}"
            '" '
            f"{btn}"
            '>100%</button><button type="button" data-zoom="in" data-for="'
            f"{svg_id}"
            '" '
            f"{btn}"
            ' aria-label="Increase zoom">+</button><button type="button" '
            'data-zoom="out" data-for="'
            f"{svg_id}"
            '" '
            f"{btn}"
            ' aria-label="Decrease zoom">-</button></span>'
        )
        hint = (
            '<p style="margin:.4em 0 0;font-size:.76rem;color:'
            f"{t['ink_3']}"
            '">Use the mouse wheel to change zoom. Drag the map to change its '
            "position. Click a component to show it. Use Escape to show the previous "
            "view.</p>"
        )
        panel = (
            f'<div id="{panel_id}" class="systemap-panel" style="margin-top:.9em" '
            f'aria-live="polite"></div>'
        )
        script = (
            f"<style>{panel_css(t)}</style>"
            + interactive_script(t, svg_id, panel_id, detail_json)
            + "<script>(function(){"
            f'var svg = document.getElementById("{svg_id}");'
            "if(!svg || !svg.systemap){ return; }"
            f"Array.prototype.slice.call(document.querySelectorAll('[data-for=\"{svg_id}\"]'))"
            ".forEach(function(b){ b.addEventListener('click', function(){"
            "var z = b.dataset.zoom, v = svg.systemap.view;"
            "if(z === 'fit'){ v.fit(); } else if(z === 'actual'){ v.actual(); }"
            "else { v.zoomBy(z === 'in' ? 1.25 : 1 / 1.25); } }); });"
            "document.addEventListener('keydown', function(e){"
            "if(e.key === 'Escape'){ svg.systemap.clear(); svg.systemap.view.back(); } });"
            "})();</script>"
        )
    # Legend labels and node names are generated, so a prose linter should
    # skip the figure rather than judge text nobody wrote by hand. The figure
    # opens at Fit, the whole map across the column; text is drawn at 11px
    # and zoom brings it back to size.
    return (
        f'<figure data-generated="systemap" '
        f'style="margin:2.4em 0;padding:1.1em 1.1em .9em;'
        f"background:{t['bg']};border:1px solid {t['line']};border-radius:8px;"
        f'overflow-x:auto;color:{t["ink_2"]};font-family:{t["font_ui"]}">'
        f"{svg}{hint}"
        f'<div style="margin-top:.9em;font-size:.78rem;line-height:1.9;'
        f'color:{t["ink_3"]}">{swatches}{controls}</div>'
        f"{panel}"
        f'<figcaption style="margin-top:.7em;font-size:.82rem;line-height:1.5;'
        f'color:{t["ink_3"]}">{caption}</figcaption>'
        f"{script}"
        f"</figure>\n"
    )


def make(
    cfg: Config,
    model: Model,
    meaning: Meaning,
    t: dict[str, Any],
    facts: dict[str, Any],
    *,
    mode: str = "",
    components: tuple[str, ...] = (),
    base: str = "",
    head: str = "HEAD",
    caption: str = "",
    svg_id: str = "lessonmap",
    interactive: bool = False,
    bare: bool = False,
    layer: str = "",
    map_id: str = "",
    opens: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[str, list[str]]:
    """This function gives figure HTML and label or header diagnostics.

    An empty mode selects change if a base ref or component IDs are given; otherwise, it
    selects system. Unknown component IDs give ConfigError. An empty Git range gives
    FigureError. The bare option gives SVG only. The layer and map_id arguments select a
    layer and nested map.
    """
    page_url = f"{cfg.out_dir}/{map_id}/index.html" if map_id else f"{cfg.out_dir}/index.html"
    facts_url = f"{cfg.out_dir}/{cfg.facts_file}"
    inside = f"Inside {map_id.rpartition('/')[2]}: " if map_id else ""
    mode = mode or ("change" if (base or components) else "system")
    known = model.ids
    reading = _reading(model, meaning, layer)

    changed: set[str] = set()
    changed_modules: set[str] = set()
    adjacent: set[str] = set()
    gained: dict[str, dict[str, int]] = {}
    hot: set[str] = set()
    legend_mode = "system"

    if mode == "change" and components:
        ids = [s.strip() for s in components if s.strip()]
        unknown = sorted(set(ids) - known)
        if unknown:
            raise ConfigError(f"unknown component ids: {', '.join(unknown)}")
        changed = set(ids)
        legend_mode = "reach"
        caption = caption or (
            f"{inside}"
            "The system with "
            f"{len(changed)}"
            " components in the plan. This figure shows the planned scope. It does not "
            "show a diff. The generator is <code>"
            f"{GENERATOR}"
            "</code>, which also makes the map at <code>"
            f"{page_url}"
            "</code>."
        )
    elif mode == "change":
        if not base:
            raise FigureError("A change figure must have a base ref.")
        ch = change_mod.compute(cfg, model, base, facts, head)
        if not ch["has_change"]:
            raise FigureError(
                f"No change occurs between {base} and {head}. No change figure is necessary."
            )
        changed = ch["direct"]
        changed_modules = ch["modules"]
        adjacent = ch["adjacent"]
        gained = {k: v["gained"] for k, v in ch["per_component"].items()}
        hot = ch["flow_artifacts"]
        legend_mode = "change"
        caption = caption or (
            f"{inside}"
            "This figure shows the system with this change. The generator is <code>"
            f"{GENERATOR}"
            "</code>, which also makes the map at <code>"
            f"{page_url}"
            "</code>."
        )
    elif reading is not None:
        sub = reading.sub[:1].upper() + reading.sub[1:] if reading.sub else ""
        caption = caption or (
            f"{inside}"
            f"{reading.label}"
            ": "
            f"{reading.question}"
            " "
            f"{(sub + '. ' if sub else '')}"
            "This figure shows one layer. The page at <code>"
            f"{page_url}"
            "</code> has all layers. The generator is <code>"
            f"{GENERATOR}"
            "</code>. The source facts are at <code>"
            f"{facts_url}"
            "</code>. Each component shows source code at this snapshot."
        )
    else:
        caption = caption or (
            f"{inside}"
            "This figure shows the system map. The generator is <code>"
            f"{GENERATOR}"
            "</code>. The source facts are at <code>"
            f"{facts_url}"
            "</code>. Each component shows source code at this snapshot. Click a "
            "component to read its description and connections."
        )

    svg, detail = render_schematic(
        model,
        meaning,
        t,
        facts,
        changed=changed,
        changed_modules=changed_modules,
        adjacent=adjacent,
        mode=mode,
        svg_id=svg_id,
        gained=gained,
        hot_artifacts=hot,
        layer=layer,
        observed_by=cfg.observed_by,
        opens=opens,
    )
    meta = json.loads(detail).get("_meta", {})
    collisions: list[str] = list(meta.get("collisions", []))
    if bare:
        return bare_svg(svg, t), collisions

    if legend_mode == "reach":
        rows = [
            (legend_rows(t, "change")[0][0], t["change"], "in the plan"),
            (t["ghost"][0], t["ghost"][1], "not in the plan"),
        ]
    else:
        rows = legend_rows(t, legend_mode)
    out = figure(
        t, model, meaning, svg, caption, rows, svg_id, detail if interactive else None, layer
    )
    return out, collisions


def _reading(model: Model, meaning: Meaning, layer: str) -> Layer | None:
    """This function selects a page layer, or all layers if no layer ID is given.

    An unknown ID gives a diagnostic with the available layer IDs.
    """
    if not layer:
        return None
    layers = all_layers(model, meaning)
    for lay in layers:
        if lay.id == layer:
            return lay
    raise ConfigError(
        f"unknown layer id: {layer}. The page layer IDs are {', '.join(lay.id for lay in layers)}"
    )


def configured(
    cfg: Config,
    tree: nest.Tree,
    m: nest.Map,
    facts: dict[str, Any],
    fig: Figure,
) -> tuple[str, list[str]]:
    """This function makes a figure from a configuration entry for the selected map.

    Refresh writes the result and check compares it. An out path with .svg selects SVG
    only.
    """
    return make(
        cfg,
        m.model,
        m.meaning,
        m.theme,
        facts,
        mode="change" if fig.mode == "reach" else "system",
        components=fig.components,
        caption=fig.caption,
        svg_id=fig.svg_id,
        interactive=fig.interactive,
        bare=fig.out.endswith(".svg"),
        layer=fig.layer,
        map_id=m.id,
        opens=nest.opens(tree, m, links=False),
    )
