"""A piece of work projected onto the map, and then checked against what happened.

Before the work: you describe the task in your own words, Jev reads it
against every card's purpose, and the cards it gives real weight to are the
ones the work will most likely change. Around each of those, the map says
what it sits in: the flows that leave and reach it, the walks that pass
through it, and the rules that govern it. That is the part a plan usually
leaves out, and the part that goes wrong.

After the work: `systemap plan --check` compares what was projected with the
cards the code actually changed. A card that changed and was not projected
is the finding. It is not a failure of the plan; it is the place where the
system did something the plan did not see, which is exactly what a map is
for.

The cut is measured, not chosen by taste. Over 80 real bug reports with the
cards their fixing pull request touched, a cut at 0.05 of Jev's probability
covered 86% of those cards while naming 2.1 cards per report; on 39 issues
of a repository no threshold was chosen on, it covered 71% while naming 2.1.
The bar, set before the run, was 70% covered with at most 2 extra cards.
`bench/jev/plan_eval.py` runs it and `bench/jev/README.md` holds the table.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap import graph
from systemap.config import Config
from systemap.model import Meaning, Model

# The measured cut: a card is in the projection when Jev gives it at least
# this much of the probability. See the docstring above for what it scored.
CUT = 0.05
# The text is cut here, as triage cuts an issue: a question with a whole
# design document in it is a question about the document, not the work.
TEXT_CAP = 2000
PLAN_Q = (
    "`task` is a piece of work someone is about to do on this system. "
    "Which component will the work most likely have to change?"
)


@dataclass(frozen=True)
class Around:
    """What one card sits in: what a plan that names the card still misses."""

    card: str
    flows: tuple[str, ...] = ()
    journeys: tuple[str, ...] = ()
    rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class Projection:
    """The cards a task is expected to change, and what each sits in."""

    id: str
    task: str
    at: str
    cards: tuple[str, ...] = ()
    weights: dict[str, float] = field(default_factory=dict)
    around: tuple[Around, ...] = ()

    def as_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task": self.task,
            "at": self.at,
            "cards": list(self.cards),
            "weights": self.weights,
            "around": [
                {
                    "card": a.card,
                    "flows": list(a.flows),
                    "journeys": list(a.journeys),
                    "rules": list(a.rules),
                }
                for a in self.around
            ],
        }


def named(probabilities: dict[str, float], cut: float = CUT) -> list[str]:
    """The cards Jev gives real weight to, the heaviest first."""
    ranked = sorted(probabilities.items(), key=lambda kv: -kv[1])
    return [cid for cid, p in ranked if p >= cut and not cid.startswith("none")]


def around(model: Model, meaning: Meaning, card: str) -> Around:
    """What the map says the card sits in, in the words the map uses."""
    flows = [f"{f.src} -> {f.dst} ({f.artifact})" for f in graph.out_flows(model).get(card, ())]
    flows += [f"{f.src} -> {f.dst} ({f.artifact})" for f in graph.in_flows(model).get(card, ())]
    walks = [
        f"{j.id}: {j.label}"
        for j in meaning.journeys
        if any(card in (*s.acts, *s.measures, *s.edge) for s in j.steps)
    ]
    rules = [f"{r.n}. {r.text}" for r in graph.rules_on(model).get(card, ())]
    return Around(card, tuple(flows), tuple(walks), tuple(rules))


def project(
    model: Model,
    meaning: Meaning,
    task: str,
    probabilities: dict[str, float],
    at: str = "",
) -> Projection:
    """Jev's answer as a projection: the cards, their weight, and what each sits in."""
    cards = named(probabilities)
    return Projection(
        id=plan_id(task),
        task=task,
        at=at or time.strftime("%Y-%m-%d"),
        cards=tuple(cards),
        weights={cid: round(probabilities.get(cid, 0.0), 3) for cid in cards},
        around=tuple(around(model, meaning, cid) for cid in cards),
    )


def plan_id(task: str) -> str:
    """A short name for this plan: the first words of the task, and the day."""
    words = [w for w in "".join(c if c.isalnum() else " " for c in task).split()[:4] if w]
    stem = "-".join(w.lower() for w in words) or "plan"
    return f"{time.strftime('%Y%m%d')}-{stem}"


def path_of(cfg: Config, plan: str) -> Path:
    return cfg.root / ".systemap/plans" / f"{plan}.json"


def save(cfg: Config, projection: Projection) -> Path:
    path = path_of(cfg, projection.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(projection.as_json(), indent=1) + "\n", encoding="utf-8")
    return path


def load(cfg: Config, plan: str) -> dict[str, Any] | None:
    path = path_of(cfg, plan)
    if not path.is_file():
        return None
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def saved(cfg: Config) -> list[str]:
    """Every plan written here, newest name last."""
    folder = cfg.root / ".systemap/plans"
    return sorted(p.stem for p in folder.glob("*.json")) if folder.is_dir() else []


def touched(base: dict[str, Any], head: dict[str, Any], owner: dict[str, str]) -> set[str]:
    """The cards whose modules the change touched: edited, added or removed."""
    b, h = base.get("components", {}), head.get("components", {})
    moved = {m for m in set(b) & set(h) if b[m].get("sha") != h[m].get("sha")}
    return {owner[m] for m in moved | (set(b) ^ set(h)) if m in owner}


def check(projected: list[str], changed: set[str]) -> tuple[list[str], list[str]]:
    """What changed and was not projected, and what was projected and did not change."""
    return sorted(changed - set(projected)), sorted(set(projected) - changed)
