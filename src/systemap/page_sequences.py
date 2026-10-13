"""The Sequences view: its toolbar, its panel and the sequence data for the page.

The toolbar selects a sequence and shows it as the whole route or step by step.
The panel lists the route in order, all sequences with a small region map, and
the entry points that have a sequence. `data` gives the page script the entry
point names, the region maps and the counts. The page script draws the route.
"""

from __future__ import annotations

import html
from collections.abc import Collection
from typing import Any

from systemap.journey_coverage import outside_map, ways_in_without_journey
from systemap.model import Box, Journey, Meaning, Model
from systemap.page_icons import icon
from systemap.source_facts import entry_identity, entry_label

# The region map in each row of the sequence list: 56 x 40 pixels.
GLYPH_W, GLYPH_H = 72.0, 52.0
MISSING_SHOWN = 5

# The route on the map. A line keeps the color of its flow kind and the width of a
# map line: 1.6 px. The current step is the selected line of the map: 2.6 px over
# the halo. Later steps are at 40 percent opacity. The other sizes are in map
# units: about 0.9 units for one board pixel. The text of a tag, a step number
# and a step note is 13.6 units or more, the size of the card descriptions: it
# shows at 11 px or more when the map is at 81 percent or more.
MARKS_CSS = r"""
/* ---- the route on the map ------------------------------------------------ */
#schematic .seq-lines,#schematic .seq-marks{pointer-events:none}
#schematic .seq-line{fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;
vector-effect:non-scaling-stroke}
#schematic .seq-line--later{opacity:.4}
#schematic .seq-pill__bg{fill:var(--map)}
#schematic .seq-pill circle{fill:var(--map);stroke:var(--ink-2);stroke-width:1}
#schematic .seq-pill text{font-family:var(--fs);font-size:13.6px;fill:var(--ink-2)}
#schematic .seq-pill .seq-pill__n{font:600 13.6px var(--fm);fill:var(--ink);text-anchor:middle}
#schematic .seq-pill--later circle{stroke:var(--line-2)}
#schematic .seq-pill--later text,#schematic .seq-pill--later .seq-pill__n{fill:var(--ink-3)}
#schematic .seq-pill--route circle,#schematic .seq-pill--now circle{fill:var(--accent);
stroke:var(--map);stroke-width:2}
#schematic .seq-pill--route .seq-pill__n,#schematic .seq-pill--now .seq-pill__n{
fill:var(--on-accent);font-weight:700}
#schematic .seq-pill--route text{fill:var(--ink);font-weight:600}
#schematic .seq-tagm rect{fill:var(--accent)}
#schematic .seq-tagm text{font:700 13.6px var(--fm);letter-spacing:.06em;fill:var(--on-accent);
text-anchor:middle}
#schematic .seq-tagm--meas rect,#schematic .seq-tagm--start rect{fill:var(--map);
stroke:var(--steel);stroke-width:1}
#schematic .seq-tagm--meas text{fill:var(--steel)}
#schematic .seq-tagm--start rect{stroke:var(--ink-3)}
#schematic .seq-tagm--start text{fill:var(--ink-2)}
#schematic .seq-leader{stroke:var(--accent);stroke-width:1.4}
#schematic .seq-leader-dot{fill:var(--accent)}
#schematic .seq-callout{transition:opacity .16s ease-out}
#schematic .seq-callout.wait{opacity:0}
#schematic .seq-co{box-sizing:border-box;width:100%;display:flex;flex-direction:column;gap:7px;
padding:11px 14px 14px;border:1px solid var(--accent);border-radius:9px;
background:var(--surface);color:var(--ink);font:14.75px/21.5px var(--fs);text-align:left}
#schematic .seq-co p{margin:0;color:inherit;overflow-wrap:anywhere}
#schematic .seq-co .seq-co__head{display:flex;align-items:center;gap:9px;
font:600 13.6px/18px var(--fs);color:var(--accent)}
#schematic .seq-co__n{width:22.7px;height:22.7px;flex:none;border-radius:50%;
background:var(--accent);color:var(--on-accent);display:inline-flex;align-items:center;
justify-content:center;font:700 13.6px/1 var(--fm)}
#schematic .seq-co .seq-co__ft{font:13.6px/18px var(--fm);color:var(--ink-3)}
#schematic .node.dim.seq-route{opacity:1}
body[data-mode="trace"] #schematic .flowlbl{display:none}
body[data-mode="trace"] #schematic .node.endpoint:not(.acts):not(.meas) .node__box{
stroke:var(--card-line);stroke-width:1.1}
body[data-mode="trace"] #schematic .node.endpoint.meas:not(.acts) .node__box{stroke:var(--steel);
stroke-width:2}
"""

