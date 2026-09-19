"""Could Jev assign modules to the agent's first-draft cards better than the agent did?

For each first-map run in bench/scratch, the agent's first write of
map/model.py is read out of the session log. Every module is then asked the
owner question (the one measured in the owner experiment) with the DRAFT
cards as the options, and three assignments are scored against the finished
map, over the modules whose final card already existed in the draft by id:

    agent draft ... the card the draft's implemented_by gave the module
    Jev ........... Jev's pick among the draft cards
    Jev >= 0.9 .... Jev's pick where its confidence is 0.9 or more, else the draft's

The finished map is the reference: the agent's own answer after check,
judgement and the second pass. It is not ground truth, and a module the
agent never moved counts as right for the draft.

    uv run python bench/jev/draft.py
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from common import HERE, NONE, Repo, choice, module_state, owner_criteria
from turns import RUNS, calls

from systemap import config, extract, jev, nest
from systemap.audit import OWNER_Q
from systemap.extract import is_empty_marker
from systemap.model import claimed

OUT = HERE / "results" / "draft"
CONFIDENT = 0.9


def model_versions(run: Path) -> list[str]:
    """Every state of map/model.py the agent wrote, in order: the first write,
    then each edit applied to it."""
    content: str | None = None
    out = []
    for use, _result, _tok in calls(run / "session.jsonl"):
        inp = use["input"]
        if not str(inp.get("file_path", "")).endswith("map/model.py"):
            continue
        if use["name"] == "Write":
            content = str(inp["content"])
        elif use["name"] == "Edit" and content is not None and inp.get("old_string") in content:
            count = -1 if inp.get("replace_all") else 1
            content = content.replace(inp["old_string"], inp["new_string"], count)
        else:
            continue
        out.append(content)
    return out


DUMP = """
import json, runpy, sys
ns = runpy.run_path(sys.argv[1])
cards = [
    {"id": c.id, "kind": c.kind, "does": c.does, "interface": getattr(c, "interface", ""),
     "implemented_by": list(c.implemented_by)}
    for c in ns["MODEL"].components
]
print(json.dumps({"cards": cards, "plain": dict(ns["MEANING"].plain)}))
"""


def load_model(run: Path, source: str) -> tuple[Any, Any]:
    """The draft's cards, loaded by the systemap the run used: the schema has
    changed since, so today's cannot build a draft written for it."""
    python = run / "tools/systemap/bin/python"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "draft_model.py"
        path.write_text(source)
        out = subprocess.run(
            [str(python), "-c", DUMP, str(path)], capture_output=True, text=True, check=True
        )
    data = json.loads(out.stdout)
    cards = tuple(
        SimpleNamespace(**{**c, "implemented_by": tuple(c["implemented_by"])})
        for c in data["cards"]
    )
    return SimpleNamespace(components=cards), SimpleNamespace(plain=data["plain"])


def owners(model: Any, mods: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in model.components:
        for m in claimed(c, mods):
            out.setdefault(m, c.id)
    return out


def first_loadable(run: Path) -> tuple[Any, Any, int] | None:
    """The first state of the model that loads, and how many writes and edits in it is."""
    for k, source in enumerate(model_versions(run)):
        try:
            model, meaning = load_model(run, source)
        except subprocess.CalledProcessError:
            continue
        return model, meaning, k
    return None


def repos(run: Path) -> tuple[Repo, Repo, int] | None:
    found = first_loadable(run)
    if found is None:
        return None
    model, meaning, edits = found
    root = run / "repo"
    cfg = config.load(root)
    facts = extract.read_facts(cfg.facts_path)
    mods = [m for m, r in facts["components"].items() if not is_empty_marker(r)]
    top = nest.load(cfg).top
    name = run.name.split("-first-map")[0]
    final = Repo(name, root, cfg, top.model, top.meaning, facts, owners(top.model, mods))
    draft = Repo(name, root, cfg, model, meaning, facts, owners(model, mods))
    return final, draft, edits


def asks(final: Repo, draft: Repo) -> list[jev.Ask]:
    placeable = {c.id for c in final.placeable()}
    criteria = {"owner": choice(OWNER_Q, owner_criteria(draft))}
    return [
        jev.Ask(m, {"system": final.name, "module": module_state(final, m)}, criteria)
        for m in sorted(final.owner)
        if final.owner[m] in placeable
    ]


def score(final: Repo, draft: Repo, answers: dict[str, Any]) -> dict[str, Any]:
    draft_ids = {c.id for c in draft.placeable()}
    judged = [m for m in answers if final.owner[m] in draft_ids]
    a = {m: answers[m]["owner"] for m in judged}
    right = lambda pick: sum(pick(m) == final.owner[m] for m in judged)  # noqa: E731
    confident = [m for m in judged if a[m]["confidence"] >= CONFIDENT]
    return {
        "run": final.name,
        "modules": len(answers),
        "draft cards": len(draft_ids),
        "final cards": len({c.id for c in final.placeable()}),
        "judged": len(judged),
        "agent draft": right(lambda m: draft.owner.get(m)),
        "Jev": right(lambda m: a[m]["choice"]),
        "Jev confident": len(confident),
        "Jev confident right": sum(a[m]["choice"] == final.owner[m] for m in confident),
        "Jev >= 0.9 else draft": right(
            lambda m: a[m]["choice"] if a[m]["confidence"] >= CONFIDENT else draft.owner.get(m)
        ),
        "Jev says none": sum(a[m]["choice"] == NONE for m in judged),
        "moved after draft": sum(draft.owner.get(m) != final.owner[m] for m in judged),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = jev.from_env("jev-latest", HERE / "data" / "draft-cache.json")
    rows = []
    for run in RUNS:
        pair = repos(run)
        if pair is None:
            print(f"{run.name}: no draft write in the log")
            continue
        final, draft, edits = pair
        print(f"{final.name}: the draft is the model after {edits} edits of the first write")
        batch = asks(final, draft)
        answered = client.ask(batch)
        answers = {k: v for k, v in answered.items()}
        (OUT / f"{final.name}.json").write_text(json.dumps(answers))
        rows.append(score(final, draft, answers))
    print(client.usage.line())
    (OUT / "scores.json").write_text(json.dumps(rows, indent=1))
    for r in rows:
        n = r["judged"]
        conf = r["Jev confident"]
        print(
            f"{r['run']:<14} modules {r['modules']:>4}, cards draft/final {r['draft cards']}/{r['final cards']}, "
            f"judged {n:>4} ({n / r['modules']:.0%}); moved after draft {r['moved after draft'] / n:.0%}; "
            f"agent draft {r['agent draft'] / n:.0%}, Jev {r['Jev'] / n:.0%}, "
            f"Jev>=0.9 else draft {r['Jev >= 0.9 else draft'] / n:.0%}; "
            f"Jev confident on {conf / n:.0%}, right {r['Jev confident right'] / max(1, conf):.0%}; "
            f"Jev says none {r['Jev says none']}"
        )
    tot = {k: sum(r[k] for r in rows) for k in rows[0] if k != "run"}
    n = tot["judged"]
    print(
        f"{'all':<14} judged {n}; moved after draft {tot['moved after draft'] / n:.0%}; "
        f"agent draft {tot['agent draft'] / n:.0%}, Jev {tot['Jev'] / n:.0%}, "
        f"Jev>=0.9 else draft {tot['Jev >= 0.9 else draft'] / n:.0%}; "
        f"Jev confident on {tot['Jev confident'] / n:.0%}, right {tot['Jev confident right'] / tot['Jev confident']:.0%}"
    )


if __name__ == "__main__":
    main()
