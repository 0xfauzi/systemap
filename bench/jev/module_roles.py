"""Gate G1 of the module role specification (revision 2, section 18.4): blind labels.

The script has its own copy of the rules of the specification: the units of 7.1
(with the call-site names of 7.1a and the `defined_as` resolution of 7.1 step 2), the
symbol rule of 9.2, and the import crossing states of 10.1. It comes from
`design/validation/module_roles_v2.py` and `module_roles.py` of the design team.

Acceptance values (written before the first run of this script):

(a) MUST, section 18.1. With the blind labels as accepted module roles, each of these
    import crossings is `open`, through one or more units that are not opened only by "*":
    Django 6.1.3:      Admin->Orm, Auth->Mail, Auth->Signals, Utils->Mail, Utils->Cache.
    starlette 0.46.2:  Middleware->WebSockets, Authentication->WebSockets,
                       TestClient->WebSockets.
    SQLAlchemy 2.1.9:  UnitOfWork->Engine.
    If one is `closed` or `waiting`, the gate fails. The script prints the units and
    the labels of that import crossing.
(w) MUST, section 18.4 step 4: waiting = 0 on each map (each unit has a label that
    passes the symbol rule of 9.2).
(r) MUST, section 18.4 step 3: the script refuses a label file with a record that does
    not pass 9.2, or with a record for a module that is not a unit. Then it writes no
    states and exits 1.
Expected values (measured in section 18.3, not acceptance values): run-time import
crossings Django 283, SQLAlchemy 135, starlette 15; module use lines Django 226,
SQLAlchemy 101, starlette 8. If a value is different, the script prints it, and the
cause must be recorded.
Recorded with no target: open, waiting and closed import crossings, the questions
(module use lines + open import crossings) and their ratio to the run-time import
crossings, the import crossings open only through "*", and the module role counts.

The script reads only the recorded facts and models (`nest.load` runs no model code)
and parses source text with `ast` for the import forms. It runs no project code.

Run:
  uv run --project /home/user/systemap python -I module_roles.py units <map root> <name> <units file>
  uv run --project /home/user/systemap python -I module_roles.py states <map root> <name> <labels file> <output file>
The labels file is a list of records with `unit`, `role`, and `symbol` or `handoff`.
A record with a `map` key applies only to the map of that name.
The states step adds the result of the map to the output file (a JSON object, one key
for each map).
"""

from __future__ import annotations

import ast
import collections
import json
import sys
from pathlib import Path
from typing import Any

from systemap import config, facts_file, judgement, nest, python_calls

ACCEPT = {
    "django": [
        ("Admin", "Orm"),
        ("Auth", "Mail"),
        ("Auth", "Signals"),
        ("Utils", "Mail"),
        ("Utils", "Cache"),
    ],
    "starlette": [
        ("Middleware", "WebSockets"),
        ("Authentication", "WebSockets"),
        ("TestClient", "WebSockets"),
    ],
    "sqlalchemy": [("UnitOfWork", "Engine")],
}
EXPECTED = {"django": (283, 226), "sqlalchemy": (135, 101), "starlette": (15, 8)}
LINE = "module use: other components import {} and no flow connects them to its component"
ROLES = ("helper", "handoff", "mixed")


# ---- import forms (the forms of section 4.4, from the source text) ----------------------


def tc_sign(test: ast.expr, aliases: set[str]) -> int:
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return -tc_sign(test.operand, aliases)
    if isinstance(test, ast.Name) and test.id in aliases:
        return 1
    if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
        return 1
    return 0


def tc_aliases(node: ast.AST) -> set[str]:
    out = {"TYPE_CHECKING"}
    for n in ast.walk(node):
        if isinstance(n, ast.ImportFrom) and n.module in ("typing", "typing_extensions"):
            out.update(a.asname or a.name for a in n.names if a.name == "TYPE_CHECKING")
    return out


FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def if_forms(n: ast.If, form: str, sign: int) -> list[tuple[ast.AST, str]]:
    body_form = "type" if sign == 1 else form
    else_form = "type" if sign == -1 else form
    body = [(c, body_form) for c in n.body]
    orelse = [(c, else_form) for c in n.orelse]
    return [*body, *orelse, (n.test, form)]


def child_forms(n: ast.AST, form: str, aliases: set[str]) -> list[tuple[ast.AST, str]]:
    if isinstance(n, FUNCTIONS):
        inner = "type" if form == "type" else "call"
        return [(c, inner) for c in ast.iter_child_nodes(n)]
    if isinstance(n, ast.If):
        sign = tc_sign(n.test, aliases)
        if sign:
            return if_forms(n, form, sign)
    return [(c, form) for c in ast.iter_child_nodes(n)]


