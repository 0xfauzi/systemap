"""Color palettes for the map, inspector and page.

The Dark, Light and Clay palettes contain the same CSS tokens.
The reader selects a palette on the page. Default text colors have
a contrast ratio of 4.5:1 or more on their background.
tests/test_theme.py measures these contrast ratios.

`[theme]` changes the default palette. A named table such as
`[theme.light]` changes that palette. Each layer has one color. Card kind marks
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

STANDARD_LAYERS_DARK: dict[str, str] = {
    "structure": "#d8d3c6",
    "system": "#8fb0c4",
    "data": "#8fbfa6",
    "control": "#c9ae7c",
    "agents": "#c893ad",
    "context": "#c186c1",
    "tools": "#86c189",
}

LAYER_PALETTE_DARK: list[str] = ["#d39a8c", "#a99bd0", "#a9b87a", "#7fa6d1"]

DARK: dict[str, Any] = {
    "name": "systemap",
    "scheme": "dark",
    "color_scheme": "dark",
    "bg": "#08090a",
    "surface": "#101014",
    "raised": "#19191d",
    "line": "#252529",
    "line_2": "#424249",
    "ink": "#fafafa",
    "ink_2": "#bcbcc4",
    "ink_3": "#9898a3",
    "accent": "#fafafa",
    "accent_soft": "#fafafa14",
    "steel": "#8fb0c4",
    "good": "#8cbf8a",
    "warn": "#d6b14a",
    "bad": "#d97b6c",
    "violet": "#a99bd0",
    "state": {"built": ["#101014", "#71717a", "source recorded"]},
    "ghost": ["#101014", "#252529"],
    "container": {
        "host": ["#424249", "#0d0e11"],
        "client": ["#424249", "#0d0e11"],
        "server": ["#424249", "#0d0e11"],
        "isolated": ["#66666f", "#121216"],
    },
    "region": "#9898a3",
    "change": "#d97b6c",
    "reach": "#fafafa",
    "flow": "#52525b",
    "layer_palette": LAYER_PALETTE_DARK,
    "layers": dict(STANDARD_LAYERS_DARK),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": "#8fb0c4",
        "types": "#8cbf8a",
        "refusals": "#d97b6c",
        "tests": "#fafafa",
    },
    "font_ui": SANS,
    "font_mono": MONO,
}

STANDARD_LAYERS_LIGHT: dict[str, str] = {
    "structure": "#71674d",
    "system": "#466c84",
    "data": "#417158",
    "control": "#7e6434",
    "agents": "#9a4f74",
    "context": "#954c95",
    "tools": "#3c743f",
}

LAYER_PALETTE_LIGHT: list[str] = ["#a1513d", "#7059b1", "#616d3b", "#396aa0"]

LIGHT: dict[str, Any] = {
    "name": "systemap",
    "scheme": "light",
    "color_scheme": "light",
    "bg": "#ffffff",
    "surface": "#ffffff",
    "raised": "#f4f4f4",
    "line": "#e5e5e5",
    "line_2": "#b8b8bd",
    "ink": "#0a0a0a",
    "ink_2": "#525252",
    "ink_3": "#646464",
    "accent": "#0a0a0a",
    "accent_soft": "#0a0a0a0d",
    "steel": "#466c84",
    "good": "#41733f",
    "warn": "#7f641d",
    "bad": "#b5412f",
    "violet": "#7059b1",
    "state": {"built": ["#ffffff", "#a1a1aa", "source recorded"]},
    "ghost": ["#f4f4f4", "#e5e5e5"],
    "container": {
        "host": ["#b8b8bd", "#fafafa"],
        "client": ["#b8b8bd", "#fafafa"],
        "server": ["#b8b8bd", "#fafafa"],
        "isolated": ["#a1a1aa", "#f4f4f4"],
    },
    "region": "#646464",
    "change": "#b5412f",
    "reach": "#0a0a0a",
    "flow": "#a1a1aa",
    "layer_palette": LAYER_PALETTE_LIGHT,
    "layers": dict(STANDARD_LAYERS_LIGHT),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": "#466c84",
        "types": "#41733f",
        "refusals": "#b5412f",
        "tests": "#0a0a0a",
    },
    "font_ui": SANS,
    "font_mono": MONO,
}

STANDARD_LAYERS_CLAY: dict[str, str] = {
    "structure": "#d9cdb2",
    "system": "#82a7ba",
    "data": "#e39a86",
    "control": "#dd9bbd",
    "agents": "#b48ec9",
    "context": "#86c9a9",
    "tools": "#b7c27c",
}

LAYER_PALETTE_CLAY: list[str] = ["#e3b778", "#bbc1f1", "#7ed1d6", "#e7b8bb"]

CLAY: dict[str, Any] = {
    "name": "systemap",
    "scheme": "clay",
    "color_scheme": "dark",
    "bg": "#111214",
    "surface": "#17181b",
    "raised": "#1e1f21",
    "line": "#292a2c",
    "line_2": "#4d4e52",
    "ink": "#fbfcfc",
    "ink_2": "#cdcecf",
    "ink_3": "#9a9b9d",
    "accent": "#cf8b6b",
    "accent_soft": "#cf8b6b1a",
    "steel": "#82a7ba",
    "good": "#8fc470",
    "warn": "#c4a077",
    "bad": "#dda5a1",
    "violet": "#b48ec9",
    "state": {"built": ["#17181b", "#85868a", "source recorded"]},
    "ghost": ["#17181b", "#292a2c"],
    "container": {
        "host": ["#4d4e52", "#141518"],
        "client": ["#4d4e52", "#141518"],
        "server": ["#4d4e52", "#141518"],
        "isolated": ["#8c6251", "#1b1716"],
    },
    "region": "#9a9b9d",
    "change": "#dda5a1",
    "reach": "#cf8b6b",
    "flow": "#65605e",
    "layer_palette": LAYER_PALETTE_CLAY,
    "layers": dict(STANDARD_LAYERS_CLAY),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": "#82a7ba",
        "types": "#8fc470",
        "refusals": "#dda5a1",
        "tests": "#cf8b6b",
    },
    "font_ui": SANS,
    "font_mono": MONO,
}

SCHEMES: dict[str, dict[str, Any]] = {"dark": DARK, "light": LIGHT, "clay": CLAY}
DEFAULT_SCHEME = "dark"
LIGHT_SCHEME = "light"

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
    """Give the palette name from `[theme]`, from the configuration.

    Reject unknown names and list the available palettes."""
    scheme = tokens.get("scheme", DEFAULT_SCHEME)
    if not isinstance(scheme, str):
        raise ValueError(f"Select a theme scheme from {', '.join(SCHEMES)}")
    name = scheme
    if name not in SCHEMES:
        raise ValueError(f"Unknown theme scheme {scheme!r}. The schemes are {', '.join(SCHEMES)}")
    return name


def _layers(t: dict[str, Any], layers: Iterable[Layer]) -> dict[str, str]:
    """Assign one color to each layer in layer order.

    Named layers keep their table color. Other layers use palette colors
    in sequence."""
    named: dict[str, str] = dict(t.get("layers") or {})
    palette: list[str] = list(t.get("layer_palette") or LAYER_PALETTE_DARK)
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
    selection first. Without a stored selection, it uses Light for a system
    light preference or Dark. CSS media declarations supply the device theme
    without the script."""
    schemes: dict[str, dict[str, Any]] = t.get("schemes") or {t["scheme"]: t}
    out = [f":root{{{css_vars(schemes.get(DEFAULT_SCHEME, t))}}}"]
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
