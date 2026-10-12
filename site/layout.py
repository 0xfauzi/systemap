"""The HTML of the website pages: the head, the header, the navigation and the footer.

site/build.py gives the rendered Markdown and the page order. This module gives
the page parts around them. The parts have the names and the classes of the map
page where the map page has the same part, for example the header and the mark.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from systemap import __version__, page, page_icons

REPO = "https://github.com/0xfauzi/systemap"
PYPI = "https://pypi.org/project/systemap/"

# The theme setting has the key and the values of the map page, so the two
# pages on one site keep one selection.
SCHEME_KEY = page.SCHEME_KEY
HEAD_SCRIPT = (
    "(function(){var d=document.documentElement,s=null;d.className+=' js';"
    f"try{{s=localStorage.getItem('{SCHEME_KEY}')}}catch(e){{}}"
    "if(s!=='dark'&&s!=='light'){s=window.matchMedia&&"
    "matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'}"
    "d.setAttribute('data-theme',s)})();"
)


class SiteError(Exception):
    """A site input that the build cannot use."""


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


@dataclass
class Page:
    """One docs page: a guide page or a reference page."""

    slug: str
    title: str
    summary: str
    source: Path
    text: str
    number: int = 0
    body: str = ""
    toc: list[tuple[int, str, str, bool]] = field(default_factory=list)

    @property
    def href(self) -> str:
        return f"{self.slug}.html"


# ---- page parts ------------------------------------------------------------------

THEME_BUTTON = (
    '<button type="button" class="tool" id="theme" aria-label="Paper theme" '
    'title="Paper theme" hidden>'
    f'<span class="tool__to-paper">{page_icons.icon("sun")}</span>'
    f'<span class="tool__to-ink">{page_icons.icon("moon")}</span></button>'
)


def head(title: str, description: str, up: str, body_class: str) -> str:
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n"
        f'<meta name="description" content="{esc(description)}">\n'
        f'<link rel="icon" href="{up}assets/mark.svg" type="image/svg+xml">\n'
        f'<link rel="preload" href="{up}assets/inter.woff2" as="font" type="font/woff2" '
        "crossorigin>\n"
        f'<link rel="stylesheet" href="{up}assets/site.css">\n'
        f"<script>{HEAD_SCRIPT}</script>\n"
        f'<script src="{up}assets/site.js" defer></script>\n'
        f'</head>\n<body class="{body_class}">\n'
        '<a class="skip" href="#main">Go to the content</a>\n'
    )


def header(up: str, current: str) -> str:
    items = [("Docs", f"{up}guide/", "docs"), ("Live example", f"{up}map/", "map")]
    links = "".join(
        f'<a class="nav__a" href="{href}"'
        + (' aria-current="page"' if key == current else "")
        + f">{name}</a>"
        for name, href, key in items
    )
    return (
        '<header class="bar">\n'
        f'<a class="brand" href="{up or "./"}">{page.MARK}<span class="brand__name">'
        "systemap</span></a>\n"
        f'<nav class="nav" aria-label="Site">{links}'
        f'<a class="nav__a" href="{REPO}">GitHub</a></nav>\n'
        f'<span class="bar__space"></span>\n{THEME_BUTTON}\n</header>\n'
    )


def footer(up: str) -> str:
    return (
        '<footer class="foot" id="footer">\n<div class="foot__in">\n'
        f'<a class="brand brand--small" href="{up or "./"}">{page.MARK}'
        '<span class="brand__name">systemap</span></a>\n'
        f'<span class="foot__v">Version <code>{esc(__version__)}</code></span>\n'
        '<span class="foot__links">'
        f'<a href="{REPO}/blob/main/LICENSE">MIT license</a>'
        f'<a href="{REPO}">GitHub</a>'
        f'<a href="{PYPI}">PyPI</a>'
        f'<a href="{REPO}/blob/main/CHANGELOG.md">Changelog</a>'
        "</span>\n"
        f'<span class="foot__font">The page font is Inter, under the '
        f'<a href="{up}assets/Inter-OFL.txt">SIL Open Font License 1.1</a>.</span>\n'
        "</div>\n</footer>\n</body>\n</html>\n"
    )


def ring(n: int) -> str:
    return f'<span class="ring" aria-hidden="true">{n}</span>'


def side_nav(guide: Sequence[Page], refs: Sequence[Page], current: str) -> str:
    def item(p: Page) -> str:
        now = ' aria-current="page"' if p.slug == current else ""
        mark = ring(p.number) if p.number else ""
        return f'<li><a href="{p.href}"{now}>{mark}<span>{esc(p.title)}</span></a></li>'

    home = ' aria-current="page"' if current == "index" else ""
    out = [
        '<nav class="side" id="side" aria-label="Docs">',
        f'<a class="side__home" href="index.html"{home}>Docs home</a>',
    ]
    if guide:
        out += ['<p class="kicker">Guide</p>', '<ol class="side__list">']
        out += [item(p) for p in guide] + ["</ol>"]
    out += ['<p class="kicker">Reference</p>', '<ul class="side__list">']
    out += [item(p) for p in refs] + ["</ul>", "</nav>"]
    return "\n".join(out) + "\n"


def doc_bar(title: str) -> str:
    """Give the phone row that opens the docs navigation."""
    return (
        '<div class="docbar"><button type="button" class="docbar__btn" aria-controls="side" '
        f'aria-expanded="false" hidden><span class="kicker">Docs</span>'
        f'<span class="docbar__t">{esc(title)}</span>{page_icons.icon("down")}</button></div>\n'
    )


def toc(page_: Page) -> str:
    if len(page_.toc) < 2:
        return ""
    rows = "".join(
        f'<li class="toc__l{level}"><a href="#{hid}">'
        + (f"<code>{esc(text)}</code>" if code else esc(text))
        + "</a></li>"
        for level, text, hid, code in page_.toc
    )
    return (
        '<aside class="toc" id="toc" aria-label="On this page">'
        f'<p class="kicker">On this page</p><ul>{rows}</ul></aside>\n'
    )


def pager(order: Sequence[Page], k: int) -> str:
    cells = []
    if k > 0:
        p = order[k - 1]
        cells.append(
            f'<a class="pager__a" href="{p.href}" rel="prev"><span class="kicker">Previous'
            f"</span><span>{esc(p.title)}</span></a>"
        )
    if k + 1 < len(order):
        p = order[k + 1]
        cells.append(
            f'<a class="pager__a pager__next" href="{p.href}" rel="next"><span class="kicker">'
            f"Next</span><span>{esc(p.title)}</span></a>"
        )
    return f'<nav class="pager" aria-label="Pages">{"".join(cells)}</nav>\n'


def kicker(page_: Page, guide_count: int) -> str:
    if page_.number:
        return f"Guide · {page_.number} of {guide_count}"
    return "Reference"


def doc_page(page_: Page, guide: Sequence[Page], refs: Sequence[Page]) -> str:
    order = [*guide, *refs]
    k = order.index(page_)
    return (
        head(f"{page_.title} · systemap", page_.summary, "../", "docs-page")
        + header("../", "docs")
        + doc_bar(page_.title)
        + '<div class="layout">\n'
        + side_nav(guide, refs, page_.slug)
        + '<main id="main" class="doc">\n'
        + f'<p class="kicker doc__k">{esc(kicker(page_, len(guide)))}</p>\n'
        + f"<h1>{esc(page_.title)}</h1>\n"
        + page_.body
        + pager(order, k)
        + "</main>\n"
        + toc(page_)
        + "</div>\n"
        + footer("../")
    )


def home_rows(pages: Iterable[Page]) -> str:
    rows = []
    for p in pages:
        mark = ring(p.number) if p.number else ""
        rows.append(
            f'<li><a class="row{" row--n" if mark else ""}" href="{p.href}">{mark}'
            f'<span class="row__t">{esc(p.title)}'
            f'</span><span class="row__s">{esc(p.summary)}</span></a></li>'
        )
    return '<ul class="rows">' + "".join(rows) + "</ul>\n"


def docs_home(guide: Sequence[Page], refs: Sequence[Page]) -> str:
    parts = [
        head("Docs · systemap", "The systemap guide and reference.", "../", "docs-page"),
        header("../", "docs"),
        doc_bar("Docs home"),
        '<div class="layout">\n',
        side_nav(guide, refs, "index"),
        '<main id="main" class="doc">\n<p class="kicker doc__k">Docs</p>\n',
        "<h1>systemap docs</h1>\n",
        '<p class="lead">The guide tells you how to make a map, read it, and update it '
        "after a change. The reference gives each rule, command, and setting.</p>\n",
    ]
    if guide:
        parts += ['<h2 id="guide">Guide</h2>\n', home_rows(guide)]
    parts += ['<h2 id="reference">Reference</h2>\n', home_rows(refs), "</main>\n"]
    parts += ["</div>\n"]
    return "".join(parts) + footer("../")


# ---- landing page --------------------------------------------------------------

PLACEHOLDER = re.compile(r"\{\{([a-z-]+)\}\}")


def excerpt(text: str, first: str, stop: str, source: str) -> str:
    """Give the lines of recorded output from the line that starts with `first` to the
    line before the next line that starts with `stop`. The file keeps the full output."""
    lines = text.rstrip("\n").split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith(first)]
    if not starts:
        raise SiteError(f"{source}: no line starts with {first!r}.")
    ends = [i for i, line in enumerate(lines) if i > starts[0] and line.startswith(stop)]
    return "\n".join(lines[starts[0] : ends[0] if ends else len(lines)])


def landing(template: str, delta: str, check: str) -> str:
    values = {
        "head": head(
            "systemap: see what your coding agents are building",
            "Your coding agent draws a map of your system from the code. CI checks the map "
            "against the code. Each pull request shows what changed in the system.",
            "",
            "home",
        ),
        "header": header("", "home"),
        "footer": footer(""),
        "delta": esc(excerpt(delta, "delta:", "next to the change:", "site/delta.txt")),
        "check": esc(excerpt(check, "coverage:", "  fix:", "site/check.txt")),
        "version": esc(__version__),
    }

    def fill(match: re.Match[str]) -> str:
        if match[1] not in values:
            raise SiteError(f"site/index.html: the placeholder {match[0]} has no value.")
        return values[match[1]]

    # The footer ends the file with one newline.
    return PLACEHOLDER.sub(fill, template.rstrip())
