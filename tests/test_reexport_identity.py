"""The defining identity of a re-exported name, for the two language adapters.

Codex results adapters-4, adapters-14, adapters-15 and model-3 have one cause: the facts
lost the module and the symbol that define a re-exported name. Each test gives a Python
fixture and a TypeScript fixture.

Acceptance values:

- A chain of two re-exports: the name records `defined_in` as the defining module and
  `defined_as` as the defining symbol. The interface `Ledger.record()` gives no problem.
- An alias: the name records the original symbol. The interface `Public.get()` gives no
  problem.
- Two star exports of the same binding: one record for the name, with no ambiguity record.
- A Python star re-export gives the public names of its source module. A literal
  `__all__` limits these names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import check, config, extract, reexports, source_facts
from systemap.model import Component, defines_entry

TS_ROOTS = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "app"\n',
    "tsconfig.json": "{}",
}

CHAIN = {
    "python": {
        "pkg/__init__.py": "from .books import Ledger\n",
        "pkg/books/__init__.py": "from .ledger import Ledger\n",
        "pkg/books/ledger.py": "class Ledger:\n    def record(self) -> None:\n        pass\n",
    },
    "typescript": {
        **TS_ROOTS,
        "src/index.ts": 'export { Ledger } from "./books";\n',
        "src/books.ts": 'export { Ledger } from "./ledger";\n',
        "src/ledger.ts": "export class Ledger { record(): void {} }\n",
    },
}

ALIAS = {
    "python": {
        "pkg/__init__.py": "from .core import Store as Public\n",
        "pkg/core.py": "class Store:\n    def get(self) -> int:\n        return 1\n",
    },
    "typescript": {
        **TS_ROOTS,
        "src/index.ts": 'export { Store as Public } from "./core";\n',
        "src/core.ts": "export class Store { get(): number { return 1; } }\n",
    },
}

SAME_BINDING = {
    "python": {
        "pkg/__init__.py": "from .a import *\nfrom .b import *\n",
        "pkg/a/__init__.py": "from ..base import Item\n",
        "pkg/b/__init__.py": "from ..base import Item\n",
        "pkg/base.py": "class Item:\n    def go(self) -> None:\n        pass\n",
    },
    "typescript": {
        **TS_ROOTS,
        "src/index.ts": 'export * from "./a";\nexport * from "./b";\n',
        "src/a.ts": 'export { Item } from "./base";\n',
        "src/b.ts": 'export { Item } from "./base";\n',
        "src/base.ts": "export class Item { go(): void {} }\n",
    },
}

ROOT = {"python": "pkg", "typescript": "app.index"}
PREFIX = {"python": "pkg", "typescript": "app"}


def components(root: Path, files: dict[str, str]) -> dict[str, Any]:
    write_tree(root, files)
    return extract.build(config.load(root))["components"]


def entry(record: dict[str, Any], name: str) -> dict[str, Any]:
    found = [n for n in record["names"] if n["name"] == name]
    assert len(found) == 1, record["names"]
    return found[0]


def card(module: str, interface: str) -> Component:
    return Component("Books", "Keeps books.", implemented_by=(module,), interface=interface)


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_a_chain_of_two_reexports_keeps_the_defining_module(tmp_path: Path, language: str) -> None:
    found = components(tmp_path, CHAIN[language])
    prefix = PREFIX[language]
    defining = f"{prefix}.books.ledger" if language == "python" else f"{prefix}.ledger"
    ledger = entry(found[ROOT[language]], "Ledger")
    assert ledger["kind"] == "class"
    assert (ledger["defined_in"], ledger["defined_as"]) == (defining, "Ledger")
    assert check.interface_problem(card(ROOT[language], "Ledger.record()"), found) == ""
    problem = check.interface_problem(card(ROOT[language], "Ledger.erase()"), found)
    assert "Ledger has no public method erase" in problem


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_an_alias_keeps_the_defining_symbol(tmp_path: Path, language: str) -> None:
    found = components(tmp_path, ALIAS[language])
    public = entry(found[ROOT[language]], "Public")
    assert public["kind"] == "class"
    assert (public["defined_in"], public["defined_as"]) == (f"{PREFIX[language]}.core", "Store")
    assert check.interface_problem(card(ROOT[language], "Public.get()"), found) == ""
    assert "no public method put" in check.interface_problem(
        card(ROOT[language], "Public.put()"), found
    )


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_two_star_exports_of_the_same_binding_are_one_name(tmp_path: Path, language: str) -> None:
    found = components(tmp_path, SAME_BINDING[language])
    root = found[ROOT[language]]
    item = entry(root, "Item")
    assert (item["defined_in"], item["defined_as"]) == (f"{PREFIX[language]}.base", "Item")
    assert not root.get("unknown"), root.get("unknown")
    assert check.interface_problem(card(ROOT[language], "Item.go()"), found) == ""


def test_typescript_star_exports_of_two_bindings_stay_ambiguous(tmp_path: Path) -> None:
    """Acceptance: two different definitions of one name give the ambiguity record."""
    found = components(
        tmp_path,
        {
            **TS_ROOTS,
            "src/index.ts": 'export * from "./a";\nexport * from "./b";\n',
            "src/a.ts": "export class Item {}\n",
            "src/b.ts": "export class Item {}\n",
        },
    )
    reasons = [u["reason"] for u in found["app.index"].get("unknown", [])]
    assert reasons == ["ambiguous star export Item"]


def test_a_python_star_import_rebinds_in_source_order(tmp_path: Path) -> None:
    """Acceptance: a later Python binding replaces an earlier one, with no ambiguity."""
    found = components(
        tmp_path,
        {
            "pkg/__init__.py": "from .a import *\nfrom .b import *\nfrom .c import run\n",
            "pkg/a.py": "class Item:\n    pass\n\n\ndef run() -> None:\n    pass\n",
            "pkg/b.py": "class Item:\n    pass\n\n\ndef run() -> None:\n    pass\n",
            "pkg/c.py": "def run() -> None:\n    pass\n",
        },
    )
    root = found["pkg"]
    assert not root.get("unknown"), root.get("unknown")
    assert entry(root, "Item")["defined_in"] == "pkg.b"
    assert entry(root, "run")["defined_in"] == "pkg.c"


def test_a_python_star_reexport_gives_the_public_names(tmp_path: Path) -> None:
    """Acceptance: `serve` is a public name and a valid entry. `_hidden` is not public."""
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "from .service import *\n",
            "pkg/service.py": "def serve() -> None:\n    pass\n\n\ndef _hidden() -> None:\n    pass\n",
        },
    )
    facts = extract.build(config.load(tmp_path))
    root = facts["components"]["pkg"]
    assert root["names"] == [
        {
            "name": "serve",
            "kind": "function",
            "reexport_of": "pkg.service",
            "defined_in": "pkg.service",
            "defined_as": "serve",
        }
    ]
    serve = Component("Service", "Serves.", implemented_by=("pkg",), entry="serve")
    assert defines_entry(serve, facts)


def test_a_literal_all_limits_the_python_star_names(tmp_path: Path) -> None:
    """Acceptance: only the names in `__all__` come through the star re-export."""
    found = components(
        tmp_path,
        {
            "pkg/__init__.py": "from .service import *\n",
            "pkg/service.py": (
                '__all__ = ["serve"]\n__all__ += ("Store",)\n\n\n'
                "def serve() -> None:\n    pass\n\n\ndef other() -> None:\n    pass\n\n\n"
                "class Store:\n    pass\n"
            ),
        },
    )
    assert [n["name"] for n in found["pkg"]["names"]] == ["serve", "Store"]


def test_a_computed_all_gives_an_unknown_record(tmp_path: Path) -> None:
    """Acceptance: the star names of a computed `__all__` are not known. The importer gets
    one unknown record and no guessed name."""
    found = components(
        tmp_path,
        {
            "pkg/__init__.py": "from .service import *\n",
            "pkg/service.py": (
                "from pkg import names\n__all__ = names.ALL\n\n\ndef serve() -> None:\n    pass\n"
            ),
            "pkg/names.py": 'ALL = ["serve"]\n',
        },
    )
    assert found["pkg"]["names"] == []
    reasons = [u["reason"] for u in found["pkg"].get("unknown", [])]
    assert reasons == ["the `*` re-export from pkg.service gives names that are not known"]
    lines = source_facts.unknown_fact_lines({"components": found})
    assert any("pkg:" in line or "pkg " in line for line in lines), lines


def test_an_unknown_definition_is_not_known() -> None:
    """Acceptance: a re-export of a module outside the facts has no defining identity."""
    names = {
        "pkg": {"names": [{"name": "gone", "kind": "reexport", "reexport_of": "pkg.nowhere"}]},
    }
    reexports.resolve_reexports(names)
    gone = names["pkg"]["names"][0]
    assert gone["kind"] == "unknown"
    assert gone["defined_in"] is None and gone["defined_as"] is None
    assert "has no public method" in check.interface_problem(card("pkg", "gone.run()"), names)
