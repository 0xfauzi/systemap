"""Scoped scene, evidence and inspector styles for pages and figures."""

from __future__ import annotations

from typing import Any

from systemap.theme import Palette


def _svg_style(svg_id: str, t: Palette) -> str:
    """Selection preserves readable card text and each flow's evidence pattern."""
    s = f"#{svg_id}"
    return (
        "<style>"
        f"{s} .node{{cursor:pointer}}"
        f"{s} .node.subject .node__box{{stroke:var(--subject)}}"
        f"{s} .node.subject rect.node__mark{{stroke:var(--subject)}}"
        f"{s} .node.subject path.node__mark{{fill:var(--subject)}}"
        f"{s} .node.sel .node__box{{stroke:{t['accent']};stroke-width:2.6}}"
        f"{s} .node.endpoint .node__box{{stroke:{t['accent']};stroke-width:2}}"
        f"{s} .node.meas .node__box{{stroke:{t['steel']};stroke-width:2.2}}"
        f"{s} .node.acts .node__box{{stroke:{t['accent']};stroke-width:2.4}}"
        f"{s} .node__ring{{display:none;fill:none;stroke:{t['steel']};stroke-width:1.6}}"
        f"{s} .node.meas .node__ring{{display:inline}}"
        f"{s} .node__selection{{display:none}}"
        f"{s} .node.sel .node__selection,{s} .node.endpoint .node__selection{{display:inline}}"
        f"{s} .node:focus-visible{{outline:none}}"
        f"{s} .node:focus-visible .node__box{{stroke:{t['accent']};stroke-width:2.6}}"
        f"{s} .node:hover .node__box{{stroke-width:1.8}}"
        f"{s} .flow{{transition:stroke-width .18s ease-out}}"
        f"{s} .flow.off:not(.peek),{s} .flowlbl.off:not(.peek){{display:none}}"
        f"{s} .flow.dim{{stroke-opacity:.38}}"
        f"{s} .flow.hot{{stroke-opacity:1;stroke-width:2.6}}"
        f"{s} .flow.peek{{stroke-opacity:1;stroke-width:2.2}}"
        f"{s} .flow.moving,{s} .flowtrace.moving{{animation:systemapflow 1.8s linear infinite}}"
        f"{s} .flow.moving[data-evidence=structural]{{animation-name:systemapstructural}}"
        f"{s} .flowtrace{{fill:none;stroke:{t['ink']};stroke-width:2;"
        "stroke-dasharray:1 11;stroke-linecap:round;pointer-events:none}"
        f"{s} .flowlbl{{cursor:pointer;outline:none}}"
        f"{s} .flowlbl text{{pointer-events:none}}"
        f"{s} .flowlbl.hot text{{fill:{t['accent']};font-weight:600}}"
        f"{s} .flowlbl:focus-visible .flowlbl__hit{{stroke:{t['accent']};stroke-width:1.5}}"
        f"{s}{{width:100%;height:auto;display:block;overflow:hidden;touch-action:none;cursor:grab}}"
        f"{s}.panning{{cursor:grabbing}}"
        f"{s} .zone__h{{cursor:zoom-in;-webkit-user-select:none;user-select:none}}"
        "@keyframes systemapflow{to{stroke-dashoffset:-12}}"
        "@keyframes systemapstructural{to{stroke-dashoffset:-7}}"
        f"@media print{{{s} .view{{transform:none!important}}}}"
        f":root[data-reduce-motion=true] {s} .moving{{animation:none!important}}"
        "@media (prefers-reduced-motion:reduce){"
        f"{s} .flow.hot{{animation:none}}"
        f"{s} .moving{{animation:none!important}}"
        f"{s} .node,{s} .flow,{s} .flowlbl{{transition:none}}}}"
        "</style>"
    )


def _defs(svg_id: str, t: Palette) -> str:
    """Arrowheads: one per layer colour, plus the change-map colours.

    Sized in user units so a thick focused edge and a hairline ghost edge
    carry the same head; the thickness is the emphasis, the head is the
    direction.
    """
    heads = {lid: t.layer(lid) for lid in t.t["layers"]}
    heads["change"] = t["change"]
    heads["reach"] = t["reach"]
    heads["selected"] = t["accent"]
    out = ["<defs>"]
    for name, colour in heads.items():
        out.append(
            f'<marker id="{svg_id}-m-{name}" viewBox="0 0 8 8" refX="7" refY="4" '
            f'markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" '
            f'orient="auto-start-reverse">'
            f'<path d="M0,0 L8,4 L0,8 z" fill="{colour}"/></marker>'
        )
    out.append("</defs>")
    return "".join(out)


