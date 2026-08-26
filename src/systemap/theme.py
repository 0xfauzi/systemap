"""The map's look, as one table of tokens per scheme.

Everything visual lives here so the scene, the panel and the page cannot
disagree about a colour. Three schemes, each a full table of the same
tokens, and the reader picks one on the page:

    warm ....... the default: ink #ece5d8 on a warm dark ground #161310,
                 an amber accent #e5a84f, low-chroma layer hues
    graphite ... the cool dark scheme: ink #e6e4df on graphite #121417,
                 a muted amber #e0a458
    paper ...... the light scheme: ink #1d2024 on paper #f4f2ee, with
                 every hue that is read as text darkened until it clears
                 4.5:1 on paper

Every text token of every scheme clears 4.5:1 on its ground (measured, not
guessed; the ratios are recorded in the commit that set them, and
tests/test_theme.py holds them). A consumer picks the default with
`scheme = "warm"` under `[theme]` and overrides any token from there
(`[theme]` applies to the default scheme, `[theme.paper]` to one scheme);
the result is merged over the scheme's table, so every token name is the
same in all three. The names 0.11 used, `dark` and `light`, still pick
graphite and paper.

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
page carries (`css_vars`), so the page switches schemes at runtime
without a redraw. A figure that leaves the page (`systemap figure`, a
README image) carries no table and is written with the literal colours
(`Palette` without `variables`); the two are the same table read two
ways, never two tables.
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

# The ground, the ink and the accent each scheme is named for.
WARM_GROUND = "#161310"
WARM_INK = "#ece5d8"
WARM_AMBER = "#e5a84f"
GRAPHITE_GROUND = "#121417"
GRAPHITE_INK = "#e6e4df"
GRAPHITE_AMBER = "#e0a458"
PAPER_GROUND = "#f4f2ee"
PAPER_INK = "#1d2024"
PAPER_AMBER = "#905c1a"

# The standard layers' hues per scheme: the two derived readings, the two
# standard kinds, and the three agent readings. Each reads apart from the
# others and stays quieter than the accent. Then the hues for the model's
# own layers, taken in order; a map with more custom layers than this
# wraps around. Warm's four were searched for the widest CIELAB distance
# from its standard hues at low chroma (the first is the eighth hue of the
# scheme; the other three were picked by that search and looked at).
STANDARD_LAYERS_WARM: dict[str, str] = {
    "structure": "#d9cdb2",
    "system": "#82a7ba",
    "data": "#e39a86",
    "control": "#dd9bbd",
    "agents": "#b48ec9",
    "context": "#86c9a9",
    "tools": "#b7c27c",
}
LAYER_PALETTE_WARM: list[str] = ["#e3b778", "#bbc1f1", "#7ed1d6", "#e7b8bb"]

STANDARD_LAYERS_GRAPHITE: dict[str, str] = {
    "structure": "#d8d3c6",
    "system": "#8fb0c4",
    "data": "#8fbfa6",
    "control": "#c9ae7c",
    "agents": "#c893ad",
    "context": "#c186c1",
    "tools": "#86c189",
}
LAYER_PALETTE_GRAPHITE: list[str] = ["#d39a8c", "#a99bd0", "#a9b87a", "#7fa6d1"]

# Graphite's hues darkened in HSL until each clears 4.5:1 as text on paper.
STANDARD_LAYERS_PAPER: dict[str, str] = {
    "structure": "#71674d",
    "system": "#466c84",
    "data": "#417158",
    "control": "#7e6434",
    "agents": "#9a4f74",
    "context": "#954c95",
    "tools": "#3c743f",
}
LAYER_PALETTE_PAPER: list[str] = ["#a1513d", "#7059b1", "#616d3b", "#396aa0"]

# Each table: `scheme` is its name, `color_scheme` what the browser is told
# (its form controls and scrollbars follow). A card's `state` is its fill,
# its stroke, then the word the legend prints; there is one state, a card
# is code that exists today. `ghost` is what a change map or a reach figure
# draws for the parts it does not mark, (fill, stroke). `container` holds
# the hard boundaries, (stroke, fill) per tone.
WARM: dict[str, Any] = {
    "name": "systemap",
    "scheme": "warm",
    "color_scheme": "dark",
    "bg": WARM_GROUND,
    "surface": "#1e1a15",
    "raised": "#27221a",
    "line": "#2e2820",
    "line_2": "#4a4237",
    "ink": WARM_INK,
    "ink_2": "#c4b9a4",
    "ink_3": "#a2967f",
    "accent": WARM_AMBER,
    "accent_soft": "#e5a84f2e",
    "steel": "#82a7ba",
    "good": "#8fc470",
    "warn": "#d9b036",
    "bad": "#e26d5a",
    "violet": "#b48ec9",
    "state": {
        "built": ["#27221a", "#8a7d63", "built"],
    },
    "ghost": ["#1a1713", "#2e2820"],
    "container": {
        "host": ["#4a4237", "#1a1713"],
        "client": ["#4a4237", "#1a1713"],
        "server": ["#3b3428", "#1b1814"],
        "isolated": ["#6b4a3d", "#1d1613"],
    },
    "region": "#a2967f",
    "change": "#e26d5a",
    "reach": WARM_AMBER,
    "flow": "#5e5548",
    "layer_palette": LAYER_PALETTE_WARM,
    "layers": dict(STANDARD_LAYERS_WARM),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": "#82a7ba",
        "types": "#8fc470",
        "refusals": "#e26d5a",
        "tests": WARM_AMBER,
    },
    "font_ui": SANS,
    "font_mono": MONO,
}

GRAPHITE: dict[str, Any] = {
    "name": "systemap",
    "scheme": "graphite",
    "color_scheme": "dark",
    "bg": GRAPHITE_GROUND,
    "surface": "#181b1f",
    "raised": "#1f2329",
    "line": "#262b32",
    "line_2": "#3a4149",
    "ink": GRAPHITE_INK,
    "ink_2": "#b3b1aa",
    "ink_3": "#858a92",
    "accent": GRAPHITE_AMBER,
    "accent_soft": "#e0a4582e",
    "steel": "#8fb0c4",
    "good": "#8cbf8a",
    "warn": "#d6b14a",
    "bad": "#d97b6c",
    "violet": "#a99bd0",
    "state": {
        "built": ["#1f2329", "#6b7380", "built"],
    },
    "ghost": ["#15181c", "#262b32"],
    "container": {
        "host": ["#3a4149", "#15181c"],
        "client": ["#3a4149", "#15181c"],
        "server": ["#2f353d", "#16191d"],
        "isolated": ["#6b5347", "#1a1715"],
    },
    "region": "#858a92",
    "change": "#d97b6c",
    "reach": GRAPHITE_AMBER,
    "flow": "#4a515a",
    "layer_palette": LAYER_PALETTE_GRAPHITE,
    "layers": dict(STANDARD_LAYERS_GRAPHITE),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": "#8fb0c4",
        "types": "#8cbf8a",
        "refusals": "#d97b6c",
        "tests": GRAPHITE_AMBER,
    },
    "font_ui": SANS,
    "font_mono": MONO,
}

PAPER: dict[str, Any] = {
    "name": "systemap",
    "scheme": "paper",
    "color_scheme": "light",
    "bg": PAPER_GROUND,
    "surface": "#ffffff",
    "raised": "#ebe9e4",
    "line": "#d9d6cf",
    "line_2": "#b9b5ac",
    "ink": PAPER_INK,
    "ink_2": "#55534d",
    "ink_3": "#646870",
    "accent": PAPER_AMBER,
    "accent_soft": "#905c1a2e",
    "steel": "#466c84",
    "good": "#41733f",
    "warn": "#7f641d",
    "bad": "#b5412f",
    "violet": "#7059b1",
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
    "region": "#646870",
    "change": "#b5412f",
    "reach": PAPER_AMBER,
    "flow": "#b4b8be",
    "layer_palette": LAYER_PALETTE_PAPER,
    "layers": dict(STANDARD_LAYERS_PAPER),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": "#466c84",
        "types": "#41733f",
        "refusals": "#b5412f",
        "tests": PAPER_AMBER,
    },
    "font_ui": SANS,
    "font_mono": MONO,
}

# The schemes in the order the page offers them.
SCHEMES: dict[str, dict[str, Any]] = {"warm": WARM, "graphite": GRAPHITE, "paper": PAPER}
# The names 0.11 knew the two older schemes by.
ALIASES: dict[str, str] = {"dark": "graphite", "light": "paper"}
# The scheme a consumer gets when it names none.
DEFAULT_SCHEME = "warm"
# The scheme a first visit gets when the reader's system prefers light.
LIGHT_SCHEME = "paper"
# The tokens that are read as text somewhere on the page, held to 4.5:1
# on the ground; a layer hue is text too (an edge's label, a verb tag).
TEXT_TOKENS = (
    "ink",
    "ink_2",
    "ink_3",
    "accent",
    "steel",
    "good",
    "warn",
    "bad",
    "violet",
    "region",
)


def merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """`override` laid over `base`: tables merge by key, everything else replaces."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def scheme_name(tokens: dict[str, Any]) -> str:
    """The default scheme a consumer's `[theme]` names, the older names mapped.

    A word that is no scheme is refused with the three named: a typo that
    quietly fell back to one of them would render a page the consumer did
    not ask for.
    """
    scheme = tokens.get("scheme", DEFAULT_SCHEME)
    if not isinstance(scheme, str):
        raise ValueError(f"theme scheme must be one of {', '.join(SCHEMES)}")
    name = ALIASES.get(scheme, scheme)
    if name not in SCHEMES:
        raise ValueError(
            f"unknown theme scheme {scheme!r}; the schemes are {', '.join(SCHEMES)} "
            f"(dark and light, the names 0.11 used, still pick graphite and paper)"
        )
    return name


