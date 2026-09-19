"""The PR idea, second form: audit each touched card's old sentence against its modules at the head commit."""

import json
from pathlib import Path

from build_meaning import git, model_components
from common import SCRATCH, SYSTEMAP, write

from systemap import config
from systemap.delta import facts_at
from systemap.model import module_matches

rows = []
drift = [
    json.loads(line)
    for line in (Path(__file__).parent / "data/drift.jsonl").read_text().splitlines()
]

cache = {}
for d in drift:
    tag = d["repo"]
    if tag.startswith("systemap@"):
        root, head = SYSTEMAP, tag.split("@")[1]
        old_model = git(root, "show", f"{head}^:map/model.py")
    else:
        run = next(
            p for p in SCRATCH.glob("repo-maintenance-*") if p.name.endswith(tag.split("@")[1])
        )
        root, head = run / "repo", "HEAD"
        old_model = git(root, "show", "HEAD:map/model.py")
    key = (str(root), head)
    if key not in cache:
        cache[key] = facts_at(config.load(root), head)["components"]
    recs = cache[key]
    cid = d["state"]["component"]["id"]
    pats = model_components(old_model)[cid]["implemented_by"]
    mods = sorted(m for m in recs if any(module_matches(p, m) for p in pats))[:6]
    state_mods = [
        {
            "module": m,
            "docstring": " ".join((recs[m].get("docstring") or "").split())[:300] or None,
            "public_names": [n["name"] for n in recs[m].get("names", [])][:15],
        }
        for m in mods
    ]
    rows.append(
        {
            **d,
            "exp": "drift_head",
            "state": {"sentence": d["state"]["component"]["does"], "modules": state_mods},
            "questions": {
                "describes": {
                    "type": "noul",
                    "instructions": "Does `sentence` accurately describe what the code in `modules` does, taken together as one part of the system?",
                }
            },
        }
    )
write("drift_head", rows)
