"""The Changes view: the change map, its toolbar and its panel.

The page has a revision comparison only when `systemap render --base REF`
makes it. The source comparison uses the model and the stored source facts of
this page for both revisions. It has no flow evidence for the base revision, so
the toolbar offers Hold B (the map without change marks) and no base
evidence control. The panel text comes from the comparison counts, the flow
evidence in the change map detail, and the map changes of `page_changes_map`
(the committed model at the base against the model of this page). It does not
claim more than these records show."""

from __future__ import annotations

import html
from typing import Any

from systemap import page_changes_map
from systemap.page_changes_script import EMPTY_SCRIPT as EMPTY_SCRIPT
from systemap.page_changes_script import SCRIPT as SCRIPT
from systemap.schematic_change import tests_only as tests_only


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def has_comparison(ch: dict[str, Any]) -> bool:
    """Tell if the page was made with a base revision."""
    return bool(ch.get("has_change") or ch.get("comparison_requested"))


def _parts(ch: dict[str, Any]) -> dict[str, Any]:
    return dict(ch.get("per_component") or ch.get("parts") or {})


def _source(ch: dict[str, Any]) -> list[str]:
    """Give the changed components with changed source, in name order."""
    return sorted(set(ch.get("direct", ())) - tests_only(ch))


def _short(revision: str) -> str:
    return revision[:7]


def _names(ids: list[str]) -> str:
    """Join names for a sentence: A, B and C."""
    if len(ids) < 2:
        return "".join(ids)
    return ", ".join(ids[:-1]) + " and " + ids[-1]


def _prefix(modules: list[str]) -> str:
    """Give the package prefix that all modules share, such as "systemap."."""
    heads = {m.split(".", 1)[0] for m in modules if "." in m}
    if len(heads) != 1 or any("." not in m for m in modules):
        return ""
    return heads.pop() + "."


def _ref(name: str, revision: str) -> str:
    return (
        f'<span class="chg-ref" title="{esc(revision)}"><span>{esc(name)}</span>'
        f"<code>{esc(_short(revision))}</code></span>"
    )


def toolbar(ch: dict[str, Any]) -> str:
    """Give the Changes toolbar row content, or nothing without a comparison."""
    if not has_comparison(ch):
        return ""
    return (
        '<span class="chg-bar__k">Compare</span>'
        + _ref(ch.get("base", ""), ch.get("base_revision", ""))
        + '<span class="chg-bar__k">to</span>'
        + _ref(ch.get("head", ""), ch.get("head_revision", ""))
        + '<span class="chg-bar__sep" aria-hidden="true"></span>'
        '<button type="button" class="chg-hold" id="chg-hold" aria-pressed="false" '
        'title="The page has no flow evidence for the base revision.">'
        "<kbd>B</kbd><span>Hold B to show the map without change marks</span></button>"
    )


def _summary(ch: dict[str, Any]) -> str:
    """Give the summary sentence that the counts support."""
    source, tests = _source(ch), sorted(tests_only(ch))
    if not ch.get("has_change"):
        return "The comparison found no source difference between the resolved revisions."
    if source:
        verb = "has" if len(source) == 1 else "have"
        return f"{_names(source)} {verb} changed source."
    if tests:
        return f"Only the tests of {_names(tests)} changed."
    return (
        f"{ch.get('files', 0)} files changed. "
        "No component of this map has a source module in these files."
    )


def _card(cid: str, modules: list[str], prefix: str) -> str:
    short = [m.removeprefix(prefix) for m in modules]
    chips = "".join(
        f'<code class="chg-chip" title="{esc(m)}">{esc(n)}</code>'
        for m, n in zip(modules, short, strict=True)
    )
    return (
        f'<article class="chg-card" data-change-card="{esc(cid)}">'
        f'<button type="button" class="chg-card__head" data-change-go="{esc(cid)}" '
        'aria-pressed="false"><span class="chg-tag chg-tag--changed">CHANGED</span>'
        f'<b>{esc(cid)}</b><span class="chg-card__mods">{esc(", ".join(short))}</span>'
        '<span class="chg-card__flag" hidden>review necessary</span></button>'
        + (f'<div class="chg-chips">{chips}</div>' if chips else "")
        + '<p class="chg-card__note" hidden></p><div class="chg-card__detail" hidden></div>'
        "</article>"
    )


