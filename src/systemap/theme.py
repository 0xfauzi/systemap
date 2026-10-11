"""Color palettes for the map, inspector and page.

The Ink palette (scheme `dark`, the default) and the Paper palette
(scheme `light`) contain the same CSS tokens. The page shows the names
in `SCHEME_LABELS`. The reader selects a palette on the page.

Only the flow kind, the selection and the change have a color. All other
items are neutral. Each flow kind layer has one color. Derived layers have
the card border color and do not change the color of flow lines. Selection uses
`accent`: Ink shows an amber line and ring, and Paper shows an ink line
and ring on a yellow highlighter fill (`hl`). `change` shows only in the
Changes view. Measurement components use `steel`, which is neutral. The
tokens `good`, `warn`, `bad` and `violet` stay for configuration
compatibility, and they have neutral text values. `brand` is the color
of the two dots in the logo. It is not a map color.

Text tokens have a contrast ratio of 4.5:1 or more on the bg, surface,
raised, map and card colors. Line colors have 3:1 or more on the map.
tests/test_theme.py measures these contrast ratios.

`[theme]` changes the default palette. A named table such as
`[theme.light]` changes that palette. A removed scheme name, such as
`clay`, gives a configuration error. Card kind marks use an inner ring,
notch or dotted border.

Page colors use `var(--token)` through Palette with `variables=True`.
The page contains each palette table as CSS declarations. A palette
change does not cause another render. Separate figures use literal
color values from the same table."""

from __future__ import annotations

import copy
import re
from collections.abc import Iterable
from typing import Any

from systemap.model import Layer

# The marks a card may carry for its kind. A ring is a second border inside
# the first; a notch is a filled corner; dotted is the border itself.
MARKS = ("ring", "notch", "dotted")
KIND_MARKS: dict[str, str] = {"agent": "ring", "tool": "notch", "context": "dotted"}

# The page uses the fonts of the computer and loads no font files. `system-ui`
# gives SF Pro on macOS, Segoe UI on Windows and the desktop font on Linux.
# Card descriptions use the measured font in `schematic_cards.PLAIN_FONT`.
SANS = 'system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
MONO = 'ui-monospace,"SF Mono",SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace'

# ---- Ink (scheme `dark`, the default) -----------------------------------------
# The values come from the measured color work (CIEDE2000 between the colors
# that show on one view, with normal vision and three color deficiencies).
# A derived layer (structure, system, agents) selects lines and does not
# color them: its flow lines keep the color of their kind. Its only color is
# the border of its subject cards, which is the card border color, as on the
# design boards.

INK_2_DARK = "#BEB8AC"
CARD_LINE_DARK = "#716C63"

# No kind color in Ink or Paper has an OKLCH hue from 180 to 350 degrees.
# This hue range contains cyan, blue, violet, purple and magenta.
STANDARD_LAYERS_DARK: dict[str, str] = {
    "structure": CARD_LINE_DARK,
    "system": CARD_LINE_DARK,
    "data": "#2CB59A",
    "control": "#B97874",
    "agents": CARD_LINE_DARK,
    "context": "#D1EC9F",
    "tools": "#8A8708",
}

# The first entry is the first custom kind ("judge" on the self-map).
# context, tools and the custom kinds after the first were measured with the
# same limits: data, control, context and tools pass on one view, and data,
# control and two custom kinds pass on one view. With these values, five
# kinds on one view do not pass, so a view shows four kind colors at most.
LAYER_PALETTE_DARK: list[str] = ["#8A8B22", "#DCE8B8", "#C6ED9F", "#7C9128"]

DARK: dict[str, Any] = {
    "name": "systemap",
    "scheme": "dark",
    "color_scheme": "dark",
    "bg": "#0F0E0C",
    "surface": "#161411",
    "raised": "#211E1A",
    "map": "#12110F",
    "grid": "#1E1C18",
    "card": "#1C1A17",
    "card_line": CARD_LINE_DARK,
    "line": "#27241F",
    "line_2": "#37332D",
    "ink": "#F1EDE4",
    "ink_2": INK_2_DARK,
    "ink_3": "#989184",
    "accent": "#FCB442",
    "accent_soft": "#FCB4421F",
    "on_accent": "#1C1405",
    "hl": "#FCB4422E",
    "hl_soft": "#1C1A17",
    "hl_line": "#FCB44200",
    "brand": "#F2B33D",
    "steel": INK_2_DARK,
    "good": INK_2_DARK,
    "warn": "#F1EDE4",
    "bad": "#F1EDE4",
    "violet": "#F1EDE4",
    "state": {"built": ["#1C1A17", CARD_LINE_DARK, "source recorded"]},
    "ghost": ["#1C1A17", "#37332D"],
    "container": {
        "host": ["#37332D", "none"],
        "client": ["#37332D", "none"],
        "server": ["#37332D", "none"],
        "isolated": [CARD_LINE_DARK, "none"],
    },
    "region": "#6B665D",
    "change": "#D4675B",
    "on_change": "#1E0904",
    "reach": "#D4675B",
    "flow": "#66625A",
    "layer_palette": LAYER_PALETTE_DARK,
    "layers": dict(STANDARD_LAYERS_DARK),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": "#D4675B",
        "types": "#F1EDE4",
        "refusals": INK_2_DARK,
        "tests": "#989184",
    },
    "font_ui": SANS,
    "font_mono": MONO,
}

