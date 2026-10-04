"""A self-contained workspace for understanding, tracing and reviewing a system."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from typing import Any

from systemap import nest, page_atlas, page_data
from systemap import theme as theme_mod
from systemap.config import Config
from systemap.model import Component, Meaning, Model, all_layers
from systemap.page_assets import CSS
from systemap.page_script import JS
from systemap.schematic import interactive_script, kind_rows, panel_css
from systemap.schematic import render as render_schematic

STATE_WORD = {"built": "built", "actor": "outside"}
NUMBER_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]

# Where the page keeps the reader's scheme, in this browser.
SCHEME_KEY = "systemap-theme"

# The mark, inline, so the tab shows it with nothing fetched. It is not
# themed: a tab's icon is one picture.
FAVICON = "data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%20512%20512'%3E%3Crect%20width='512'%20height='512'%20rx='112'%20fill='%23121417'/%3E%3Cpath%20d='M380,132%20H172%20V256%20H340%20V380%20H132'%20fill='none'%20stroke='%23e6e4df'%20stroke-width='40'%20stroke-linecap='round'%20stroke-linejoin='round'/%3E%3Ccircle%20cx='380'%20cy='132'%20r='40'%20fill='%23e0a458'/%3E%3Ccircle%20cx='132'%20cy='380'%20r='40'%20fill='%23e0a458'/%3E%3C/svg%3E"


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def number_word(n: int) -> str:
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else str(n)


def counted(n_components: int, n_actors: int) -> str:
    """`15 components and 3 actors`: the cards that are code, then the actors
    when there are any. The header and the strip count the same way, so the
    two never disagree about what a component is."""
    out = f"{n_components} component{'' if n_components == 1 else 's'}"
    if n_actors:
        out += f" and {n_actors} actor{'' if n_actors == 1 else 's'}"
    return out


@dataclass(frozen=True)
class Nesting:
    """Where a page sits in the tree of maps: what is above it, what opens below.

    `path` is the map's id (`Gateway`, `Gateway/Routes`), empty for the
    top; `card` the card the page is inside; `parent_label` what the map
    above is called (the project for the top map, else its card); `opens`
    what each opening card on this page opens, as the panel prints it.
    """

    model_file: str
    path: str = ""
    card: str = ""
    parent_href: str = ""
    parent_label: str = ""
    opens: dict[str, dict[str, Any]] = field(default_factory=dict)
    review: dict[str, Any] | None = None


def nesting_of(
    cfg: Config, tree: nest.Tree, m: nest.Map, facts: dict[str, Any] | None = None
) -> Nesting:
    """The nesting of one map's page: the link up is always `../index.html`.

    With `facts`, each opening card's record carries a preview of the map
    inside it: that map's Structure reading, drawn by the same generator
    at render time and inlined in the page data, so the panel shows it
    with nothing fetched.
    """
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
        review=page_data.tree_review(cfg, tree, m, facts) if facts is not None else None,
    )


def preview(cfg: Config, m: nest.Map, facts: dict[str, Any]) -> str:
    """The map inside a card as a small drawing: its Structure reading, every
    card and no edge, under an id of its own so its styles stay its own. It
    is part of the page, so it draws through the page's tokens and follows
    the scheme the reader picks."""
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
    return svg


def _index_entry(c: Component, state: str, plain: str) -> str:
    cid = c.id
    return (
        f'<button type="button" class="ix" data-go="{esc(cid)}" '
        f'data-search="{esc(" ".join((cid, plain, c.does, *c.implemented_by)).lower())}">'
        f'<span class="ix__plain">{esc(plain or cid)}</span>'
        f"<code>{esc(cid)}</code>"
        f'<span class="chip chip--{esc(state)}">{esc(STATE_WORD[state])}</span>'
        "</button>"
    )


def _header(
    cfg: Config, model: Model, meaning: Meaning, facts: dict[str, Any], nesting: Nesting, cards: str
) -> str:
    commit = (facts.get("built_at_commit") or "")[:10]
    parent = (
        f'<a href="{esc(nesting.parent_href)}">{esc(nesting.parent_label)}</a> / '
        if nesting.parent_href
        else ""
    )
    return (
        '<a class="skip" href="#map">Skip to the map</a><header class="bar">'
        '<a class="brand" href="#map" aria-label="systemap: system map">'
        '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M25 6H10v10h12v10H7" '
        'fill="none" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="25" cy="6" r="3" fill="currentColor"/>'
        '<circle cx="7" cy="26" r="3" fill="currentColor"/></svg>systemap</a>'
        f'<div class="project"><h1>{parent}{esc(nesting.path or cfg.name)}</h1>'
        f'<p class="meta">System map: {cards}, {len(model.flows)} flows, '
        f"{number_word(len(all_layers(model, meaning)))} layers.</p></div>"
        '<nav class="header-links" aria-label="Page sections">'
        '<a href="#components">Find a part</a><a href="#invariants">Rules</a>'
        '<a href="#review">Review</a></nav>'
        '<div class="snapshot"><span>Stored snapshot</span>'
        '<p>Extracted at HEAD <code title="HEAD when the working tree was read">'
        f"{esc(commit) if commit else 'commit not recorded'}</code>.</p></div>"
        '<label class="scheme">Appearance <select id="scheme" aria-label="Scheme">'
        + "".join(
            f'<option value="{esc(name)}">{esc(name.title())}</option>'
            for name in ("warm", "graphite", "paper")
        )
        + "</select></label></header>"
    )


def _index(model: Model, meaning: Meaning, states: dict[str, str], cfg: Config) -> str:
    groups: dict[str, list[Component]] = {}
    for c in model.components:
        groups.setdefault(c.region or "outside", []).append(c)
    regions = [(r.id, r.label) for r in model.regions] + [("outside", cfg.outside_label)]
    out = [
        '<section id="components" class="part-index"><h2>Find a part</h2>'
        '<label class="search"><span class="sr-only">Search by job, name or module</span>'
        '<input id="partsearch" type="search" placeholder="Job, name or module" '
        'autocomplete="off" aria-controls="partlist" aria-describedby="search-help"></label>'
        '<p id="search-help">Search names, purposes and modules. Press / or Ctrl/Cmd+K.</p>'
        '<p class="search-count" id="searchcount" role="status"></p>'
        '<details id="partlist-disclosure"><summary>Part index</summary>'
        '<div class="ixgrid" id="partlist">'
    ]
    for rid, label in regions:
        if rid not in groups:
            continue
        out.append(f'<div class="ixgroup"><h3 class="region">{esc(label)}</h3>')
        for c in groups[rid]:
            out.append(_index_entry(c, states[c.id], meaning.plain.get(c.id, "")))
        out.append("</div>")
    out.append(
        '</div></details><p id="searchempty" hidden>No matching part. Try its job or module.</p>'
    )
    out.append("</section>")
    return "\n".join(out)


def _journeys(meaning: Meaning) -> str:
    out = [
        '<section class="journey-index" id="journeyindex" hidden><h2>Choose an operation</h2>'
        "<p>A journey follows one operation through the system, step by step.</p>"
    ]
    for k, j in enumerate(meaning.journeys):
        out.append(
            f'<button class="journey-choice" type="button" data-journey="{k}" '
            f'aria-pressed="false"><span>{esc(j.label)}</span><small>'
            f"{esc(j.starts) if j.starts else 'Start not named'} / {len(j.steps)} steps"
            f"{' / draft' if j.drafted else ''}</small></button>"
        )
    if not meaning.journeys:
        out.append(
            "<p>No journeys have been authored. A way into the system is where a run can "
            "start. List them with <code>systemap facts --entry-points</code>, then write "
            "a journey in the model.</p>"
        )
    out.append("</section>")
    return "\n".join(out)


def _review_index(review: dict[str, Any]) -> str:
    out = [
        '<section class="review-index" id="reviewindex" hidden><h2>Decisions to make</h2>'
        "<p>Judgement finds questions the code cannot settle. These findings use the "
        'stored facts for this map.</p><div class="review-count">'
        f"<strong>{len(review['open'])}</strong> open "
        f"<span>{len(review['answered'])} answered</span></div>"
        '<div class="review-filters" role="group" aria-label="Review status">'
        '<button type="button" data-review-filter="open" aria-pressed="true">Open</button>'
        '<button type="button" data-review-filter="answered" '
        'aria-pressed="false">Answered</button></div><div id="reviewlist"></div>'
    ]
    for key, label in (("pending", "Pending answers"), ("policies", "Policy answers")):
        notices = review.get(key, [])
        if notices:
            out.append(
                f"<details><summary>{label}</summary><ul>"
                + "".join(f"<li>{esc(item)}</li>" for item in notices)
                + "</ul></details>"
            )
    out.append("</section>")
    return "\n".join(out)


def _commands(ch: dict[str, Any]) -> str:
    commands = [
        (
            "Update the snapshot",
            "Read the current code and regenerate the map.",
            "systemap refresh",
        ),
        ("Check the current tree", "Verify that the map still matches the code.", "systemap check"),
        (
            "Review the decisions",
            "List open findings and stale answers across every map.",
            "systemap judgement --verbose",
        ),
        (
            "Compare a change",
            "Replace REF with the revision to compare against. Open Review after rendering.",
            "systemap render --base REF",
        ),
        ("Explain how it changed", "Read structural changes through time.", "systemap history"),
        (
            "Examine a proposed change",
            "Replace the example with the change you intend to make.",
            'systemap plan "describe the change"',
        ),
        (
            "Verify a saved plan",
            "Replace ID and REF. Compare the saved plan with source changes. "
            "This check does not ask a model.",
            "systemap plan --check ID --base REF",
        ),
        (
            "Read a source comparison",
            "Replace REF with a revision. Imports show possible effects, "
            "not established behaviour.",
            "systemap delta --base REF",
        ),
        (
            "Ask for a second opinion",
            "With a configured Jev key, ask an external model to review authored meaning.",
            "systemap audit",
        ),
        (
            "Investigate an issue",
            "Replace the example issue. Jev provides external advice when configured.",
            'systemap triage "describe the issue"',
        ),
        (
            "Export a figure",
            "Write a self-contained SVG from the same authored map.",
            "systemap figure --static --out system.svg",
        ),
    ]
    out = ['<details class="commands"><summary>Work with the current code</summary>']
    out.append("<p>Run these in the project terminal. This page reads a stored snapshot.</p>")
    for title, why, command in commands:
        out.append(
            f'<div class="command"><b>{title}</b><p>{why}</p><code>{esc(command)}</code>'
            f'<button type="button" data-copy="{esc(command)}" '
            f'aria-label="Copy {esc(command)}">Copy</button></div>'
        )
    if not ch.get("has_change") and not ch.get("comparison_requested"):
        out.append("<p>No revision comparison was included in this page.</p>")
    out.append('<p id="copystatus" role="status"></p></details>')
    return "\n".join(out)


def _rules(model: Model) -> str:
    out = [
        '<details class="rulebook" id="invariants"><summary>Rules of this system</summary>'
        "<p>An invariant is a rule that must remain true. Select a part to see the rules "
        'that govern it.</p><ol class="rules">'
    ]
    for inv in sorted(model.invariants, key=lambda i: i.n):
        out.append(
            f'<li id="rule-{inv.n}" value="{inv.n}"><span>{esc(inv.text)}</span>'
            '<span class="governs">'
            + " ".join(
                f'<button type="button" class="gv" data-go="{esc(i)}">{esc(i)}</button>'
                for i in inv.governs
            )
            + "</span></li>"
        )
    out.append("</ol></details>")
    return "\n".join(out)


def _controls(model: Model, meaning: Meaning, t: dict[str, Any]) -> str:
    palette = theme_mod.Palette(t, variables=True)
    out = ['<div class="controls"><div class="seg" role="group" aria-label="Layer">']
    for layer in all_layers(model, meaning):
        out.append(
            f'<button type="button" class="seg__b" data-layer-btn="{esc(layer.id)}" '
            f'aria-pressed="false" style="--c:{palette.layer(layer.id)}" '
            f'title="{esc(layer.question)}"><i></i>{esc(layer.label)}</button>'
        )
    out.append(
        '<button type="button" class="seg__b" data-layer-btn="all" '
        'aria-pressed="false">All</button></div>'
        '<label class="mobile-layer">Layer <select id="layer-select" aria-label="Layer">'
        + "".join(
            f'<option value="{esc(layer.id)}">{esc(layer.label)}</option>'
            for layer in all_layers(model, meaning)
        )
        + '<option value="all">All layers</option></select></label>'
        '<div class="zoom" role="group" '
        'aria-label="Zoom"><button type="button" data-zoom="out" aria-label="Zoom out">'
        '-</button><span id="zpct" aria-live="off"></span>'
        '<button type="button" data-zoom="in" aria-label="Zoom in">+</button>'
        '<button type="button" data-zoom="fit" aria-pressed="true">Fit</button>'
        '<button type="button" data-zoom="actual" aria-pressed="false">100%</button>'
        '</div><div class="view-switch" role="group" aria-label="Map view">'
        '<button type="button" id="view-map" aria-pressed="true">Map</button>'
        '<button type="button" id="view-reading" aria-pressed="false">Reading view</button>'
        "</div></div>"
    )
    return "\n".join(out)


def _trace_controls(meaning: Meaning) -> str:
    return (
        '<div class="trace-controls" id="tracecontrols">'
        '<label for="journey" class="sr-only">Journey</label><select id="journey" '
        'aria-label="Journey"><option value="">Choose an operation</option>'
        + "".join(
            f'<option value="{k}">{esc(j.label)}</option>' for k, j in enumerate(meaning.journeys)
        )
        + '</select><button type="button" class="jb" id="jprev" '
        'aria-label="Previous step" disabled>Previous</button>'
        '<span id="jcount" aria-live="polite"></span>'
        '<button type="button" class="jb" id="jnext" aria-label="Next step" disabled>'
        'Next</button><button type="button" id="jreturn" hidden>Back to journey</button>'
        '<button type="button" id="jend" hidden>End journey</button>'
        '<label class="motion-control"><input type="checkbox" id="reduce-motion" '
        'aria-describedby="motion-meaning">Reduce motion</label>'
        '<span id="motion-meaning" class="sr-only">Motion shows the authored flow direction, '
        "not live execution.</span></div>"
    )


def _inspector() -> str:
    return (
        '<aside class="inspector" aria-label="Details and evidence">'
        '<div class="inspector-empty" id="inspector-empty">'
        "<h2>Inspect the system</h2><p>Select a card to read its purpose and source. "
        "Select a flow label to inspect the exact relationship and its evidence.</p>"
        "<p>The map keeps its authored positions when you switch layers. "
        "Reading view lists the same parts and exact flows at text size.</p>"
        '<button type="button" class="text-action" data-mode="trace">Trace an operation</button>'
        '<button type="button" class="text-action" data-mode="review">Review the map</button>'
        '</div><div class="drawer" id="drawer" data-dock="right" hidden>'
        '<div class="drawer__in"><button type="button" class="drawer__x" id="drawerclose" '
        'aria-label="Close the panel">Clear selection</button>'
        '<div class="systemap-panel" id="panel" aria-live="polite"></div>'
        '<div id="source-detail"></div></div></div>'
        '<details class="strip" id="strip" hidden open><summary>Current journey step '
        '<span class="strip__n" id="stripn"></span><p class="strip__say" id="stripsay"></p>'
        "</summary>"
        '<p class="strip__meas" id="stripmeas"></p><p class="strip__foot" id="stripfoot"></p>'
        '<div id="step-evidence"></div>'
        '</details><div id="review-detail" hidden></div></aside>'
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
        'aria-label="Return to parent map">Return to parent</button></div>'
        '<iframe class="submap__frame" id="submapframe" title="The map inside the card" '
        'src="about:blank"></iframe></div>'
    )


def _comparison_limits(ch: dict[str, Any]) -> str:
    out = []
    if ch.get("comparison_base"):
        out.append(
            f"<p>Source differences start at merge base <code>{esc(ch['comparison_base'])}</code>. "
            "The drawing uses this page's authored model and stored facts. "
            "It does not reconstruct a historical map.</p>"
        )
    if not ch.get("reach_known", False):
        out.append("<p>Import reach was not recorded. Possible downstream effects are unknown.</p>")
    if ch.get("unparsed"):
        out.append(
            "<p>Source differences could not be parsed for <code>"
            + esc(", ".join(ch["unparsed"]))
            + "</code>. Fix the source or extractor error, then rerun "
            "<code>systemap render --base REF</code> in the terminal.</p>"
        )
    for cid, data in ch.get("per_component", {}).items():
        for module, records in data.get("unknown", {}).items():
            for revision, issues in records.items():
                for issue in issues:
                    out.append(
                        f"<p>Unknown {esc(revision)} surface for <code>"
                        f"{esc(cid)} / {esc(module)}</code>: "
                        f"{esc(issue.get('reason', 'The source could not be read.'))} "
                        f"(line {esc(issue.get('line', 0))}, "
                        f"column {esc(issue.get('column', 0))}).</p>"
                    )
    return "".join(out)


def _change(ch: dict[str, Any], svg: str) -> str:
    if not svg:
        return ""
    title = (ch.get("pr") or {}).get("title") or f"{ch['base']}..{ch['head']}"
    return (
        '<section id="change" class="change-view" hidden>'
        f"<h2>Revision comparison: {esc(title)}</h2>"
        f"<p>Base <code>{esc(ch.get('base_revision', ch['base']))}</code>; "
        f"head <code>{esc(ch.get('head_revision', ch['head']))}</code>.</p>"
        f"<p>{len(ch['direct'])} parts changed; {len(ch['adjacent'])} adjacent parts; "
        f"{ch['files']} files. Adjacent means connected by an import, not proven impact.</p>"
        + _comparison_limits(ch)
        + (
            "<p>No source differences were found for the resolved revisions.</p>"
            if not ch.get("has_change")
            else ""
        )
        + '<div class="legend"><span>Accent: changed inside</span>'
        "<span>Secondary colour: adjacent</span><span>Muted: untouched</span></div>"
        f'<div class="comparison-panes"><div class="stage">{svg}</div>'
        '<aside class="systemap-panel" id="change-panel" aria-label="Comparison details" '
        'aria-live="polite"><p>Select a comparison card to inspect its source changes.</p>'
        "</aside></div></section>"
    )


def _map_key(t: dict[str, Any], model: Model) -> str:
    marks = {"ring": "an inner ring", "notch": "a notch", "dotted": "a dotted border"}
    out = [
        '<details class="map-key"><summary>Read the map: card, flow, layer and journey</summary>'
        '<div class="legend"><span class="lg"><i class="lg--solidline"></i>source reviewed</span>'
        '<span class="lg"><i class="lg--dashline"></i>unreviewed flow</span></div>'
        "<p>Cards group modules by their job. Dashed cards are actors outside the code. "
        "A flow names what travels between cards. A solid internal line records a source "
        "review whose references resolve. A short dashed line has structural evidence: an "
        "import, shared module or named mechanism. A long dashed line is declared without "
        "that evidence. Both dashed states still need review of direction and artifact. "
        "External flows cross the code boundary. None records execution. "
        "A layer shows flows that answer one question. "
        "A journey follows an authored operation step by step. A dot marks a note. "
        "A stacked card opens a map inside.</p>"
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
        "<p>Extraction could not resolve these records. The missing information limits "
        "what this map can establish. Read the exact finding, fix its source or extractor "
        "configuration, then run <code>systemap refresh</code> in the terminal.</p>"
        + "".join(f"<p><code>{esc(line)}</code></p>" for line in provenance["unknown"])
        + "</details>"
    )


def build(
    cfg: Config,
    model: Model,
    meaning: Meaning,
    t: dict[str, Any],
    facts: dict[str, Any],
    ch: dict[str, Any],
    nesting: Nesting | None = None,
) -> str:
    """Generate a workspace from facts and meaning, with no runtime dependencies."""
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
    data = json.loads(detail)
    states = {cid: rec["state"] for cid, rec in data.items() if cid != "_meta"}
    review = (
        nesting.review
        if nesting.review is not None
        else page_data.review(
            cfg, model, meaning, facts, f"{nesting.path}: " if nesting.path else ""
        )
    )
    payload: dict[str, Any] = {
        "sources": page_data.sources(model, facts),
        "review": review,
        "comparison": page_data.comparison(ch),
        "provenance": page_data.provenance(cfg, facts, nesting.model_file),
        "regions": [
            {"label": r.label, "ids": [c.id for c in model.components if c.region == r.id]}
            for r in model.regions
        ],
    }
    change_svg, change_detail = "", ""
    if ch.get("has_change") or ch.get("comparison_requested"):
        change_svg, change_detail = render_schematic(
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
        )
    n_actors = sum(c.kind == "actor" for c in model.components)
    cards = counted(len(model.components) - n_actors, n_actors)
    schemes = list(t.get("schemes") or {t["scheme"]: t})
    title = f"{cfg.name} system map" + (f": {nesting.path}" if nesting.path else "")
    o = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<title>{esc(title)}</title><link rel="icon" href="{FAVICON}">',
        "<script>(function(){var s=null;try{s=localStorage.getItem("
        f"{json.dumps(SCHEME_KEY)})}}catch(e){{}}"
        f"if({json.dumps(schemes)}.indexOf(s)<0){{s=(window.matchMedia&&"
        "window.matchMedia('(prefers-color-scheme: light)').matches)?"
        f"{json.dumps(theme_mod.LIGHT_SCHEME)}:{json.dumps(t['scheme'])}}}"
        "document.documentElement.setAttribute('data-theme',s)})();</script>",
        f"<style>{panel_css(t, variables=True)}{CSS.replace('{ROOT}', theme_mod.root_css(t))}"
        f"{page_atlas.CSS}"
        '</style></head><body data-mode="understand">',
        _header(cfg, model, meaning, facts, nesting, cards),
        '<main class="main"><section class="map" id="map" aria-label="System map">'
        '<span id="activity-label" hidden></span><h2 id="activity-question" class="sr-only">'
        "What are the parts, and how do they fit?</h2>",
        _map_key(t, model),
        _controls(model, meaning, t),
        _trace_controls(meaning),
        '<div class="lstrip" id="lstrip" aria-live="polite"></div>'
        '<div class="atlas" id="atlas" aria-label="Reading view of the system" hidden></div>',
        '<div class="spatial-map" id="spatialmap">'
        f'<div class="mapwrap" id="mapwrap"><div class="stage" id="stage">{system_svg}'
        '</div></div></div><p class="hint">Scroll to zoom. Drag to pan. Fit shows the whole map. '
        "Tab reaches cards and flow labels. Enter inspects. Arrow keys switch layers or journey "
        "steps. Escape returns to the previous view.</p>"
        '<p id="linkstatus" role="status" aria-live="polite"></p>'
        '<div class="map-actions"><button type="button" id="resetmap">Fit map</button>'
        '<button type="button" data-mode="understand">Find a part</button>'
        '<button type="button" data-mode="trace">Choose a journey</button>'
        '<button type="button" data-mode="review">Review stored findings</button></div>',
        '<p class="hint">Double-click a card that opens a map, or press Enter on it '
        "a second time in the spatial drawing, to read the map inside.</p>"
        if nesting.opens
        else "",
        "</section>",
        _inspector(),
        '</main><section class="reference" aria-label="Map records">',
        _index(model, meaning, states, cfg),
        _journeys(meaning),
        '<section id="review" class="review-records"><h2>Review the stored snapshot</h2>',
        _review_index(review),
        _change(ch, change_svg),
        "</section>",
        '<details class="map-links"><summary>Maps inside</summary>'
        + ", ".join(
            f'<a href="{esc(child["href"])}">{esc(child["name"])}</a>'
            for child in nesting.opens.values()
        )
        + "</details>"
        if nesting.opens
        else "",
        _rules(model),
        _commands(ch),
        _unknown_provenance(payload["provenance"]),
        "</section>",
        _submap(cfg, nesting),
        '<footer class="foot">Generated from '
        f"<code>{esc(cfg.out_dir)}/{esc(cfg.facts_file)}</code> and "
        f"<code>{esc(nesting.model_file)}</code>. "
        "HEAD at extraction was "
        f"<code>{esc(facts.get('built_at_commit') or 'not recorded')}</code>. "
        "Extraction reads the working tree, which can contain uncommitted changes. "
        "This page cannot detect later changes. Run <code>systemap refresh</code> "
        "in the project terminal to update it.</footer>",
        "<script>window.systemapWorkspace="
        + json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")
        + ";</script>",
        interactive_script(t, "schematic", "panel", detail, variables=True),
    ]
    if change_svg:
        o.append(interactive_script(t, "changemap", "change-panel", change_detail, variables=True))
    o += [f"<script>{JS}</script>", f"<script>{page_atlas.SCRIPT}</script>", "</body></html>"]
    return "\n".join(o) + "\n"
