"""Make the systemap website in docs/.

The site has a landing page, a docs home, one page for each guide page in
site/pages/, and one page each for docs/reference.md and docs/benchmarks.md.
The colors and the font stacks come from src/systemap/theme.py. The type sizes,
the radii and the spacing come from the front matter of DESIGN.md. The font is
the Inter subset of src/systemap/page_font.py. Thus the site and the map page
use the same values.

    uv run --group site python site/build.py
    uv run --group site python site/build.py --check

--check writes no file. It exits 1 if a file in docs/ differs from the build,
or if docs/ has a file in a generated directory that the build does not make.
The build stops with exit 1 if a relative link or an anchor has no target.
site/README.md gives the page names and the heading id rule.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import os
import posixpath
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

from systemap import page, page_font, theme

# site/ is not a package. The page parts are in site/layout.py, next to this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from highlight import highlight_blocks  # noqa: E402
from layout import (  # noqa: E402
    REPO,
    Page,
    SiteError,
    doc_page,
    docs_home,
    esc,
    landing,
)

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DOCS = ROOT / "docs"

# The build owns these paths in docs/. It keeps all other files in docs/.
OWNED_DIRS = ("guide", "assets")
OWNED_FILES = ("index.html", ".nojekyll")

# A guide page is site/pages/NN-slug.md. NN gives the order and slug gives the URL.
PAGE_NAME = re.compile(r"(\d\d)-([a-z0-9]+(?:-[a-z0-9]+)*)\.md")

# The pages that the build makes from docs/*.md, after the guide pages.
# The docs home shows these summaries, because the first paragraph of each
# file tells a maintainer how to change the file.
REFERENCE_PAGES: tuple[tuple[str, str], ...] = (
    ("reference", "This page gives the rules of each check, each command, and each setting."),
    ("benchmarks", "This page gives the recorded runs of the map procedure and their costs."),
)

# The ids of the page layout. A heading with one of these ids gets a number after it.
LAYOUT_IDS = frozenset({"main", "side", "toc", "theme", "top", "content", "footer"})

# The color tokens that the site uses, with the CSS names of the map page.
SITE_TOKENS = (
    "bg",
    "surface",
    "raised",
    "map",
    "card",
    "card_line",
    "line",
    "line_2",
    "ink",
    "ink_2",
    "ink_3",
    "accent",
    "on_accent",
    "hl",
    "hl_soft",
    "brand",
    "region",
    "change",
    "accent_soft",
)
# The flow kind colors of the map page. The landing page gives one to each section.
SITE_KINDS = ("data", "control", "context", "tools")
# A code block has the Ink colors in both themes. Each text color has 4.5:1 or more
# on the Ink surface. tests/test_site.py measures the ratios.
CODE_TOKENS: dict[str, str] = {
    "bg": "surface",
    "line": "line_2",
    "ink": "ink",
    "ink-2": "ink_2",
    "ink-3": "ink_3",
    "k": "accent",
    "n": "change",
}
CODE_KINDS: dict[str, str] = {"s": "data", "f": "context", "a": "control"}

# The DESIGN.md front matter values that the site uses.
DESIGN_KEYS: dict[str, tuple[str, ...]] = {
    "rounded": ("control", "menu", "guide", "tag"),
    "spacing": ("header", "map-gutter", "control-gap", "phone-margin"),
    "typography": (
        "body",
        "project-name",
        "layer-question",
        "panel-title",
        "secondary",
        "kicker",
        "mono",
    ),
}
TYPE_FIELDS = {
    "fontSize": "size",
    "lineHeight": "lh",
    "fontWeight": "weight",
    "letterSpacing": "ls",
}

# ---- pages -------------------------------------------------------------------


def split_title(text: str, source: Path) -> tuple[str, str]:
    """Give the title of the first line `# Title` and the text after it."""
    first, _, rest = text.partition("\n")
    if not first.startswith("# "):
        raise SiteError(f"{source}: the first line must be '# Title'.")
    return first[2:].strip(), rest


def first_paragraph(md: MarkdownIt, text: str) -> str:
    """Give the plain text of the first paragraph."""
    tokens = md.parse(text)
    for i, tok in enumerate(tokens):
        if tok.type == "paragraph_open":
            return inline_text(tokens[i + 1])
        if tok.type == "heading_open":
            break
    return ""


def guide_pages(md: MarkdownIt, pages_dir: Path) -> list[Page]:
    """Read site/pages/NN-slug.md in the order of NN."""
    if not pages_dir.is_dir():
        return []
    out: list[Page] = []
    for source in sorted(pages_dir.glob("*.md")):
        match = PAGE_NAME.fullmatch(source.name)
        if match is None:
            raise SiteError(f"{source}: a guide page name must have the form NN-slug.md.")
        text = source.read_text(encoding="utf-8")
        title, rest = split_title(text, source)
        summary = first_paragraph(md, rest)
        if not summary:
            raise SiteError(f"{source}: the page must have a summary paragraph after its title.")
        out.append(Page(match[2], title, summary, source, rest, number=int(match[1])))
    slugs = [p.slug for p in out]
    if len(set(slugs)) != len(slugs) or set(slugs) & {"index", *dict(REFERENCE_PAGES)}:
        raise SiteError(f"{pages_dir}: two pages have the same slug, or a slug is reserved.")
    return out


def reference_pages(docs_dir: Path) -> list[Page]:
    out = []
    for slug, summary in REFERENCE_PAGES:
        source = docs_dir / f"{slug}.md"
        title, rest = split_title(source.read_text(encoding="utf-8"), source)
        out.append(Page(slug, title, summary, source, rest))
    return out


# ---- markdown ------------------------------------------------------------------


def slugify(text: str) -> str:
    """Give the heading id: the ASCII letters and digits, lowercase, words joined by '-'."""
    return "-".join(re.findall(r"[a-z0-9]+", text.lower())) or "section"


def unique(base: str, seen: set[str]) -> str:
    candidate, n = base, 1
    while candidate in seen:
        n += 1
        candidate = f"{base}-{n}"
    seen.add(candidate)
    return candidate


def inline_text(token: Token) -> str:
    """Give the text of an inline token, with the text of its code spans."""
    parts = []
    for child in token.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts).strip()


# A table with more columns than this keeps each cell on one line and scrolls in its box.
WIDE_TABLE = 4


def _table_open(self: Any, tokens: list[Token], idx: int, options: Any, env: Any) -> str:
    label = tokens[idx].meta.get("label", "")
    name = f'aria-labelledby="{esc(label)}"' if label else 'aria-label="Table"'
    wide = " table--wide" if tokens[idx].meta.get("columns", 0) > WIDE_TABLE else ""
    return f'<div class="table{wide}" role="region" tabindex="0" {name}>\n<table>\n'


def _columns(tokens: list[Token], i: int) -> int:
    """Give the number of header cells of the table that starts at token i."""
    n = 0
    for tok in tokens[i:]:
        if tok.type == "thead_close":
            break
        n += tok.type == "th_open"
    return n


def _table_close(self: Any, tokens: list[Token], idx: int, options: Any, env: Any) -> str:
    return "</table>\n</div>\n"


def markdown() -> MarkdownIt:
    """Give the CommonMark renderer with pipe tables. HTML comments go to the page."""
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    md.add_render_rule("table_open", _table_open)
    md.add_render_rule("table_close", _table_close)
    return md


def _heading(tokens: list[Token], i: int, page_: Page, seen: set[str]) -> str:
    text = inline_text(tokens[i + 1])
    hid = unique(slugify(text), seen)
    tokens[i].attrSet("id", hid)
    level = int(tokens[i].tag[1])
    parts = [c.type for c in tokens[i + 1].children or [] if c.content.strip()]
    if level in (2, 3):
        page_.toc.append((level, text, hid, parts == ["code_inline"]))
    return hid


def _links(token: Token, resolve: Callable[[str], str]) -> None:
    for child in token.children or []:
        if child.type == "link_open":
            child.attrSet("href", resolve(str(child.attrGet("href") or "")))
        elif child.type == "image":
            child.attrSet("src", resolve(str(child.attrGet("src") or "")))


def render_page(md: MarkdownIt, page_: Page, resolve: Callable[[str], str]) -> None:
    """Render the body of a page. Give ids to headings and resolve the links."""
    tokens = md.parse(page_.text)
    seen = set(LAYOUT_IDS)
    last = ""
    lead = True
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open":
            last = _heading(tokens, i, page_, seen)
            lead = False
        elif tok.type == "paragraph_open" and lead and tok.level == 0:
            tok.attrSet("class", "lead")
            lead = False
        elif tok.type == "table_open":
            tok.meta.update(label=last, columns=_columns(tokens, i))
        elif tok.type == "inline":
            _links(tok, resolve)
    page_.body = md.renderer.render(tokens, md.options, {})


# ---- links ---------------------------------------------------------------------

EXTERNAL = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//)")


@dataclass
class Links:
    """Give the site URL for a link in a Markdown source.

    A link to a rendered Markdown file goes to its page. A link that names a
    file of the site stays. A link to another file of the repository goes to
    GitHub. Other links stay as they are, and the link check reports them."""

    source: Path
    out_dir: str
    rendered: dict[Path, str]
    exists: Callable[[str], bool]
    docs_dir: Path = DOCS

    def __call__(self, href: str) -> str:
        if not href or href.startswith("#") or EXTERNAL.match(href):
            return href
        path, hash_, frag = href.partition("#")
        tail = hash_ + frag
        for candidate in self._sources(path):
            if candidate in self.rendered:
                return self._relative(self.rendered[candidate]) + tail
        if self.exists(posixpath.normpath(posixpath.join(self.out_dir, path))):
            return href
        return self._repository(path, tail) or href

    def _sources(self, path: str) -> list[Path]:
        """Give the targets of a path: from the source file, from docs/ and from the root."""
        site = self.docs_dir / posixpath.normpath(posixpath.join(self.out_dir, path))
        return [(self.source.parent / path).resolve(), site.resolve(), (ROOT / path).resolve()]

    def _relative(self, target: str) -> str:
        return posixpath.relpath(target, self.out_dir or ".")

    def _repository(self, path: str, tail: str) -> str:
        for candidate in self._sources(path):
            if not candidate.exists() or not candidate.is_relative_to(ROOT):
                continue
            rel = candidate.relative_to(ROOT).as_posix()
            if rel.startswith("docs/") and not rel.endswith(".md"):
                return self._relative(rel.removeprefix("docs/")) + tail
            kind = "tree" if candidate.is_dir() else "blob"
            return f"{REPO}/{kind}/main/{rel}{tail}"
        return ""


# ---- assets --------------------------------------------------------------------


def front_matter(text: str) -> dict[str, dict[str, Any]]:
    """Read the tables of the YAML front matter of DESIGN.md that have two or three levels."""
    block = text.split("---\n")[1]
    out: dict[str, dict[str, Any]] = {}
    top: dict[str, Any] = {}
    second: dict[str, str] = {}
    for line in block.splitlines():
        indent = len(line) - len(line.lstrip(" "))
        key, _, value = line.strip().partition(":")
        value = value.strip().strip("'\"")
        if indent == 0:
            top = out.setdefault(key, {})
        elif indent == 2 and not value:
            second = top.setdefault(key, {})
        elif indent == 2:
            top[key] = value
        else:
            second[key] = value
    return out


def design_css(design: dict[str, dict[str, Any]]) -> str:
    """Give the CSS variables of the radii, the spacing and the type scale of the map page."""
    out = []
    for group, keys in DESIGN_KEYS.items():
        for key in keys:
            value = design.get(group, {}).get(key)
            if value is None:
                raise SiteError(f"DESIGN.md: the front matter has no {group}.{key}.")
            if group == "typography":
                out += [
                    f"--t-{key}-{TYPE_FIELDS[k]}:{v};" for k, v in value.items() if k in TYPE_FIELDS
                ]
            else:
                out.append(f"--{'radius' if group == 'rounded' else 'space'}-{key}:{value};")
    return "".join(out)


def colour_css(table: dict[str, Any]) -> str:
    out = [f"color-scheme:{table['color_scheme']};"]
    out += [f"{theme.CSS_NAMES[key]}:{table[key]};" for key in SITE_TOKENS]
    out += [f"--k-{kind}:{table['layers'][kind]};" for kind in SITE_KINDS]
    return "".join(out)


def code_colours() -> dict[str, str]:
    """Give the colors of a code block by CSS name: the Ink palette."""
    ink = theme.SCHEMES[theme.DEFAULT_SCHEME]
    out = {f"--code-{name}": ink[key] for name, key in CODE_TOKENS.items()}
    out |= {f"--code-{name}": ink["layers"][kind] for name, kind in CODE_KINDS.items()}
    return out


def site_css(source: str, design: dict[str, dict[str, Any]]) -> str:
    dark, light = theme.SCHEMES[theme.DEFAULT_SCHEME], theme.SCHEMES[theme.LIGHT_SCHEME]
    return (
        "/* site/build.py makes this file from site/site.css, src/systemap/theme.py and "
        "DESIGN.md. Do not edit it. */\n"
        f'@font-face{{font-family:{page_font.FAMILY};src:url(inter.woff2) format("woff2");'
        "font-weight:400 700;font-display:swap}\n"
        f":root{{{colour_css(dark)}--fs:{theme.SANS};--fm:{theme.MONO};{design_css(design)}"
        + "".join(f"{name}:{value};" for name, value in code_colours().items())
        + "}\n"
        f':root[data-theme="light"]{{{colour_css(light)}}}\n'
        "@media (prefers-color-scheme:light){:root:not([data-theme])"
        f"{{{colour_css(light)}}}}}\n" + source
    )


def font_bytes() -> bytes:
    data = base64.b64decode(page_font.WOFF2_BASE64)
    if len(data) != page_font.WOFF2_BYTES or hashlib.sha256(data).hexdigest() != (
        page_font.WOFF2_SHA256
    ):
        raise SiteError("page_font.py: the Inter subset does not agree with its size and digest.")
    return data


def mark_svg() -> str:
    """Give the browser tab icon: the mark on the Ink page color."""
    route = re.search(r'd="([^"]+)"', page.MARK)
    if route is None:
        raise SiteError("page.MARK has no route path.")
    t = theme.SCHEMES[theme.DEFAULT_SCHEME]
    dot = '<circle cx="{}" cy="{}" r="44" fill="' + t["brand"] + '"/>'
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        f'<rect width="512" height="512" rx="112" fill="{t["bg"]}"/>'
        f'<path d="{route[1]}" fill="none" stroke="{t["ink"]}" stroke-width="44" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        + dot.format(380, 132)
        + dot.format(132, 380)
        + "</svg>\n"
    )


# ---- the build -----------------------------------------------------------------


@dataclass
class Inputs:
    """The input directories. The tests use their own pages."""

    pages_dir: Path = SITE / "pages"
    docs_dir: Path = DOCS
    site_dir: Path = SITE


def outputs_of(guide: Sequence[Page], refs: Sequence[Page]) -> list[str]:
    names = ["index.html", ".nojekyll", "guide/index.html"]
    names += [f"guide/{p.href}" for p in [*guide, *refs]]
    names += ["assets/site.css", "assets/site.js", "assets/inter.woff2"]
    return names + ["assets/Inter-OFL.txt", "assets/mark.svg"]


def static_exists(docs_dir: Path, generated: set[str]) -> Callable[[str], bool]:
    """Give a test for a path relative to docs/: a generated file or a kept file."""

    def exists(rel: str) -> bool:
        rel = rel.rstrip("/")
        if rel in generated or f"{rel}/index.html" in generated:
            return True
        if rel.startswith("..") or rel.split("/")[0] in OWNED_DIRS:
            return False
        target = docs_dir / rel
        return target.is_file() or (target / "index.html").is_file()

    return exists


def build(inputs: Inputs | None = None) -> dict[str, bytes]:
    """Make all site files in memory. The keys are paths relative to docs/."""
    inputs = inputs or Inputs()
    md = markdown()
    guide = guide_pages(md, inputs.pages_dir)
    refs = reference_pages(inputs.docs_dir)
    exists = static_exists(inputs.docs_dir, set(outputs_of(guide, refs)))
    rendered = {p.source.resolve(): f"guide/{p.href}" for p in [*guide, *refs]}
    for p in [*guide, *refs]:
        render_page(md, p, Links(p.source, "guide", rendered, exists, inputs.docs_dir))
    files: dict[str, str | bytes] = {
        ".nojekyll": b"",
        "index.html": landing(
            (inputs.site_dir / "index.html").read_text(encoding="utf-8"),
            (inputs.site_dir / "delta.txt").read_text(encoding="utf-8"),
            (inputs.site_dir / "check.txt").read_text(encoding="utf-8"),
        ),
        "guide/index.html": docs_home(guide, refs),
        "assets/site.css": site_css(
            (inputs.site_dir / "site.css").read_text(encoding="utf-8"),
            front_matter((ROOT / "DESIGN.md").read_text(encoding="utf-8")),
        ),
        "assets/site.js": (inputs.site_dir / "site.js").read_text(encoding="utf-8"),
        "assets/inter.woff2": font_bytes(),
        "assets/Inter-OFL.txt": (ROOT / "src/systemap/fonts/Inter-OFL.txt").read_bytes(),
        "assets/mark.svg": mark_svg(),
    }
    for p in [*guide, *refs]:
        files[f"guide/{p.href}"] = doc_page(p, guide, refs)
    for name, value in files.items():
        if name.endswith(".html") and isinstance(value, str):
            files[name] = highlight_blocks(value)
    out = {k: v.encode("utf-8") if isinstance(v, str) else v for k, v in files.items()}
    problems = broken_links(out, exists)
    if problems:
        raise SiteError("Links without a target:\n  " + "\n  ".join(problems))
    return out


# ---- the link check --------------------------------------------------------------

ATTR = re.compile(r"<([a-zA-Z]+)\b[^>]*>")
URL_ATTR = re.compile(r'\s(href|src|srcset)="([^"]*)"')
ID_ATTR = re.compile(r'\sid="([^"]+)"')
# Tags whose URL the browser loads with the page.
LOADS = frozenset({"img", "source", "script", "link", "iframe", "video", "audio"})


def urls(text: str) -> Iterable[tuple[str, str]]:
    """Give each tag name and URL of a page. A srcset gives its first URL."""
    for tag in ATTR.finditer(text):
        for attr, value in URL_ATTR.findall(tag[0]):
            url = html.unescape(value).split(",")[0].split(" ")[0] if attr == "srcset" else value
            yield tag[1].lower(), html.unescape(url)


def _check_url(page_: str, tag: str, url: str, ids: dict[str, set[str]], exists: Any) -> str:
    if EXTERNAL.match(url):
        return f"{page_}: <{tag}> loads {url}" if tag in LOADS else ""
    if url.startswith("/"):
        return f"{page_}: {url} is not a relative link"
    path, _, frag = url.partition("#")
    target = page_
    if path:
        target = posixpath.normpath(posixpath.join(posixpath.dirname(page_), path))
        target = f"{target}/index.html" if path.endswith("/") or target == "." else target
        target = target.removeprefix("./")
        if not exists(target):
            return f"{page_}: {url} has no file"
    if frag and target in ids and frag not in ids[target]:
        return f"{page_}: {url} has no id {frag!r}"
    return ""


def broken_links(files: dict[str, bytes], exists: Callable[[str], bool]) -> list[str]:
    """Give each relative link without a file or an id, and each external request.

    An anchor is examined only in a generated page. The map page uses its
    anchors as view names, such as #changes, so its anchors are not examined."""
    pages = {k: v.decode("utf-8") for k, v in files.items() if k.endswith(".html")}
    ids = {k: set(ID_ATTR.findall(v)) for k, v in pages.items()}
    out = []
    for name, text in sorted(pages.items()):
        for tag, url in urls(text):
            problem = _check_url(name, tag, url, ids, exists)
            if problem:
                out.append(problem)
    return out