def forms_by_node(node: ast.AST) -> dict[int, str]:
    aliases = tc_aliases(node)
    out: dict[int, str] = {}
    stack: list[tuple[ast.AST, str]] = [(node, "load")]
    while stack:
        n, form = stack.pop()
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            out[id(n)] = form
        else:
            stack.extend(child_forms(n, form, aliases))
    return out


def import_forms(root: Path, facts: dict[str, Any]) -> dict[tuple[str, str], set[str]]:
    mods = facts["components"]
    prefixes, known = set(facts["packages"]), set(mods)
    forms: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for module, record in mods.items():
        path = root / record["file"]
        try:
            syntax = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeError, OSError, ValueError, RecursionError):
            continue
        by_node = forms_by_node(syntax)
        for node, _l, target, _n, _ln in python_calls.import_targets(
            syntax, prefixes, known, module, path.name == "__init__.py"
        ):
            if target != module:
                forms[(module, target)].add(by_node.get(id(node), "load"))
    return forms


# ---- units (section 7.1) -----------------------------------------------------------------


def load(root: Path) -> tuple[nest.Tree, dict[str, Any]]:
    cfg = config.load(root)
    return nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root)


def entry(mods: dict[str, Any], target: str, name: str) -> dict[str, Any] | None:
    for e in mods.get(target, {}).get("names", []):
        if isinstance(e, dict) and e.get("name") == name:
            return e
    return None


def is_star_site(s: dict[str, Any], target: str) -> bool:
    return s.get("bound") == "import" and s.get("name") == "*" and s.get("target") == target


def site_names(s: dict[str, Any]) -> set[str] | None:
    """The attribute names of one call-site record, or None when they are not known."""
    uses = s.get("uses") or []
    if "." in str(s.get("local", "")) or s.get("local") == "*" or not uses:
        return None
    attrs = {u[2] for u in uses}
    return None if "" in attrs else attrs


def star_names(mods: dict[str, Any], module: str, target: str) -> set[str]:
    """Section 7.1a: the call-site names of a whole-module import, or {"*"}."""
    sites = mods[module].get("call_sites")
    if not isinstance(sites, list):
        return {"*"}
    parts = [site_names(s) for s in sites if is_star_site(s, target)]
    known = [names for names in parts if names is not None]
    if not parts or len(known) < len(parts):
        return {"*"}
    return set().union(*known) or {"*"}


def use_units(
    mods: dict[str, Any], owner: dict[str, str], module: str, target: str, notes: list[str]
) -> dict[str, set[str]]:
    out: dict[str, set[str]] = collections.defaultdict(set)
    names = set(mods[module]["uses"].get(target) or ["*"])
    if "*" in names:
        names = (names - {"*"}) | star_names(mods, module, target)
    for n in names:
        if n == "*":
            out[target].add("*")
            continue
        e = entry(mods, target, n)
        d = e.get("defined_in") if e else None
        if e and isinstance(d, str) and d in mods and d != target:
            if owner.get(d) == owner.get(target):
                out[d].add(str(e.get("defined_as") or n))
                continue
            notes.append(f"{target}:{n} is defined in {d} ({owner.get(d)})")
        out[target].add(n)
    return out


def add_users(
    units: dict[str, dict[str, Any]], found: dict[str, set[str]], user: dict[str, str], line: str
) -> None:
    for u, names in found.items():
        rec = units.setdefault(u, {"unit": u, "users": [], "pairs": set(), "notes": set()})
        rec["users"].append({**user, "names": sorted(names)})
        rec["pairs"].add(line)


def finish_unit(
    rec: dict[str, Any], tree: nest.Tree, owners: dict[str, dict[str, str]], mods: dict[str, Any]
) -> None:
    u = rec["unit"]
    holders = [m for m in tree.maps if u in owners[m.id]]
    lm = max(holders, key=lambda m: len(m.id)) if holders else None
    rec["line_map"] = lm.id if lm else None
    rec["component"] = owners[lm.id][u] if lm else None
    rec["line"] = (lm.prefix if lm else "") + LINE.format(u)
    rec["file"] = mods.get(u, {}).get("file")
    rec["provided"] = sorted(provided(mods.get(u, {})))
    rec["used"] = sorted({n for us in rec["users"] for n in us["names"] if n != "*"})
    rec["star"] = any("*" in us["names"] for us in rec["users"])
    rec["pairs"] = sorted(rec["pairs"])
    rec["notes"] = sorted(rec["notes"])


def crossing_units(
    mods: dict[str, Any],
    owner: dict[str, str],
    units: dict[str, dict[str, Any]],
    user: dict[str, str],
    rt: list[tuple[str, str]],
    line: str,
) -> dict[str, list[str]]:
    """Add the users of the run-time edges of one import crossing. Return its units."""
    pu: dict[str, set[str]] = collections.defaultdict(set)
    for s, t in rt:
        notes: list[str] = []
        found = use_units(mods, owner, s, t, notes)
        add_users(units, found, {**user, "module": s, "target": t}, line)
        for u, names in found.items():
            pu[u] |= names
            units[u]["notes"].update(notes)
    return {u: sorted(v) for u, v in sorted(pu.items())}