CSS = (
    r"""
/* ---- Sequences toolbar --------------------------------------------------- */
.seq-choose{position:relative;flex:0 1 320px;min-width:150px}
.seq-choose__btn{width:100%;height:32px;display:flex;align-items:center;gap:8px;
padding:0 8px 0 12px;background:var(--card);color:var(--ink);font:500 13px var(--fs);
text-align:left}
.seq-choose__name{flex:1}
.seq-choose__btn .icon{color:var(--ink-2)}
.seq-choose__list{position:fixed;z-index:30;display:flex;flex-direction:column;gap:2px;padding:6px;
overflow:auto;border:1px solid var(--line-2);border-radius:10px;
background:var(--surface);box-shadow:0 14px 40px color-mix(in srgb,#000 40%,transparent)}
:root[data-theme="light"] .seq-choose__list{box-shadow:0 14px 40px color-mix(in srgb,#5a4a2a 18%,
transparent)}
.trace-controls:has([aria-expanded="true"]){z-index:20}
.seq-choose__list .seq-pick{flex:none;cursor:pointer}
.seq-choose__list .seq-pick:not(.on):hover{background:var(--raised);color:var(--ink)}
.seq-choose__list .seq-pick:focus-visible{outline-offset:-2px}
.seq-seg{display:flex;flex:none;margin-left:6px;border:1px solid var(--line-2);border-radius:6px;
overflow:hidden}
.seq-seg button{height:30px;min-height:30px;padding:0 12px;border:0;border-radius:0;
background:transparent;color:var(--ink-2);font:13px var(--fs)}
.seq-seg button+button{border-left:1px solid var(--line-2)}
.seq-seg button[aria-pressed="true"]{background:var(--card);color:var(--ink);font-weight:500}
.seq-div{flex:none;width:1px;height:24px;margin:0 6px;background:var(--line)}
.seq-tb{display:flex;align-items:center;gap:8px;flex:none}
.seq-btn{height:32px;min-height:32px;padding:0 12px;display:inline-flex;align-items:center;gap:8px;
border:1px solid var(--line);border-radius:6px;background:transparent;color:var(--ink-2);
font:13px var(--fs);white-space:nowrap}
.seq-btn--primary{border-color:var(--ink);background:var(--ink);color:var(--bg);font-weight:600}
.seq-btn--primary:hover{background:var(--ink);color:var(--bg);opacity:.9}
.present kbd{font:11px/14px var(--fm);color:var(--ink-3);
border:1px solid var(--line-2);border-radius:4px;padding:1px 5px}
#jcount{font:12px var(--fm);color:var(--ink-2);padding:0 6px;white-space:nowrap}

/* ---- Sequences panel ----------------------------------------------------- */
.journey-index,#seqbody{display:flex;flex-direction:column;gap:14px;flex:1 1 auto;min-height:0}
.journey-index[data-view="steps"],.journey-index[data-view="steps"] #seqbody{flex:0 0 auto}
.readpanel .seq-kicker{margin:0;font:600 11px/16px var(--fm);letter-spacing:.08em;
color:var(--ink-3)}
.seq-count{font:12px var(--fm);color:var(--ink-3)}
.seq-row{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.seq-sec{padding-top:14px;border-top:1px solid var(--line)}
.seq-head{display:flex;flex-direction:column;gap:4px}
.readpanel .seq-title{margin:0;font:600 19px/25px var(--fs);color:var(--ink)}
.readpanel :is(.seq-entry,.seq-draft,.seq-note){margin:0;font:12px/18px var(--fs);
color:var(--ink-3)}
.seq-entry code,.seq-cover code{font-family:var(--fm);font-size:12px;color:var(--ink-2)}
.readpanel .seq-draft{color:var(--ink)}
.readpanel .seq-note--tight{margin-top:-6px}
.seq-n{width:20px;height:20px;flex:none;box-sizing:border-box;border-radius:50%;display:inline-flex;
align-items:center;justify-content:center;font:700 11px/1 var(--fm);background:var(--accent);
color:var(--on-accent)}
.seq-route{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:2px}
.seq-route button{width:100%;height:26px;min-height:26px;padding:0;display:grid;
grid-template-columns:20px minmax(0,1fr) auto;gap:10px;align-items:center;border:0;
border-radius:4px;background:transparent;text-align:left}
.seq-route button:hover{background:var(--raised)}
.seq-ft,.seq-art,.seq-pick__label,.seq-pick__meta,.seq-choose__name{white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.seq-ft,.seq-art{font:12px/16px var(--fm);color:var(--ink)}
.seq-art{color:var(--ink-2);max-width:160px}
.seq-all{list-style:none;margin:0 -8px;padding:0 8px;display:flex;flex-direction:column;gap:2px;
flex:1 1 0;min-height:168px;overflow:auto;
-webkit-mask-image:linear-gradient(to bottom,#000 85%,transparent);
mask-image:linear-gradient(to bottom,#000 85%,transparent)}
.seq-all li:last-child{padding-bottom:24px}
.seq-pick{width:100%;min-height:54px;display:grid;grid-template-columns:56px minmax(0,1fr);
gap:0 12px;align-items:center;padding:6px 8px;border:1px solid transparent;border-radius:8px;
background:transparent;text-align:left;color:var(--ink-2)}
.seq-pick.on{border-color:var(--accent);background:var(--card);color:var(--ink)}
.seq-pick__text{display:flex;flex-direction:column;gap:2px;min-width:0}
.seq-pick__label{font:13px/18px var(--fs)}
.seq-pick.on .seq-pick__label{font-weight:600}
.seq-pick__meta{font:12px/16px var(--fm);color:var(--ink-3)}
.seq-glyph{display:block;width:56px;height:40px}
.seq-glyph rect{fill:none;stroke:var(--line-2);vector-effect:non-scaling-stroke}
.seq-glyph rect.on{fill:var(--ink-3);fill-opacity:.3;stroke:var(--ink-3)}
.seq-glyph circle{fill:var(--ink)}
.seq-pick.on .seq-glyph rect.on{fill:var(--accent);fill-opacity:.28;
stroke:var(--accent)}
.seq-pick.on .seq-glyph circle{fill:var(--accent)}
:root[data-theme="light"] .seq-pick.on .seq-glyph rect.on{fill:var(--hl);
fill-opacity:1}
.seq-cover{display:flex;flex-direction:column;gap:6px;padding-top:12px;
border-top:1px solid var(--line)}
.seq-cover .seq-count{color:var(--ink-2)}
.seq-bar{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:2px}
.seq-bar i{height:6px;border-radius:1px;box-sizing:border-box;border:1px solid var(--ink-3)}
.seq-bar i.on{background:var(--ink-3)}
.readpanel .seq-cover p{margin:0;font:12px/18px var(--fs);color:var(--ink-2)}
.seq-cover p code{color:var(--ink)}

/* ---- the step list ------------------------------------------------------- */
.seq-steps{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.seq-step{width:100%;display:grid;grid-template-columns:22px minmax(0,1fr);gap:4px 10px;
padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:transparent;
text-align:left;color:var(--ink-3);font:13px/19px var(--fs);min-height:0}
.seq-step:hover{background:var(--raised)}
.seq-step .seq-n{background:transparent;border:1px solid var(--line-2);color:var(--ink-3);
font-weight:600}
.seq-step[data-at="before"]{color:var(--ink-2)}
.seq-step[data-at="before"] .seq-n{border-color:var(--ink-2);color:var(--ink)}
.seq-step__head{font:12px/20px var(--fm);overflow-wrap:anywhere}
.seq-step__say{grid-column:2}
.seq-step[aria-current="step"]{padding:12px;border-color:var(--accent);background:var(--hl-soft);
color:var(--ink)}
.seq-step[aria-current="step"]:hover{background:var(--hl-soft)}
.seq-step[aria-current="step"] .seq-n{border:0;background:var(--accent);color:var(--on-accent);
font-weight:700}
.seq-step[aria-current="step"] .seq-step__head{color:var(--accent);justify-self:start}
:root[data-theme="light"] .seq-step[aria-current="step"] .seq-step__head{background:var(--hl);
padding:0 3px;margin-left:-3px;border-radius:2px}
.seq-roles{grid-column:2;display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding-top:4px}
.seq-roles code{font:12px/18px var(--fm);color:var(--ink)}
.seq-roles .seq-tag+code+.seq-tag,.seq-roles code+.seq-tag{margin-left:8px}
.seq-tag{display:inline-block;box-sizing:border-box;font:700 11px/16px var(--fm);
letter-spacing:.06em;padding:0 6px;border-radius:3px;white-space:nowrap}
.seq-tag--acts,.seq-tag--start{background:var(--accent);color:var(--on-accent);line-height:18px}
.seq-tag--meas{border:1px solid var(--steel);color:var(--steel)}
.seq-more{border-top:1px solid var(--line);padding-top:4px}
.seq-more>summary{font-size:12px;color:var(--ink-3)}
.readpanel .seq-more p{font-size:12px;line-height:18px}

/* ---- legend marks -------------------------------------------------------- */
.seq-lg-now{border-top-width:3px;
box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 30%,transparent)}
:root[data-theme="light"] .seq-lg-now{box-shadow:0 0 0 3px var(--hl-line)}
.seq-lg-later{opacity:.4}
.seq-lg-n{width:18px;height:18px;border-radius:50%;background:var(--accent);color:var(--on-accent);
display:inline-flex;align-items:center;justify-content:center;font:700 11px/1 var(--fm);
font-style:normal}
.seq-lg-quiet{display:block;width:18px;height:12px;border:1px solid var(--line-2);border-radius:3px}
.lg .seq-tag{font-size:11px;line-height:14px;padding:0 4px;border-radius:2px;font-style:normal}
.lg .seq-tag--meas{line-height:12px}

@media(max-width:820px){.trace-controls{overflow-x:auto;gap:6px;padding:0 12px}
.trace-controls__label{display:none}}
"""
    + MARKS_CSS
)


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def chooser(meaning: Meaning, key: str) -> str:
    """Give the sequence chooser: a button that opens the list of the sequences.

    The button shows the name of the current sequence. The page script fills
    the list with one option for each sequence: its region map, its name, its
    entry point and its step count. The element `{key}-label` names the list."""
    name = esc(meaning.journeys[0].label) if meaning.journeys else "No sequences"
    off = "" if meaning.journeys else " disabled"
    return (
        f'<div class="seq-choose"><button type="button" class="seq-choose__btn" id="{key}" '
        f'aria-haspopup="listbox" aria-expanded="false" aria-controls="{key}-list" '
        f'aria-labelledby="{key}-label {key}"{off}><span class="seq-choose__name">{name}</span>'
        f'{icon("down")}</button><div class="seq-choose__list" id="{key}-list" role="listbox" '
        f'aria-labelledby="{key}-label" hidden></div></div>'
    )


