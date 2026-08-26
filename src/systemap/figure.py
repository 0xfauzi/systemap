"""Emit a figure of the system for embedding in a lesson or a document.

A lesson needs a picture of where a change landed, or of what a plan will
reach. The map already draws that picture. Drawing a second one by hand
would produce a rival diagram of the same system, and the hand-drawn one
would drift the moment a component moved. So this runs the same generator on
the same data and wraps the result in a figure.

The picture is therefore a citation, not a restatement: it is regenerated
from the facts every time, and it cannot disagree with the map it links to.

Three sources for what is marked:

    base and head refs    what a git range changed (mode change)
    component ids         what a plan reaches, no git consulted (mode change)
    mode system           nothing marked: the plain system figure

And one reading or all of them: `layer` draws only the edges the page's
layer switch shows for that layer (its own filter, `model.reading`), with
every card, the legend reduced to that layer and the layer's question as
the title. Structure has no edges at all; the whole map with every layer
at once is too many arrows for a document, and a reading is the page's
own answer to that.

An interactive figure carries the map's focus interaction as a
self-contained fragment: clicking a component dims the rest, thickens its
edges in their layer colours with their labels, tags each neighbour with the
verb that relates it, frames the component and its neighbours, and draws
the relationship wheel in a panel under the figure. The figure opens at Fit
and pans and zooms like the map page (wheel, pinch, drag, Fit / 100% / +
/ -, Escape to go back). Plain DOM, no libraries.
"""

from __future__ import annotations

import json
import re
from typing import Any

from systemap import change as change_mod
from systemap.config import Config, ConfigError, Figure
from systemap.model import Layer, Meaning, Model, all_layers
from systemap.schematic import interactive_script, kind_rows, layer_rows, legend_rows, panel_css
from systemap.schematic import render as render_schematic

GENERATOR = "systemap"


class FigureError(Exception):
    """The figure cannot be drawn as asked; the message says why."""


