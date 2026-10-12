"""Make the Inter subset that the map page contains, and measure its widths.

The script downloads the npm package inter-ui 4.1.1 and compares its SHA-512
value with the recorded value. It reads InterVariable.woff2 and LICENSE.txt from
the package in memory. It does not extract the package to the disk.
It writes src/systemap/page_font.py and src/systemap/fonts/Inter-OFL.txt.
Then it prints the font sizes and the character widths for the width rules of the map.

    uv run --group fonts python scripts/inter_subset.py
    uv run --group fonts python scripts/inter_subset.py --package inter-ui-4.1.1.tgz
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import sys
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

from systemap.schematic_cards import (
    LABEL_CHAR_W,
    LABEL_PX,
    NAME_ADVANCE,
    PLAIN_ADVANCES,
    SUB_CHAR,
    TEXT_PX,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src/systemap/page_font.py"
LICENSE = ROOT / "src/systemap/fonts/Inter-OFL.txt"

PACKAGE = "inter-ui 4.1.1"
URL = "https://registry.npmjs.org/inter-ui/-/inter-ui-4.1.1.tgz"
INTEGRITY = (
    "sha512-451h0J29HyOmA+JXgSi/6M12tL7ZCZ8arYKZUXiOXTJpJbAKqJvFh3k5Si"
    "V3x7tKe0C0KyrKUUiQIvvZ2PQDcA=="
)
FONT_MEMBER = "package/variable/InterVariable.woff2"
LICENSE_MEMBER = "package/LICENSE.txt"

# ASCII and the other characters of the sans text of the page: the middle dot,
# the right arrow and the minus sign. The page shows its other arrows and the
# command key symbol in the monospace font. Inter has no U+21C4, so the system
# sans font shows that character.
CHARACTERS = [*range(32, 127), 0x00B7, 0x2192, 0x2212]
# The page text uses the weights 400, 500, 600 and 650. Bold text is 700.
WEIGHTS = (400, 700)
OPTICAL_SIZE = 14
# No page rule uses tabular figures, so the subset does not keep tnum.
FEATURES = ["kern"]
# Copyright, family, subfamily, version, license description and license URL.
NAME_IDS = [0, 1, 2, 5, 13, 14]
CHUNK = 88


def package_bytes(path: str | None) -> bytes:
    """Give the package bytes after a comparison with the recorded SHA-512 value."""
    if path:
        data = Path(path).read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read()
    found = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()
    if found != INTEGRITY:
        sys.exit(f"The package has a different SHA-512 value: {found}")
    return data


def member(data: bytes, name: str) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        handle = tar.extractfile(name)
        if handle is None:
            sys.exit(f"The package has no file {name}")
        return handle.read()


def load(data: bytes) -> TTFont:
    """Read a font. A save keeps the time records of the source, so the output is the same."""
    return TTFont(io.BytesIO(data), recalcTimestamp=False)


def instance(source: bytes, limits: dict[str, Any]) -> TTFont:
    """Give the font with these axis limits, read again from its bytes."""
    buffer = io.BytesIO()
    font = instancer.instantiateVariableFont(load(source), limits)
    font.flavor = None
    font.save(buffer)
    return load(buffer.getvalue())


def make_subset(source: bytes) -> bytes:
    """Give the WOFF2 subset: the characters, the weight range and one optical size."""
    font = instance(source, {"wght": WEIGHTS, "opsz": OPTICAL_SIZE})
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = FEATURES
    options.name_IDs = NAME_IDS
    options.notdef_outline = False
    options.hinting = False
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=CHARACTERS)
    subsetter.subset(font)
    font.flavor = "woff2"
    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue()


def module_text(woff2: bytes, version: str, characters: str) -> str:
    text = base64.b64encode(woff2).decode()
    chunks = "\n".join(f'    "{text[i : i + CHUNK]}"' for i in range(0, len(text), CHUNK))
    extra = "".join(f"\\u{ord(c):04x}" for c in characters if ord(c) > 126)
    plural = "s" if len(FEATURES) > 1 else ""
    return f'''"""The embedded sans font of the map page: a subset of Inter.

Inter is Copyright 2016 The Inter Project Authors. It has the SIL Open Font License,
Version 1.1, with no Reserved Font Name. `fonts/Inter-OFL.txt` contains the license.
The name table of the subset keeps the copyright, version and license records.