def toolbar(meaning: Meaning) -> str:
    """Give the Sequences toolbar row: the sequence choice, the view and the step controls."""
    off = "" if meaning.journeys else " disabled"
    return (
        '<div class="trace-controls" id="tracecontrols" role="toolbar" aria-label="Sequence">'
        '<span class="trace-controls__label" id="seqpick-label">Sequence</span>'
        + chooser(meaning, "seqpick")
        + '<div class="seq-seg" role="group" aria-label="Show">'
        f'<button type="button" id="jwhole" aria-pressed="true"{off}>Whole route</button>'
        f'<button type="button" id="jsteps" aria-pressed="false"{off}>Steps</button></div>'
        '<span class="seq-div" aria-hidden="true"></span>'
        '<span class="seq-tb" id="jwholebar">'
        f'<button type="button" class="seq-btn seq-btn--primary" id="jstart"{off}>'
        "Start at step 1</button></span>"
        '<span class="seq-tb" id="jstepbar" hidden>'
        '<button type="button" class="seq-btn" id="jprev" disabled>Previous</button>'
        '<span id="jcount" aria-live="polite"></span>'
        '<button type="button" class="seq-btn seq-btn--primary" id="jnext" disabled>Next</button>'
        '<button type="button" class="seq-btn" id="jend">End sequence</button>'
        '<button type="button" class="seq-btn" id="jreturn" hidden>Go to sequence</button>'
        "</span></div>"
    )


