"""The Content-Security-Policy of a map page.

The policy lets the browser run only the scripts and the style elements of the page.
It contains the SHA-256 digest of each inline script and each style element. The
digests come from the page text when the command makes the page. Thus a script that
an injection adds to the page does not run.

The page has no network request. Thus the policy permits no network source. It permits
`data:` images and fonts, because the page contains its icon and its font as `data:`
URLs. It permits frames from the same origin, because a card can open a child map in a
frame. Style attributes stay permitted, because the map and its scripts use them. A
style attribute cannot run a script.

`systemap live` adds a script to each page, and this script reads events from the live
server. For such a page, `with_live_script` adds the digest of the script and permits
connections to the same origin. The server of `systemap serve` and of `systemap live`
sends the policy of the page in the Content-Security-Policy header.
"""

from __future__ import annotations

import base64
import hashlib
import html
import re
from collections.abc import Iterable
from pathlib import Path

from systemap import repo_files

# The page scripts and style elements have no attributes. A script text contains no
# "</" (`schematic_script.interactive_script` and `page_live.script` escape it).
_SCRIPT = re.compile(r"<script>(.*?)</script>", re.S)
_STYLE = re.compile(r"<style>(.*?)</style>", re.S)
_META = re.compile(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)">')
_CHARSET = '<meta charset="utf-8">'
# The policy meta element is near the start of a page. The server reads only this part.
_HEAD_BYTES = 64 * 1024
# The policy of an SVG figure file. A figure has style elements and no script.
FIGURE_POLICY = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; "
    "object-src 'none'; base-uri 'none'"
)


def _digest(text: str) -> str:
    value = base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")
    return f"'sha256-{value}'"


def _digests(pattern: re.Pattern[str], texts: Iterable[str], decoded: bool) -> list[str]:
    """Give the digests of the elements in `texts`, in their first sequence, one time each.

    The browser gives the text of a style element in an SVG element after it decodes the
    character references. Thus, with `decoded`, a text with "&" also gives the digest of
    the decoded text. The text of a script element is not decoded."""
    found: dict[str, None] = {}
    for text in texts:
        for match in pattern.finditer(text):
            body = match.group(1)
            found[_digest(body)] = None
            if decoded and "&" in body:
                found[_digest(html.unescape(body))] = None
    return list(found)


def policy(page: str, inserted: Iterable[str] = ()) -> str:
    """Give the policy for `page`.

    `inserted` gives the HTML texts that the page scripts put into the page, for example
    the child map previews. Their style elements get digests too."""
    texts = [_META.sub("", page), *inserted]
    scripts = " ".join(_digests(_SCRIPT, texts, False)) or "'none'"
    styles = " ".join(_digests(_STYLE, texts, True)) or "'none'"
    parts = [
        "default-src 'none'",
        f"script-src {scripts}",
        # A browser without style-src-elem and style-src-attr uses this value.
        "style-src 'unsafe-inline'",
        f"style-src-elem {styles}",
        "style-src-attr 'unsafe-inline'",
        "img-src data:",
        "font-src data:",
        "frame-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ]
    return "; ".join(parts)


def with_policy(page: str, inserted: Iterable[str] = ()) -> str:
    """Give `page` with a policy meta element after its charset meta element.

    If the page has a policy meta element, the new element replaces it. If the page has
    no charset meta element, the page does not change."""
    page = _META.sub("", page)
    if _CHARSET not in page:
        return page
    return page.replace(_CHARSET, _CHARSET + _meta(policy(page, inserted)), 1)


def with_live_script(page: str, script: str) -> str:
    """Give `page` with a policy that also permits the live script and its connection.

    `script` is the text of the script element that `systemap live` adds. The function
    keeps the digests of the policy that the page has. If the page has no policy, the
    page does not change."""
    old = of_page(page)
    if not old:
        return page
    digest = _digest(script)
    parts = [
        _with_source(part, digest)
        for part in old.split("; ")
        if not part.startswith("connect-src ")
    ]
    meta = _meta("; ".join([*parts, "connect-src 'self'"]))
    return _META.sub(lambda _found: meta, page, count=1)


def _with_source(part: str, digest: str) -> str:
    """Add `digest` to a script-src directive. Give a different directive without a change."""
    name, *sources = part.split(" ")
    if name != "script-src":
        return part
    return " ".join([name, *(s for s in sources if s != "'none'"), digest])


def _meta(value: str) -> str:
    return f'<meta http-equiv="Content-Security-Policy" content="{value}">'


def of_page(page: str) -> str:
    """Give the policy in the meta element of `page`, or an empty string."""
    found = _META.search(page)
    return found.group(1) if found else ""


def of_file(root: Path, path: Path) -> str:
    """Give the policy for a file that a server in `root` sends, or an empty string.

    An HTML file gives the policy in its meta element. An SVG file gives FIGURE_POLICY.
    A directory gives the policy of its index.html file. The function reads the file
    with `repo_files.read_bytes`, so a link out of `root` or a FIFO gives no policy."""
    if path.is_dir():
        path = path / "index.html"
    if path.suffix == ".svg":
        return FIGURE_POLICY
    if path.suffix not in {".html", ".htm"}:
        return ""
    try:
        head = repo_files.read_bytes(root, path.relative_to(root), _HEAD_BYTES)
    except (OSError, ValueError):
        return ""
    return of_page(head.decode("utf-8", errors="replace"))
