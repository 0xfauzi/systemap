"""Diagram and inspector styles for pages and figures."""

from __future__ import annotations

from typing import Any

from systemap.schematic_cards import PLAIN_FONT
from systemap.theme import Palette

# The stroke pattern of each evidence state, the same on the map and in the
# inspector swatches. A dash shows evidence and nothing else.
DASHES: dict[str, tuple[int, int]] = {"structural": (3, 4), "declared": (7, 5)}


def tok(P: Palette, key: str, *fallbacks: str) -> str:
    """Give a theme token that an older palette table can lack.

    With CSS variables, the value is `var(--key, fallback)`. With literal
    values, the value is the first key that the palette table contains."""
    if P.variables:
        tail = P[fallbacks[-1]]
        for name in reversed(fallbacks[:-1]):
            tail = f"var(--{name.replace('_', '-')}, {tail})"
        return f"var(--{key.replace('_', '-')}, {tail})"
    for name in (key, *fallbacks):
        value = P.t.get(name)
        if isinstance(value, str) and value:
            return value
    return P[fallbacks[-1]]


def _node_style(s: str, t: Palette) -> str:
    """Give the card states: quiet, selected or acting, endpoint, measured, focus, preview.

    Selection is a 1 px border and a 2 px ring in the accent color, with the
    highlight fill. Keyboard focus is a 2 px ink ring with a 3 px gap."""
    ink, accent, steel = t["ink"], t["accent"], t["steel"]
    line = tok(t, "card_line", "line_2")
    return (
        f"{s} .node{{cursor:pointer;outline:none;transition:opacity .16s ease-out}}"
        f'{s} .node [data-layer="job"] text{{font-family:{PLAIN_FONT};'
        "font-kerning:none;font-variant-ligatures:none}"
        # Only the page script sets --subject. A figure without the script
        # keeps the stroke that the renderer gives each card.
        f"{s}[data-live] .node.subject .node__box{{stroke:var(--subject,{line})}}"
        f"{s}[data-live] .node.subject rect.node__mark{{stroke:var(--subject,{line})}}"
        f"{s}[data-live] .node.subject path.node__mark{{fill:var(--subject,{line})}}"
        f"{s} .node.dim,{s} .node.quiet{{opacity:.32}}"
        f"{s} .node__ring,{s} .node__selection{{display:none}}"
        f"{s} .node__hl,{s} .node__halo{{display:none;pointer-events:none}}"
        f"{s} .node__hl{{fill:{tok(t, 'hl_soft', 'hl', 'accent_soft')}}}"
        f"{s} .node__halo{{fill:none;stroke:{ink};stroke-width:1.5;"
        "vector-effect:non-scaling-stroke}"
        f"{s} .node__box{{transition:stroke .16s ease-out,stroke-width .16s ease-out}}"
        f"{s} .node:not(.sel):not(.acts):hover .node__box{{stroke-width:1.8}}"
        f"{s}[data-live] .node:not(.sel):not(.acts):not(.endpoint):not(.subject):hover "
        f".node__box{{stroke:{t['ink_3']}}}"
        f"{s} .node.endpoint .node__box{{stroke:{accent};stroke-width:2}}"
        f"{s} .node.meas .node__box{{stroke:{steel};stroke-width:2}}"
        f"{s} .node.sel .node__box,{s} .node.acts .node__box{{stroke:{accent};stroke-width:3}}"
        f"{s} .node.sel .node__hl,{s} .node.acts .node__hl{{display:inline}}"
        f"{s} .node.peekend .node__halo{{display:inline}}"
        f"{s} .node:focus-visible .node__halo{{display:inline;stroke-width:2}}"
    )


