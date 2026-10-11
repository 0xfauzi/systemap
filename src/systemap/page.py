"""The map page, component search, sequences and source records."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from typing import Any

from systemap import (
    nest,
    page_changes,
    page_data,
    page_groups,
    page_guide,
    page_icons,
    page_mapview,
    page_motion,
    page_palette,
    page_phone,
    page_present,
    page_sequence_script,
    page_sequences,
)
from systemap import theme as theme_mod
from systemap.config import Config
from systemap.model import Meaning, Model, all_layers, reading
from systemap.page_assets import CSS
from systemap.page_icons import icon
from systemap.page_script import JS
from systemap.page_workspace import SCRIPT as WORKSPACE_SCRIPT
from systemap.schematic import interactive_script, kind_rows, panel_css
from systemap.schematic import render as render_schematic

NUMBER_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]

# Where the page keeps the reader's scheme, in this browser.
SCHEME_KEY = "systemap-theme"
# Where the page keeps the Reduce motion setting. Motion is on until the reader
# sets it. The system setting for reduced motion does not change the page.
MOTION_KEY = "systemap-reduce-motion"

# The mark, inline, so the tab shows it with nothing fetched. It is not
# themed: a tab's icon is one picture.
FAVICON = "data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%20512%20512'%3E%3Crect%20width='512'%20height='512'%20rx='112'%20fill='%23121417'/%3E%3Cpath%20d='M380,132%20H172%20V256%20H340%20V380%20H132'%20fill='none'%20stroke='%23e6e4df'%20stroke-width='40'%20stroke-linecap='round'%20stroke-linejoin='round'/%3E%3Ccircle%20cx='380'%20cy='132'%20r='40'%20fill='%23e0a458'/%3E%3Ccircle%20cx='132'%20cy='380'%20r='40'%20fill='%23e0a458'/%3E%3C/svg%3E"

# The mark in the header: one route between two ends. The path draws one
# time when the page loads (page_motion).
MARK = (
    '<svg class="mark" viewBox="0 0 512 512" aria-hidden="true">'
    '<path class="mark__path" pathLength="1" d="M380,132 H172 V256 H340 V380 H132"/>'
    '<circle class="mark__dot" cx="380" cy="132" r="44"/>'
    '<circle class="mark__dot" cx="132" cy="380" r="44"/></svg>'
)


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def number_word(n: int) -> str:
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else str(n)


def counted(n_components: int, n_actors: int) -> str:
    """Give the component count and the number of actors.

    The page header and layer strip use these same numbers."""
    out = f"{n_components} component{'' if n_components == 1 else 's'}"
    if n_actors:
        out += f" and {n_actors} actor{'' if n_actors == 1 else 's'}"
    return out


@dataclass(frozen=True)
class Nesting:
    """The parent and child maps for one page.

    `path` identifies this map and is empty for the top map.
    `card` identifies the component that contains this page.
    `parent_label` names the parent map.
    `opens` gives the child map records for the inspector."""

    model_file: str
    path: str = ""
    card: str = ""
    parent_href: str = ""
    parent_label: str = ""
    opens: dict[str, dict[str, Any]] = field(default_factory=dict)


def nesting_of(
    cfg: Config, tree: nest.Tree, m: nest.Map, facts: dict[str, Any] | None = None
) -> Nesting:
    """Give the parent link and child map records.

    The parent link uses `../index.html`. With `facts`, each child record
    contains a Structure diagram. The inspector uses this stored diagram
    without an external request."""
    parent = tree.parent_of(m)
    opens = nest.opens(tree, m)
    if facts is not None:
        for child in tree.children(m):
            opens[child.card]["preview"] = preview(cfg, child, facts)
    return Nesting(
        model_file=m.rel,
        path=m.id,
        card=m.card,
        parent_href="../index.html" if parent is not None else "",
        parent_label=(cfg.name if parent.top else parent.card) if parent is not None else "",
        opens=opens,
    )


def preview(cfg: Config, m: nest.Map, facts: dict[str, Any]) -> str:
    """Render the child map with all cards and no flow lines.

    A different SVG identifier prevents style conflicts. The diagram uses
    the page CSS tokens and the selected palette."""
    svg, _detail = render_schematic(
        m.model,
        m.meaning,
        m.theme,
        facts,
        svg_id=f"preview-{m.card}",
        layer="structure",
        observed_by=cfg.observed_by,
        variables=True,
    )
    svg = _no_tooltips(svg)
    return svg


def _views(meaning: Meaning, ch: dict[str, Any]) -> str:
    dot = (
        '<i class="views__dot" aria-label="The page has a revision comparison"></i>'
        if ch.get("has_change")
        else ""
    )
    return (
        '<nav class="views" aria-label="Views">'
        '<button type="button" data-mode="understand" aria-pressed="true">Map</button>'
        '<button type="button" data-mode="trace" aria-pressed="false">Sequences'
        f'<span class="sr-only"> ({len(meaning.journeys)})</span></button>'
        f'<button type="button" data-mode="change" aria-pressed="false">Changes{dot}</button>'
        "</nav>"
    )


SCHEME_ICONS = {"dark": "moon", "light": "sun"}


def _tool(id_: str, name: str, glyph: str, extra: str = "") -> str:
    """Give one icon button of the header, with its name and its tooltip."""
    return (
        f'<button type="button" class="tool" id="{id_}" aria-label="{esc(name)}" '
        f'title="{esc(name)}"{extra}>{icon(glyph)}</button>'
    )


def _tools() -> str:
    """Give the header settings: the theme, Reduce motion and the keyboard keys.

    The theme group has one button for each scheme. The page shows only the
    button of the scheme that is not in use, so the group is one toggle."""
    labels: dict[str, str] = getattr(theme_mod, "SCHEME_LABELS", {})
    schemes = "".join(
        _tool(
            f"scheme-{name}",
            f"{labels.get(name, name.title())} theme",
            SCHEME_ICONS.get(name, "sun"),
            f' data-scheme="{esc(name)}" aria-pressed="false"',
        )
        for name in theme_mod.SCHEMES
    )
    return (
        f'<div class="bar__tools"><div id="scheme" role="group" aria-label="Theme">{schemes}</div>'
        + _tool("reduce-motion", "Reduce motion", "motion", ' aria-pressed="false"')
        + _tool(
            "keys-open", "Keyboard keys", "help", ' aria-haspopup="dialog" aria-keyshortcuts="?"'
        )
        + '</div><span class="bar__div" aria-hidden="true"></span>'
        + _tool(
            "panel-toggle",
            "Details",
            "panel",
            ' aria-pressed="false" aria-controls="readpanel" aria-keyshortcuts="D"',
        )
    )


def _summary(model: Model, meaning: Meaning) -> str:
    """Give the map counts for a screen reader. The header does not show them."""
    n_actors = sum(c.kind == "actor" for c in model.components)
    cards = counted(len(model.components) - n_actors, n_actors)
    return (
        f'<p class="sr-only">System map: {cards}, {len(model.flows)} flows, '
        f"{number_word(len(all_layers(model, meaning)))} layers.</p>"
    )


def _snap(commit: str, records: str) -> str:
    """Give the stored commit in the header. It opens the source records of the page."""
    text = (
        f'<span class="snap__at">at </span><code>{esc(commit)}</code>'
        if commit
        else "commit not recorded"
    )
    return (
        '<div class="snap-at"><button type="button" class="snap" id="snap" '
        'aria-expanded="false" aria-controls="snap-pop" title="Source of this map">'
        f"{text}</button>"
        '<div class="snap__pop" id="snap-pop" role="region" aria-label="Source of this map" '
        f'hidden><p class="snap__k">SOURCE OF THIS MAP</p>{records}</div></div>'
    )


def _header(
    cfg: Config,
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    nesting: Nesting,
    ch: dict[str, Any],
    records: str,
) -> str:
    parent = (
        f'<a class="crumb" href="{esc(nesting.parent_href)}">{esc(nesting.parent_label)}</a>'
        '<span class="crumb__sep" aria-hidden="true">/</span>'
        if nesting.parent_href
        else ""
    )
    snap = _snap((facts.get("built_at_commit") or "")[:7], records)
    return (
        '<a class="skip" href="#map">Skip to the map</a><header class="bar">'
        f'<a class="brand" href="#map" aria-label="systemap: system map">{MARK}</a>'
        f'<div class="project">{parent}<h1 class="project-name">'
        f"{esc(nesting.path or cfg.name)}</h1>{snap}{_summary(model, meaning)}</div>"
        + _views(meaning, ch)
        + '<div class="bar__space"></div>'
        + '<button type="button" class="find" id="find-open" aria-haspopup="dialog" '
        'aria-controls="palette" aria-expanded="false" aria-keyshortcuts="Control+K Meta+K /" '
        f'title="Find">{icon("search")}<span class="find__label">Find</span>'
        '<kbd data-mod-key aria-hidden="true">Ctrl K</kbd></button>' + _tools() + "</header>"
    )


def _rules(model: Model) -> str:
    """Give all rules of the system, for the panel of the Map view.

    The panel of a component gives the rules that govern that component."""
    if not model.invariants:
        return ""
    rows = "".join(
        f'<li id="rule-{inv.n}" value="{inv.n}" tabindex="-1"><span>{esc(inv.text)}</span>'
        '<span class="governs">'
        + "".join(
            f'<button type="button" class="gv" data-go="{esc(i)}">{esc(i)}</button>'
            for i in inv.governs
        )
        + "</span></li>"
        for inv in sorted(model.invariants, key=lambda i: i.n)
    )
    return (
        '<details class="read__more" id="invariants"><summary><span class="seq-kicker">RULES'
        f'</span><span class="seq-count">{len(model.invariants)}</span></summary>'
        "<p>A rule must stay correct. Select a component to see its rules.</p>"
        f'<ol class="rules">{rows}</ol></details>'
    )


def tab_layers(model: Model, meaning: Meaning) -> list[Any]:
    """Give the layers in tab order: System context first when actors have flows."""
    layers = list(all_layers(model, meaning))
    system = [layer for layer in layers if layer.id == "system"]
    if system and reading(model, meaning, "system")[0]:
        layers = system + [layer for layer in layers if layer.id != "system"]
    return layers


def _first_question(model: Model, meaning: Meaning) -> str:
    layers = tab_layers(model, meaning)
    return layers[0].question if layers else ""


def _readpanel(meaning: Meaning, model: Model, t: dict[str, Any], ch: dict[str, Any]) -> str:
    return (
        '<aside class="readpanel" id="readpanel" aria-label="Details">'
        '<div class="inspector-empty" id="inspector-empty"></div>'
        '<div class="read-more" id="read-more">' + _map_key(t, model) + _rules(model) + "</div>"
        '<div class="drawer" id="drawer" hidden><div class="drawer__in">'
        '<button type="button" class="drawer__x" id="drawerclose" '
        'aria-label="Clear the selection">Clear</button>'
        '<div class="systemap-panel" id="panel" aria-live="polite"></div>'
        '<div id="source-detail"></div></div></div>'
        + page_sequences.panel(meaning)
        + page_changes.panel(ch)
        + "</aside>"
    )


def _submap(cfg: Config, nesting: Nesting) -> str:
    if not nesting.opens:
        return ""
    here = f"{cfg.name} / {nesting.path}" if nesting.path else cfg.name
    return (
        '<div class="submap" id="submap" role="dialog" aria-modal="true" '
        f'aria-label="The map inside a card" data-here="{esc(here)}" hidden>'
        '<div class="submap__bar"><span class="submap__crumb" id="submapcrumb"></span>'
        '<button type="button" class="submap__x" id="submapclose" '
        'aria-label="Go to parent map">Go to parent</button></div>'
        '<iframe class="submap__frame" id="submapframe" title="The map inside the card" '
        'src="about:blank"></iframe></div>'
    )


def _map_key(t: dict[str, Any], model: Model) -> str:
    marks = {"ring": "an inner ring", "notch": "a notch", "dotted": "a dotted border"}
    out = [
        '<details class="read__more" id="mapkey"><summary><span class="seq-kicker">'
        "LINES AND CARDS</span></summary>"
        '<div class="legend"><span class="lg"><i class="lg--solidline"></i>'
        "source review recorded</span>"
        '<span class="lg"><i class="lg--dashline"></i>flow without source review</span></div>'
        "<p>A card groups modules by function. "
        "A dashed card identifies an actor outside the source code. "
        "A flow names an artifact between components. A layer shows flows for one question.</p>"
        "<p>A solid internal line records a source review with resolved references. "
        "A short dashed line shows structural evidence: an import, shared module "
        "or configured mechanism. "
        "A long dashed line has no structural evidence. "
        "For both dashed states, source review of direction and artifact is necessary. "
        "External flows cross the source code boundary. No flow records program execution.</p>"
        "<p>A sequence gives the steps of one operation in the model. A dot identifies a note. "
        "A stacked card opens a child map.</p>"
    ]
    for kind, mark in kind_rows(t, model):
        out.append(f'<p class="lg--mark-{mark}">A {esc(kind)} has {marks[mark]}.</p>')
    out.append("</details>")
    return "\n".join(out)


def _unknown_provenance(provenance: dict[str, Any]) -> str:
    if not provenance["unknown"]:
        return ""
    return (
        '<details class="unknown-records"><summary>Unknown source information</summary>'
        "<p>The extractor could not read these records. The missing information limits "
        "the information on the map. Read the finding. Correct the source or extractor "
        "configuration. Then run <code>systemap refresh</code> in the terminal.</p>"
        + "".join(f"<p><code>{esc(line)}</code></p>" for line in provenance["unknown"])
        + "</details>"
    )


def _source_files(cfg: Config, facts: dict[str, Any], nesting: Nesting) -> str:
    return (
        "<p>HEAD at extraction was "
        f"<code>{esc(facts.get('built_at_commit') or 'not recorded')}</code>.</p>"
        f"<p>Source files: <code>{esc(cfg.out_dir)}/{esc(cfg.facts_file)}</code> and "
        f"<code>{esc(nesting.model_file)}</code>.</p>"
        "<p>Extraction reads the working tree, which can contain uncommitted changes. "
        "This page cannot find subsequent changes. Run <code>systemap refresh</code> "
        "in the project terminal to update it.</p>"
    )


def _map_section(model: Model, meaning: Meaning, system_svg: str, ch: dict[str, Any]) -> str:
    return (
        '<section class="map" id="map" aria-label="System map">'
        '<span id="activity-label" hidden></span><h2 id="activity-question" class="sr-only">'
        "What are the components and their connections?</h2>"
        + page_mapview.toolbar(tab_layers(model, meaning))
        + page_mapview.title(_first_question(model, meaning))
        + page_sequences.toolbar(meaning)
        + '<div class="change-controls" id="changecontrols">'
        + page_changes.toolbar(ch)
        + "</div>"
        + '<div class="spatial-map" id="spatialmap">'
        + '<div class="mapwrap" id="mapwrap"><div class="stage" id="stage">'
        + system_svg
        + "</div></div></div>"
        + page_mapview.zoom()
        + '<div class="legend map-legend" id="map-legend" aria-label="Legend"></div>'
        '<p class="readout" id="map-context" aria-live="polite"></p>'
        + page_guide.card()
        + '<p class="hint sr-only" id="map-detail">Select a component or flow to read its source '
        "evidence. Scroll to zoom. Drag to move the map. Fit shows all components. "
        "Tab selects cards and flow paths. Enter opens their data. Arrow keys change layers or "
        "sequence steps. Escape shows the previous view.</p>"
        '<p id="linkstatus" role="status" aria-live="polite"></p>'
        '<p class="sr-only" id="copystatus" role="status"></p>'
    )


def _change_svg(
    cfg: Config,
    model: Model,
    meaning: Meaning,
    t: dict[str, Any],
    facts: dict[str, Any],
    ch: dict[str, Any],
) -> tuple[str, str]:
    if not (ch.get("has_change") or ch.get("comparison_requested")):
        return "", ""
    return render_schematic(
        model,
        meaning,
        t,
        facts,
        changed=ch["direct"],
        changed_modules=ch["modules"],
        adjacent=ch["adjacent"],
        mode="change",
        svg_id="changemap",
        gained={k: v["gained"] for k, v in ch["per_component"].items()},
        hot_artifacts=ch["flow_artifacts"],
        observed_by=cfg.observed_by,
        variables=True,
        tests_only=page_changes.tests_only(ch),
    )


def _head(cfg: Config, t: dict[str, Any], nesting: Nesting, extra_css: str) -> str:
    schemes = list(t.get("schemes") or {t["scheme"]: t})
    title = f"{cfg.name} system map" + (f": {nesting.path}" if nesting.path else "")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(title)}</title><link rel="icon" href="{FAVICON}">'
        "<script>(function(){var s=null;try{s=localStorage.getItem("
        f"{json.dumps(SCHEME_KEY)})}}catch(e){{}}"
        f"if({json.dumps(schemes)}.indexOf(s)<0){{s=(window.matchMedia&&"
        "window.matchMedia('(prefers-color-scheme: light)').matches)?"
        f"{json.dumps(theme_mod.LIGHT_SCHEME)}:{json.dumps(theme_mod.DEFAULT_SCHEME)}}}"
        "document.documentElement.setAttribute('data-theme',s);var m='false';try{"
        f"if(localStorage.getItem({json.dumps(MOTION_KEY)})==='true'){{m='true'}}}}catch(e){{}}"
        "document.documentElement.setAttribute('data-reduce-motion',m)})();</script>"
        "<style>"
        + _compact_css(
            panel_css(t, variables=True) + CSS.replace("{ROOT}", theme_mod.root_css(t)) + extra_css
        )
        + "</style></head>"
    )


# A <title> in an inline SVG is a browser tooltip on every shape under it, and the
# map's titles only repeat its name ("System map"). The SVG keeps its aria-label for
# screen readers; the panel and the legend explain notes and inner maps on screen.
_SVG_TITLE = re.compile(r"<title>[^<]*</title>")


def _no_tooltips(svg: str) -> str:
    """Remove the SVG titles that a browser shows as tooltips on the map."""
    return _SVG_TITLE.sub("", svg)


def build(
    cfg: Config,
    model: Model,
    meaning: Meaning,
    t: dict[str, Any],
    facts: dict[str, Any],
    ch: dict[str, Any],
    nesting: Nesting | None = None,
) -> str:
    """Make the map page from the model and stored facts, without external files."""
    nesting = nesting or Nesting(model_file=cfg.model)
    system_svg, detail = render_schematic(
        model,
        meaning,
        t,
        facts,
        svg_id="schematic",
        observed_by=cfg.observed_by,
        opens=nesting.opens,
        variables=True,
    )
    system_svg = _no_tooltips(system_svg)
    payload: dict[str, Any] = {
        "sources": page_data.sources(model, facts),
        "comparison": page_data.comparison(ch),
        "provenance": page_data.provenance(cfg, facts, nesting.model_file),
        "regions": [
            {"label": r.label, "ids": [c.id for c in model.components if c.region == r.id]}
            for r in model.regions
        ],
        # The Find dialog names the region of each component, or this label.
        "outside": cfg.outside_label,
        "tabs": [layer.id for layer in tab_layers(model, meaning)],
        "guide": page_guide.steps(model, meaning),
        "sequences": page_sequences.data(model, meaning, facts),
    }
    change_svg, change_detail = _change_svg(cfg, model, meaning, t, facts, ch)
    change_svg = _no_tooltips(change_svg)
    extra_css = (
        page_guide.CSS
        + page_sequences.CSS
        + page_present.CSS
        + page_changes.CSS
        + page_groups.CSS
        + page_mapview.CSS
        + page_icons.CSS
        + page_phone.CSS
        + page_motion.CSS
        + page_motion.SURFACE_CSS
        + page_palette.CSS
    )
    o = [
        _head(cfg, t, nesting, extra_css),
        '<body data-mode="understand" data-panel="closed">',
        _header(
            cfg,
            model,
            meaning,
            facts,
            nesting,
            ch,
            _unknown_provenance(payload["provenance"]) + _source_files(cfg, facts, nesting),
        ),
        '<main class="main">',
        _map_section(model, meaning, system_svg, ch),
        page_changes.stage(ch, change_svg),
        '<p class="hint sr-only">Double-click a card that opens a map, or press Enter on it '
        "a second time in the diagram, to read the map inside.</p>"
        if nesting.opens
        else "",
        "</section>",
        _readpanel(meaning, model, t, ch),
        "</main>",
        '<details class="map-links"><summary>Child maps</summary>'
        + ", ".join(
            f'<a href="{esc(child["href"])}">{esc(child["name"])}</a>'
            for child in nesting.opens.values()
        )
        + "</details>"
        if nesting.opens
        else "",
        _submap(cfg, nesting),
        page_present.html(),
        page_phone.html(model, meaning),
        page_motion.keys_sheet(),
        page_palette.html(),
        "<script>window.systemapWorkspace="
        + json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")
        + ";</script>",
        _compact(interactive_script(t, "schematic", "panel", detail, variables=True)),
    ]
    if change_svg:
        o.append(
            _compact(
                interactive_script(t, "changemap", "change-none", change_detail, variables=True)
            )
        )
    scripts = (
        JS,
        page_guide.SCRIPT,
        page_sequence_script.SCRIPT,
        WORKSPACE_SCRIPT,
        page_changes.SCRIPT if change_svg else page_changes.EMPTY_SCRIPT,
        page_groups.SCRIPT,
        page_mapview.SCRIPT,
        page_phone.SCRIPT,
        page_present.SCRIPT,
        page_motion.SCRIPT,
        page_palette.SCRIPT,
    )
    o += [f"<script>{_compact(js)}</script>" for js in scripts]
    o.append("</body></html>")
    return "\n".join(o) + "\n"


def _compact(js: str) -> str:
    """Remove comment lines, indentation and empty lines from a page script.

    The page scripts have no template literals, so no string continues on a second line."""
    lines = (line.strip() for line in js.splitlines())
    return "\n".join(line for line in lines if line and not line.startswith("//"))


def _compact_css(css: str) -> str:
    """Remove comments, line breaks and indentation from the page styles.

    A line break after a semicolon, a brace or a comma goes. A different line
    break becomes one space, because it can separate two values."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.sub(r"([;{},])?[ \t]*\n\s*", lambda m: m.group(1) or " ", css).strip()
