"""The call-site record is the language-neutral form of the `call_sites` fact.

Each language adapter finds the bindings and the uses in its own syntax. This module
gives the record that the adapters write. Thus the two adapters write the same
fields. It does not read source.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

IMPORT = "import"
VALUE = "value"
WHOLE = "*"


@dataclass
class Binding:
    """One local name, the module that it comes from, and the lines that use it.

    `scope` is the adapter's syntax node of the function that makes a plain local name,
    or None. A use outside that function is not a use of the binding.
    """

    local: str
    target: str
    name: str
    bound: str
    line: int
    scope: Any = None
    uses: set[tuple[int, int, str]] = field(default_factory=set)


def records(bindings: Iterable[Binding], module: str) -> list[dict[str, Any]]:
    """Give one record for each local name, target, and imported name, in line order.

    Two bindings of the same name in the same scope give one record with the first
    binding line. A binding of the module itself is not a call site.
    """
    merged: dict[tuple[str, str, str, str, int], Binding] = {}
    for b in bindings:
        if b.target == module:
            continue
        key = (b.local, b.target, b.name, b.bound, id(b.scope))
        first = merged.setdefault(key, b)
        if first is not b:
            first.line = min(first.line, b.line)
            first.uses |= b.uses
    out = [
        {
            "local": b.local,
            "target": b.target,
            "name": b.name,
            "bound": b.bound,
            "line": b.line,
            "uses": [list(use) for use in sorted(b.uses)],
        }
        for b in merged.values()
    ]
    return sorted(out, key=lambda r: (r["line"], r["local"]))