def _row(tag: str, ids: list[str], text: str) -> str:
    names = ", ".join(
        f'<button type="button" class="chg-name" data-change-go="{esc(i)}">{esc(i)}</button>'
        for i in ids
    )
    return (
        f'<span class="chg-tag chg-tag--{tag.lower()}">{tag}</span>'
        f'<span class="chg-row" data-change-row="{tag.lower()}">{names}: {text}</span>'
    )


def _rows(ch: dict[str, Any]) -> str:
    tests, imports = sorted(tests_only(ch)), sorted(ch.get("adjacent", ()))
    out = ""
    if tests:
        out += _row("TESTS", tests, "only their tests changed.")
    if imports:
        pronoun = "it imports" if len(imports) == 1 else "they import"
        out += _row(
            "IMPORTS",
            imports,
            f"{pronoun} changed source. An import does not show an effect on the program.",
        )
    return f'<div class="chg-rows">{out}</div>' if out else ""


def comparison_limits(ch: dict[str, Any]) -> str:
    """Give the limits of the comparison as paragraphs."""
    out = [
        page_changes_map.limit(ch.get("map")),
        "<p>Flow evidence comes from the stored source facts of this page. The page has no "
        "flow evidence for the base revision.</p>",
    ]
    if ch.get("comparison_base"):
        out.append(
            "<p>Source differences start at the merge base "
            f"<code>{esc(_short(ch['comparison_base']))}</code>.</p>"
        )
    if not ch.get("reach_known", False):
        out.append(
            "<p>No import data shows connections for this change. "
            "Effects on other modules are unknown.</p>"
        )
    if ch.get("unparsed"):
        out.append(
            "<p>systemap could not parse the source differences for <code>"
            + esc(", ".join(ch["unparsed"]))
            + "</code>. Correct the source or extractor error. Then run "
            "<code>systemap render --base REF</code> in the terminal.</p>"
        )
    for cid, data in _parts(ch).items():
        for module, records in data.get("unknown", {}).items():
            for revision, issues in records.items():
                out.extend(_unknown(cid, module, revision, issue) for issue in issues)
    return "".join(out)


def _unknown(cid: str, module: str, revision: str, issue: dict[str, Any]) -> str:
    return (
        f"<p>Unknown {esc(revision)} surface for <code>{esc(cid)} / {esc(module)}</code>: "
        f"{esc(issue.get('reason', 'systemap could not read the source.'))} "
        f"(line {esc(issue.get('line', 0))}, column {esc(issue.get('column', 0))}).</p>"
    )


def panel(ch: dict[str, Any]) -> str:
    """Give the Changes panel. The script adds the flows and the sequences."""
    start = '<aside class="change-panel" id="change-panel" aria-label="Changes" hidden>'
    if not has_comparison(ch):
        return (
            start + '<p class="chg-cap" id="changes">CHANGES</p>'
            '<p class="chg-note">This page has no revision comparison.</p></aside>'
        )
    parts, source = _parts(ch), _source(ch)
    prefix = _prefix(sorted({m for cid in source for m in parts[cid].get("modules", [])}))
    base, head = _short(ch.get("base_revision", "")), _short(ch.get("head_revision", ""))
    title = (ch.get("pr") or {}).get("title", "")
    return (
        start + '<div class="chg-head"><h2 class="chg-cap" id="changes">CHANGES</h2>'
        f'<span class="chg-range" aria-label="{esc(base)} to {esc(head)}">'
        f"{esc(base)} → {esc(head)}</span></div>"
        + (f'<p class="chg-pr">{esc(title)}</p>' if title else "")
        + '<p class="chg-sum" id="chg-summary"><span data-chg-where></span>'
        f"<span>{esc(_summary(ch))}</span><span data-chg-flows></span></p>"
        '<section class="chg-parts" id="chg-parts" aria-label="Components">'
        + "".join(_card(cid, parts[cid].get("modules", []), prefix) for cid in source)
        + _rows(ch)
        + "</section>"
        + page_changes_map.section(ch.get("map"))
        + '<section class="chg-sec" id="chg-flows" aria-label="Flows to examine" hidden></section>'
        '<section class="chg-sec" id="chg-seqs" aria-label="Sequences" hidden></section>'
        '<section class="chg-limits" aria-label="Limits of the comparison">'
        '<h3 class="chg-cap">NOT IN THIS COMPARISON</h3>' + comparison_limits(ch) + "</section>"
        "</aside>"
    )


