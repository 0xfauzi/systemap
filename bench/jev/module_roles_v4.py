"""Stage 4a of the module role specification (revision 2): acceptance on the test maps.

Step `before` (section 19, stage 4a). Acceptance values, written before the first run:
the policy answers are refused answers with their counts; the module use lines are
Django 226, SQLAlchemy 101 and starlette 8; 0 crossing import lines are open; the
waiting import crossings are Django 283, SQLAlchemy 135 and starlette 15.

Steps `write` and `compare` are step V4 (section 18.5). Acceptance value, written before
the first run: with the G1 labels as exact module role answers with current digests, the
import crossing states of the real `systemap judgement --json` are identical to the G1
states (`module_roles_G1.json`) for every import crossing on the three maps. The step
prints each difference.

Use a scratch copy of each map. Never write the `systemap.toml` of a test map. The script
reads the recorded facts and the models (`nest.load` runs no model code), and it runs no
project code.

Run:
  uv run --project /home/user/systemap python -I module_roles_v4.py before <map root> <name>
  uv run --project /home/user/systemap python -I module_roles_v4.py write <map root> <name> <labels>
  systemap --root <map root> judgement --json > <judgement json>
  uv run --project /home/user/systemap python -I module_roles_v4.py compare <judgement json> <name> <G1 json>
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from systemap import config, facts_file, judgement_json, module_use, nest

EXPECTED = {"django": (226, 283), "sqlalchemy": (101, 135), "starlette": (8, 15)}


def before(root: Path, name: str) -> None:
    cfg = config.load(root)
    start = time.perf_counter()
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    judged = judgement_json.evaluate(nest.load(cfg), facts, cfg)
    took = time.perf_counter() - start
    uses = [line for line in judged.lines if judgement_json.judgement.kind_of(line) == "module use"]
    crossing = [
        line
        for line in judged.result.open
        if judgement_json.judgement.kind_of(line) == "crossing import"
    ]
    states = [row["state"] for row in judged.crossings.values()]
    print(name, f"evaluate {took:.1f} s")
    for row in judged.refused_rows:
        print("  refused:", row["cause"], row["answer"], "lines", row["lines"])
    print("  module use lines", len(uses), "expected", EXPECTED[name][0])
    print("  open crossing import lines", len(crossing), "expected 0")
    print(
        "  import crossings",
        len(states),
        "waiting",
        states.count("waiting"),
        "expected",
        EXPECTED[name][1],
        "open",
        states.count("open"),
        "closed",
        states.count("closed"),
    )


def write(root: Path, name: str, labels: Path) -> None:
    cfg = config.load(root)
    tree = nest.load(cfg)
    found = module_use.index(tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    digests = module_use.evidence(found)
    rows = []
    for lab in json.loads(labels.read_text()):
        if lab.get("map", name) != name:
            continue
        unit = found.units[lab["unit"]]
        keys = [f"item = {json.dumps(unit.line)}", f"role = {json.dumps(lab['role'])}"]
        if lab.get("symbol"):
            keys.append(f"symbol = {json.dumps(lab['symbol'])}")
        if lab.get("handoff"):
            keys.append(f"handoff = {json.dumps(lab['handoff'])}")
        keys += [f"evidence = {json.dumps(digests[unit.module])}", 'reason = "A G1 label."']
        rows.append("  { " + ", ".join(keys) + " },\n")
    toml = root / "systemap.toml"
    text = toml.read_text(encoding="utf-8")
    if "\nanswered = [\n" in text:
        text = text.replace("\nanswered = [\n", "\nanswered = [\n" + "".join(rows), 1)
    else:
        text += "\n[judgement]\nanswered = [\n" + "".join(rows) + "]\n"
    toml.write_text(text, encoding="utf-8")
    print(name, "answers written", len(rows))


def compare(path: Path, name: str, g1: Path) -> int:
    out = json.loads(path.read_text())
    now = {c["line"]: c["state"] for c in out["import_crossings"]["crossings"]}
    earlier = json.loads(g1.read_text())[name]["states"]
    diff = sorted(set(now) ^ set(earlier))
    diff += [line for line in sorted(now) if line in earlier and now[line] != earlier[line]]
    print(name, "import crossings", len(now), "G1", len(earlier), "differences", len(diff))
    for line in diff:
        print("  DIFF", line, now.get(line), earlier.get(line))
    c = out["import_crossings"]
    print("  open", c["open"], "waiting", c["waiting"], "closed", c["closed"])
    print("  module_roles", out["module_roles"])
    print("  refused", [(r["cause"], r["answer"][:60], r["lines"]) for r in out["refused_answers"]])
    return 1 if diff else 0


def main() -> int:
    step = sys.argv[1]
    if step == "before":
        before(Path(sys.argv[2]), sys.argv[3])
        return 0
    if step == "write":
        write(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
        return 0
    return compare(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))


if __name__ == "__main__":
    sys.exit(main())