def _flow_style(s: str, t: Palette, base: bool) -> str:
    """Give the line states: at rest, selected, preview, the cue and the labels.

    At rest a line is 1.6 px at every zoom. The selected line is 3 px in the
    accent color over the highlighter line. A preview line is 2.6 px and the
    other lines go dim. The change map sets its own line widths."""
    ink, accent = t["ink"], t["accent"]
    hl = tok(t, "hl", "accent_soft")
    ground = tok(t, "map", "bg")
    rest = (
        f"{s} .flow,{s} .flowtrace,{s} .flowhl{{vector-effect:non-scaling-stroke}}"
        f"{s} .flow{{stroke-width:1.6;stroke-opacity:1}}"
        f"{s}.focused .flow{{stroke-width:1.8}}"
        if base
        else ""
    )
    return (
        rest + f"{s} .flow{{cursor:pointer;pointer-events:stroke;outline:none;"
        "transition:opacity .12s ease-out,stroke-width .12s ease-out,visibility 0s}"
        f"{s} .flow.off:not(.peek),{s} .flowlbl.off:not(.peek){{opacity:0;visibility:hidden;"
        "pointer-events:none;transition:opacity .16s ease-out,visibility 0s linear .16s}"
        f"{s} .flow.peek{{stroke-opacity:1;stroke-width:2.6}}"
        f"{s} .flow.hot{{stroke-opacity:1;stroke-width:3}}"
        f"{s}.peeking .flow:not(.peek),{s}.peeking .flowlbl:not(.peek){{opacity:.35}}"
        f"{s} .flowhl{{fill:none;stroke:{tok(t, 'hl_line', 'hl', 'accent_soft')};"
        "stroke-width:11;stroke-opacity:.9;stroke-linecap:round;stroke-linejoin:round;"
        "pointer-events:none}"
        f"{s} .flowdot{{fill:{accent};stroke:{hl};stroke-width:10;paint-order:stroke;"
        "pointer-events:none}"
        f"{s} .flowtrace{{stroke-width:2.6;pointer-events:none}}"
        f"{s} .flowlbl{{cursor:pointer;outline:none;"
        "transition:opacity .16s ease-out,visibility 0s}"
        f"{s} .flowlbl text{{pointer-events:none;fill:{ink};stroke:{ground}}}"
        f"{s} .flowlbl__chip{{fill:{ground};pointer-events:none}}"
        f"{s} .flowlbl.hot text{{fill:{accent};font-weight:600}}"
        f"{s} .flowlbl.peek .flowlbl__chip{{stroke:{t['line_2']};stroke-width:1}}"
        f"{s} .flowlbl.cueing{{opacity:0}}"
        f"{s} .flowlbl:focus-visible .flowlbl__hit{{stroke:{ink};stroke-width:1.5}}"
    )


def _svg_style(svg_id: str, t: Palette) -> str:
    """Give the card states, the selection, the preview and the direction cue.

    Selection is the accent ring and the highlight fill. Keyboard focus is an
    ink ring with a gap. A preview makes one line thicker and dims the other
    lines. Line dashes come from the evidence and do not change."""
    s = f"#{svg_id}"
    return (
        "<style>"
        + _node_style(s, t)
        + _flow_style(s, t, svg_id != "changemap")
        + f"{s}{{width:100%;height:auto;display:block;overflow:hidden;touch-action:none;"
        "cursor:grab}"
        f"{s}.panning{{cursor:grabbing}}"
        f"{s} .zone__h{{cursor:zoom-in;-webkit-user-select:none;user-select:none}}"
        f"@media print{{{s} .view{{transform:none!important}}}}"
        f":root[data-reduce-motion=true] {s} *{{transition:none!important;"
        "animation:none!important}"
        f"@media (prefers-reduced-motion:reduce){{{s} *{{transition:none!important;"
        "animation:none!important}}"
        "</style>"
    )


def _defs(svg_id: str, t: Palette) -> str:
    """Make arrowheads for layer and change colors.

    Arrowheads use SVG user units. Line thickness changes emphasis without
    a change to the arrowhead size. The arrowhead shows direction."""
    heads = {lid: t.layer(lid) for lid in t.t["layers"]}
    heads["change"] = t["change"]
    heads["reach"] = t["reach"]
    heads["selected"] = t["accent"]
    out = ["<defs>"]
    for name, color in heads.items():
        out.append(
            f'<marker id="{svg_id}-m-{name}" viewBox="0 0 8 8" refX="7" refY="4" '
            f'markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" '
            f'orient="auto-start-reverse">'
            f'<path d="M0,0 L8,4 L0,8 z" fill="{color}"/></marker>'
        )
    out.append("</defs>")
    return "".join(out)


