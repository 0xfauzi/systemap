"""The map's look, as one table of tokens.

Everything visual lives here so the scene, the panel and the page cannot
disagree about a colour. The default is a neutral dark scheme with one
accent; a consumer overrides any token from the `[theme]` table of its
configuration and the result is merged over this table.

Colour carries meaning or is absent:

    accent ...... you are interacting with this (selection, focus, the node
                  that ACTS in a journey step)
    steel ....... measurement (the node that MEASURES a step)
    layers ...... one hue per layer of the map, printed in the page legend;
                  taken from `layer_palette` in layer order unless the
                  `layers` table names a colour for the layer id
    good ........ built; warn: part built; muted, dashed: planned
    bad ......... only for "nothing measures this step" and a change map

Nothing else on the page is coloured.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable
from typing import Any

from systemap.model import Layer

SANS = (
    'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,'
    '"Helvetica Neue",Arial,sans-serif'
)
MONO = 'ui-monospace,"SF Mono",SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace'

# Eight hues that read apart from each other on a near-black ground and stay
# quieter than the accent. A map with more layers than this wraps around.
LAYER_PALETTE: list[str] = [
    "#D9D2C0",
    "#82A7BA",
    "#E39A86",
    "#DD9BBD",
    "#B48EC9",
    "#86C9A9",
    "#B7C27C",
    "#E3B778",
]

DEFAULT: dict[str, Any] = {
    "name": "default",
    "scheme": "dark",
    "bg": "#131416",
    "surface": "#1A1C1F",
    "raised": "#232629",
    "line": "#2B2F34",
    "line_2": "#454B53",
    "ink": "#E8EAED",
    "ink_2": "#B9BEC6",
    "ink_3": "#8A9099",
    "accent": "#5DADE2",
    "accent_soft": "#5DADE22E",
    "steel": "#9AA5B1",
    "good": "#7DC383",
    "warn": "#E0B23C",
    "bad": "#E06C5F",
    "violet": "#B39DDB",
    # Build state is one ordinal scale: fill and stroke per step, then the
    # word the legend prints.
    "state": {
        "built": ["#232629", "#7E858F", "built"],
        "partial": ["#262620", "#E0B23C", "part built"],
        "planned": ["#17181A", "#454B53", "planned"],
    },
    "ghost": ["#17181A", "#2B2F34"],
    # Hard boundaries: (stroke, fill) per tone.
    "container": {
        "host": ["#454B53", "#17181A"],
        "client": ["#454B53", "#17181A"],
        "server": ["#3A3F46", "#181A1D"],
        "isolated": ["#6B4F45", "#1B1817"],
    },
    "region": "#8A9099",
    "change": "#E06C5F",
    "reach": "#5DADE2",
    "flow": "#5C636B",
    "layer_palette": LAYER_PALETTE,
    "layers": {},
    "delta": {
        "operations": "#82A7BA",
        "types": "#7DC383",
        "refusals": "#E06C5F",
        "tests": "#5DADE2",
    },
    "font_ui": SANS,
    "font_mono": MONO,
}


def merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """`override` laid over `base`: tables merge by key, everything else replaces."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def resolve(tokens: dict[str, Any], layers: Iterable[Layer]) -> dict[str, Any]:
    """The theme with a colour for every layer of the map, in layer order.

    A layer named in the `layers` table keeps its colour; the rest take the
    palette in order. The result is what the drawing reads.
    """
    t = merge(DEFAULT, tokens)
    named: dict[str, str] = dict(t.get("layers") or {})
    palette: list[str] = list(t.get("layer_palette") or LAYER_PALETTE)
    resolved: dict[str, str] = {}
    for i, layer in enumerate(layers):
        resolved[layer.id] = named.get(layer.id) or palette[i % len(palette)]
    t["layers"] = resolved
    return t


def css_vars(t: dict[str, Any]) -> str:
    """The :root block. One source for both halves of the page."""
    layers = "".join(f"--l-{k}:{v};" for k, v in t["layers"].items())
    return (
        f"color-scheme:{t['scheme']};"
        f"--bg:{t['bg']};--surface:{t['surface']};--raised:{t['raised']};"
        f"--line:{t['line']};--line-2:{t['line_2']};"
        f"--ink:{t['ink']};--ink-2:{t['ink_2']};--ink-3:{t['ink_3']};"
        f"--accent:{t['accent']};--accent-soft:{t['accent_soft']};"
        f"--steel:{t['steel']};--good:{t['good']};--warn:{t['warn']};"
        f"--bad:{t['bad']};--violet:{t['violet']};"
        f"--fs:{t['font_ui']};--fm:{t['font_mono']};"
        f"{layers}"
    )
