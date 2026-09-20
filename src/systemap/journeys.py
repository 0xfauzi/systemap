"""A journey written for a way in nothing walks from yet.

`systemap judgement` says which ways into the system no journey walks from.
This writes one: the agent reads the code from that way in and answers with
a walk, and systemap checks the walk against the map before it is written
into the model.

What systemap supplies is the map's own vocabulary: the cards with their
sentences, the flows already drawn, and the way in with the module behind
it. What the agent supplies is the reading: which cards a run really passes
through, in what order, and one sentence per step.

What systemap refuses is a walk the map cannot hold: a step tracing a flow
that is not there, or naming a card that does not exist. Those come back as
lines to fix rather than as a journey, since a journey that names flows the
map does not draw would fail `systemap check` a moment later.

A generated journey is a draft: it is written into the model with the way in
it starts from, and `systemap judgement` asks the maintainer to confirm it
until they answer the line. Nothing here writes prose of its own, and with
no agent set nothing runs at all.

The walk was first proposed from the imports instead, and measured: the
cards it named overlapped the ones a person wrote by 0.28 where the bar was
0.60, because the module behind a command line imports the whole system.
`bench/jev/propose.py` keeps that attempt and `bench/jev/paths.py` scores it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from systemap import judgement
from systemap.agent import Agent
from systemap.evidence import owners
from systemap.extract import entry_label
from systemap.model import Journey, Meaning, Model, Step

QUESTION = """You are reading a repository to write one journey for its system map.

A journey is the walk a reader takes through the system when a run starts at
one way in: which parts it passes through, in order, and what happens at each
step. It is written for a newcomer, in plain words.

Read the code from the way in named below. Then answer with JSON only, in this
shape, and nothing else:

{"id": "short-id", "label": "what a person would call this walk",
 "steps": [{"edge": ["CardA", "CardB"], "acts": ["CardA"], "measures": [],
            "say": "one sentence, from the acting side"}]}

