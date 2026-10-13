"""The name check refuses model names that the page and the figures cannot use.

The renderer uses each layer ID in CSS names (`--l-<id>`), in SVG marker IDs and in
HTML attributes. Thus a layer ID must be a safe name: letters, digits, "_" and "-".
The detail JSON has one record for each component ID and one record `_meta`. The page
reads the JSON as a JavaScript object, where the key `__proto__` sets the prototype.
Thus `_meta` and `__proto__` cannot be component IDs.
"""

from __future__ import annotations

import re

from systemap.model import Meaning, Model

SAFE_NAME = re.compile(r"[A-Za-z0-9_-]+")
DATA_KEYS = frozenset({"_meta", "__proto__"})


def problem(model: Model, meaning: Meaning) -> str:
    """Give the first name that the page cannot use, or an empty string."""
    for c in model.components:
        if c.id in DATA_KEYS:
            return (
                f"the component ID {c.id!r} is a key of the page data. Give the component "
                "a different ID"
            )
    for layer in meaning.layers:
        if SAFE_NAME.fullmatch(layer.id) is None:
            return (
                f"the layer ID {layer.id!r} is not a safe name. The page uses layer IDs as "
                "CSS names and SVG IDs. Use only letters, digits, _ and -"
            )
    return ""
