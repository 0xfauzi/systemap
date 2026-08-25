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
from typing import Any

from systemap import change as change_mod
from systemap.config import Config, ConfigError
from systemap.model import Meaning, Model
from systemap.schematic import interactive_script, layer_rows, legend_rows, panel_css
from systemap.schematic import render as render_schematic

GENERATOR = "systemap"


class FigureError(Exception):
    """The figure cannot be drawn as asked; the message says why."""


def figure(
    t: dict[str, Any],
    meaning: Meaning,
    svg: str,
    caption: str,
    legend: list[tuple[str, str, str]],
    svg_id: str,
    detail_json: str | None,
) -> str:
    """The figure element. A detail JSON makes it interactive."""
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
        f'<span style="width:1em;height:3px;border-radius:2px;background:{colour};'
        f'display:inline-block"></span>{label}</span>'
        for _lid, colour, label in layer_rows(t, meaning)
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
            f'<label style="display:inline-flex;align-items:center;gap:.4em;'
            f'margin-left:1em;white-space:nowrap;cursor:pointer;min-height:24px">'
            f'<input type="checkbox" data-endstate="{svg_id}"> end state: planned '
            f"components at full strength</label>"
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
            f"var box = document.querySelector('[data-endstate=\"{svg_id}\"]');"
            f'var svg = document.getElementById("{svg_id}");'
            "if(!box || !svg || !svg.systemap){ return; }"
            "box.addEventListener('change', function(){ svg.systemap.setEndstate(box.checked); });"
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
        f"</figure>"
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
) -> tuple[str, list[str]]:
    """(the figure HTML, the label collisions the drawing reported).

    `mode` is "system" or "change"; empty picks "change" when a base ref or
    component ids are given and "system" otherwise. Unknown component ids
    are a ConfigError; an empty git range is a FigureError.
    """
    page_url = f"{cfg.out_dir}/index.html"
    facts_url = f"{cfg.out_dir}/{cfg.facts_file}"
    mode = mode or ("change" if (base or components) else "system")
    known = model.ids

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
    else:
        caption = caption or (
            f"The system as the map describes it. Drawn by <code>{GENERATOR}</code> "
            f"from <code>{facts_url}</code>; planned components are the "
            f"dashed ghosts. Click a component to read what it is to its neighbours."
        )

    svg, detail = render_schematic(
        model,
        meaning,
        t,
        facts,
        issue_url=cfg.issue_url,
        changed=changed,
        changed_modules=changed_modules,
        adjacent=adjacent,
        mode=mode,
        svg_id=svg_id,
        gained=gained,
        hot_artifacts=hot,
    )
    meta = json.loads(detail).get("_meta", {})
    collisions: list[str] = list(meta.get("collisions", []))

    if legend_mode == "reach":
        rows = [
            (legend_rows(t, "change")[0][0], t["change"], "in the plan's reach"),
            (t["ghost"][0], t["ghost"][1], "not in the plan"),
        ]
    else:
        rows = legend_rows(t, legend_mode)
    out = figure(t, meaning, svg, caption, rows, svg_id, detail if interactive else None)
    return out, collisions