Rules:
- Every `edge` must be one of the flows listed below, exactly as given.
- Every card named in `acts` and `measures` must be one of the cards listed.
- `measures` names a card that watches or records the step, or is empty.
- Four to eight steps. Each sentence says what happens, not how the code does it.
- The walk must be what the code does, not what it could do.
"""


# The same question, for a crowd. This is the wording measured in
# `bench/jev/group_journeys.py`: 19 crowds over mealie, paperless-ngx and
# poetry, and every answer came back as a walk the map could hold.
GROUP_QUESTION = QUESTION.replace(
    "Read the code from the way in named below.",
    "Below is a group of ways in of one kind, all of them into the same part of "
    "the system. Write ONE journey that stands for the whole group: the walk "
    "they share, not the special case of any one of them. Read the code behind "
    "two or three of them first.",
)


@dataclass(frozen=True)
class Group:
    """What one walk is asked for: a way in, or a crowd of them into one card."""

    ways_in: tuple[dict[str, str], ...]
    card: str = ""

    @property
    def one(self) -> dict[str, str]:
        return self.ways_in[0]

    @property
    def whole(self) -> bool:
        """Is this a crowd, walked once for the card rather than once each?"""
        return bool(self.card) and len(self.ways_in) > judgement.TOGETHER_AT

    @property
    def label(self) -> str:
        if not self.whole:
            return entry_label(self.one)
        return f"{len(self.ways_in)} {self.one['kind']}s into {self.card}"

    @property
    def starts(self) -> str:
        """What the journey records as the way in it walks from.

        A crowd is recorded as the card, because a walk that stands for a
        hundred routes cannot name one of them without claiming to be about
        that one. `systemap judgement` reads a card here as covering every way
        in of that kind the card claims.
        """
        return self.card if self.whole else self.one["name"]


@dataclass
class Draft:
    """What came back for one way in: a journey, or the reasons it was refused."""

    entry: dict[str, str]
    journey: Journey | None = None
    problems: tuple[str, ...] = ()


def uncovered(
    meaning: Meaning, facts: dict[str, Any], owner: dict[str, str] | None = None
) -> list[dict[str, str]]:
    """The ways in no journey walks from, by the rule `systemap judgement` uses."""
    return judgement.ways_in_without_journey(meaning, facts, owner=owner)


def gather(model: Model, meaning: Meaning, facts: dict[str, Any]) -> list[Group]:
    """The ways in with no walk, as the questions to ask: crowds first.

    A card that takes a hundred routes is one question, not a hundred, which
    is how `systemap judgement` already prints it. Everything else is asked
    about on its own.
    """
    owner = owners(model, facts)
    held: dict[tuple[str, str], list[dict[str, str]]] = {}
    for point in uncovered(meaning, facts, owner):
        held.setdefault((point["kind"], owner.get(point["module"], "")), []).append(point)
    out: list[Group] = []
    for (_kind, card), found in held.items():
        group = Group(tuple(found), card)
        out.append(group) if group.whole else out.extend(Group((p,), card) for p in found)
    return sorted(out, key=lambda g: (-len(g.ways_in), g.label))


def context(model: Model, meaning: Meaning, facts: dict[str, Any], group: Group) -> dict[str, Any]:
    """What the agent is told: the way in, the cards, the flows, and where to read."""
    return {
        "way_in": _asked(facts, group),
        "cards": {
            c.id: " ".join(filter(None, [meaning.plain.get(c.id, ""), c.does]))
            for c in model.components
        },
        "flows": [
            [f.src, f.dst, f.artifact, meaning.relations.get(f.edge, "")] for f in model.flows
        ],
        "journeys_already_written": [j.label for j in meaning.journeys],
    }


# How many of a crowd's ways in the agent is shown. A list of a hundred and
# ninety routes is not read, and the point of a crowd is that they are the
# same kind of thing.
SHOWN = 14


def _asked(facts: dict[str, Any], group: Group) -> dict[str, Any]:
    """The way in, or the crowd, as the agent is told about it."""
    records = facts.get("components", {})

    def one(p: dict[str, str]) -> dict[str, Any]:
        return {
            "named": entry_label(p),
            "kind": p["kind"],
            "module": p["module"],
            "file": records.get(p["module"], {}).get("file", ""),
            "function": p.get("target") or p.get("name", ""),
        }

    if not group.whole:
        return one(group.one)
    return {
        "a_group": f"{len(group.ways_in)} {group.one['kind']}s into {group.card}",
        "kind": group.one["kind"],
        "into_card": group.card,
        "how_many": len(group.ways_in),
        "each": [one(p) for p in group.ways_in[:SHOWN]],
    }


def _steps(raw: Any, model: Model, problems: list[str]) -> tuple[Step, ...]:
    cards = {c.id for c in model.components}
    flows = {f.edge for f in model.flows}
    out: list[Step] = []
    for k, step in enumerate(raw if isinstance(raw, list) else [], start=1):
        edge = tuple(step.get("edge", []))
        acts = tuple(step.get("acts", []))
        measures = tuple(step.get("measures", []))
        unknown = sorted({*acts, *measures, *edge} - cards)
        if len(edge) != 2 or edge not in flows:
            problems.append(
                f"step {k} traces {' -> '.join(edge) or 'nothing'}, which is not a flow"
            )
        elif unknown:
            problems.append(f"step {k} names {', '.join(unknown)}, which the map has no card for")
        else:
            out.append(Step(acts=acts, measures=measures, edge=edge, say=str(step.get("say", ""))))
    return tuple(out)


def read_answer(text: str, model: Model, group: Group) -> Draft:
    """The agent's answer as a journey, or the reasons it cannot be one."""
    entry = group.one
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return Draft(entry=entry, problems=("the agent did not answer with JSON",))
    try:
        raw = json.loads(text[start : end + 1])
    except ValueError as exc:
        return Draft(entry=entry, problems=(f"the agent's JSON could not be read: {exc}",))
    problems: list[str] = []
    steps = _steps(raw.get("steps"), model, problems)
    if not steps:
        problems.append("no step of the walk could be used")
        return Draft(entry=entry, problems=tuple(problems))
    journey = Journey(
        id=str(raw.get("id") or entry["name"]).strip(),
        label=str(raw.get("label") or group.label).strip(),
        steps=steps,
        starts=group.starts,
        drafted=True,
    )
    return Draft(entry=entry, journey=journey, problems=tuple(problems))


def write_one(
    agent: Agent, model: Model, meaning: Meaning, facts: dict[str, Any], group: Group
) -> Draft:
    """Ask the agent for the walk, one way in or a crowd, and check what comes back."""
    question = GROUP_QUESTION if group.whole else QUESTION
    answer = agent.ask(question, context(model, meaning, facts, group))
    return read_answer(answer, model, group)


ANCHORS = ("JOURNEYS = (", "journeys=(")


def add_to_source(source: str, journey: Journey) -> str | None:
    """The model module with one journey written into it, or None when there is
    nowhere to put it: the file names its journeys somewhere this cannot find."""
    for anchor in ANCHORS:
        at = source.find(anchor)
        if at < 0:
            continue
        line_end = source.find("\n", at)
        if line_end < 0:
            continue
        block = "\n".join(as_source(journey))
        return source[: line_end + 1] + block + "\n" + source[line_end + 1 :]
    return None


def as_source(journey: Journey) -> list[str]:
    """One journey as it is written in the model module, ready to paste in."""
    out = [
        "    Journey(",
        f'        id="{journey.id}",',
        f'        label="{journey.label}",',
        f'        starts="{journey.starts}",',
        "        drafted=True,  # read it, then remove this line",
        "        steps=(",
    ]
    for step in journey.steps:
        acts = ", ".join(f'"{c}"' for c in step.acts)
        measures = ", ".join(f'"{c}"' for c in step.measures)
        out += [
            "            Step(",
            f"                acts=({acts}{',' if len(step.acts) == 1 else ''}),",
            f"                measures=({measures}{',' if len(step.measures) == 1 else ''}),",
            f'                edge=("{step.edge[0]}", "{step.edge[1]}"),',
            f'                say="{step.say}",',
            "            ),",
        ]
    out += ["        ),", "    ),"]
    return out