def _swatches() -> str:
    """Give the short line before each flow in the inspector, with its evidence dash."""
    rules = [
        ".systemap-f__swatch{display:inline-block;width:18px;height:2px;flex:none;"
        "background:var(--c,currentColor)}"
    ]
    for state, (dash, gap) in DASHES.items():
        rules.append(
            f'.systemap-f__swatch[data-dash="{state}"]{{background:repeating-linear-'
            f"gradient(90deg,var(--c,currentColor) 0 {dash}px,"
            f"transparent {dash}px {dash + gap}px)}}"
        )
    return "".join(rules)


def _panel_text(P: Palette) -> str:
    """Give the head row, the names, the section labels and the rows."""
    hl = tok(P, "hl", "accent_soft")
    caps = (
        f"font:600 11px/16px {P['font_mono']};letter-spacing:.08em;text-transform:uppercase;"
        f"color:{P['ink_3']};margin:0"
    )
    return (
        ".systemap-f{display:flex;flex-direction:column;gap:18px;min-width:0}"
        ".systemap-f>*{margin:0}"
        ".systemap-f__head{display:flex;justify-content:space-between;align-items:center;gap:12px;"
        "min-height:16px}"
        ".systemap-f__head--room{padding-right:70px}"
        f".systemap-f__eyebrow,.systemap-f__label{{{caps}}}"
        f".systemap-f__clear{{height:28px;padding:0 10px;border:1px solid {P['line_2']};"
        f"border-radius:6px;background:none;color:{P['ink_2']};font:12px {P['font_ui']};"
        "cursor:pointer;flex:none}"
        f".systemap-f__clear:hover{{color:{P['ink']};background:{P['raised']}}}"
        ".systemap-f__title{display:flex;flex-direction:column;gap:4px}"
        f".systemap-f__code{{font:600 19px/25px {P['font_mono']};color:{P['ink']};margin:0;"
        "letter-spacing:-.01em;overflow-wrap:anywhere}"
        f".systemap-f__plain{{font:15px/20px {P['font_ui']};color:{P['ink_2']};margin:0}}"
        f".systemap-f__does{{font:13px/20px {P['font_ui']};color:{P['ink_2']}}}"
        ".systemap-f__section{display:flex;flex-direction:column;gap:8px;min-width:0}"
        ".systemap-f__label-row{display:flex;justify-content:space-between;align-items:center;"
        "gap:10px;height:16px}"
        f".systemap-f__count{{font:12px/16px {P['font_mono']};color:{P['ink_3']}}}"
        ".systemap-f__flow-list{display:flex;flex-direction:column;gap:18px}"
        ".systemap-f__flow-group{display:grid;grid-template-columns:18px minmax(0,1fr) auto;"
        "column-gap:10px;row-gap:0;align-items:center;min-width:0}"
        ".systemap-f__flow-group{margin-bottom:-3.5px}"
        ".systemap-f__flow-group>.systemap-f__label-row{grid-column:1/-1;margin-bottom:4.5px}"
        ".systemap-f__flow-choice{grid-column:1/-1;display:grid;"
        "grid-template-columns:18px minmax(0,1fr) auto;grid-template-columns:subgrid;"
        "align-items:center;column-gap:10px;min-height:25px;padding:3px 0;margin:0;"
        f"border:0;border-radius:4px;background:none;color:{P['ink']};text-align:left;"
        f"font:13px/18px {P['font_ui']};cursor:pointer}}"
        ".systemap-f__flow-choice b{font-weight:400;min-width:0;overflow-wrap:anywhere}"
        f".systemap-f__route{{font:12px/18px {P['font_mono']};color:{P['ink_3']};"
        "white-space:nowrap;text-align:left}"
        # A shadow on each side widens the row color without page overflow.
        f".systemap-f__flow-choice:hover{{background:{P['raised']};"
        f"box-shadow:-6px 0 0 {P['raised']},6px 0 0 {P['raised']}}}"
        f".systemap-f__flow-choice[aria-pressed=true]{{background:{hl};"
        f"box-shadow:-6px 0 0 {hl},6px 0 0 {hl}}}"
        ".systemap-f__sr{position:absolute;width:1px;height:1px;overflow:hidden;"
        "clip:rect(0 0 0 0);white-space:nowrap}"
    )


