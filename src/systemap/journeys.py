"""Write a draft sequence for entry points without a sequence.

The configured agent examines source code from the entry point.
It writes ordered steps under the mandatory ASD-STE100 language policy.
systemap refuses steps with absent flows or unknown component identifiers.
Accepted drafts have `drafted=True` until the maintainer examines them against source.

The earlier import-based experiment had overlap 0.28 against acceptance value 0.60.
The CLI module imported components that the actual sequence did not use.
`bench/jev/propose.py` and `bench/jev/paths.py` keep that experiment and its measurements.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import tokenize
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap import journey_coverage as judgement
from systemap.agent import Agent
from systemap.evidence import owners
from systemap.extract import entry_identity, entry_label
from systemap.model import Journey, Meaning, Model, Step

QUESTION = """Examine the repository and write one sequence for its system map.

A sequence contains the ordered steps that start at an entry point.
Each step shows the components that act and the artifact that moves.
You must use ASD-STE100 Issue 9 for the identifier, label, and step sentences.
Use the project glossary supplied in the language policy.

Read the source code from the entry point below. Write only JSON with this shape:

{"id": "short-id", "label": "short sequence name",
 "steps": [{"edge": ["CardA", "CardB"], "acts": ["CardA"], "measures": [],
            "say": "one sentence from the acting component"}]}

Requirements:
- Keep every edge identical to a listed flow.
- Use only listed component identifiers in acts and measures.
- Use measures for a component that monitors or records the step. Otherwise, use an empty list.
- Write four to eight steps.
- Write one sentence per step about the action and its result.
- Write only steps that the source code supports.
"""

# The earlier group experiment accepted all answers for 19 entry point groups.
# `bench/jev/group_journeys.py` records those tests on mealie, paperless-ngx, and poetry.
GROUP_QUESTION = QUESTION.replace(
    "Read the source code from the entry point below.",
    "The entry points below have the same kind and component. "
    "Write one sequence for their common steps. "
    "Do not substitute a special case from one entry point. "
    "First read the source code for two or three of the entry points.",
)


@dataclass(frozen=True)
class Group:
    """The entry points assigned to one requested sequence."""

    ways_in: tuple[dict[str, str], ...]
    card: str = ""

    @property
    def one(self) -> dict[str, str]:
        return self.ways_in[0]

    @property
    def whole(self) -> bool:
        """Return whether one sequence represents the component's entry point group."""
        return bool(self.card) and len(self.ways_in) > judgement.TOGETHER_AT

    @property
    def label(self) -> str:
        if not self.whole:
            return entry_label(self.one)
        return judgement.crowd_label(len(self.ways_in), self.one["kind"], self.card)

    @property
    def starts(self) -> str:
        """The display label for the entry point or its component.

        A group uses the component identifier instead of one specific entry point.
        Coverage still requires the exact identities in `covers`.
        """
        return self.card if self.whole else self.one["name"]


@dataclass
class Draft:
    """The draft sequence or the reasons for refusal."""

    entry: dict[str, str]
    journey: Journey | None = None
    problems: tuple[str, ...] = ()
    answer: str = ""


def uncovered(
    meaning: Meaning,
    facts: dict[str, Any],
    owner: dict[str, str] | None = None,
    covered: Collection[str] | None = None,
) -> list[dict[str, str]]:
    """Return entry points without recorded sequence coverage."""
    return judgement.ways_in_without_journey(meaning, facts, owner=owner, covered=covered)


def gather(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    *,
    modules: Collection[str] | None = None,
    covered: Collection[str] | None = None,
) -> list[Group]:
    """Group uncovered entry points into requests, with large groups first.

    Entry points of the same kind and component can share one request.
    Other entry points each have a separate request.
    """
    owner = owners(model, facts)
    held: dict[tuple[str, str], list[dict[str, str]]] = {}
    for point in uncovered(meaning, facts, owner, covered):
        if modules is not None and point["module"] not in modules:
            continue
        held.setdefault((point["kind"], owner.get(point["module"], "")), []).append(point)
    out: list[Group] = []
    for (_kind, card), found in held.items():
        group = Group(tuple(found), card)
        out.append(group) if group.whole else out.extend(Group((p,), card) for p in found)
    return sorted(out, key=lambda g: (-len(g.ways_in), g.label))


def context(model: Model, meaning: Meaning, facts: dict[str, Any], group: Group) -> dict[str, Any]:
    """Supply the entry points, components, flows, and source paths to the agent."""
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
    """Make the source records for one entry point or entry point group."""
    records = facts.get("components", {})

    def one(p: dict[str, str]) -> dict[str, Any]:
        return {
            "named": entry_label(p),
            "identity": entry_identity(p),
            "kind": p["kind"],
            "module": p["module"],
            "file": records.get(p["module"], {}).get("file", ""),
            "function": p.get("target") or p.get("name", ""),
        }

    if not group.whole:
        return one(group.one)
    return {
        "a_group": group.label,
        "kind": group.one["kind"],
        "into_card": group.card,
        "how_many": len(group.ways_in),
        "each": [one(p) for p in group.ways_in[:SHOWN]],
    }