def bare_svg(svg: str, t: dict[str, Any]) -> str:
    """The drawing alone, on its ground, for embedding as an image.

    The scene draws no background of its own because the figure element
    and the page supply one. An `<img>` on someone else's page supplies
    nothing, so a ground rectangle the size of the viewBox is put behind
    the drawing. Nothing else changes: the same element, the same style,
    the same text at the same size.
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
    """The figure element. A detail JSON makes it interactive; a layer id
    reduces the line legend to that one reading."""
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
            f'<span style="display:inline-flex;align-items:center;gap:.4em;'
            f'margin-right:1.1em;white-space:nowrap">'
            f'<span style="width:1em;height:0;border-top:2px dashed {t["ink_3"]};'
            f'display:inline-block"></span>declared</span>'
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
            f'<span style="display:inline-flex;gap:.3em;margin-left:1em;white-space:nowrap">'
            f'<button type="button" data-zoom="fit" data-for="{svg_id}" {btn}>Fit</button>'
            f'<button type="button" data-zoom="actual" data-for="{svg_id}" {btn}>100%</button>'
            f'<button type="button" data-zoom="in" data-for="{svg_id}" {btn} '
            f'aria-label="Zoom in">+</button>'
            f'<button type="button" data-zoom="out" data-for="{svg_id}" {btn} '
            f'aria-label="Zoom out">-</button></span>'
        )
        hint = (
            f'<p style="margin:.4em 0 0;font-size:.76rem;color:{t["ink_3"]}">Scroll to zoom, '
            "drag to pan, click a component to frame it, Escape to go back.</p>"
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
) -> tuple[str, list[str]]:
    """(the figure HTML, the label and header problems the drawing reported).

    `mode` is "system" or "change"; empty picks "change" when a base ref or
    component ids are given and "system" otherwise. Unknown component ids
    are a ConfigError; an empty git range is a FigureError. `bare` returns
    the SVG alone, on its ground, instead of the figure element. `layer`
    is one reading's id; an id the page does not have is a ConfigError
    naming the ones it does.
    """
    page_url = f"{cfg.out_dir}/index.html"
    facts_url = f"{cfg.out_dir}/{cfg.facts_file}"
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
            f"The system, with the {len(changed)} components a plan reaches as "
            f"the figure. This marks a plan's reach, not a diff. Drawn by "
            f"<code>{GENERATOR}</code>, the same generator the map uses, so "
            f"this cannot disagree with <code>{page_url}</code>."
        )
    elif mode == "change":
        if not base:
            raise FigureError("a base ref is required for a change figure")
        ch = change_mod.compute(cfg, model, base, facts, head)
        if not ch["has_change"]:
            raise FigureError(f"no change between {base} and {head}: nothing to draw")
        changed = ch["direct"]
        changed_modules = ch["modules"]
        adjacent = ch["adjacent"]
        gained = {k: v["gained"] for k, v in ch["per_component"].items()}
        hot = ch["flow_artifacts"]
        legend_mode = "change"
        caption = caption or (
            f"The system, with this change as the figure. Drawn by "
            f"<code>{GENERATOR}</code>, the same generator the map uses, so "
            f"this cannot disagree with <code>{page_url}</code>."
        )
    elif reading is not None:
        sub = reading.sub[:1].upper() + reading.sub[1:] if reading.sub else ""
        caption = caption or (
            f"{reading.label}: {reading.question} {sub + '. ' if sub else ''}"
            f"One reading of the system; the page at <code>{page_url}</code> has them "
            f"all. Drawn by <code>{GENERATOR}</code> from <code>{facts_url}</code>; "
            f"every card is code in the tree today."
        )
    else:
        caption = caption or (
            f"The system as the map describes it. Drawn by <code>{GENERATOR}</code> "
            f"from <code>{facts_url}</code>; every card is code in the tree today. "
            f"Click a component to read what it is to its neighbours."
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
    )
    meta = json.loads(detail).get("_meta", {})
    collisions: list[str] = list(meta.get("collisions", []))
    if bare:
        return bare_svg(svg, t), collisions

    if legend_mode == "reach":
        rows = [
            (legend_rows(t, "change")[0][0], t["change"], "in the plan's reach"),
            (t["ghost"][0], t["ghost"][1], "not in the plan"),
        ]
    else:
        rows = legend_rows(t, legend_mode)
    out = figure(
        t, model, meaning, svg, caption, rows, svg_id, detail if interactive else None, layer
    )
    return out, collisions


def _reading(model: Model, meaning: Meaning, layer: str) -> Layer | None:
    """The layer a figure is restricted to, or None for the whole map.

    The ids are the page's: the standard readings, the agent readings when
    the model has an agent, then the model's own. A wrong id is refused
    with the right ones named, since a figure of a reading that is not on
    the page would be a picture the page cannot back.
    """
    if not layer:
        return None
    layers = all_layers(model, meaning)
    for lay in layers:
        if lay.id == layer:
            return lay
    raise ConfigError(
        f"unknown layer id: {layer}; the readings the page has are "
        f"{', '.join(lay.id for lay in layers)}"
    )


def configured(
    cfg: Config,
    model: Model,
    meaning: Meaning,
    t: dict[str, Any],
    facts: dict[str, Any],
    fig: Figure,
) -> tuple[str, list[str]]:
    """One figure from the configuration's `[[figures]]` table.

    `systemap refresh` writes it and `systemap check` compares it, through
    this one function, so the two cannot disagree about what the file
    should hold. An `out` ending in `.svg` is the bare drawing.
    """
    return make(
        cfg,
        model,
        meaning,
        t,
        facts,
        mode="change" if fig.mode == "reach" else "system",
        components=fig.components,
        caption=fig.caption,
        svg_id=fig.svg_id,
        interactive=fig.interactive,
        bare=fig.out.endswith(".svg"),
        layer=fig.layer,
    )
