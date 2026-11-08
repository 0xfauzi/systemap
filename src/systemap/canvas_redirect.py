"""The small page of a nested map: it goes to the canvas page (docs/design/nested-canvas.md).

The canvas page is the top page of the map tree (`canvas_page`). The page of each nested
map, for example `Gateway/index.html`, is a small page that goes to the top page with the
ID of its map in the URL hash: `../index.html#Gateway`. Thus a link to a nested page still
opens that map.

The small page keeps the hash of the link. Its script adds the hash to the ID of the map:
`Gateway/index.html#Routes` goes to `../index.html#Gateway/Routes`. The address of the
top page is fixed text, relative to the small page. The hash of the link goes only after
the "#" of that address. Thus a hash cannot change the scheme, the host or the path, and
the page cannot go to a different site.

Without a script, the refresh meta element goes to the map (not to the card of the hash).
The page also has a visible link to the map. The policy of the page (`page_csp`) permits
only the digest of its script. It permits no frame, no connection and no style element.

Acceptance values (tests/test_canvas_page.py and tests/test_canvas_redirect_browser.py):

1. The page has a viewport meta element, one script element in its head, and the SHA-256
   digest of that script is the only source of script-src.
2. The script goes to the address of the top page and the incoming hash:
   `Gateway/index.html#Routes` goes to `index.html#Gateway/Routes`. A map ID with a
   space or a "<" character is quoted in the address.
3. A refresh meta element and a visible link go to `index.html#<map ID>`.
4. The policy has default-src 'none', no connect-src, and frame-src 'none'.
5. The page has 2,048 bytes or less for a map ID of 40 characters.
"""

from __future__ import annotations

import html
import json
from urllib.parse import quote

from systemap import nest, page_csp


def target(m: nest.Map) -> str:
    """Give the URL of the top page with the hash of the map, relative to the page of `m`."""
    if not m.id:
        return "index.html"
    return "../" * (m.id.count("/") + 1) + "index.html#" + quote(m.id, safe="/")


def _script(url: str) -> str:
    """Give the script that goes to `url` with the hash of the link after the map ID."""
    fixed = json.dumps(url).replace("</", "<\\/")
    return (
        f"(function(){{var t={fixed},h=location.hash.slice(1);"
        'location.replace(t+(h?"/"+h:""));})();'
    )


def page(m: nest.Map) -> str:
    """Give the small page of the nested map `m`. It goes to the top page with the map ID."""
    url = target(m)
    shown = html.escape(m.id)
    href = html.escape(url, quote=True)
    return page_csp.with_policy(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f"<title>{shown} system map</title>"
        f"<script>{_script(url)}</script>"
        f'<meta http-equiv="refresh" content="0;url={href}">'
        "</head><body>"
        f'<p>The map {shown} is on the <a href="{href}">canvas page</a>.</p>'
        "</body></html>\n",
        frame=page_csp.NO_FRAME,
    )
