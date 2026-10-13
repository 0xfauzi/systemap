"""The claim match and the re-export resolver read neutral facts, and extraction is shared.

Acceptance values for the work item decoupling-join:

- A TypeScript claim `web.users.user.*` gives 0 modules from the sibling files
  `user.service.ts` and `user.controller.ts`. It gives the module of `user/profile.ts`.
- For each module and each claim of a Python fixture with three package levels, the
  claim match with the `package` fact gives the same result as the dotted module name
  (100% equal).
- A `*` re-export does not give a name with `star_export` set to `false`, also when the
  name is not `default`. The TypeScript adapter sets the field for `default` only. The
  Python adapter sets it for no name.
- `build`, `drift`, and `mapping_drift` are defined in the shared module `extraction`.
- A facts file of format 5 is stale, because format 6 changed the `package` fact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import write_tree

from systemap import check, config, extract, extraction
from systemap.model import Component, Model, Region, claimed, covers, module_matches
from systemap.reexports import resolve_reexports

PYTHON_TREE = {
    "systemap.toml": 'language = "python"\n',
    "pyproject.toml": '[project]\nname = "shop"\nversion = "1"\n',
    "src/shop/__init__.py": "",
    "src/shop/cli.py": "def main() -> None:\n    pass\n",
    "src/shop/orders/__init__.py": "",
    "src/shop/orders/store.py": "VALUE = 1\n",
    "src/shop/orders/billing/__init__.py": "",
    "src/shop/orders/billing/tax.py": "RATE = 2\n",
    "src/shop/orders_extra.py": "EXTRA = 3\n",
}
TYPESCRIPT_TREE = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": '{"name":"@acme/web"}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "src/users/user.service.ts": "export class UserService {}\n",
    "src/users/user.controller.ts": "export class UserController {}\n",
    "src/users/user/profile.ts": "export class Profile {}\n",
    "src/lib.ts": "export default function make(): void {}\nexport const SIZE = 1;\n",
    "src/index.ts": 'export * from "./lib";\n',
}


def _facts(root: Path, tree: dict[str, str]) -> dict[str, Any]:
    write_tree(root, tree)
    return extraction.build(config.load(root))


def _card(*claims: str) -> Component:
    return Component(
        "Users",
        "Keeps the users.",
        implemented_by=claims,
        region="all",
        x=20,
        y=20,
    )


def test_a_typescript_claim_does_not_catch_a_sibling_file_with_dots(tmp_path: Path) -> None:
    facts = _facts(tmp_path, TYPESCRIPT_TREE)
    components = facts["components"]
    assert components["web.users.user.controller"]["package"] == "web.users"
    assert claimed(_card("web.users.user.*"), components) == ["web.users.user.profile"]
    assert not covers("web.users.user.*", "web.users.user.controller", components)
    assert not covers("web.users.user.*", "web.users.user.service", components)
    # Without the records, the dotted names give the earlier, incorrect result.
    assert module_matches("web.users.user.*", "web.users.user.controller")
    # The map check also reads the fact: the claim for the folder `user` covers one module.
    model = Model(
        canvas=(600, 200),
        containers=(),
        regions=(Region("all", "ALL", (0, 0, 600, 200)),),
        components=(_card("web.users.user.*"),),
        flows=(),
        flow_kinds=(),
    )
    coverage = check.check_coverage(model, facts, [])
    assert "unmapped: web.users.user.controller (no component has this module claim)" in (
        coverage.problems
    )
    assert not any("web.users.user.profile" in p for p in coverage.problems)


def test_a_python_claim_gives_the_dotted_name_result(tmp_path: Path) -> None:
    components = _facts(tmp_path, PYTHON_TREE)["components"]
    heads = set(components) | {m.rpartition(".")[0] for m in components} | {"shop.order"}
    patterns = sorted(heads | {f"{h}.*" for h in heads if h})
    checked = 0
    for pattern in patterns:
        for module in components:
            assert covers(pattern, module, components) == module_matches(pattern, module)
            checked += 1
        assert claimed(_card(pattern), components) == claimed(_card(pattern), list(components))
    assert checked == len(patterns) * len(components) > 50
    assert claimed(_card("shop.orders.*"), components) == [
        "shop.orders",
        "shop.orders.billing",
        "shop.orders.billing.tax",
        "shop.orders.store",
    ]


def test_a_star_re_export_reads_the_star_export_fact(tmp_path: Path) -> None:
    components: dict[str, Any] = {
        "a": {
            "names": [
                {"name": "hidden", "kind": "function", "star_export": False},
                {"name": "default", "kind": "function"},
            ]
        },
        "b": {"names": [{"name": "*", "kind": "reexport", "reexport_of": "a", "star": True}]},
    }
    resolve_reexports(components)
    assert [n["name"] for n in components["b"]["names"]] == ["default"]
    ts = _facts(tmp_path / "ts", TYPESCRIPT_TREE)["components"]
    marked = [n["name"] for r in ts.values() for n in r["names"] if "star_export" in n]
    assert marked == ["default"]
    assert [n["name"] for n in ts["web.index"]["names"]] == ["SIZE"]
    py = _facts(tmp_path / "py", PYTHON_TREE)["components"]
    assert not [n for r in py.values() for n in r["names"] if "star_export" in n]


def test_build_and_drift_are_in_the_shared_module(tmp_path: Path) -> None:
    for name in ("build", "drift", "mapping_drift", "language_for"):
        assert getattr(extraction, name).__module__ == "systemap.extraction"
        assert getattr(extract, name) is getattr(extraction, name)
    fresh = _facts(tmp_path, PYTHON_TREE)
    assert fresh["version"] == extraction.FORMAT == 11
    assert extraction.drift(fresh, {**fresh, "version": 6})[0].startswith("facts format 6 ")