scripts/inter_subset.py makes this file from InterVariable.woff2 in the npm package
{PACKAGE}. The font version is "{version}".
The subset has the characters in CHARACTERS, the weight axis from {WEIGHTS[0]} to {WEIGHTS[1]},
and the optical size {OPTICAL_SIZE}. It keeps the {" and ".join(FEATURES)} feature{plural}.
The page gives the font the family name "systemap Inter".
Thus an installed version of Inter does not replace it."""

from __future__ import annotations

FAMILY = '"systemap Inter"'
CHARACTERS = "".join(map(chr, range(32, 127))) + "{extra}"
WOFF2_BYTES = {len(woff2)}
WOFF2_SHA256 = "{hashlib.sha256(woff2).hexdigest()}"

WOFF2_BASE64 = (
{chunks}
)

FACE = (
    "@font-face{{font-family:" + FAMILY + ";"
    "src:url(data:font/woff2;base64," + WOFF2_BASE64 + ') format("woff2");'
    "font-weight:{WEIGHTS[0]} {WEIGHTS[1]};font-display:block}}"
)
'''


def advances(source: bytes, weight: int) -> tuple[dict[int, int], int]:
    """Give the advance of each subset character, in font units, for one weight."""
    font = instance(source, {"wght": weight, "opsz": OPTICAL_SIZE})
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    return {c: hmtx[cmap[c]][0] for c in CHARACTERS if c in cmap}, font["head"].unitsPerEm


def report_rule(name: str, widths: dict[int, float], limit: float) -> None:
    wider = sorted((c for c, w in widths.items() if w > limit + 1e-9), key=lambda c: -widths[c])
    top = max(widths, key=lambda c: widths[c])
    shown = " ".join(f"{chr(c)}={widths[c]:.2f}" for c in wider[:10])
    print(
        f"{name}: limit {limit:.3f}, largest {chr(top)!r} {widths[top]:.3f}, "
        f"{len(wider)} of {len(widths)} characters are wider. {shown}"
    )


def measure(source: bytes) -> None:
    """Print each map width rule with the Inter widths of the subset characters."""
    by_weight = {w: advances(source, w) for w in (400, 500, 600)}
    for weight, px, limit, name in (
        (500, LABEL_PX, LABEL_CHAR_W, "flow label, Inter 500"),
        (600, LABEL_PX, LABEL_CHAR_W, "flow label under selection, Inter 600"),
        (400, TEXT_PX, SUB_CHAR, "container description, Inter 400"),
        (600, TEXT_PX, NAME_ADVANCE * TEXT_PX, "card name per character, Inter 600"),
    ):
        table, upm = by_weight[weight]
        report_rule(name, {c: a * px / upm for c, a in table.items()}, limit)
    table, upm = by_weight[400]
    plain = {c: a * 2048 / upm for c, a in table.items() if c < 127}
    wider = [chr(c) for c in plain if plain[c] > PLAIN_ADVANCES[c - 32]]
    print(f"card description, Inter 400 against the Arial table: {len(wider)} of 95 are wider")
    total_inter = sum(plain.values())
    print(f"sum of ASCII advances, Inter 400 / Arial: {total_inter / sum(PLAIN_ADVANCES):.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--package", help="use this package file and do not download it")
    args = parser.parse_args()
    data = package_bytes(args.package)
    source = member(data, FONT_MEMBER)
    woff2 = make_subset(source)
    font = load(woff2)
    characters = "".join(chr(c) for c in sorted(font.getBestCmap()))
    missing = [f"U+{c:04X}" for c in CHARACTERS if chr(c) not in characters]
    if missing:
        sys.exit(f"The font has no glyph for {', '.join(missing)}")
    version = font["name"].getDebugName(5) or ""
    MODULE.write_text(module_text(woff2, version, characters), encoding="utf-8")
    LICENSE.parent.mkdir(exist_ok=True)
    LICENSE.write_bytes(member(data, LICENSE_MEMBER))
    encoded = len(base64.b64encode(woff2))
    print(f"{PACKAGE}: {version}; source {len(source)} bytes")
    print(f"subset: {len(characters)} characters, WOFF2 {len(woff2)} bytes, base64 {encoded}")
    measure(source)


if __name__ == "__main__":
    main()
