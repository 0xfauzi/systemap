"""The map's look, as one table of tokens.

Everything visual lives here so the scene, the panel and the page cannot
disagree about a colour. The palette is cool graphite with one muted amber
accent and low-chroma layer hues; nothing on the page is saturated:

    graphite #121417 .. the ground
    surface #181b1f ... panels; raised #1f2329 for what sits on a panel
    ink #e6e4df ....... text; ink_2 #b3b1aa and ink_3 #858a92 quieter
    amber #e0a458 ..... the component the reader clicked (accent), and reach
    steel #8fb0c4 ..... measurement

Two schemes share the palette. `dark` puts ink on graphite; `light` puts
ink #1d2024 on paper #f4f2ee, with every hue that is read as text darkened
until it clears 4.5:1 on paper (measured, not guessed; the values are
recorded in the commit that set them). A consumer picks one with
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

GRAPHITE = "#121417"
INK = "#e6e4df"
AMBER = "#e0a458"
STEEL = "#8fb0c4"
PAPER = "#f4f2ee"
INK_ON_PAPER = "#1d2024"

# The standard layers' hues on graphite: the two derived readings, the two
# standard kinds, and the three agent readings. Each reads apart from the
# others (the agent three were searched for the widest CIE distance from
# the rest at low chroma) and stays quieter than the accent.
STANDARD_LAYERS_DARK: dict[str, str] = {
    "structure": "#d8d3c6",
    "system": "#8fb0c4",
    "data": "#8fbfa6",
    "control": "#c9ae7c",
    "agents": "#c893ad",
    "context": "#c186c1",
    "tools": "#86c189",
}

# Hues for the model's own layers, taken in order; a map with more custom
# layers than this wraps around.
LAYER_PALETTE: list[str] = ["#d39a8c", "#a99bd0", "#a9b87a", "#7fa6d1"]

# The same hues darkened in HSL until each clears 4.5:1 as text on paper.
STANDARD_LAYERS_LIGHT: dict[str, str] = {
    "structure": "#786e52",
    "system": "#4a738c",
    "data": "#45785d",
    "control": "#866b37",
    "agents": "#a4547b",
    "context": "#9f519f",
    "tools": "#3f7b42",
}
LAYER_PALETTE_LIGHT: list[str] = ["#ab5641", "#7660b4", "#67743e", "#3d71aa"]

DARK: dict[str, Any] = {
    "name": "systemap",
    "scheme": "dark",
    "bg": GRAPHITE,
    "surface": "#181b1f",
    "raised": "#1f2329",
    "line": "#262b32",
    "line_2": "#3a4149",
    "ink": INK,
    "ink_2": "#b3b1aa",
    "ink_3": "#858a92",
    "accent": AMBER,
    "accent_soft": "#e0a4582e",
    "steel": STEEL,
    "good": "#8cbf8a",
    "warn": "#d6b14a",
    "bad": "#d97b6c",
    "violet": "#a99bd0",
    # A card's fill and stroke, then the word the legend prints. There is
    # one state: a card is code that exists today.
    "state": {
        "built": ["#1f2329", "#6b7380", "built"],
    },
    # What a change map or a reach figure draws for the parts it does not
    # mark: (fill, stroke).
    "ghost": ["#15181c", "#262b32"],
    # Hard boundaries: (stroke, fill) per tone.
    "container": {
        "host": ["#3a4149", "#15181c"],
        "client": ["#3a4149", "#15181c"],
        "server": ["#2f353d", "#16191d"],
        "isolated": ["#6b5347", "#1a1715"],
    },
    "region": "#858a92",
    "change": "#d97b6c",
    "reach": AMBER,
    "flow": "#4a515a",
    "layer_palette": LAYER_PALETTE,
    "layers": dict(STANDARD_LAYERS_DARK),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": STEEL,
        "types": "#8cbf8a",
        "refusals": "#d97b6c",
        "tests": AMBER,
    },
    "font_ui": SANS,
    "font_mono": MONO,
}

LIGHT: dict[str, Any] = {
    "name": "systemap",
    "scheme": "light",
    "bg": PAPER,
    "surface": "#ffffff",
    "raised": "#ebe9e4",
    "line": "#d9d6cf",
    "line_2": "#b9b5ac",
    "ink": INK_ON_PAPER,
    "ink_2": "#55534d",
    "ink_3": "#6a6f77",
    "accent": "#99621c",
    "accent_soft": "#99621c2e",
    "steel": "#4a738c",
    "good": "#457a43",
    "warn": "#876b1f",
    "bad": "#bf4531",
    "violet": "#7660b4",
    "state": {
        "built": ["#ffffff", "#7c838d", "built"],
    },
    "ghost": ["#efede8", "#d9d6cf"],
    "container": {
        "host": ["#b9b5ac", "#efede8"],
        "client": ["#b9b5ac", "#efede8"],
        "server": ["#c4c0b7", "#f1efea"],
        "isolated": ["#b08a7c", "#f3ece8"],
    },
    "region": "#6a6f77",
    "change": "#bf4531",
    "reach": "#99621c",
    "flow": "#b4b8be",
    "layer_palette": LAYER_PALETTE_LIGHT,
    "layers": dict(STANDARD_LAYERS_LIGHT),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": "#4a738c",
        "types": "#457a43",
        "refusals": "#bf4531",
        "tests": "#99621c",
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
    picks the graphite scheme. An unknown scheme word is not refused here:
    the page's `color-scheme` carries it through, and the tokens fall back
    to the graphite scheme, so an older configuration keeps rendering.
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
