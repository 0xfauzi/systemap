"""Color palettes for the map, inspector and page.

The warm, graphite and paper palettes contain the same CSS tokens.
The reader selects a palette on the page. Default text colors have
a contrast ratio of 4.5:1 or more on their background.
tests/test_theme.py measures these contrast ratios.

`[theme]` changes the default palette. A named table such as
`[theme.paper]` changes that palette. The aliases `dark` and `light`
select graphite and paper. Each layer has one color. Card kind marks
use an inner ring, notch or dotted border. Selection and active
sequence components use `accent`. Measurement components use `steel`.

Page colors use `var(--token)` through Palette with `variables=True`.
The page contains each palette table as CSS declarations. A palette
change does not cause another render. Separate figures use literal
color values from the same table."""

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
        "built": ["#27221a", "#8a7d63", "source recorded"],
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
    "ink_3": "#868b93",
    "accent": GRAPHITE_AMBER,
    "accent_soft": "#e0a4582e",
    "steel": "#8fb0c4",
    "good": "#8cbf8a",
    "warn": "#d6b14a",
    "bad": "#d97b6c",
    "violet": "#a99bd0",
    "state": {
        "built": ["#1f2329", "#6b7380", "source recorded"],
    },
    "ghost": ["#15181c", "#262b32"],
    "container": {
        "host": ["#3a4149", "#15181c"],
        "client": ["#3a4149", "#15181c"],
        "server": ["#2f353d", "#16191d"],
        "isolated": ["#6b5347", "#1a1715"],
    },
    "region": "#868b93",
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
        "built": ["#ffffff", "#7c838d", "source recorded"],
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
    """Combine tables by key. Replace other values from `base` with values from `override`."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def scheme_name(tokens: dict[str, Any]) -> str:
    """Give the palette name from `[theme]`, with support for the old aliases.

    Reject unknown names and list the available palettes."""
    scheme = tokens.get("scheme", DEFAULT_SCHEME)
    if not isinstance(scheme, str):
        raise ValueError(f"Select a theme scheme from {', '.join(SCHEMES)}")
    name = ALIASES.get(scheme, scheme)
    if name not in SCHEMES:
        raise ValueError(
            f"Unknown theme scheme {scheme!r}. The schemes are {', '.join(SCHEMES)} "
            f"(the 0.11 aliases dark and light select graphite and paper)"
        )
    return name


def _layers(t: dict[str, Any], layers: Iterable[Layer]) -> dict[str, str]:
    """Assign one color to each layer in layer order.

    Named layers keep their table color. Other layers use palette colors
    in sequence."""
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
    """Give the default palette table and all palette tables under `schemes`.

    `tokens` contains `[theme]` configuration. `scheme` selects the default
    palette. A named table changes that palette. Other keys change the
    default palette. The page uses all tables. Separate figures use only
    the default table."""
    layers = list(layers)
    name = scheme_name(tokens)
    own = {k: v for k, v in tokens.items() if k != "scheme" and k not in SCHEMES}
    tables: dict[str, dict[str, Any]] = {}
    for scheme, base in SCHEMES.items():
        override = tokens.get(scheme) or {}
        if not isinstance(override, dict):
            raise ValueError(f"theme.{scheme} must contain a table of CSS tokens")
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
    """Mix color `a` with color `b` by the fraction `t`."""
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
    """Calculate color mixtures for CSS declarations and separate figures."""
    return {
        "actor": mix(
            t["bg"], t["surface"] if t["color_scheme"] == "light" else t["line_2"], ACTOR_MIX
        ),
        "changed_fill": mix(t["bg"], t["change"], CHANGED_MIX),
        "reach_fill": mix(t["bg"], t["reach"], REACH_MIX),
        "tags": {lid: mix(t["raised"], colour, TAG_MIX) for lid, colour in t["layers"].items()},
    }


class Palette:
    """Give colors as CSS tokens or literal values from one palette table.

    With `variables`, values use `var(--token)` declarations from `css_vars`.
    Without `variables`, values contain literal colors for separate figures."""

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
        """Give the fill color for a layer direction verb label."""
        return self._v(f"--lt-{lid}", self._tints["tags"][lid])

    def state(self, name: str) -> tuple[str, str, str]:
        """Give the card fill, stroke and legend label for the specified state."""
        fill, stroke, label = self.t["state"][name]
        return self._v(f"--card-{name}", fill), self._v(f"--card-{name}-line", stroke), label

    def actor(self) -> tuple[str, str]:
        """Give the actor fill and stroke colors."""
        return self._v("--actor", self._tints["actor"]), self["ink_3"]

    def ghost(self) -> tuple[str, str]:
        """Give fill and stroke colors for components outside the selection."""
        fill, stroke = self.t["ghost"]
        return self._v("--ghost", fill), self._v("--ghost-line", stroke)

    def container(self, tone: str) -> tuple[str, str]:
        """Give the container stroke and fill colors for the specified tone."""
        stroke, fill = self.t["container"][tone]
        return self._v(f"--box-{tone}-line", stroke), self._v(f"--box-{tone}", fill)

    def delta(self, key: str) -> str:
        return self._v(f"--d-{key}", self.t["delta"][key])

    def changed_fill(self) -> str:
        return self._v("--changed-fill", self._tints["changed_fill"])

    def reach_fill(self) -> str:
        return self._v("--reach-fill", self._tints["reach_fill"])


def root_css(t: dict[str, Any]) -> str:
    """Give default, named and system light-palette CSS declarations.

    The page script sets `data-theme` before the first render. The page uses a stored
    selection first. Without a stored selection, it uses paper for a system
    light preference or the default palette. CSS media declarations
    supply the system preference when the script does not run."""
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
    """Give CSS declarations for all specified and calculated palette tokens."""
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