def build(
    tree: nest.Tree, facts: dict[str, Any], forms: dict[tuple[str, str], set[str]]
) -> dict[str, Any]:
    mods = facts["components"]
    owners = {m.id: judgement._owner_of(m.model, facts) for m in tree.maps}
    pairs: list[dict[str, Any]] = []
    units: dict[str, dict[str, Any]] = {}
    for m in tree.maps:
        for (p, q), edges in judgement.crossing_imports(m.model, facts).items():
            line = m.prefix + judgement.crossing_line(p, q)
            rt = [e for e in edges if forms.get(e, {"load"}) - {"type"}]
            if rt:
                user = {"map": m.id, "component": p}
                found = crossing_units(mods, owners[m.id], units, user, rt, line)
                pairs.append({"line": line, "map": m.id, "from": p, "to": q, "units": found})
    for rec in units.values():
        finish_unit(rec, tree, owners, mods)
    return {"pairs": pairs, "units": units}


# ---- the symbol rule (section 9.2) and the states (section 10.1) ------------------------


def entry_names(entries: Any) -> set[str]:
    out: set[str] = set()
    for e in entries or []:
        if isinstance(e, dict) and isinstance(e.get("name"), str):
            out.add(e["name"])
        elif isinstance(e, str):
            out.add(e)
    return out


def provided(rec: dict[str, Any]) -> set[str]:
    out = {e["name"] for e in rec.get("names", []) if isinstance(e, dict) and "name" in e}
    for key in ("functions", "classes", "constants", "types"):
        out |= entry_names(rec.get(key, []))
    for names in (rec.get("uses") or {}).values():
        out |= {n for n in names if n != "*"}
    return out


def known(unit: dict[str, Any]) -> set[str]:
    return set(unit["used"]) | set(unit["provided"])


def check_mixed(unit: dict[str, Any], label: dict[str, Any]) -> str | None:
    item, hand = unit["line"], label.get("handoff") or []
    if label.get("symbol", ""):
        return f"'{item}': symbol is not permitted with role \"mixed\"."
    if not hand:
        return f"'{item}': role \"mixed\" must have handoff."
    bad = [n for n in hand if n not in known(unit)]
    return f"'{item}': {bad[0]} in handoff is not a name of {unit['unit']}." if bad else None


def check_helper(unit: dict[str, Any], label: dict[str, Any]) -> str | None:
    item, sym, m = unit["line"], label.get("symbol", ""), unit["unit"]
    if not known(unit):
        return None if not sym else f"'{item}': the facts give no names for {m}."
    if not sym:
        return f"'{item}': role \"helper\" must have a symbol."
    if sym in unit["used"] or (unit["star"] and sym in unit["provided"]):
        return None
    return f"'{item}': {sym} is not a name of {m} that other components import."


def check_label(unit: dict[str, Any], label: dict[str, Any]) -> str | None:
    role, item, sym = label.get("role"), unit["line"], label.get("symbol", "")
    if role not in ROLES:
        return f'\'{item}\': role must be "helper", "handoff", or "mixed".'
    if role == "mixed":
        return check_mixed(unit, label)
    if label.get("handoff"):
        return f"'{item}': handoff is permitted only with role \"mixed\"."
    if role == "helper":
        return check_helper(unit, label)
    if sym and sym not in known(unit):
        return f"'{item}': {sym} is not a name of {unit['unit']}."
    return None


def unit_state(lab: dict[str, Any], pnames: list[str]) -> tuple[bool, str]:
    """True when the import crossing uses handoff code of the unit, and the row text."""
    by_name = bool(set(lab.get("handoff") or []) & set(pnames))
    if lab["role"] == "handoff" or (lab["role"] == "mixed" and by_name):
        return True, lab["role"] + " (used)"
    if lab["role"] == "mixed" and "*" in pnames:
        return True, lab["role"] + " (used by *)"
    return False, lab["role"]


def crossing_state(
    pair: dict[str, Any], roles: dict[str, dict[str, Any]]
) -> tuple[str, list[list[str]]]:
    why: list[list[str]] = []
    found: set[str] = set()
    for u, pnames in pair["units"].items():
        lab = roles.get(u)
        used, text = unit_state(lab, pnames) if lab is not None else (False, "none")
        why.append([u, text])
        found.add("open" if used else text)
    state = "open" if "open" in found else "waiting" if "none" in found else "closed"
    return state, why


# ---- steps -------------------------------------------------------------------------------