def _layers(t: dict[str, Any], layers: Iterable[Layer]) -> dict[str, str]:
    """A colour for every layer of the map, in layer order: a layer named in
    the `layers` table keeps its colour (the scheme names every standard
    layer); the rest, the model's own, take the palette in order."""
    named: dict[str, str] = dict(t.get("layers") or {})
    palette: list[str] = list(t.get("layer_palette") or LAYER_PALETTE_WARM)
    resolved: dict[str, str] = {}
    unnamed = 0
    for layer in layers:
        colour = named.get(layer.id)
        if not colour:
            colour = palette[unnamed % len(palette)]
            unnamed += 1
        resolved[layer.id] = colour
    return resolved


def resolve(tokens: dict[str, Any], layers: Iterable[Layer]) -> dict[str, Any]:
    """The default scheme's table with a colour for every layer of the map,
    carrying every scheme's table under `schemes`.

    `tokens` is the consumer's `[theme]`: `scheme` names the default, a
    sub-table named for a scheme (`[theme.paper]`) overrides that scheme,
    and every other key overrides the default scheme. Each scheme's table
    is merged the same way, so the page can carry all three and a token
    name means the same thing in each. The result is what the drawing
    reads; a figure reads the default's table alone.
    """
    layers = list(layers)
    name = scheme_name(tokens)
    own = {k: v for k, v in tokens.items() if k != "scheme" and k not in SCHEMES}
    tables: dict[str, dict[str, Any]] = {}
    for scheme, base in SCHEMES.items():
        override = tokens.get(scheme) or {}
        if not isinstance(override, dict):
            raise ValueError(f"theme.{scheme} must be a table of tokens")
        if scheme == name:
            override = merge(own, override)
        t = merge(base, override)
        t["scheme"] = scheme
        t["layers"] = _layers(t, layers)
        tables[scheme] = t
    out = copy.deepcopy(tables[name])
    out["schemes"] = tables
    return out


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


def root_css(t: dict[str, Any]) -> str:
    """The page's root blocks: the default scheme's table on `:root`, every
    scheme's under `:root[data-theme="<name>"]`, and the light scheme's
    under `prefers-color-scheme: light` for a root no script has stamped.

    The page's head script stamps `data-theme` before the first paint
    (the stored pick, else paper when the system prefers light, else the
    default), so the attribute blocks are what a reader sees; the bare
    `:root` and the media block carry a page whose script did not run.
    """
    schemes: dict[str, dict[str, Any]] = t.get("schemes") or {t["scheme"]: t}
    out = [f":root{{{css_vars(t)}}}"]
    out += [f':root[data-theme="{name}"]{{{css_vars(table)}}}' for name, table in schemes.items()]
    light = schemes.get(LIGHT_SCHEME)
    if light is not None:
        out.append(
            f"@media (prefers-color-scheme:light){{:root:not([data-theme]){{{css_vars(light)}}}}}"
        )
    return "".join(out)


def css_vars(t: dict[str, Any]) -> str:
    """One scheme's declarations: every token the page's drawing and panel
    name, plain and derived, as one `:root` block's body."""
    d = tints(t)
    out = [f"color-scheme:{t['color_scheme']};"]
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
