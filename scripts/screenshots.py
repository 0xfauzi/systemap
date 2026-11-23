"""Make screenshots of the atlas page and its controls.

The script renders the page of `[render] page` from stored facts and the model. That is the
atlas page (docs/design/atlas.md) by default, with the History view from the Git log.
It writes one page per scheme and serves the pages through HTTP.
Headless Chrome makes scheme screenshots at 1600 by 900 pixels.
It makes 12 tour frames at 1600 by 900 pixels.
It makes one phone image at 390 by 844 pixels.
It makes the WebP images of the five views on the landing page (site/index.html),
at 1600 by 900 pixels and for a phone at 390 by 760 pixels with 2 device pixels.
The views are Map, Sequences, States, Focus and History.
The change marks of `render --base` compare the commit CHANGE_HEAD with its parent
CHANGE_BASE. The last tour frame shows them, and under the headline it shows the
disclosure "Not in this comparison" of the comparison. The other frames do not show it.
A change to the page makes the committed images old. Run the script again after it.
Each frame shows a view, a layer, a card, or a sequence step.
ffmpeg puts the frames together in a 30-second GIF, with a 4 MiB size limit.
Examine the images before use in the README.

    uv run python scripts/screenshots.py
    uv run python scripts/screenshots.py --keep
    uv run python scripts/screenshots.py --chrome /path/to/chrome --ffmpeg ffmpeg

Chrome can write an image without stopping.
After 15 seconds, the script stops Chrome and uses the image if it is available.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from systemap import (
    change,
    cli,
    config,
    facts_file,
    nest,
    page,
    page_csp,
    render_pages,
)
from systemap import theme as theme_mod

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
WINDOW = "1600,900"
# The tour uses the same viewport as the theme images.
TOUR_WINDOW = WINDOW
PHONE_WINDOW = "390,844"
SECONDS_PER_STATE = 2.5
GIF_LIMIT = 4 * 1024 * 1024
TIMEOUT = 15

# The states the tour walks, in order: what the reader would do with the
# page in half a minute. Each is the script run after the page's own.
# A frame with "compare" in its name uses the page with the revision comparison.
TOUR: list[tuple[str, str]] = [
    ("system", ""),
    ("structure", "layer('structure');"),
    ("data", "layer('data');"),
    ("control", "layer('control');"),
    ("judge", "layer('judge');"),
    ("card", "layer('all'); card('CLI');"),
    ("journey-route", "journey(0);"),
    ("journey-2", "journey(0); next(); next();"),
    ("journey-diagram", "journey(0); next(); next(); diagram();"),
    ("states", "view('states');"),
    ("focus", "view('focus');"),
    ("compare", "layer('all');"),
]
# The frame of the tour that scripts/screenshots.py also writes as sequence.png.
SEQUENCE_FRAME = "journey-2"

# The views on the landing page, with the script for each view.
VIEWS: list[tuple[str, str]] = [
    ("map", ""),
    ("sequence", "journey(0); next(); next(); diagram();"),
    ("states", "view('states');"),
    ("focus", "view('focus');"),
    ("history", "view('history');"),
]
CHANGE_BASE = "d8ac070"
CHANGE_HEAD = "0254afb"
LANDING_PHONE = "390,760"

# Each tour frame contains the header and the canvas. The helpers use the controls of
# the page, as a reader does. Each helper waits for the page to draw the result of the
# helper before it (STEP_MS), because the page builds a view in its frames.
STEP_MS = 250
DRIVER = """<script>(function(){{
var steps = [], at = 0;
function q(s){{ return document.querySelector(s); }}
function later(f){{ steps.push(f); }}
function view(m){{ later(function(){{ q('#atlas-head [data-mode="' + m + '"]').click(); }}); }}
function layer(id){{ later(function(){{ q('#atlas-tabs [data-layer="' + id + '"]').click(); }}); }}
function card(id){{ later(function(){{ location.hash = id; }}); }}
function journey(k){{ view('seq');
  later(function(){{ document.querySelectorAll('#atlas-rail-list button')[k].click(); }}); }}
function next(){{ later(function(){{ q('#atlas-step-next').click(); }}); }}
function diagram(){{ later(function(){{ q('[data-form="diagram"]').click(); }}); }}
{actions}
function run(){{ if (at < steps.length) {{ steps[at++](); setTimeout(run, {step}); }} }}
setTimeout(run, {step});
}})();</script>
"""


def render(root: Path, compare: bool = False) -> str:
    """Make the page of the map tree from stored facts, as `systemap render` does. With
    `compare`, the page has the revision comparison of CHANGE_HEAD with CHANGE_BASE."""
    cfg = config.load(root)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    if not facts:
        raise SystemExit("No facts are available. First run systemap refresh.")
    of = None
    if compare:
        source = change.source_change(cfg, CHANGE_BASE, facts, CHANGE_HEAD)
        of = render_pages.page_change(cfg, facts, CHANGE_BASE, CHANGE_HEAD, source, {})
    history, lines = render_pages.history(cfg, tree, facts)
    for line in lines:
        print(line, file=sys.stderr)
    pages = {m.id: html for m, html in render_pages.pages(cfg, tree, facts, of, history=history)}
    return pages[tree.top.id]


def seeded(html: str, scheme: str) -> str:
    """The page with the browser's storage seeded to one scheme, ahead of the
    page's own head script, which reads it back and stamps the root. A style
    stops CSS transitions and animations, so each screenshot shows a final
    state. `driven` gives the policy the digests of these elements."""
    seed = (
        "<script>try{localStorage.setItem("
        f"{json.dumps(page.SCHEME_KEY)},{json.dumps(scheme)});"
        "}catch(e){}</script>"
        "<style>*,*::before,*::after{transition:none!important;animation:none!important}</style>"
    )
    return html.replace('<meta charset="utf-8">', '<meta charset="utf-8">' + seed, 1)


def driven(html: str, actions: str, style: str = "") -> str:
    """The page with the tour script after the page's own script, and an optional style.
    The policy of the page gets the digests of the added elements."""
    head, tail = html.rsplit("</body>", 1)
    if style:
        head = head.replace("</head>", f"<style>{style}</style></head>", 1)
    script = DRIVER.format(actions=actions, step=STEP_MS)
    return page_csp.with_policy(head + script + "</body>" + tail)


def shoot(
    chrome: str, url: str, out: Path, window: str = WINDOW, sandbox: bool = True, scale: int = 1
) -> None:
    # An earlier image must not count as the image of this run.
    out.unlink(missing_ok=True)
    args = [
        chrome,
        *([] if sandbox else ["--no-sandbox"]),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--force-prefers-reduced-motion",
        "--virtual-time-budget=3000",
        f"--window-size={window}",
        f"--force-device-scale-factor={scale}",
        f"--screenshot={out}",
        url,
    ]
    try:
        subprocess.run(args, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        pass
    if not out.is_file():
        raise SystemExit(f"Chrome wrote no screenshot for {url}")
    print(f"Wrote {out.name} ({out.stat().st_size // 1024} KB)")


def webp(ffmpeg: str, png: Path, out: Path) -> None:
    """Convert a PNG screenshot into a WebP image for the landing page."""
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(png),
            "-c:v",
            "libwebp",
            "-quality",
            "80",
            str(out),
        ],
        check=True,
    )
    print(f"Wrote {out.name} ({out.stat().st_size // 1024} KB)")


def landing(args: argparse.Namespace, root: Path, site: Path, base: str, out: Path) -> None:
    """Make the WebP images of the five views of the landing page."""
    html = render(root)
    shots = site.parent / "landing"
    shots.mkdir()
    sizes = (
        ("", WINDOW, 1, ""),
        ("-phone", LANDING_PHONE, 2, "html,body{width:390px;max-width:390px}"),
    )
    for name, actions in VIEWS:
        for scheme in theme_mod.SCHEMES:
            for size, window, scale, style in sizes:
                stem = f"view-{name}{size}-{scheme}"
                (site / f"{stem}.html").write_text(
                    driven(seeded(html, scheme), actions, style), encoding="utf-8"
                )
                png = shots / f"{stem}.png"
                shoot(args.chrome, f"{base}/{stem}.html", png, window, not args.no_sandbox, scale)
                webp(args.ffmpeg, png, out / f"{stem}.webp")


def stitch(ffmpeg: str, frames: Path, out: Path) -> None:
    """Make a GIF from frames. Decrease its width until its size meets the limit."""
    for width in (1200, 1000, 800):
        filters = (
            f"scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];"
            "[b][p]paletteuse=dither=bayer:bayer_scale=3"
        )
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-framerate",
                f"1/{SECONDS_PER_STATE}",
                "-i",
                str(frames / "tour-%02d.png"),
                "-vf",
                filters,
                "-loop",
                "0",
                str(out),
            ],
            check=True,
        )
        size = out.stat().st_size
        print(f"{out.name}: {width} px wide, {size / 1024 / 1024:.2f} MB")
        if size <= GIF_LIMIT:
            return
    raise SystemExit(f"{out} is over the limit at every width")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="docs/screenshots")
    parser.add_argument("--chrome", default=CHROME)
    parser.add_argument("--ffmpeg", default=FFMPEG)
    parser.add_argument("--keep", action="store_true", help="Keep the temporary pages")
    parser.add_argument(
        "--no-sandbox",
        action="store_true",
        help="Start Chrome without its sandbox, as root in a container",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)

    scratch = Path(tempfile.mkdtemp(prefix="systemap-shots-"))
    site = scratch / "site"
    site.mkdir()
    html = render(root)
    for scheme in theme_mod.SCHEMES:
        (site / f"{scheme}.html").write_text(driven(seeded(html, scheme), ""), encoding="utf-8")
    base_page = seeded(html, theme_mod.DEFAULT_SCHEME)
    compared = seeded(render(root, compare=True), theme_mod.DEFAULT_SCHEME)
    for k, (name, actions) in enumerate(TOUR, start=1):
        start = compared if "compare" in name else base_page
        (site / f"tour-{k:02d}.html").write_text(driven(start, actions), encoding="utf-8")
    # Chrome can use a window wider than the requested phone screenshot.
    # The document width must agree with the screenshot width.
    phone = driven(base_page, "", "html,body{width:390px;max-width:390px}")
    (site / "phone.html").write_text(phone, encoding="utf-8")

    httpd = cli.make_server(site, 0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        for scheme in theme_mod.SCHEMES:
            shoot(
                args.chrome,
                f"{base}/{scheme}.html",
                out / f"{scheme}.png",
                sandbox=not args.no_sandbox,
            )
        frames = scratch / "frames"
        frames.mkdir()
        for k, (name, _actions) in enumerate(TOUR, start=1):
            shoot(
                args.chrome,
                f"{base}/tour-{k:02d}.html",
                frames / f"tour-{k:02d}.png",
                TOUR_WINDOW,
                not args.no_sandbox,
            )
            print(f"  state {k}: {name}")
        at = [name for name, _ in TOUR].index(SEQUENCE_FRAME) + 1
        shutil.copyfile(frames / f"tour-{at:02d}.png", out / "sequence.png")
        shoot(
            args.chrome,
            f"{base}/phone.html",
            out / "phone.png",
            PHONE_WINDOW,
            not args.no_sandbox,
        )
        stitch(args.ffmpeg, frames, out / "tour.gif")
        landing(args, root, site, base, out)
    finally:
        httpd.shutdown()
        httpd.server_close()
    if args.keep:
        print(f"Temporary pages are at {scratch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
