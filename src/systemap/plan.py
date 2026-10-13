"""The plan projects a task onto map components and compares the projection with a later
change.

A decision provider gives component weights from the task and component descriptions.
The context includes connected flows, sequences, and invariants. A later comparison
identifies unplanned changes and planned components without changes.

A plan ID has three parts: the date, a digest of the full task, and the first four
words of the task. The same task on the same date gives the same ID. A save does not
replace the plan file of a different task.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap import evidence, file_write, graph
from systemap.audit import NONE
from systemap.config import Config
from systemap.model import Meaning, Model

# The hex characters of the task digest in a plan ID.
DIGEST_CHARS = 12
# The cut of each provider is `plan_cut` in `systemap.decision.THRESHOLDS`.
# The text is cut here, as triage cuts an issue: a question with a whole
# design document in it is a question about the document, not the work.
TEXT_CAP = 2000
PLAN_Q = (
    "`task` gives the planned work on this system. Which component has the largest "
    "probability of a change from this task?"
)


class PlanError(Exception):
    """A plan cannot be saved. The message gives the cause."""


@dataclass(frozen=True)
class Around:
    """This record gives flow, sequence, and invariant context for one component."""

    card: str
    flows: tuple[str, ...] = ()
    journeys: tuple[str, ...] = ()
    rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class Projection:
    """This record contains projected components, their weights, and their map context."""

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


def named(probabilities: dict[str, float], cut: float) -> list[str]:
    """This function selects components with a probability at or above the cut, with the
    largest probabilities first. The option "none of these" is not a component.
    """
    ranked = sorted(probabilities.items(), key=lambda kv: -kv[1])
    return [cid for cid, p in ranked if p >= cut and cid != NONE]


def around(model: Model, meaning: Meaning, card: str) -> Around:
    """This function gives the map context for one component."""
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
    *,
    cut: float,
) -> Projection:
    """This function converts a choice answer into weighted components and map context."""
    cards = named(probabilities, cut)
    return Projection(
        id=plan_id(task),
        task=task,
        at=at or time.strftime("%Y-%m-%d"),
        cards=tuple(cards),
        weights={cid: round(probabilities.get(cid, 0.0), 3) for cid in cards},
        around=tuple(around(model, meaning, cid) for cid in cards),
    )


def plan_id(task: str) -> str:
    """This function makes a plan ID: the date, a digest of the full task, and the first
    four words of the task.
    """
    words = [w for w in "".join(c if c.isalnum() else " " for c in task).split()[:4] if w]
    stem = "-".join(w.lower() for w in words) or "plan"
    digest = hashlib.sha256(task.encode("utf-8")).hexdigest()[:DIGEST_CHARS]
    return f"{time.strftime('%Y%m%d')}-{digest}-{stem}"


def path_of(cfg: Config, plan: str) -> Path:
    return cfg.root / ".systemap/plans" / f"{plan}.json"


def save(cfg: Config, projection: Projection) -> Path:
    """This function writes the projection. If the plan file of the ID has a different task,
    or if it is not a plan, the function gives PlanError and does not change the file.
    """
    path = path_of(cfg, projection.id)
    if path.exists():
        held = load(cfg, projection.id)
        if held is None or held.get("task") != projection.task:
            raise PlanError(
                f"{cfg.rel(path)} does not contain this task, and systemap did not replace it. "
                "The file has a different task, or it is not a plan"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(projection.as_json(), indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    return path


def load(cfg: Config, plan: str) -> dict[str, Any] | None:
    """Give the stored plan, or None if it is missing or not usable.

    A link out of the plan folder, a FIFO, and a device give `file_write.RefusedFile`
    with the cause. They do not give None.
    """
    try:
        text = file_write.read_text(path_of(cfg, plan))
        found = json.loads(text) if text is not None else None
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def saved(cfg: Config) -> list[str]:
    """This function lists stored plans in name order."""
    folder = cfg.root / ".systemap/plans"
    return sorted(p.stem for p in folder.glob("*.json")) if folder.is_dir() else []


def owners(
    head: Model, base: Model | None, base_facts: dict[str, Any], head_facts: dict[str, Any]
) -> dict[str, str]:
    """This function gives the component of each module in the two snapshots.

    The head model and the head facts give the first owner. The head model and the base
    facts give the owner of a removed module. If the head model does not claim a removed
    module, the base model gives its owner.
    """
    owner: dict[str, str] = {}
    for model, facts in ((head, head_facts), (head, base_facts), (base, base_facts)):
        if model is not None:
            for module, card in evidence.owners(model, facts).items():
                owner.setdefault(module, card)
    return owner


def touched(base: dict[str, Any], head: dict[str, Any], owner: dict[str, str]) -> set[str]:
    """This function finds components with edited, added, or removed modules."""
    b, h = base.get("components", {}), head.get("components", {})
    moved = {m for m in set(b) & set(h) if b[m].get("sha") != h[m].get("sha")}
    return {owner[m] for m in moved | (set(b) ^ set(h)) if m in owner}


def check(projected: list[str], changed: set[str]) -> tuple[list[str], list[str]]:
    """This function finds unplanned changed components and planned components without
    changes.
    """
    return sorted(changed - set(projected)), sorted(set(projected) - changed)
