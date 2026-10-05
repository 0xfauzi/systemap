"""Make screenshots of the map page and its controls.

The script renders the page from stored facts and the model.
It writes one page per scheme and serves the pages through HTTP.
Headless Chrome makes scheme screenshots at 1600 by 900 pixels.
It makes 12 tour frames at 1600 by 1520 pixels.
Each frame shows a layer, component, or sequence step.
ffmpeg puts the frames together in a 30-second GIF, with a 4 MiB size limit.
Examine the images before use in the README.

    uv run python scripts/screenshots.py
    uv run python scripts/screenshots.py --keep

Chrome can write an image without stopping.
After 15 seconds, the script stops Chrome and uses the image if it is available.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from systemap import cli, config, extract, nest, page
from systemap import theme as theme_mod

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
WINDOW = "1600,900"
# The tour shows the whole map with the controls above and the sentence
# under it, which at Fit needs the taller window; the GIF is scaled down.
TOUR_WINDOW = "1600,1520"
SECONDS_PER_STATE = 2.5
GIF_LIMIT = 4 * 1024 * 1024
TIMEOUT = 15

# The states the tour walks, in order: what the reader would do with the
# page in half a minute. Each is the script run after the page's own.
TOUR: list[tuple[str, str]] = [
    ("structure", ""),
    ("system", "layer('system');"),
    ("data", "layer('data');"),
    ("control", "layer('control');"),
    ("judge", "layer('judge');"),
    ("all", "layer('all');"),
    ("card", "A.select('CLI');"),
    ("spoke", "A.select('CLI'); A.peek(A.detail['CLI'].edges[0]);"),
    ("journey-1", "journey(0); "),
    ("journey-2", "journey(0); next();"),
    ("journey-3", "journey(0); next(); next();"),
    ("card-control", "layer('control'); A.select('Check');"),
]

# The tour frames hide the page header and start at the map, rather than
# scrolling to it: headless Chrome photographs a scrolled page with a blank
# band where the header was (measured on 140.x), and the map is the tour.
DRIVER = """<script>(function(){{
var A = document.getElementById('schematic').systemap;
document.querySelector('.bar').style.display = 'none';
document.querySelector('.main').style.paddingTop = '0';
function layer(id){{ document.querySelector('[data-layer-btn="' + id + '"]').click(); }}
function journey(k){{
  var s = document.getElementById('journey'); s.value = String(k);
  s.dispatchEvent(new Event('change'));
}}
function next(){{ document.getElementById('jnext').click(); }}
{actions}
}})();</script>
"""


def render(root: Path) -> str:
    """Make the top map page from stored facts."""
    cfg = config.load(root)
    tree = nest.load(cfg)
    m = tree.top
    facts = extract.read_facts(cfg.facts_path)
    if not facts:
        raise SystemExit("No facts are available. First run systemap refresh.")
    return page.build(
        cfg,
        m.model,
        m.meaning,
        m.theme,
        facts,
        {"has_change": False},
        page.nesting_of(cfg, tree, m, facts),
    )


def seeded(html: str, scheme: str) -> str:
    """The page with the browser's storage seeded to one scheme, ahead of
    the page's own head script, which reads it back and stamps the root."""
    seed = (
        "<script>try{localStorage.setItem("
        f"{json.dumps(page.SCHEME_KEY)},{json.dumps(scheme)})}}catch(e){{}}</script>"
    )
    return html.replace('<meta charset="utf-8">', '<meta charset="utf-8">' + seed, 1)


def shoot(chrome: str, url: str, out: Path, profile: Path, window: str = WINDOW) -> None:
    args = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--force-prefers-reduced-motion",
        "--virtual-time-budget=3000",
        f"--user-data-dir={profile}",
        f"--window-size={window}",
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
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)

    scratch = Path(tempfile.mkdtemp(prefix="systemap-shots-"))
    site = scratch / "site"
    site.mkdir()
    html = render(root)
    for scheme in theme_mod.SCHEMES:
        (site / f"{scheme}.html").write_text(seeded(html, scheme), encoding="utf-8")
    head, tail = seeded(html, theme_mod.DEFAULT_SCHEME).rsplit("</body>", 1)
    for k, (_name, actions) in enumerate(TOUR, start=1):
        driven = head + DRIVER.format(actions=actions) + "</body>" + tail
        (site / f"tour-{k:02d}.html").write_text(driven, encoding="utf-8")

    httpd = cli.make_server(site, 0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        profile = scratch / "profile"
        for scheme in theme_mod.SCHEMES:
            shoot(args.chrome, f"{base}/{scheme}.html", out / f"{scheme}.png", profile)
        frames = scratch / "frames"
        frames.mkdir()
        for k, (name, _actions) in enumerate(TOUR, start=1):
            shoot(
                args.chrome,
                f"{base}/tour-{k:02d}.html",
                frames / f"tour-{k:02d}.png",
                profile,
                TOUR_WINDOW,
            )
            print(f"  state {k}: {name}")
        stitch(args.ffmpeg, frames, out / "tour.gif")
    finally:
        httpd.shutdown()
        httpd.server_close()
    if args.keep:
        print(f"Temporary pages are at {scratch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
