"""The data of the Details panel of the canvas page (docs/design/nested-canvas.md, step 5).

`canvas_data` adds these keys to each map. The Details panel (`page_canvas_details`)
gives them for the selected card, as the panel of the linked page does (`page_data.sources`
and the rules of `page._rules`). This module adds no facts.

- `mf`: the model file of the map.
- `ff`: the facts file. Only the top map has it.
- `iv`: the invariants in number order, if any. Each has `n` (the number), `t` (the
  text), `g` (the components that the invariant governs, if any) and `as` (the assurance
  level and the freshness, if known).
- `ir`: the import rules in model order, if any. Each has `id`, `k` (the kind), `s` and
  `t` (the source and the destination components, if any), `iv` (the number of the
  invariant that the rule examines, if any) and `as`.
- `md`: the modules of the cards of the map, in the order of the cards and their claims,
  if any. Each module has `i` (the module ID), `f` (the file), `im` (the imports), `ib`
  (the modules that import it), `ex` (the external imports) and `uk` (the facts that the
  extractor could not read). An import is the index of a module in `md`, or the module ID
  when that module is not in `md`. `n` gives two counts: the public names, and the tests
  that import the module. A module with no public name and no test has no `n`.
- `fr`: the file rule of the map, if two or more modules follow it: a prefix and a suffix.
  The file of a module without `f` is the prefix, the module ID with "/" for each ".", and
  the suffix. A module that the rule does not give has `f`, also an empty `f`.
- `ib` gives only the importers that the page cannot find. The page finds each module of
  `md` that has the module in its `im`. When that set is not the set of the facts, `ib`
  gives all importers and the module has `ia` (1).

The data does not give the module descriptions, the names of the public names and the
names of the tests. The facts file has them, and the panel tells the reader this. With
them, the self-map page is too large for acceptance 10 of `tests/test_canvas_details.py`
(S9 in `bench/jev/README.md`).
- `sr`: the source records of each card that is not an actor, by card ID, if any. Each
  has `mo` (the indexes of its modules in `md`), `pt` (the entry points of these
  modules) and `sc` (the public names that the model claims, as "module:name").
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from systemap import assurance, nest, page_data
from systemap.config import Config


def _some(**fields: Any) -> dict[str, Any]:
    """Give the fields that have a value. An empty list, a zero or a text is not a value."""
    return {key: value for key, value in fields.items() if value not in ("", [], None, 0)}


def _level(claim: assurance.Claim | None) -> dict[str, list[str]]:
    return {"as": [claim.level, claim.freshness]} if claim is not None else {}


def _unknown(problem: Any) -> str:
    """Give the text of a fact that the extractor could not read, as the linked page does."""
    if isinstance(problem, str):
        return problem
    where = (
        f"Line {problem['line']}, column {problem.get('column', '')}: "
        if problem.get("line")
        else ""
    )
    return where + str(problem.get("reason") or "The fact could not be read.")


def _counts(mod: dict[str, Any]) -> list[int]:
    """Give the count of public names and the count of tests of a module, or no counts."""
    counts = [len(mod["public_names"]), len(mod["tests"])]
    return counts if any(counts) else []


def _rules(m: nest.Map, claims: list[assurance.Claim]) -> dict[str, Any]:
    model = m.model
    inv = assurance.by_type(claims, assurance.INVARIANT)
    imp = assurance.by_type(claims, assurance.IMPORT_RULE)
    return _some(
        iv=[
            {"n": i.n, "t": i.text, **_some(g=list(i.governs)), **_level(inv.get(str(i.n)))}
            for i in sorted(model.invariants, key=lambda i: i.n)
        ],
        ir=[
            {
                "id": r.id,
                "k": r.kind,
                **_some(s=list(r.src), t=list(r.dst), iv=r.invariant),
                **_level(imp.get(r.id)),
            }
            for r in model.import_rules
        ],
    )


def _file_rule(table: list[dict[str, Any]]) -> tuple[str, str] | None:
    """Give the most common rule `prefix + module path + suffix` of the files of the table,
    where the module path is the module ID with "/" for each ".". Give None when no two
    modules follow one rule."""
    rules: Counter[tuple[str, str]] = Counter()
    for mod in table:
        path, file = mod["id"].replace(".", "/"), mod["file"]
        at = file.find(path) if file else -1
        if at >= 0:
            rules[file[:at], file[at + len(path) :]] += 1
    best = rules.most_common(1)
    return best[0][0] if best and best[0][1] >= 2 else None


def _file(mod: dict[str, Any], rule: tuple[str, str] | None) -> dict[str, str]:
    """Give `f` of a module: none when the file rule of the map gives the file."""
    if rule is not None and mod["file"] == rule[0] + mod["id"].replace(".", "/") + rule[1]:
        return {}
    return {"f": mod["file"]} if mod["file"] or rule is not None else {}


def _importers(
    mod: dict[str, Any], index: dict[str, int], table: list[dict[str, Any]]
) -> dict[str, Any]:
    """Give `ib` of a module: the importers that the page cannot find from `im`.

    The page finds each module of the table that has this module in its imports. When that
    set is not the set of the facts, `ib` gives all importers, and `ia` is 1."""
    found = {j for j, other in enumerate(table) if mod["id"] in other["imports"]}
    known = {index[x] for x in mod["imported_by"] if x in index}
    if found == known:
        return _some(ib=[x for x in mod["imported_by"] if x not in index])
    return {"ib": [index.get(x, x) for x in mod["imported_by"]], "ia": 1}


def _modules(sources: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Give the table of the modules (`md`, and `fr` for the file rule) and the source
    records of each card."""
    index: dict[str, int] = {}
    table: list[dict[str, Any]] = []
    for record in sources.values():
        for mod in record["modules"]:
            if mod["id"] not in index:
                index[mod["id"]] = len(table)
                table.append(mod)
    rule = _file_rule(table)
    md = [
        {
            "i": mod["id"],
            **_file(mod, rule),
            **_some(
                im=[index.get(x, x) for x in mod["imports"]],
                ex=list(mod["external"]),
                uk=[_unknown(x) for x in mod["unknown"]],
                n=_counts(mod),
            ),
            **_importers(mod, index, table),
        }
        for mod in table
    ]
    sr = {
        cid: rec
        for cid, record in sources.items()
        if (
            rec := _some(
                mo=[index[mod["id"]] for mod in record["modules"]],
                pt=record["points"],
                sc=[f"{s['module']}:{s['name']}" for s in record["symbol_claims"]],
            )
        )
    }
    return _some(md=md, fr=list(rule) if rule else None), sr


def of_map(
    cfg: Config, m: nest.Map, facts: dict[str, Any], claims: list[assurance.Claim]
) -> dict[str, Any]:
    """Give the keys of the Details panel for map m (see the module docstring).

    `claims` are the assurance claims of the map (`assurance.of_model`)."""
    actors = {c.id for c in m.model.components if c.kind == "actor"}
    sources = {
        cid: rec for cid, rec in page_data.sources(m.model, facts).items() if cid not in actors
    }
    table, sr = _modules(sources)
    top = {"ff": f"{cfg.out_dir}/{cfg.facts_file}"} if m.top else {}
    return {"mf": m.rel, **top, **_rules(m, claims), **table, **_some(sr=sr)}