def _panel_blocks(P: Palette) -> str:
    """Give the sequence buttons, the module chips, the rules and the details."""
    return (
        f".systemap-f__seq{{display:flex;justify-content:space-between;align-items:flex-start;"
        f"gap:10px;width:100%;padding:8px 10px;border:1px solid {P['line']};border-radius:8px;"
        f"background:none;color:{P['ink']};font:13px/18px {P['font_ui']};text-align:left}}"
        "button.systemap-f__seq{cursor:pointer}"
        f"button.systemap-f__seq:hover{{border-color:{P['line_2']};background:{P['raised']}}}"
        f".systemap-f__steps{{font:12px {P['font_mono']};color:{P['ink_3']};"
        "white-space:nowrap}"
        ".systemap-f__chips{display:flex;flex-wrap:wrap;gap:6px}"
        f".systemap-f__chip{{font:12px/16px {P['font_mono']};color:{P['ink_2']};"
        f"border:1px solid {P['line_2']};border-radius:4px;padding:3px 7px;overflow-wrap:anywhere}}"
        f".systemap-f__iface{{font:12px/18px {P['font_mono']};color:{P['ink_3']};margin:0;"
        "overflow-wrap:anywhere}"
        ".systemap-f__rules{display:grid;grid-template-columns:24px minmax(0,1fr);gap:6px 8px;"
        f"margin:0;font:13px/19px {P['font_ui']};color:{P['ink_2']}}}"
        f".systemap-f__rules b{{font:12px/19px {P['font_mono']};color:{P['ink_3']}}}"
        f".systemap-f__note{{padding:10px 12px;color:{P['ink']};background:{P['raised']};"
        "border-radius:6px;font-size:13px;line-height:19px}"
        f".systemap-f__note b{{font-weight:600;margin-right:.35rem}}"
        f".systemap-f__opens{{color:{P['ink_3']};font-size:12px}}"
        f".systemap-f__opens b{{font-weight:500;color:{P['ink']}}}"
        f".systemap-f__preview{{border-radius:6px;overflow:hidden;background:{P['bg']}}}"
        ".systemap-f__preview svg{width:100%;height:auto;display:block}"
        f".systemap-f__open{{appearance:none;display:block;min-height:32px;padding:0 12px;"
        f"border-radius:6px;border:1px solid {P['line_2']};background:none;color:{P['ink']};"
        f"font:13px {P['font_ui']};cursor:pointer;justify-self:start}}"
        f".systemap-f__open:hover{{background:{P['raised']}}}"
        f".systemap-f__details{{border-top:1px solid {P['line']};padding-top:4px}}"
        f".systemap-f__details p{{margin:.5rem 0;font-size:13px;line-height:19px;"
        f"color:{P['ink_2']}}}"
        f".systemap-f__entry{{font-family:{P['font_mono']};font-size:12px!important;"
        f"overflow-wrap:anywhere}}"
        f".systemap-f__kind{{color:{P['ink_3']}}}"
    )