def panel_css(t: dict[str, Any], variables: bool = False) -> str:
    """The exact relationship reads before connected parts and source details."""
    P = Palette(t, variables)
    return (
        f".systemap-panel{{font-family:{P['font_ui']};font-size:13px;line-height:1.5;"
        f"color:{P['ink_2']};background:{P['surface']};border:1px solid {P['line']};"
        "border-radius:8px;padding:1rem;min-height:3rem;overflow-wrap:anywhere}"
        f".systemap-panel:empty::before{{content:'Select a part or route label to inspect it.';"
        f"color:{P['ink_3']}}}"
        f".systemap-f__code{{font-family:{P['font_mono']};font-size:19px;color:{P['ink']};"
        "font-weight:600;line-height:1.25;margin:0;letter-spacing:-.02em}"
        f".systemap-f__plain{{font-size:14px;color:{P['ink_2']};line-height:1.45;margin:.35rem 0}}"
        f".systemap-f__kind{{color:{P['ink_3']};font-size:12px;margin:.2rem 0 .7rem}}"
        f".systemap-f__note{{margin:.75rem 0;padding:.65rem .75rem;"
        f"color:{P['ink']};background:{P['raised']};border-radius:6px}}"
        f".systemap-f__note b{{color:{P['warn']};margin-right:.35rem}}"
        f".systemap-f__relationship{{padding:1rem 0;margin:.7rem 0;"
        f"border-block:1px solid {P['line']}}}"
        f".systemap-f h4{{font-size:13px;font-weight:600;color:{P['ink']};margin:0 0 .55rem}}"
        f".systemap-f__artifact{{font-size:15px;font-weight:600;color:{P['ink']};"
        "margin:.3rem 0 .65rem}"
        ".systemap-f__endpoints{display:grid;grid-template-columns:1fr 1fr;gap:.5rem}"
        f".systemap-f__endpoint{{min-width:0;min-height:66px;display:grid;gap:.2rem;"
        f"text-align:left;padding:.65rem;border:1px solid {P['line_2']};border-radius:6px;"
        f"background:{P['bg']};color:{P['ink']};cursor:pointer;font:inherit}}"
        f".systemap-f__endpoint:hover{{border-color:{P['accent']}}}"
        f".systemap-f__endpoint small,.systemap-f__endpoint span{{font-size:11px;"
        f"color:{P['ink_3']}}}"
        f".systemap-f__endpoint code{{font-family:{P['font_mono']};font-size:12px;"
        "overflow-wrap:anywhere}"
        f".systemap-f__metadata{{color:{P['ink_3']};font-size:12px;margin:.65rem 0}}"
        f".systemap-f__state{{font-family:{P['font_mono']};margin-left:.5rem;color:{P['ink']}}}"
        f".systemap-f__state.declared,.systemap-f__state.structural{{color:{P['warn']}}}"
        f".systemap-f__say{{margin:.5rem 0;color:{P['ink']};font-size:13px;line-height:1.5}}"
        f".systemap-f__evidence{{font-family:{P['font_mono']};font-size:11.5px;"
        f"color:{P['ink_2']};margin:.5rem 0}}"
        f".systemap-f__reason,.systemap-f__hint{{font-size:12px;color:{P['ink_3']};margin:.5rem 0}}"
        f".systemap-f__review-warning{{font-size:12px;color:{P['warn']};margin:.65rem 0;"
        "overflow-wrap:anywhere}"
        ".systemap-f__review-warning p{margin:.4rem 0}"
        f".systemap-f__refs{{font-size:12px;color:{P['ink_2']};overflow-wrap:anywhere}}"
        ".systemap-f__refs ul,.systemap-f__review-warning ul{padding-left:1.2rem}"
        f".systemap-f summary{{cursor:pointer;min-height:44px;display:flex;align-items:center;"
        f"color:{P['ink']};font-weight:600;gap:.5rem}}"
        ".systemap-f summary::before{content:'+';font-weight:400}"
        ".systemap-f details[open]>summary::before{content:'−'}"
        ".systemap-f__wheel{margin:.2rem 0 .65rem}"
        ".systemap-f__wheel svg{width:100%;height:auto;display:block;margin:0 auto}"
        ".systemap-f__flow-list{display:grid;gap:.15rem}"
        f".systemap-f__flow-choice{{min-height:44px;display:grid;gap:.15rem;text-align:left;"
        f"padding:.6rem .7rem;border:0;border-radius:5px;background:none;color:{P['ink']};"
        "font:inherit;cursor:pointer;overflow-wrap:anywhere}"
        f".systemap-f__flow-choice span,.systemap-f__flow-choice small{{font-size:11.5px;"
        f"color:{P['ink_3']}}}"
        f".systemap-f__flow-choice:hover{{background:{P['bg']}}}"
        f".systemap-f__flow-choice[aria-pressed=true]{{background:{P['raised']};"
        f"box-shadow:inset 0 0 0 1px {P['accent']}}}"
        f".systemap-f__details{{margin-top:1rem;border-top:1px solid {P['line']};"
        "padding-top:.3rem}"
        f".systemap-f__does{{margin:.4rem 0;color:{P['ink_2']}}}"
        f".systemap-f__iface,.systemap-f__entry{{font-family:{P['font_mono']};font-size:11.5px;"
        f"color:{P['ink_2']};margin:.6rem 0;overflow-wrap:anywhere}}"
        ".systemap-f__modules{padding-left:1rem;margin:.4rem 0}"
        ".systemap-f__modules li{margin:.3rem 0}"
        f".systemap-f__rule{{color:{P['ink_2']};margin:.6rem 0}}"
        f".systemap-f__rule b{{font-family:{P['font_mono']};color:{P['violet']}}}"
        f".systemap-f__opens{{margin:.6rem 0;color:{P['ink_3']};font-size:12px}}"
        f".systemap-f__opens b{{font-weight:500;color:{P['ink']}}}"
        f".systemap-f__preview{{margin:.5rem 0;border-radius:6px;overflow:hidden;"
        f"background:{P['bg']}}}"
        ".systemap-f__preview svg{width:100%;height:auto;display:block}"
        f".systemap-f__open{{appearance:none;display:block;margin:.5rem 0;min-height:44px;"
        f"padding:0 .8rem;border-radius:6px;border:1px solid {P['accent']};background:none;"
        f"color:{P['accent']};font:inherit;cursor:pointer}}"
        f".systemap-f__open:hover{{background:{P['bg']}}}"
        f".systemap-f button:focus-visible,.systemap-f summary:focus-visible{{outline:2px solid "
        f"{P['accent']};outline-offset:2px}}"
        ".systemap-w__spoke{cursor:pointer;outline:none}"
        ".systemap-w__hit{stroke:transparent;stroke-width:26;fill:none;pointer-events:stroke}"
        ".systemap-w__line{fill:none;stroke-width:1.5;transition:stroke-width .12s ease-out}"
        f".systemap-w__verb{{font-family:{P['font_ui']};font-size:11px;font-weight:500;"
        f"text-anchor:middle;paint-order:stroke;stroke:{P['surface']};stroke-width:5;"
        "stroke-linejoin:round;pointer-events:none}"
        f".systemap-w__name{{font-family:{P['font_mono']};font-size:11px;font-weight:600;"
        f"fill:{P['ink']};pointer-events:none}}"
        f".systemap-w__centre rect{{fill:{P['raised']};stroke:{P['accent']};stroke-width:1.6}}"
        f".systemap-w__centre text{{font-family:{P['font_mono']};font-size:12px;font-weight:600;"
        f"fill:{P['ink']};text-anchor:middle}}"
        ".systemap-w__spoke.peek .systemap-w__line,.systemap-w__spoke:hover .systemap-w__line,"
        ".systemap-w__spoke:focus-visible .systemap-w__line{stroke-width:3.2}"
        f".systemap-w__spoke.peek .systemap-w__name,.systemap-w__spoke:hover .systemap-w__name,"
        f".systemap-w__spoke:focus-visible .systemap-w__name{{fill:{P['accent']}}}"
        f".systemap-w__empty{{font-family:{P['font_ui']};font-size:12px;fill:{P['ink_3']};"
        "text-anchor:middle}"
    )