def _steps(raw: Any, model: Model, problems: list[str]) -> tuple[Step, ...]:
    cards = {c.id for c in model.components}
    flows = {f.edge for f in model.flows}
    out: list[Step] = []
    if not isinstance(raw, list):
        problems.append("steps must be a list")
        return ()
    for k, step in enumerate(raw, start=1):
        if not isinstance(step, dict):
            problems.append(f"step {k} must be an object")
            continue
        if (
            not all(
                isinstance(step.get(key), list)
                and all(isinstance(value, str) for value in step[key])
                for key in ("edge", "acts", "measures")
            )
            or not isinstance(step.get("say"), str)
            or not step["say"].strip()
        ):
            problems.append(f"step {k} needs lists of component identifiers and a sentence")
            continue
        edge = tuple(step["edge"])
        acts = tuple(step["acts"])
        measures = tuple(step["measures"])
        unknown = sorted({*acts, *measures, *edge} - cards)
        if len(edge) != 2 or edge not in flows:
            problems.append(
                f"step {k} traces {' -> '.join(edge) or 'nothing'}, which is not a flow"
            )
        elif unknown:
            problems.append(f"step {k} has unknown component identifiers: {', '.join(unknown)}")
        else:
            out.append(Step(acts=acts, measures=measures, edge=edge, say=step["say"]))
    return tuple(out)


def read_answer(text: str, model: Model, group: Group) -> Draft:
    """Parse the draft sequence or give the reasons for refusal."""
    entry = group.one
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return Draft(entry=entry, problems=("the agent did not answer with JSON",), answer=text)
    try:
        raw = json.loads(text[start : end + 1])
    except ValueError as exc:
        return Draft(
            entry=entry, problems=(f"the agent's JSON could not be read: {exc}",), answer=text
        )
    if not isinstance(raw, dict):
        return Draft(entry=entry, problems=("the agent's JSON must be an object",), answer=text)
    problems: list[str] = []
    steps = _steps(raw.get("steps"), model, problems)
    if not steps:
        problems.append("no sequence step could be used")
    if problems:
        return Draft(entry=entry, problems=tuple(problems), answer=text)
    journey = Journey(
        id=str(raw.get("id") or entry["name"]).strip(),
        label=str(raw.get("label") or group.label).strip(),
        steps=steps,
        starts=group.starts,
        covers=tuple(entry_identity(point) for point in group.ways_in),
        drafted=True,
    )
    return Draft(entry=entry, journey=journey, answer=text)


def write_one(
    agent: Agent, model: Model, meaning: Meaning, facts: dict[str, Any], group: Group
) -> Draft:
    """Ask the agent for one sequence and validate the returned steps."""
    question = GROUP_QUESTION if group.whole else QUESTION
    supplied = context(model, meaning, facts, group)
    supplied["source_snapshot"] = _source_snapshot(agent.root, facts)
    answer = agent.ask(question, supplied)
    return read_answer(answer, model, group)


def _source_snapshot(root: Path, facts: dict[str, Any]) -> str:
    """Hash current source bytes for the sequence answer cache."""
    digest = hashlib.sha256()
    for relative in sorted({record["file"] for record in facts.get("components", {}).values()}):
        path = root / relative
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ValueError(
                f"cannot examine sequence: source {relative} is unavailable: {exc}"
            ) from exc
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def add_to_source(source: str, journey: Journey) -> str | None:
    """Insert one sequence into the model source.

    Return None if the sequence assignment cannot be found."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return None
    lines = source.splitlines(keepends=True)
    for name in ("JOURNEYS", "journeys"):
        offset = _journey_assignment_offset(tokens, lines, name)
        if offset is not None:
            return _insert_journey(source, journey, offset)
    return None


def _journey_assignment_offset(
    tokens: list[tokenize.TokenInfo], lines: list[str], name: str
) -> int | None:
    for index, token in enumerate(tokens[:-2]):
        if token.type != tokenize.NAME or token.string != name:
            continue
        if [tokens[index + offset].string for offset in (1, 2)] != ["=", "("]:
            continue
        opened = tokens[index + 2]
        return sum(len(line) for line in lines[: opened.end[0] - 1]) + opened.end[1]
    return None


def _insert_journey(source: str, journey: Journey, offset: int) -> str | None:
    block = "\n".join(as_source(journey))
    at = offset + 1 if source[offset : offset + 1] == "\n" else offset
    prefix = "" if at > offset else "\n"
    proposed = source[:at] + prefix + block + "\n" + source[at:]
    try:
        ast.parse(proposed)
    except SyntaxError:
        return None
    return proposed


def as_source(journey: Journey) -> list[str]:
    """Serialize one sequence as model source lines."""
    out = [
        "    Journey(",
        f"        id={json.dumps(journey.id, ensure_ascii=False)},",
        f"        label={json.dumps(journey.label, ensure_ascii=False)},",
        f"        starts={json.dumps(journey.starts, ensure_ascii=False)},",
        f"        covers={journey.covers!r},",
        "        drafted=True,  # examine each step against source before removal",
        "        steps=(",
    ]
    for step in journey.steps:
        acts = ", ".join(json.dumps(c, ensure_ascii=False) for c in step.acts)
        measures = ", ".join(json.dumps(c, ensure_ascii=False) for c in step.measures)
        out += [
            "            Step(",
            f"                acts=({acts}{',' if len(step.acts) == 1 else ''}),",
            f"                measures=({measures}{',' if len(step.measures) == 1 else ''}),",
            f"                edge=({json.dumps(step.edge[0], ensure_ascii=False)}, "
            f"{json.dumps(step.edge[1], ensure_ascii=False)}),",
            f"                say={json.dumps(step.say, ensure_ascii=False)},",
            "            ),",
        ]
    out += ["        ),", "    ),"]
    return out
