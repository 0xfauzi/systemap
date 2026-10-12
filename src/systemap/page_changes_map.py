"""The map changes in the Changes panel: what the change did to the model.

`delta_model.for_page` compares the committed model at the comparison base with the
model of the page. The panel lists the components, flows, sequences, and rules that the
change added, removed, or changed. A row for an item on this page selects it on the
change map, or starts the sequence. A removed item has no row action.
"""

from __future__ import annotations

import html

from systemap.delta_model import REMOVED, Item, MapChange

GROUPS = (
    ("components", "Components"),
    ("flows", "Flows"),
    ("sequences", "Sequences"),
    ("invariants", "Rules"),
)
# A group shows this many rows. A line gives the quantity of the other rows.
MOST_ROWS = 10


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _action(group: str, item: Item) -> str:
    """Give the row attributes that select the item, or nothing for a removed item."""
    if item.how == REMOVED or group == "invariants":
        return ""
    if group == "components":
        return f' data-change-go="{esc(item.name)}"'
    if item.go < 0:
        return ""
    return f' data-change-edge="{item.go}"' if group == "flows" else f' data-journey="{item.go}"'


def _name(group: str, item: Item) -> str:
    if group == "flows":
        return f"<b>{esc(item.name)}</b> {esc(item.ends[0])} to {esc(item.ends[1])}"
    if group == "invariants":
        return f"<b>Rule {esc(item.name)}</b>"
    return f"<b>{esc(item.name)}</b>"


def _row(group: str, item: Item) -> str:
    """Give one row: the name, the changed parts or the rule text, and the change."""
    said = item.text if group == "invariants" else ", ".join(item.fields)
    inner = (
        f'<span class="chg-mc__name">{_name(group, item)}'
        + (f'<span class="chg-mc__what">{esc(said)}</span>' if said else "")
        + f'</span><span class="chg-seq__steps">{esc(item.how)}</span>'
    )
    action = _action(group, item)
    kind = f"chg-seq chg-mc chg-mc--{group[0]}" + (" chg-mc--gone" if item.how == REMOVED else "")
    if not action:
        return f'<div class="{kind} chg-mc--still">{inner}</div>'
    return f'<button type="button" class="{kind}"{action}>{inner}</button>'


def _group(group: str, title: str, items: tuple[Item, ...]) -> str:
    if not items:
        return ""
    rows = "".join(_row(group, item) for item in items[:MOST_ROWS])
    more = len(items) - MOST_ROWS
    tail = f'<p class="chg-foot">{more} more {title.lower()}.</p>' if more > 0 else ""
    return f'<h4 class="chg-h4">{title}</h4>{rows}{tail}'


def section(change: MapChange | None) -> str:
    """Give the MAP CHANGES section, or nothing without a model at the base revision."""
    if change is None or change.error:
        return ""
    base = f"<code>{esc(change.base[:7])}</code>"
    head = (
        '<section class="chg-sec" id="chg-map" aria-label="Map changes">'
        '<div class="chg-sec__h"><h3 class="chg-cap">MAP CHANGES</h3>'
        f'<span class="chg-sec__n">{change.count}</span></div>'
    )
    if not change.count:
        return (
            head + f'<p class="chg-text">The model of this page is the same as the model at '
            f"{base}.</p></section>"
        )
    groups = "".join(_group(g, t, getattr(change, g)) for g, t in GROUPS)
    foot = f'<p class="chg-foot">The list compares the model at {base} with this page.</p>'
    return head + groups + foot + "</section>"


def limit(change: MapChange | None) -> str:
    """Give the first limit of the comparison: what the model comparison can show."""
    if change is not None and not change.error:
        return (
            "<p>The source comparison uses the model of this page for both revisions. "
            "Map changes compare the model at "
            f"<code>{esc(change.base[:7])}</code> with the model of this page.</p>"
        )
    reason = f", because {esc(change.error)}" if change is not None else ""
    return (
        "<p>The comparison uses the model of this page for both revisions. It cannot show "
        f"a component, flow or sequence that the change added or removed{reason}.</p>"
    )


CSS = r"""
/* ---- Changes view: map changes ------------------------------------------- */
.chg-mc{align-items:flex-start}
.chg-mc b{font-weight:600}
.chg-mc--c b{font-family:var(--fm)}
.chg-mc__what{display:block;font-size:12px;line-height:18px;color:var(--ink-3)}
.chg-mc--still{cursor:default}
.chg-mc--gone{border-style:dashed}
.chg-h4~.chg-h4{margin-top:10px}
"""
