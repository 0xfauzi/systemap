"""The map's look, as one table of tokens.

Everything visual lives here so the scene, the panel and the page cannot
disagree about a colour. The default is systemap's own palette, the one the
logo and the README use, so the page and the brand agree:

    ink #0b1020 ...... the ground
    panel #101a3a .... surfaces
    slate #4b5578 .... what is present but not lit
    muted #aab3d1 .... secondary text
    paper #f4f1ea .... text
    amber #f5a524 .... the component the reader clicked (accent)
    teal #2dd4bf ..... what it reaches: lit routes, built parts, reach

Two schemes share the palette. `dark` puts paper on ink; `light` puts ink
on paper, with amber and teal darkened to stay legible. A consumer picks one with
`scheme = "light"` under `[theme]` and overrides any token from there; the
result is merged over the scheme's table, so every token name stays the
same in both.

Colour carries meaning or is absent:

    accent ...... you are interacting with this (selection, focus, the node
                  that ACTS in a journey step)
    steel ....... measurement (the node that MEASURES a step)
    layers ...... one hue per layer of the map, printed in the page legend;
                  the `layers` table names the standard layers' colours,
                  and the model's own layers take `layer_palette` in order
    marks ....... how an agent, a tool and a context card are told apart
                  from a component: a mark per kind (ring, notch, dotted),
                  never a colour
    good ........ what is there (every card is; the check refuses the rest)
    bad ......... only for "nothing measures this step" and a change map

Nothing else on the page is coloured.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable
from typing import Any

from systemap.model import Layer

# The marks a card may carry for its kind. A ring is a second border inside
# the first; a notch is a filled corner; dotted is the border itself.
MARKS = ("ring", "notch", "dotted")
KIND_MARKS: dict[str, str] = {"agent": "ring", "tool": "notch", "context": "dotted"}

SANS = (
    'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,'
    '"Helvetica Neue",Arial,sans-serif'
)
MONO = 'ui-monospace,"SF Mono",SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace'

INK = "#0b1020"
PANEL = "#101a3a"
SLATE = "#4b5578"
MUTED = "#aab3d1"
PAPER = "#f4f1ea"
AMBER = "#f5a524"
TEAL = "#2dd4bf"

# The standard layers' hues on the ink ground: the two derived readings,
# the two standard kinds, and the three agent readings. Each reads apart
# from the others and stays quieter than the accent.
STANDARD_LAYERS_DARK: dict[str, str] = {
    "structure": "#D9D2C0",
    "system": "#82A7BA",
    "data": TEAL,
    "control": "#E3B778",
    "agents": "#B48EC9",
    "context": "#DD9BBD",
    "tools": "#B7C27C",
}

# Hues for the model's own layers, taken in order; a map with more custom
# layers than this wraps around.
LAYER_PALETTE: list[str] = [
    "#E39A86",
    "#8FB8D8",
    "#C9B47A",
    "#9BC4A0",
]

# The same on a paper ground. Pure amber and teal read at under 2:1 on
# paper, so the light scheme darkens both until they clear 4.5:1 as text
# (measured: #936316 at 4.61, #1a7b6f at 4.53) and keeps their hue.
STANDARD_LAYERS_LIGHT: dict[str, str] = {
    "structure": "#8A7F5C",
    "system": "#3D7A94",
    "data": "#1a7b6f",
    "control": "#B8792E",
    "agents": "#7B4FA3",
    "context": "#B0508E",
    "tools": "#6F7E2A",
}
LAYER_PALETTE_LIGHT: list[str] = [
    "#C2543A",
    "#3A6F94",
    "#8A6E1E",
    "#3F7A47",
]

DARK: dict[str, Any] = {
    "name": "systemap",
    "scheme": "dark",
    "bg": INK,
    "surface": PANEL,
    "raised": "#182452",
    "line": "#1c2650",
    "line_2": "#2e3a66",
    "ink": PAPER,
    "ink_2": MUTED,
    "ink_3": "#7f8ab0",
    "accent": AMBER,
    "accent_soft": "#f5a5242E",
    "steel": MUTED,
    "good": TEAL,
    "warn": "#E0B23C",
    "bad": "#E06C5F",
    "violet": "#B39DDB",
    # A card's fill and stroke, then the word the legend prints. There is
    # one state: a card is code that exists today.
    "state": {
        "built": [PANEL, "#8a95bd", "built"],
    },
    # What a change map or a reach figure draws for the parts it does not
    # mark: (fill, stroke).
    "ghost": ["#0d1430", "#1c2650"],
    # Hard boundaries: (stroke, fill) per tone.
    "container": {
        "host": ["#2e3a66", "#0d1430"],
        "client": ["#2e3a66", "#0d1430"],
        "server": ["#26305a", "#0e1533"],
        "isolated": ["#6B4F45", "#161426"],
    },
    "region": "#7f8ab0",
    "change": "#E06C5F",
    "reach": TEAL,
    "flow": SLATE,
    "layer_palette": LAYER_PALETTE,
    "layers": dict(STANDARD_LAYERS_DARK),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": "#82A7BA",
        "types": TEAL,
        "refusals": "#E06C5F",
        "tests": AMBER,
    },
    "font_ui": SANS,
    "font_mono": MONO,
}

LIGHT: dict[str, Any] = {
    "name": "systemap",
    "scheme": "light",
    "bg": PAPER,
    "surface": "#fbf9f4",
    "raised": "#ece8dc",
    "line": "#dcd7c8",
    "line_2": "#bfb9a8",
    "ink": INK,
    "ink_2": "#3a4265",
    "ink_3": "#6b7394",
    "accent": "#936316",
    "accent_soft": "#f5a5242E",
    "steel": "#6b7394",
    "good": "#1a7b6f",
    "warn": "#B07D0A",
    "bad": "#C0392B",
    "violet": "#7B4FA3",
    "state": {
        "built": ["#ffffff", "#6b7394", "built"],
    },
    "ghost": ["#f1eee6", "#dcd7c8"],
    "container": {
        "host": ["#bfb9a8", "#f7f4ec"],
        "client": ["#bfb9a8", "#f7f4ec"],
        "server": ["#c9c3b1", "#f9f6ef"],
        "isolated": ["#b08a7c", "#f8f1ee"],
    },
    "region": "#6b7394",
    "change": "#C0392B",
    "reach": "#1a7b6f",
    "flow": "#8b93b3",
    "layer_palette": LAYER_PALETTE_LIGHT,
    "layers": dict(STANDARD_LAYERS_LIGHT),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": "#3D7A94",
        "types": "#1a7b6f",
        "refusals": "#C0392B",
        "tests": "#936316",
    },
    "font_ui": SANS,
    "font_mono": MONO,
}

SCHEMES: dict[str, dict[str, Any]] = {"dark": DARK, "light": LIGHT}

# The scheme a consumer gets when it names none.
DEFAULT: dict[str, Any] = DARK


def merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """`override` laid over `base`: tables merge by key, everything else replaces."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def base_for(tokens: dict[str, Any]) -> dict[str, Any]:
    """The scheme table the consumer's tokens are laid over.

    `scheme = "light"` picks the paper scheme; anything else, or nothing,
    picks the ink scheme. An unknown scheme word is not refused here: the
    page's `color-scheme` carries it through, and the tokens fall back to
    the ink scheme, so an older configuration keeps rendering.
    """
    scheme = tokens.get("scheme")
    if isinstance(scheme, str) and scheme in SCHEMES:
        return SCHEMES[scheme]
    return DEFAULT


def resolve(tokens: dict[str, Any], layers: Iterable[Layer]) -> dict[str, Any]:
    """The theme with a colour for every layer of the map, in layer order.

    A layer named in the `layers` table keeps its colour (the scheme names
    every standard layer); the rest, the model's own, take the palette in
    order. The result is what the drawing reads.
    """
    t = merge(base_for(tokens), tokens)
    named: dict[str, str] = dict(t.get("layers") or {})
    palette: list[str] = list(t.get("layer_palette") or LAYER_PALETTE)
    resolved: dict[str, str] = {}
    unnamed = 0
    for layer in layers:
        colour = named.get(layer.id)
        if not colour:
            colour = palette[unnamed % len(palette)]
            unnamed += 1
        resolved[layer.id] = colour
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