# ---- Paper (scheme `light`) ------------------------------------------------------
# The neutrals are warm grays with an OKLCH chroma of 0.007 or less, as on a
# printed sheet. They are not beige. The map is the toned sheet. The header
# and the panel are lighter, and a card is the lightest surface.
# Selection is the ink color with the yellow highlighter `hl` under the
# selected line, and the pale highlighter `hl_soft` as the selected card fill.
# `hl_line` is the underlay under the selected or current line. Each kind
# color has 3:1 or more on it. The highlighter hue is not the hue of the paper.
# Ink has no highlighter: its `hl_soft` is the card color and its `hl_line` is clear.

INK_LIGHT = "#1D1B17"
INK_2_LIGHT = "#524F4A"
INK_3_LIGHT = "#6D6963"
CARD_LIGHT = "#FFFEFC"
CARD_LINE_LIGHT = "#8F8B85"
LINE_2_LIGHT = "#D4D1CD"

STANDARD_LAYERS_LIGHT: dict[str, str] = {
    "structure": CARD_LINE_LIGHT,
    "system": CARD_LINE_LIGHT,
    "data": "#014438",
    "control": "#A05B5A",
    "agents": CARD_LINE_LIGHT,
    "context": "#497B15",
    "tools": "#544002",
}

# Paper: data, control, context and tools pass on one view. Data, control and
# the first custom kind pass on one view. A second custom kind on that view
# does not pass, and five kinds on one view do not pass.
LAYER_PALETTE_LIGHT: list[str] = ["#493901", "#3D7C23", "#5C5C01", "#71640B"]

LIGHT: dict[str, Any] = {
    "name": "systemap",
    "scheme": "light",
    "color_scheme": "light",
    "bg": "#F1EFEC",
    "surface": "#FCFAF7",
    "raised": "#EDEAE6",
    "map": "#F4F2EF",
    "grid": "#E6E3DF",
    "card": CARD_LIGHT,
    "card_line": CARD_LINE_LIGHT,
    "line": "#E4E2DF",
    "line_2": LINE_2_LIGHT,
    "ink": INK_LIGHT,
    "ink_2": INK_2_LIGHT,
    "ink_3": INK_3_LIGHT,
    "accent": INK_LIGHT,
    "accent_soft": "#FFF5D6",
    "on_accent": "#FCFAF7",
    "hl": "#FFEBA0",
    "hl_soft": "#FFF5D6",
    "hl_line": "#FFEBA0",
    "brand": "#F2B33D",
    "steel": INK_2_LIGHT,
    "good": INK_2_LIGHT,
    "warn": INK_LIGHT,
    "bad": INK_LIGHT,
    "violet": INK_LIGHT,
    "state": {"built": [CARD_LIGHT, CARD_LINE_LIGHT, "source recorded"]},
    "ghost": [CARD_LIGHT, LINE_2_LIGHT],
    "container": {
        "host": [LINE_2_LIGHT, "none"],
        "client": [LINE_2_LIGHT, "none"],
        "server": [LINE_2_LIGHT, "none"],
        "isolated": [CARD_LINE_LIGHT, "none"],
    },
    "region": CARD_LINE_LIGHT,
    "change": "#AC312A",
    "on_change": "#FFFFFF",
    "reach": "#AC312A",
    "flow": "#8E8C85",
    "layer_palette": LAYER_PALETTE_LIGHT,
    "layers": dict(STANDARD_LAYERS_LIGHT),
    "marks": dict(KIND_MARKS),
    "delta": {
        "operations": "#AC312A",
        "types": INK_LIGHT,
        "refusals": INK_2_LIGHT,
        "tests": INK_3_LIGHT,
    },
    "font_ui": SANS,
    "font_mono": MONO,
}

SCHEMES: dict[str, dict[str, Any]] = {"dark": DARK, "light": LIGHT}
# The scheme names that the page shows. The configuration uses the keys.
SCHEME_LABELS: dict[str, str] = {"dark": "Ink", "light": "Paper"}
DEFAULT_SCHEME = "dark"
LIGHT_SCHEME = "light"
# Scheme names that earlier versions supplied. A configuration that names
# one gets the list of the available schemes.
REMOVED_SCHEMES = frozenset({"clay", "warm", "graphite"})