def panel(meaning: Meaning) -> str:
    """Give the Sequences panel. The page script fills it from the sequence data."""
    empty = (
        ""
        if meaning.journeys
        else '<p class="seq-note">The model has no sequences. An entry point is where a '
        "program can start. Write a sequence in the model, or run "
        "<code>systemap journeys</code> to write a draft.</p>"
    )
    return (
        '<section class="journey-index" id="journeyindex" aria-label="Sequences" hidden>'
        '<div id="seqbody">' + empty + "</div>"
        '<details class="seq-more" id="strip" hidden><summary>Source evidence for '
        '<span id="stripn"></span></summary><p id="stripfoot"></p><p id="stripmeas"></p>'
        '<div id="step-evidence"></div></details></section>'
    )


def _region_of(model: Model) -> dict[str, str]:
    """Give the region or container box of each component."""
    boxes = {b for b, _ in _glyph_boxes(model)}
    out: dict[str, str] = {}
    for c in model.components:
        where = c.region or c.container
        if where and where in boxes:
            out[c.id] = where
    return out


def _glyph_boxes(model: Model) -> list[tuple[str, Box]]:
    """Give the boxes of the region map: containers without regions, then regions."""
    full = {r.container for r in model.regions if r.container}
    out = [(c.id, c.box) for c in model.containers if c.id not in full]
    return out + [(r.id, r.box) for r in model.regions]


def _members(journey: Journey) -> list[str]:
    """Give the components of a sequence in step order, without repeats."""
    out: list[str] = []
    for step in journey.steps:
        for cid in (*step.acts, *step.measures, *step.edge):
            if cid not in out:
                out.append(cid)
    return out


def _start(journey: Journey) -> str:
    if not journey.steps:
        return ""
    first = journey.steps[0]
    return first.acts[0] if first.acts else first.edge[0]


def _glyph(model: Model, journey: Journey) -> str:
    """Draw the small region map of one sequence: used regions filled, a dot at the start."""
    boxes = _glyph_boxes(model)
    if not boxes:
        return ""
    x0 = min(b[0] for _, b in boxes)
    y0 = min(b[1] for _, b in boxes)
    sx = GLYPH_W / max(1, max(b[0] + b[2] for _, b in boxes) - x0)
    sy = GLYPH_H / max(1, max(b[1] + b[3] for _, b in boxes) - y0)
    where = _region_of(model)
    used = {where[c] for c in _members(journey) if c in where}
    out = ['<svg class="seq-glyph" viewBox="-1 -1 74 54" aria-hidden="true">']
    centre: dict[str, tuple[float, float]] = {}
    for bid, (x, y, w, h) in boxes:
        rx, ry, rw, rh = (x - x0) * sx, (y - y0) * sy, w * sx, h * sy
        centre[bid] = (rx + rw / 2, ry + rh / 2)
        on = ' class="on"' if bid in used else ""
        out.append(
            f'<rect{on} x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" rx="2"/>'
        )
    start = where.get(_start(journey))
    if start:
        cx, cy = centre[start]
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3"/>')
    return "".join(out) + "</svg>"


def short_entry(point: dict[str, str]) -> str:
    """Give a short name for an entry point, for example systemap init.

    If the name is the name of the target function, the name alone does not identify the
    entry point. Then the short name adds the module, for example main() in pkg.cli."""
    kind, name = point.get("kind", ""), point.get("name", "")
    module, target = point.get("module", ""), point.get("target", "")
    if kind == "subcommand":
        return f"{target} {name}" if target else f"{name} in {module}"
    if name and name == target:
        return f"{name}() in {module}"
    return name


def _entry(journey: Journey, points: list[dict[str, str]]) -> str:
    """Give the entry point name of a sequence: the recorded start or its first covered command."""
    if journey.starts:
        for p in points:
            if journey.starts in (p.get("name"), entry_label(p)):
                return short_entry(p)
        return journey.starts
    by_id = {entry_identity(p): p for p in points}
    covered = [by_id[c] for c in journey.covers if c in by_id]
    commands = [p for p in covered if p.get("kind") == "subcommand"] or covered
    return short_entry(commands[0]) if commands else ""