def differences(files: dict[str, bytes], docs_dir: Path) -> list[str]:
    """Give each file in docs/ that the build would change, add, or remove."""
    out = [f"differs: {k}" for k, v in sorted(files.items()) if _read(docs_dir / k) != v]
    for owned in OWNED_DIRS:
        for path in sorted((docs_dir / owned).rglob("*")):
            rel = path.relative_to(docs_dir).as_posix()
            if path.is_file() and rel not in files:
                out.append(f"not made by the build: {rel}")
    return out


def _read(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def write(files: dict[str, bytes], docs_dir: Path) -> None:
    for line in differences(files, docs_dir):
        if line.startswith("not made by the build: "):
            (docs_dir / line.removeprefix("not made by the build: ")).unlink()
    for rel, data in files.items():
        target = docs_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if _read(target) != data:
            target.write_bytes(data)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Make the systemap website in docs/.")
    parser.add_argument(
        "--check", action="store_true", help="Write nothing. Exit 1 on a difference."
    )
    args = parser.parse_args(argv)
    try:
        files = build()
    except SiteError as error:
        print(f"site: {error}", file=sys.stderr)
        return 1
    if args.check:
        problems = differences(files, DOCS)
        for line in problems:
            print(f"site: {line}", file=sys.stderr)
        if problems:
            print("site: Run uv run --group site python site/build.py.", file=sys.stderr)
        return 1 if problems else 0
    write(files, DOCS)
    print(f"site: wrote {len(files)} files in {os.path.relpath(DOCS)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