def _panel_flow(P: Palette) -> str:
    """Give the selected flow box: the selection border and the highlight fill."""
    fill = tok(P, "hl_soft", "hl", "accent_soft")
    ground = tok(P, "map", "bg")
    return (
        f".systemap-f__relationship{{display:flex;flex-direction:column;gap:10px;padding:12px;"
        f"border:1px solid {P['accent']};border-radius:8px;background:{fill};color:{P['ink']}}}"
        ".systemap-f__relationship[hidden]{display:none}"
        ".systemap-f__relationship>*{margin:0}"
        f".systemap-f__artifact{{display:flex;align-items:center;gap:10px;"
        f"font:600 15px/20px {P['font_ui']};color:{P['ink']}}}"
        ".systemap-f__endpoints{display:grid;grid-template-columns:1fr 1fr;gap:8px}"
        f".systemap-f__endpoint{{min-width:0;display:grid;gap:2px;text-align:left;padding:8px 10px;"
        f"border:1px solid {P['line_2']};border-radius:6px;background:{ground};color:{P['ink']};"
        f"cursor:pointer;font:12px/16px {P['font_ui']}}}"
        f".systemap-f__endpoint:hover{{border-color:{P['ink_3']}}}"
        f".systemap-f__endpoint small{{font:600 11px/16px {P['font_mono']};letter-spacing:.08em;"
        f"text-transform:uppercase;color:{P['ink_3']}}}"
        f".systemap-f__endpoint code{{font:600 13px/16px {P['font_mono']};overflow-wrap:anywhere}}"
        f".systemap-f__endpoint span{{color:{P['ink_3']}}}"
        f".systemap-f__metadata{{display:flex;flex-wrap:wrap;align-items:center;gap:8px;"
        f"font:12px/16px {P['font_ui']};color:{P['ink_3']}}}"
        f".systemap-f__state{{display:inline-flex;align-items:center;gap:6px;"
        f"font:12px/16px {P['font_mono']};color:{P['ink']}}}"
        ".systemap-f__state::before{content:'';display:inline-block;width:18px;height:2px;"
        "background:currentColor}"
        + "".join(
            f".systemap-f__state.{state}::before{{background:repeating-linear-gradient(90deg,"
            f"currentColor 0 {dash}px,transparent {dash}px {dash + gap}px)}}"
            for state, (dash, gap) in DASHES.items()
        )
        + f".systemap-f__say{{font:13px/20px {P['font_ui']};color:{P['ink']}}}"
        f".systemap-f__evidence{{font:12px/18px {P['font_mono']};color:{P['ink_2']}}}"
        f".systemap-f__reason,.systemap-f__hint{{font:12px/18px {P['font_ui']};color:{P['ink_3']}}}"
        f".systemap-f__review-warning{{font:12px/18px {P['font_ui']};color:{P['ink']};"
        f"border-left:2px solid {P['ink_3']};padding-left:8px;overflow-wrap:anywhere}}"
        ".systemap-f__review-warning p{margin:0 0 .3rem}"
        f".systemap-f__refs{{font-size:12px;color:{P['ink_2']};overflow-wrap:anywhere}}"
        ".systemap-f__refs ul,.systemap-f__review-warning ul{padding-left:1.2rem;margin:.3rem 0}"
    )


def _scope(css: str) -> str:
    """Put each inspector rule under `.systemap-f`.

    The page has general rules for panel paragraphs and headings. The higher
    specificity keeps the inspector type sizes without `!important`."""
    out: list[str] = []
    for rule in css.split("}"):
        if "{" not in rule:
            out.append(rule)
            continue
        head, body = rule.split("{", 1)
        selectors = [
            f".systemap-f {sel.strip()}" if "systemap-f__" in sel else sel.strip()
            for sel in head.split(",")
        ]
        out.append(",".join(selectors) + "{" + body)
    return "}".join(out)


def panel_css(t: dict[str, Any], variables: bool = False) -> str:
    """Give the inspector styles: the component, its flows and the selected flow.

    The layout follows the focus design: a head row, the name, the lists of
    flows that the component receives and sends, its sequences and its modules.
    Details stay below in closed sections."""
    P = Palette(t, variables)
    return (
        f".systemap-panel{{font-family:{P['font_ui']};font-size:13px;line-height:1.5;"
        f"color:{P['ink_2']};background:{P['surface']};border:1px solid {P['line']};"
        "border-radius:8px;padding:1rem;min-height:3rem;overflow-wrap:anywhere}"
        f".systemap-panel:empty::before{{content:'Select a card or flow path to examine it.';"
        f"color:{P['ink_3']}}}"
        + _scope(_swatches() + _panel_text(P) + _panel_blocks(P) + _panel_flow(P))
        + f".systemap-f summary{{cursor:pointer;min-height:36px;display:flex;align-items:center;"
        f"color:{P['ink_2']};font:13px/18px {P['font_ui']};gap:.5rem}}"
        ".systemap-f summary::before{content:'+';width:.8em}"
        ".systemap-f details[open]>summary::before{content:'\\2212'}"
        f".systemap-f button:focus-visible,.systemap-f summary:focus-visible{{outline:2px solid "
        f"{P['ink']};outline-offset:3px}}"
    )