def _coverage(
    meaning: Meaning, facts: dict[str, Any], covered: Collection[str] | None, skip: set[str]
) -> dict[str, Any]:
    """Count the entry points that have a sequence. Give the names of the others.

    The total and the missing list use the same entry points: the coverage check
    does not count an entry point that is another name for a counted one. With no
    covered identities, the coverage check gives all the counted entry points.
    The count uses the scope of judgement: the entry points in the modules of this
    map, and the sequences of all maps."""
    if facts.get("entry_points") is None:
        return {"known": False}
    counted = ways_in_without_journey(meaning, facts, skip=skip, covered=())
    missing = ways_in_without_journey(meaning, facts, skip=skip, covered=covered)
    names = [short_entry(p) for p in missing]
    return {
        "known": True,
        "total": len(counted),
        "covered": len(counted) - len(missing),
        "missing": names[:MISSING_SHOWN],
        "more": max(0, len(names) - MISSING_SHOWN),
    }


def data(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    covered: Collection[str] | None = None,
    top: bool = True,
) -> dict[str, Any]:
    """Give the sequence data that the page script reads.

    For each sequence: the entry point name, the region map, and the counts of
    regions and actors that the route uses. Also the entry point coverage.
    `covered` gives the identities that the sequences of all maps include. If it is
    None, the sequences of this map supply them. `top` tells if this map is the top map."""
    points: list[dict[str, str]] = facts.get("entry_points") or []
    regions = {r.id for r in model.regions}
    where = _region_of(model)
    actors = {c.id for c in model.components if c.kind == "actor"}
    out = []
    for journey in meaning.journeys:
        members = _members(journey)
        out.append(
            {
                "entry": _entry(journey, points),
                "glyph": _glyph(model, journey),
                "start": _start(journey),
                "regions": len({where[c] for c in members if where.get(c) in regions}),
                "actors": len([c for c in members if c in actors]),
            }
        )
    skip = outside_map(model, top, facts)
    return {"journeys": out, "coverage": _coverage(meaning, facts, covered, skip)}