COMMAND = "systemap render --base REF"


def empty() -> str:
    """Give the Changes view text for a page without a comparison."""
    return (
        '<div class="change-empty"><h2>This page has no revision comparison</h2>'
        "<p>A revision comparison shows the components with changed source between two "
        "revisions. Make the page again with a base revision. Then open Changes.</p>"
        f'<div class="chg-cmd"><code>{COMMAND}</code><button type="button" '
        f'data-copy="{COMMAND}" aria-label="Copy the command">Copy</button></div>'
        '<p class="chg-hint">Replace REF with a branch, tag or commit, for example '
        "<code>main</code>.</p></div>"
    )


def stage(ch: dict[str, Any], svg: str) -> str:
    """Give the Changes view map area: the change map, or the empty text."""
    start = '<section id="change" class="change-view" aria-label="Changes" hidden>'
    if not svg:
        return start + empty() + "</section>"
    return start + f'<div class="stage">{svg}</div></section>'


CSS = (
    r"""
/* ---- Changes view: toolbar -------------------------------------------- */
.change-controls .chg-bar__k{font-size:12px;color:var(--ink-3)}
.change-controls .chg-bar__k+.chg-ref~.chg-bar__k{font-size:13px}
.chg-ref{display:inline-flex;align-items:center;gap:8px;height:32px;padding:0 12px;
  border:1px solid var(--line-2);border-radius:6px;background:var(--card,var(--card-built));
  font-size:13px;color:var(--ink);white-space:nowrap;min-width:0}
.chg-ref span{overflow:hidden;text-overflow:ellipsis}
.chg-ref code{font:12px var(--fm);color:var(--ink-3)}
.chg-bar__sep{width:1px;height:24px;background:var(--line);margin:0 6px}
.chg-hold{display:inline-flex;align-items:center;gap:8px;height:32px;min-height:32px;
  padding:0 12px;border:1px solid var(--line-2);border-radius:6px;background:transparent;
  color:var(--ink-2);font-size:13px;white-space:nowrap;touch-action:none;
  -webkit-user-select:none;user-select:none}
.chg-hold kbd{font:11px var(--fm);color:var(--ink-3);border:1px solid var(--line-2);
  border-radius:4px;padding:0 5px;line-height:16px}
@media (max-width:760px){.chg-hold span,.chg-bar__sep,.change-controls .chg-bar__k{display:none}
  .chg-ref{padding:0 8px}.chg-ref span{max-width:96px}}
.chg-hold[aria-pressed="true"]{background:var(--raised);color:var(--ink);border-color:var(--ink-3)}

/* ---- Changes view: map stage ------------------------------------------- */
.change-view .stage{top:80px;bottom:24px}
.map-legend .chg-tag{font-size:11px;line-height:14px;padding:0 4px}
.lg__line--chg{display:block;width:18px;height:0;border-top:2px dashed var(--change)}

/* ---- the change map: marks, selection and the ordered reveal ------------- */
/* A selection in the change map keeps the change picture (board 5): no dim,
   all marked flows stay, a selected flow shows even when it has no mark. */
#changemap .node.sel .chg-halo{display:inline}
#changemap .node.sel:is([data-change="changed"],[data-change="plan"]) .node__box{
  stroke:var(--change);stroke-width:2}
#changemap .node.sel:is([data-change="tests"],[data-change="imports"]) .node__box{
  stroke:var(--change);stroke-width:1.2}
#changemap .node.dim:is([data-change="changed"],[data-change="tests"],[data-change="imports"]),
#changemap .node.sel{opacity:1}
#changemap .node.dim[data-change="end"]{opacity:.6}
#changemap .node.dim[data-change="none"]:not(.sel){opacity:.32}
#changemap :is(.flow,.flowlbl)[data-change="lost"].off{opacity:1;visibility:visible;
  pointer-events:auto}
#changemap .flow[data-change="lost"].off{pointer-events:stroke}
#changemap :is(.flow,.flowlbl)[data-change="rest"]:is(.hot,.peek){display:inline}
#changemap .chg-tag{pointer-events:none}
#changemap.chg-base .node[data-change],#changemap.chg-held .node[data-change]{opacity:1}
#changemap.chg-base .node:is([data-change="changed"],[data-change="tests"],
  [data-change="imports"]) .node__box,
#changemap.chg-held .node:is([data-change="changed"],[data-change="tests"],
  [data-change="imports"]) .node__box{stroke:var(--card-line,var(--card-built-line));
  stroke-width:1.1px;stroke-dasharray:none}
#changemap.chg-base .chg-tag,#changemap.chg-held .chg-tag{opacity:0}
#changemap.chg-base .flow[data-change="lost"],#changemap.chg-held .flow[data-change="lost"]{
  stroke:var(--flow);marker-end:url(#changemap-m-flow)}
#changemap.chg-base .flow[data-change="lost"][data-chg-recorded],
#changemap.chg-held .flow[data-change="lost"][data-chg-recorded]{stroke-dasharray:var(--chg-solid)}
#changemap.chg-held,#changemap.chg-held *{transition:none!important}
#changemap.chg-reveal .node[data-change]{transition:opacity 160ms ease-out;
  transition-delay:var(--chg-d,0ms)}
#changemap.chg-reveal .node[data-change] .node__box{transition:stroke 160ms ease-out,
  stroke-width 160ms ease-out,stroke-dasharray 160ms;transition-behavior:allow-discrete;
  transition-delay:var(--chg-d,0ms)}
#changemap.chg-reveal .flow[data-change="lost"]{transition:stroke 400ms ease-in-out,
  stroke-dasharray 400ms ease-in-out,marker-end 400ms;transition-behavior:allow-discrete;
  transition-delay:var(--chg-d,0ms)}
#changemap.chg-reveal .chg-tag{transition:opacity 160ms ease-out;transition-delay:var(--chg-d,0ms)}
:root[data-reduce-motion="true"] #changemap.chg-reveal *{transition:none!important}

/* ---- Changes view: panel ------------------------------------------------- */
.change-panel{display:flex;flex-direction:column;gap:16px;min-width:0}
.change-panel[hidden]{display:none}
.chg-cap{margin:0;font:600 11px/16px var(--fm)!important;letter-spacing:.08em;
  color:var(--ink-3)!important}
.chg-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.chg-range{font:12px var(--fm);color:var(--ink-3);white-space:nowrap}
.chg-pr{margin:-8px 0 0;font-size:13px!important;color:var(--ink-2)}
.chg-sum{margin:0;font:17px/24px var(--fs)!important;color:var(--ink)}
.chg-note{margin:0;color:var(--ink-2)}
.chg-parts{display:flex;flex-direction:column;gap:10px}
.chg-card{display:flex;flex-direction:column;gap:8px;padding:12px 14px;border:1px solid var(--line);
  border-radius:8px;background:var(--card,var(--card-built))}
.chg-card[aria-current="true"]{border-color:var(--accent)}
.chg-card__head{display:flex;align-items:center;gap:8px;min-height:24px;padding:0;border:0;
  background:none;color:var(--ink);text-align:left;font:inherit;cursor:pointer}
.chg-card__head:hover{background:none}
.chg-card__head b{font:600 14px/18px var(--fm)}
.chg-card__flag{margin-left:auto;font-size:12px;color:var(--change);white-space:nowrap}
.chg-card__mods{display:none;min-width:0;font:12px/18px var(--fm);color:var(--ink-3);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chg-picked [data-change-card]:not([aria-current="true"]){padding:10px 14px;background:transparent}
.chg-picked [data-change-card]:not([aria-current="true"])
  :is(.chg-chips,.chg-card__note,.chg-card__flag){display:none}
.chg-picked [data-change-card]:not([aria-current="true"]) .chg-card__mods{display:block}
.chg-chips{display:flex;flex-wrap:wrap;gap:6px}
.chg-chip{font:12px/16px var(--fm);color:var(--ink-2);border:1px solid var(--line-2);
  border-radius:4px;padding:2px 6px}
.chg-card__note{margin:0;font-size:12px!important;line-height:18px!important;color:var(--ink-3)}
.chg-card__detail{border-top:1px solid var(--line);padding-top:8px;font-size:12px;
  color:var(--ink-2);overflow-wrap:anywhere}
.chg-card__detail p{margin:.35rem 0;font-size:12px!important;line-height:18px!important}
.chg-card__detail code{color:var(--ink)}
.chg-tests summary{display:list-item;min-height:0;padding:0;cursor:pointer;font-size:12px;
  color:var(--ink-2);margin:.35rem 0}
.chg-tests summary b{color:var(--ink);font-weight:500}
.chg-h4{margin:0 0 .2rem;font:600 11px/16px var(--fm);letter-spacing:.08em;color:var(--ink-3);
  text-transform:uppercase}
.chg-flowpick{border-color:var(--accent)}
.chg-flowpick__art{margin:0;font-size:13px!important;color:var(--ink-2)}
.chg-flowpick__art b{color:var(--ink);font-weight:600}
.chg-tag{display:inline-block;flex:none;font:700 11px/16px var(--fm);letter-spacing:.06em;
  padding:0 5px;border-radius:3px;white-space:nowrap}
.chg-tag--changed{background:var(--change);color:var(--on-change,var(--bg))}
.chg-tag--tests{border:1px solid var(--change);color:var(--change);line-height:14px}
.chg-tag--imports{border:1px dashed var(--change);color:var(--ink-2);line-height:14px}
.chg-tag--none{border:1px solid var(--line-2);color:var(--ink-3);line-height:14px}
.chg-rows{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px 10px;align-items:baseline;
  font:13px/18px var(--fs);color:var(--ink-2)}
.chg-rows .chg-tag{justify-self:start;font-size:11px;line-height:14px}
.chg-name{display:inline;min-height:0;height:auto;padding:0;border:0;background:none;
  font:600 13px var(--fm);color:var(--ink);cursor:pointer}
.chg-name:hover{background:none;text-decoration:underline}
.chg-sec{display:flex;flex-direction:column;gap:8px;padding-top:14px;
  border-top:1px solid var(--line)}
.chg-sec[hidden]{display:none}
.chg-sec__h{display:flex;justify-content:space-between;gap:12px}
.chg-sec__n{font:12px var(--fm);color:var(--ink-3)}
.chg-flowrows{display:grid;grid-template-columns:22px minmax(0,1fr);gap:6px 10px;
  align-items:center;font:13px/18px var(--fs);color:var(--ink-2)}
.chg-flowrows svg{display:block}
.chg-edge{display:inline;min-height:0;height:auto;padding:0;border:0;background:none;
  font:inherit;color:var(--ink);cursor:pointer}
.chg-edge:hover{background:none;text-decoration:underline}
.chg-seq{display:flex;justify-content:space-between;align-items:baseline;gap:10px;width:100%;
  padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:transparent;
  color:var(--ink);font:13px/18px var(--fs);text-align:left;cursor:pointer;min-height:36px}
.chg-seq__steps{flex:none;font:12px var(--fm);color:var(--change)}
.chg-foot{margin:0;font-size:12px!important;line-height:18px!important;color:var(--ink-3)}
.chg-sec p.chg-text{margin:0;font:13px/20px var(--fs)!important;color:var(--ink-2)}
.chg-limits{display:flex;flex-direction:column;gap:6px;padding:12px 14px;
  border:1px dashed var(--line-2);border-radius:8px}
.chg-limits p{margin:0;font-size:12px!important;line-height:18px!important;color:var(--ink-2)}
.chg-limits code{color:var(--ink)}

/* ---- Changes view without a comparison ----------------------------------- */
.chg-cmd{display:flex;align-items:center;gap:8px;margin:12px 0 8px;padding:8px 8px 8px 12px;
  border:1px solid var(--line-2);border-radius:6px;background:var(--surface);max-width:420px}
.chg-cmd code{flex:1;margin:0!important;font:13px var(--fm);color:var(--ink)}
.chg-cmd button{height:28px;min-height:28px;padding:0 12px;font-size:12px}
.chg-hint{font-size:12px;color:var(--ink-3)}
.change-empty .chg-hint code{display:inline;margin:0;font:12px var(--fm)}
.change-view.chg-titled .change-empty h2{display:none}
.change-view.chg-titled .change-empty{margin:200px 24px 0;padding:0}
.change-empty p{color:var(--ink-2);font-size:13px;line-height:20px}
"""
    + page_changes_map.CSS
)
