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

The page draws through variables. Every colour its drawing and its panel
take from the table is written as `var(--token)` (`Palette`, with
`variables=True`), and the tables themselves are the `:root` blocks the
page carries (`css_vars`), so the page can switch tables at runtime
without a redraw. A figure that leaves the page (`systemap figure`, a
README image, a preview) carries no table and is written with the literal
colours (`Palette` without `variables`); the two are the same table read
two ways, never two tables.
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


def _rgb(colour: str) -> tuple[int, int, int]:
    c = colour.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    """a towards b by t."""
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    r = round(ra + (rb - ra) * t)
    g = round(ga + (gb - ga) * t)
    bl = round(ba + (bb - ba) * t)
    return f"#{r:02X}{g:02X}{bl:02X}"


# The plain tokens, each with the name the page's CSS carries it under.
CSS_NAMES: dict[str, str] = {
    "bg": "--bg",
    "surface": "--surface",
    "raised": "--raised",
    "line": "--line",
    "line_2": "--line-2",
    "ink": "--ink",
    "ink_2": "--ink-2",
    "ink_3": "--ink-3",
    "accent": "--accent",
    "accent_soft": "--accent-soft",
    "steel": "--steel",
    "good": "--good",
    "warn": "--warn",
    "bad": "--bad",
    "violet": "--violet",
    "region": "--region",
    "change": "--change",
    "reach": "--reach",
    "flow": "--flow",
    "font_ui": "--fs",
    "font_mono": "--fm",
}

# How far each derived tint leans from its ground towards its colour: an
# actor's fill from the ground towards the second line, the change map's
# two tints from the ground towards change and reach, and a verb tag's
# fill from the raised surface towards the layer.
ACTOR_MIX = 0.35
CHANGED_MIX = 0.14
REACH_MIX = 0.12
TAG_MIX = 0.16


def tints(t: dict[str, Any]) -> dict[str, Any]:
    """The colours derived from the table, computed in one place so the
    `:root` block and a literal figure cannot disagree about a tint."""
    return {
        "actor": mix(t["bg"], t["line_2"], ACTOR_MIX),
        "changed_fill": mix(t["bg"], t["change"], CHANGED_MIX),
        "reach_fill": mix(t["bg"], t["reach"], REACH_MIX),
        "tags": {lid: mix(t["raised"], colour, TAG_MIX) for lid, colour in t["layers"].items()},
    }


class Palette:
    """Every colour the drawing writes, read from one table two ways.

    With `variables` each answer is `var(--token)`: the page carries the
    tables as `:root` blocks and switches them at runtime, so its drawing
    names tokens and never values. Without it each answer is the literal
    colour, for a figure that leaves the page and carries no table. The
    token names are the ones `css_vars` writes; nothing else names them.
    """

    def __init__(self, t: dict[str, Any], variables: bool = False) -> None:
        self.t = t
        self.variables = variables
        self._tints = tints(t)

    def _v(self, name: str, literal: str) -> str:
        return f"var({name})" if self.variables else literal

    def __getitem__(self, key: str) -> str:
        return self._v(CSS_NAMES[key], str(self.t[key]))

    def layer(self, lid: str) -> str:
        return self._v(f"--l-{lid}", self.t["layers"][lid])

    def tag(self, lid: str) -> str:
        """A verb tag's fill for a layer: the raised surface tinted with it."""
        return self._v(f"--lt-{lid}", self._tints["tags"][lid])

    def state(self, name: str) -> tuple[str, str, str]:
        """(fill, stroke, the legend's word) for a card in the given state."""
        fill, stroke, label = self.t["state"][name]
        return self._v(f"--card-{name}", fill), self._v(f"--card-{name}-line", stroke), label

    def actor(self) -> tuple[str, str]:
        """(fill, stroke) for an actor: a tint of the ground, the quiet ink."""
        return self._v("--actor", self._tints["actor"]), self["ink_3"]

    def ghost(self) -> tuple[str, str]:
        """(fill, stroke) for what a change map or a reach figure leaves unmarked."""
        fill, stroke = self.t["ghost"]
        return self._v("--ghost", fill), self._v("--ghost-line", stroke)

    def container(self, tone: str) -> tuple[str, str]:
        """(stroke, fill) for a container of the given tone, as the table orders them."""
        stroke, fill = self.t["container"][tone]
        return self._v(f"--box-{tone}-line", stroke), self._v(f"--box-{tone}", fill)

    def delta(self, key: str) -> str:
        return self._v(f"--d-{key}", self.t["delta"][key])

    def changed_fill(self) -> str:
        return self._v("--changed-fill", self._tints["changed_fill"])

    def reach_fill(self) -> str:
        return self._v("--reach-fill", self._tints["reach_fill"])


def css_vars(t: dict[str, Any]) -> str:
    """One scheme's declarations: every token the page's drawing and panel
    name, plain and derived, as one `:root` block's body."""
    d = tints(t)
    out = [f"color-scheme:{t['scheme']};"]
    out += [f"{name}:{t[key]};" for key, name in CSS_NAMES.items()]
    for state, (fill, stroke, _label) in t["state"].items():
        out.append(f"--card-{state}:{fill};--card-{state}-line:{stroke};")
    out.append(f"--actor:{d['actor']};--ghost:{t['ghost'][0]};--ghost-line:{t['ghost'][1]};")
    for tone, (stroke, fill) in t["container"].items():
        out.append(f"--box-{tone}:{fill};--box-{tone}-line:{stroke};")
    out.append(f"--changed-fill:{d['changed_fill']};--reach-fill:{d['reach_fill']};")
    out += [f"--d-{key}:{colour};" for key, colour in t["delta"].items()]
    out += [
        f"--l-{lid}:{colour};--lt-{lid}:{d['tags'][lid]};" for lid, colour in t["layers"].items()
    ]
    return "".join(out)