# The route on the map, in the same function scope as the sequence controller
# (page_sequence_script): the lines of the other steps, the step numbers, the
# role tags on the cards and the note at the current step. All marks are in the
# map drawing, so they move and scale with the map.
MARKS_JS = r"""
var NS = 'http://www.w3.org/2000/svg';
function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function all(sel, root){
  return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
function byId(id){ return document.getElementById(id); }
function reduced(){
  // Only the page setting Reduce motion stops motion. The head script stamps it
  // before the first paint.
  return document.documentElement.dataset.reduceMotion === 'true';
}
function mk(name, attrs, text){
  var e = document.createElementNS(NS, name);
  Object.keys(attrs || {}).forEach(function(k){ e.setAttribute(k, attrs[k]); });
  if(text !== undefined){ e.textContent = text; }
  return e;
}
function empty(node){ while(node && node.firstChild){ node.removeChild(node.firstChild); } }
var flowLayer = svg.querySelector('.view > g[data-part="flow"]')
  || svg.querySelector('g[data-part="flow"]');
var tagLayer = svg.querySelector('g[data-part="tags"]') || svg.querySelector('.view');
var lines = mk('g', {'class':'seq-lines', 'aria-hidden':'true'});
var marks = mk('g', {'class':'seq-marks', 'aria-hidden':'true'});
var gauge = mk('g', {visibility:'hidden', 'aria-hidden':'true'}), gaugeText = mk('text', {});
gauge.appendChild(gaugeText);
if(flowLayer){ flowLayer.appendChild(lines); }
if(tagLayer){ tagLayer.appendChild(marks); tagLayer.appendChild(gauge); }

// ---- geometry -------------------------------------------------------------
function polyline(d){
  // The corners of a routed path: M, L, H and V points and the end points of Q and C.
  var t = String(d || '').match(/[A-Za-z]|-?\d*\.?\d+/g) || [], out = [], i = 0, c = '';
  function n(){ return +t[i++]; }
  while(i < t.length){
    if(/[A-Za-z]/.test(t[i])){ c = t[i++].toUpperCase(); continue; }
    var last = out[out.length - 1] || {x:0, y:0}, x = last.x, y = last.y;
    if(c === 'M' || c === 'L'){ x = n(); y = n(); }
    else if(c === 'Q'){ i += 2; x = n(); y = n(); }
    else if(c === 'C'){ i += 4; x = n(); y = n(); }
    else if(c === 'H'){ x = n(); }
    else if(c === 'V'){ y = n(); }
    else { i++; continue; }
    out.push({x:x, y:y});
  }
  return out;
}
var CARD = Object.create(null), PATH = {}, VB = svg.viewBox && svg.viewBox.baseVal;
all('.node', svg).forEach(function(n){
  var r = n.querySelector('.node__box');
  if(r){ CARD[n.dataset.id] = {x:+r.getAttribute('x'), y:+r.getAttribute('y'),
    w:+r.getAttribute('width'), h:+r.getAttribute('height')}; }
});
all('path.flow', svg).forEach(function(p){
  PATH[p.dataset.edge] = {d:p.getAttribute('d'), dash:p.getAttribute('stroke-dasharray'),
    stroke:p.getAttribute('stroke'), head:p.getAttribute('marker-end'),
    pts:polyline(p.getAttribute('d'))};
});
function walk(pts, step, trim){
  // Points along a path, every `step` units, without `trim` units at each end.
  var segs = [], total = 0, out = [];
  for(var k = 1; k < pts.length; k++){
    var a = pts[k - 1], b = pts[k], len = Math.hypot(b.x - a.x, b.y - a.y);
    if(len > 0){ segs.push({a:a, b:b, len:len, at:total}); total += len; }
  }
  segs.forEach(function(s){
    for(var u = 0; u <= s.len; u += step){
      var at = s.at + u, f = u / s.len;
      if(at < trim || at > total - trim){ continue; }
      out.push({x:s.a.x + (s.b.x - s.a.x) * f, y:s.a.y + (s.b.y - s.a.y) * f, t:at / total,
        flat:Math.abs(s.b.y - s.a.y) < 0.5, run:s.len, mid:Math.abs(u - s.len / 2) / s.len});
    }
  });
  if(!out.length && segs.length){
    var s0 = segs[Math.floor(segs.length / 2)];
    out.push({x:(s0.a.x + s0.b.x) / 2, y:(s0.a.y + s0.b.y) / 2, t:0.5, flat:true, run:s0.len,
      mid:0});
  }
  return out;
}
function hit(a, b, m){
  m = m || 0;
  return a.x < b.x + b.w + m && b.x < a.x + a.w + m && a.y < b.y + b.h + m && b.y < a.y + a.h + m;
}
function inside(p, r){ return p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h; }
function union(rects, pad){
  var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  rects.forEach(function(r){
    if(!r){ return; }
    x0 = Math.min(x0, r.x); y0 = Math.min(y0, r.y);
    x1 = Math.max(x1, r.x + r.w); y1 = Math.max(y1, r.y + r.h);
  });
  if(x0 === Infinity){ return null; }
  return {x:x0 - pad, y:y0 - pad, w:x1 - x0 + 2 * pad, h:y1 - y0 + 2 * pad};
}
function boundsOf(pts){
  return union(pts.map(function(p){ return {x:p.x, y:p.y, w:0, h:0}; }), 0);
}
function textWidth(text, cls, size){
  var w = 0;
  try {
    gauge.setAttribute('class', cls); gaugeText.textContent = text;
    if(gaugeText.getComputedTextLength){ w = gaugeText.getComputedTextLength(); }
  } catch(_x){}
  return w > 0 ? w : String(text).length * size * 0.6;
}

// ---- marks ------------------------------------------------------------------
var placed = [];
function clearMarks(){
  // The step numbers keep off the region and container labels at their layout size.
  empty(lines); empty(marks);
  placed = [].map.call(svg.querySelectorAll('.zone__h,.box__h'), function(g){
    var b = g.getBBox(); return {x:b.x, y:b.y, w:b.width, h:b.height}; });
}
function showMarks(on){
  lines.style.display = on ? '' : 'none'; marks.style.display = on ? '' : 'none'; }
function drawLine(edge, kind){
  // A copy of the flow line, with its color, its dash and its arrowhead.
  var src = PATH[edge];
  if(!src){ return null; }
  var a = {'class':'seq-line seq-line--' + kind, d:src.d, stroke:src.stroke,
    'marker-end':src.head};
  if(src.dash){ a['stroke-dasharray'] = src.dash; }
  var p = mk('path', a);
  lines.appendChild(p);
  return p;
}
function tag(id, word, kind, shift){
  var b = CARD[id];
  if(!b){ return 0; }
  // 13.6 units of type in an 18 unit tag: 11 px or more at Fit on a desktop screen.
  var w = Math.round(textWidth(word, 'seq-tagm', 13.6) + 12), h = 18;
  var x = b.x + b.w - 8 - w - shift, y = b.y - h / 2;
  var g = mk('g', {'class':'seq-tagm seq-tagm--' + kind,
    transform:'translate(' + x.toFixed(1) + ' ' + y.toFixed(1) + ')'});
  g.appendChild(mk('rect', {width:w, height:h, rx:3}));
  g.appendChild(mk('text', {x:w / 2, y:14}, word));
  marks.appendChild(g);
  placed.push({x:x, y:y, w:w, h:h});
  return w + 6;
}
function pillScore(rect, c, spec, ctx){
  var sc = c.mid * 6 + Math.abs(c.t - 0.5) * 8 - Math.min(c.run, 200) / 25;
  if(spec.label && !c.flat){ sc += 6; }
  Object.keys(CARD).forEach(function(id){
    if(hit(rect, CARD[id], 3)){ sc += ctx.ids[id] ? 1000 : 400; } });
  // A number over another label hides both: worse than a number on a card border.
  placed.forEach(function(q){ if(hit(rect, q, 3)){ sc += 1500; } });
  ctx.dots.forEach(function(p){ if(p.edge !== spec.edge && inside(p, rect)){ sc += 3; } });
  return sc;
}
function bestSpot(spec, ctx){
  var best = null;
  walk(PATH[spec.edge].pts, 6, 16).forEach(function(c){
    (spec.label ? ['r', 'l'] : ['r']).forEach(function(side){
      var x = side === 'r' ? c.x - spec.h / 2 : c.x - spec.w + spec.h / 2;
      var rect = {x:x, y:c.y - spec.h / 2, w:spec.w, h:spec.h};
      var sc = pillScore(rect, c, spec, ctx) + (side === 'l' ? 2 : 0);
      if(!best || sc < best.sc){ best = {sc:sc, c:c, rect:rect, side:side}; }
    });
  });
  return best;
}
function pill(spec, ctx){
  // A step number on its line, at a free place, with the artifact when there is room.
  if(!PATH[spec.edge]){ return null; }
  // Board size with the map at 88 percent: a 20 px number and 12 px words.
  spec.h = 23;
  spec.w = spec.label ? 23 + 4 + textWidth(spec.label, 'seq-pill seq-pill--' + spec.kind, 13.6)
    + 7 : 23;
  var at = bestSpot(spec, ctx);
  if(spec.label && (!at || at.sc >= 400)){
    var bare = {edge:spec.edge, n:spec.n, kind:spec.kind, label:'', h:23, w:23};
    var other = bestSpot(bare, ctx);
    if(other && (!at || other.sc < at.sc)){ spec = bare; at = other; }
  }
  if(!at){ return null; }
  var g = mk('g', {'class':'seq-pill seq-pill--' + spec.kind,
    transform:'translate(' + at.c.x.toFixed(1) + ' ' + at.c.y.toFixed(1) + ')'});
  if(spec.label){
    var x0 = at.side === 'r' ? -11.5 : -spec.w + 11.5;
    g.appendChild(mk('rect', {'class':'seq-pill__bg', x:x0, y:-11.5, width:spec.w, height:23,
      rx:11.5}));
  }
  g.appendChild(mk('circle', {r:spec.label || spec.kind === 'was' || spec.kind === 'later'
    ? 11 : 11.5}));
  g.appendChild(mk('text', {'class':'seq-pill__n', y:4.8}, String(spec.n)));
  if(spec.label){
    g.appendChild(mk('text', {x:at.side === 'r' ? 16 : -16, y:4.8,
      'text-anchor':at.side === 'r' ? 'start' : 'end'}, spec.label));
  }
  marks.appendChild(g);
  placed.push(at.rect);
  return g;
}
function calloutBox(no, e, say){
  var obj = mk('foreignObject', {width:220, height:400, x:-9999, y:-9999});
  var box = document.createElement('div');
  box.setAttribute('class', 'seq-co');
  box.innerHTML = '<p class="seq-co__head"><span class="seq-co__n">' + no + '</span>'
    + esc(e.art) + '</p><p class="seq-co__ft">' + esc(e.from + ' → ' + e.to) + '</p><p>'
    + esc(say) + '</p>';
  obj.appendChild(box);
  return {obj:obj, box:box};
}
function calloutScore(r, c, leader, ctx){
  var sc = Math.abs(c.t - 0.5) * 10;
  Object.keys(CARD).forEach(function(id){
    if(hit(r, CARD[id], 6)){ sc += ctx.step[id] ? 5000 : (ctx.ids[id] ? 300 : 120); }
    if(inside(leader, CARD[id])){ sc += 200; }
  });
  placed.forEach(function(q){ if(hit(r, q, 4)){ sc += 400; } });
  ctx.dots.forEach(function(p){ if(inside(p, r)){ sc += 4; } });
  if(VB && (r.x < VB.x + 8 || r.y < VB.y + 8 || r.x + r.w > VB.x + VB.width - 8
    || r.y + r.h > VB.y + VB.height - 8)){ sc += 3000; }
  var a = ctx.area;
  if(a && !(r.x >= a.x && r.y >= a.y && r.x + r.w <= a.x + a.w && r.y + r.h <= a.y + a.h)){
    sc += 250; }
  return sc;
}
function callout(no, st, ctx){
  // The note at the current step: number, artifact, endpoints and the step sentence.
  var e = A.edges[st.edge], src = PATH[st.edge];
  if(!e || !src){ return null; }
  var made = calloutBox(no, e, st.say);
  var g = mk('g', {'class':reduced() ? 'seq-callout' : 'seq-callout wait'});
  g.appendChild(made.obj); marks.appendChild(g);
  // The board callout is 194 px wide with the map at 88 percent: 220 units.
  var W = 220, G = 34, best = null;
  var h = made.box.offsetHeight > 0 ? made.box.offsetHeight + 2
    : 80 + Math.ceil(String(st.say).length * 7.4 / 192) * 21.5;
  walk(src.pts, 10, 20).forEach(function(c){
    [[c.x - W + 16, c.y + G, 'v'], [c.x - 16, c.y + G, 'v'], [c.x - W + 16, c.y - G - h, 'v'],
      [c.x - 16, c.y - G - h, 'v'], [c.x + G, c.y - 16, 'h'], [c.x + G, c.y - h + 16, 'h'],
      [c.x - G - W, c.y - 16, 'h'], [c.x - G - W, c.y - h + 16, 'h']].forEach(function(o){
      var r = {x:o[0], y:o[1], w:W, h:h};
      var end = o[2] === 'v' ? {x:c.x, y:r.y > c.y ? r.y : r.y + h}
        : {x:r.x > c.x ? r.x : r.x + W, y:c.y};
      var sc = calloutScore(r, c, {x:(c.x + end.x) / 2, y:(c.y + end.y) / 2}, ctx);
      if(!best || sc < best.sc){ best = {sc:sc, r:r, c:c, end:end}; }
    });
  });
  if(!best){ marks.removeChild(g); return null; }
  made.obj.setAttribute('x', best.r.x.toFixed(1)); made.obj.setAttribute('y', best.r.y.toFixed(1));
  made.obj.setAttribute('height', Math.ceil(h));
  g.insertBefore(mk('line', {'class':'seq-leader', x1:best.c.x, y1:best.c.y, x2:best.end.x,
    y2:best.end.y}), made.obj);
  g.insertBefore(mk('circle', {'class':'seq-leader-dot', cx:best.c.x, cy:best.c.y, r:3.2}),
    made.obj);
  placed.push(best.r);
  return {g:g, rect:best.r};
}
function lineKind(k, s){ return s < 0 ? 'route' : (k < s ? 'was' : (k > s ? 'later' : 'now')); }
function drawRoute(o){
  // o: {j, s (the current step, or -1 for the whole route), present, area}
  clearMarks();
  var steps = o.j.steps, s = o.s, cur = s >= 0 ? steps[s] : null;
  var ids = Object.create(null), step = Object.create(null);
  function members(st, into){
    var e = A.edges[st.edge];
    (st.acts || []).concat(st.measures || []).forEach(function(id){ into[id] = true; });
    if(e){ into[e.from] = true; into[e.to] = true; }
  }
  steps.forEach(function(st){ members(st, ids); });
  if(cur){ members(cur, step); }
  var kinds = {}, rank = {now:3, route:3, was:2, later:1};
  steps.forEach(function(st, k){
    var kind = lineKind(k, s);
    if(!PATH[st.edge] || (o.present && kind === 'later')){ return; }
    if(!kinds[st.edge] || rank[kind] > rank[kinds[st.edge]]){ kinds[st.edge] = kind; }
  });
  var drawn = [], dots = [];
  ['later', 'was', 'route'].forEach(function(kind){
    steps.forEach(function(st){
      if(kinds[st.edge] !== kind || drawn.some(function(d){ return d.edge === st.edge; })){
        return; }
      drawn.push({edge:st.edge, path:drawLine(st.edge, kind)});
    });
  });
  Object.keys(kinds).forEach(function(edge){
    walk(PATH[edge].pts, 8, 0).forEach(function(p){ p.edge = +edge; dots.push(p); }); });
  var tagged = Object.create(null), first = steps[0], start = first ? ((first.acts || [])[0]
    || (A.edges[first.edge] || {}).from) : '';
  if(cur){
    (cur.acts || []).forEach(function(id){ tagged[id] = (tagged[id] || 0) + tag(id, 'ACTS',
      'acts', tagged[id] || 0); });
    (cur.measures || []).forEach(function(id){ tagged[id] = (tagged[id] || 0) + tag(id,
      'MEASURES', 'meas', tagged[id] || 0); });
  }
  if(start && !tagged[start]){ tag(start, 'START', s < 0 ? 'first' : 'start', 0); }
  var ctx = {ids:ids, step:step, dots:dots, area:o.area}, note = null, pills = [];
  if(cur && !o.present){ note = callout(s + 1, cur, ctx); }
  var specs = [];
  if(cur && o.present){ specs.push({edge:cur.edge, n:s + 1, kind:'now', label:''}); }
  steps.forEach(function(st, k){
    var kind = lineKind(k, s), e = A.edges[st.edge];
    if(k === s || (o.present && kind === 'later')){ return; }
    specs.push({edge:st.edge, n:k + 1, kind:kind, label:e ? e.art : ''});
  });
  // The shortest lines have the fewest places for a number: they go first.
  // The list keeps the step order for the draw-in.
  function run(pts){
    var d = 0;
    for(var k = 1; k < pts.length; k++){
      d += Math.abs(pts[k].x - pts[k - 1].x) + Math.abs(pts[k].y - pts[k - 1].y); }
    return d;
  }
  var order = specs.map(function(_s, k){ return k; }).sort(function(a, b){
    return run(PATH[specs[a].edge].pts) - run(PATH[specs[b].edge].pts) || a - b; });
  var made = [];
  order.forEach(function(k){ made[k] = pill(specs[k], ctx); });
  specs.forEach(function(_s, k){ pills.push(made[k]); });
  var focus = [];
  Object.keys(step).forEach(function(id){ focus.push(CARD[id]); });
  if(cur && PATH[cur.edge]){ focus.push(boundsOf(PATH[cur.edge].pts)); }
  if(note){ focus.push(note.rect); }
  return {rect:union(focus, 8), note:note ? note.g : null, drawn:drawn, pills:pills};
}
function drawInRoute(made){
  // The whole route draws in step order: 300 ms for each line, the next line
  // starts at most 60 ms later. Each step number shows when its line is complete.
  if(reduced()){ return; }
  var n = made.drawn.length, gap = n > 1 ? Math.min(60, 300 / (n - 1)) : 0;
  made.drawn.forEach(function(d, k){
    var p = d.path;
    if(!p || !p.animate || !p.getTotalLength){ return; }
    var len = p.getTotalLength(), head = p.getAttribute('marker-end');
    var frames = p.getAttribute('stroke-dasharray') ? [{opacity:0}, {opacity:1}]
      : [{strokeDasharray:len + ' ' + len, strokeDashoffset:len},
        {strokeDasharray:len + ' ' + len, strokeDashoffset:0}];
    p.removeAttribute('marker-end');
    var a = p.animate(frames, {duration:300, delay:k * gap, easing:'cubic-bezier(.3,0,.2,1)',
      fill:'backwards'});
    a.onfinish = function(){ p.setAttribute('marker-end', head); };
  });
  made.pills.forEach(function(g, k){
    if(g && g.animate){ g.animate([{opacity:0}, {opacity:1}], {duration:160,
      delay:Math.min(k, n - 1) * gap + 300, fill:'backwards'}); }
  });
}
"""