# The tokens that are read as text somewhere on the page, held to 4.5:1 on
# the bg, surface, raised, map and card colors. A flow kind color is a line
# and a legend swatch: it has 4.5:1 on the map and the card, and 3:1 on the
# others. A derived layer color is a card border: 3:1 on the map.
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
    "change",
)
# Text on a filled tag: the token, then the fill under it.
ON_FILL = {"on_accent": "accent", "on_change": "change"}


def merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Combine tables by key. Replace other values from `base` with values from `override`."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def scheme_list() -> str:
    """Give the scheme keys and their page names for a configuration error."""
    names = [f"{key} ({SCHEME_LABELS.get(key, key)})" for key in SCHEMES]
    if len(names) < 2:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def unavailable(name: object) -> ValueError:
    """Give the error for a scheme name that the configuration cannot use."""
    return ValueError(
        f"The theme scheme {name!r} is not available. The schemes are {scheme_list()}."
    )


def scheme_name(tokens: dict[str, Any]) -> str:
    """Give the palette name from `[theme]`, from the configuration.

    Reject other names and list the available palettes."""
    scheme = tokens.get("scheme", DEFAULT_SCHEME)
    if not isinstance(scheme, str) or scheme not in SCHEMES:
        raise unavailable(scheme)
    return scheme


def _check_tables(tokens: dict[str, Any]) -> None:
    """Reject a `[theme.<name>]` table for a scheme that is not available.

    A table is a scheme table or a token table, such as `layers`. A removed
    scheme, such as `clay`, gives an error and not an unused token."""
    for key, value in tokens.items():
        if key in SCHEMES or key == "scheme":
            continue
        token_table = isinstance(DARK.get(key), dict)
        if key in REMOVED_SCHEMES or (isinstance(value, dict) and not token_table):
            raise unavailable(key)


# The tokens that `tints` mixes with other colors. A mixed color must have the form #RRGGBB.
MIXED_TOKENS = ("bg", "raised", "change", "reach")
HEX_COLOUR = re.compile(r"#[0-9A-Fa-f]{6}")


def _colour(key: str, value: object) -> None:
    if not isinstance(value, str) or HEX_COLOUR.fullmatch(value) is None:
        raise ValueError(
            f'The theme value {key} must be a color in the form #RRGGBB, such as "#D4675B". '
            f"The value is {value!r}."
        )


def _check_values(t: dict[str, Any]) -> None:
    """Reject a token value that the palette calculations cannot use.

    The message gives the key name. Other tokens go to the page without a change."""
    for key in MIXED_TOKENS:
        _colour(key, t.get(key))
    named = t.get("layers")
    if not isinstance(named, dict):
        raise ValueError("The theme value layers must be a table of layer IDs and colors.")
    for lid, colour in named.items():
        _colour(f"layers.{lid}", colour)
    palette = t.get("layer_palette")
    if not isinstance(palette, list) or not palette:
        raise ValueError("The theme value layer_palette must be a list of one or more colors.")
    for colour in palette:
        _colour("layer_palette", colour)
    marks = t.get("marks")
    if not isinstance(marks, dict) or not all(isinstance(v, str) for v in marks.values()):
        raise ValueError("The theme value marks must be a table of component kinds and marks.")


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
    _check_tables(tokens)
    own = {k: v for k, v in tokens.items() if k != "scheme" and k not in SCHEMES}
    tables: dict[str, dict[str, Any]] = {}
    for scheme, base in SCHEMES.items():
        override = tokens.get(scheme) or {}
        if not isinstance(override, dict):
            raise ValueError(f"theme.{scheme} must contain a table of CSS tokens")
        if scheme == name:
            override = merge(own, override)
        t = merge(base, override)
        _check_values(t)
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
    "map": "--map",
    "grid": "--grid",
    "card": "--card",
    "card_line": "--card-line",
    "on_accent": "--on-accent",
    "hl": "--hl",
    "hl_soft": "--hl-soft",
    "hl_line": "--hl-line",
    "brand": "--brand",
    "on_change": "--on-change",
}

# How far each derived tint leans from its ground towards its colour: the
# change map's two tints from the ground towards change and reach, and a
# verb tag's fill from the raised surface towards the layer.
CHANGED_MIX = 0.14
REACH_MIX = 0.12
TAG_MIX = 0.16


def tints(t: dict[str, Any]) -> dict[str, Any]:
    """Calculate color mixtures for CSS declarations and separate figures.

    An actor card has the map color as its fill, so the card shows as a
    dashed border on the map ground."""
    return {
        "actor": t["map"],
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
        """Give the actor fill and stroke colors. The stroke is the card border color."""
        return self._v("--actor", self._tints["actor"]), self["card_line"]

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
    selection first. Without a stored selection, it uses Paper for a system
    light preference or Ink. CSS media declarations supply the device theme
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