def step_units(root: Path, name: str, out: Path) -> None:
    tree, facts = load(root)
    data = build(tree, facts, import_forms(root, facts))
    ranked = sorted(data["units"].values(), key=lambda r: (-len(r["pairs"]), r["unit"]))
    out.write_text(json.dumps({"units": ranked}, indent=1, sort_keys=True))
    print(
        name,
        "run-time import crossings",
        len(data["pairs"]),
        "units",
        len(data["units"]),
        "expected",
        EXPECTED[name],
    )


def map_labels(path: Path, name: str) -> list[dict[str, Any]]:
    labels = json.loads(path.read_text())
    return [lab for lab in labels if lab.get("map", name) == name]


def acceptance(
    name: str, states: dict[str, tuple[str, list[list[str]]]], star_only: set[str]
) -> tuple[bool, list[str]]:
    ok, rows = True, []
    for p_, q_ in ACCEPT[name]:
        tail = f"crossing import: {p_} imports {q_} and no flow connects them"
        hits = [line for line in states if line.endswith(tail)]
        if not hits:
            rows.append(f"{p_}->{q_}: not an import crossing")
            ok = False
        for line in hits:
            s, why = states[line]
            rows.append(f"{line}: {s} {why}")
            ok = ok and s == "open" and line not in star_only
    return ok, rows


def accept_labels(
    units: dict[str, dict[str, Any]], labels: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], list[tuple[str, str]]]:
    roles: dict[str, dict[str, Any]] = {}
    refused: list[tuple[str, str]] = []
    for lab in labels:
        u = lab["unit"]
        err = check_label(units[u], lab) if u in units else "not a unit"
        if err:
            refused.append((u, err))
        else:
            roles[u] = lab
    return roles, refused


def summary(
    name: str,
    data: dict[str, Any],
    roles: dict[str, dict[str, Any]],
    states: dict[str, tuple[str, list[list[str]]]],
) -> dict[str, Any]:
    units = data["units"]
    c = collections.Counter(s for s, _w in states.values())
    star_only = {
        line
        for line, (s, why) in states.items()
        if s == "open" and not any(w.endswith("(used)") for _u, w in why)
    }
    ok_a, rows = acceptance(name, states, star_only)
    rc = collections.Counter(r["role"] for r in roles.values())
    return {
        "acceptance_a": ok_a,
        "acceptance_waiting": c["waiting"] == 0,
        "accept_rows": rows,
        "run_time_import_crossings": len(data["pairs"]),
        "module_use_lines": len(units),
        "counts": {k: c[k] for k in ("open", "waiting", "closed")},
        "questions": len(units) + c["open"],
        "module_roles": dict(sorted(rc.items())),
        "star_only": sorted(star_only),
        "unlabelled": sorted(u for u in units if u not in roles),
        "states": {k: v[0] for k, v in sorted(states.items())},
        "units": {k: v[1] for k, v in sorted(states.items())},
    }


def show(name: str, r: dict[str, Any]) -> None:
    c, rt, n_units = r["counts"], r["run_time_import_crossings"], r["module_use_lines"]
    print(f"== {name}")
    print(f"run-time import crossings {rt}; module use lines {n_units}; expected {EXPECTED[name]}")
    print(f"module roles {r['module_roles']}; units with no label {len(r['unlabelled'])}")
    print(f"import crossings: open {c['open']} waiting {c['waiting']} closed {c['closed']}")
    print(f"questions {r['questions']} = {n_units} + {c['open']}; ratio {r['questions'] / rt:.2f}")
    print(f"open only through '*': {len(r['star_only'])}")
    for row in r["accept_rows"]:
        print("ACCEPT", row)
    print("ACCEPTANCE (a):", "PASS" if r["acceptance_a"] else "FAIL")
    print("ACCEPTANCE (w):", "PASS" if r["acceptance_waiting"] else "FAIL")


def step_states(root: Path, name: str, lpath: Path, out: Path) -> int:
    tree, facts = load(root)
    data = build(tree, facts, import_forms(root, facts))
    roles, refused = accept_labels(data["units"], map_labels(lpath, name))
    if refused:
        print(f"== {name}: the label file is refused. {len(refused)} records fail:")
        for r in refused:
            print("  ", r)
        return 1
    states = {p["line"]: crossing_state(p, roles) for p in data["pairs"]}
    r = summary(name, data, roles, states)
    show(name, r)
    result = json.loads(out.read_text()) if out.exists() else {}
    result[name] = r
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    return 0 if r["acceptance_a"] and r["acceptance_waiting"] else 1


def main() -> int:
    step, root, name = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    if step == "units":
        step_units(root, name, Path(sys.argv[4]))
        return 0
    return step_states(root, name, Path(sys.argv[4]), Path(sys.argv[5]))


if __name__ == "__main__":
    sys.exit(main())
