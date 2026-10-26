"""Write a draft sequence for entry points without a sequence.

The configured agent examines source code from the entry point.
It writes ordered steps under the language policy of the configured writing profile.
systemap refuses steps with absent flows or unknown component identifiers.
It also refuses a step source record that does not resolve, or that is in no module of
an acting or measured component of the step.
Accepted drafts have `drafted=True` until the maintainer examines them against source.

The earlier import-based experiment had overlap 0.28 against acceptance value 0.60.
The CLI module imported components that the actual sequence did not use.
`bench/jev/propose.py` and `bench/jev/paths.py` keep that experiment and its measurements.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import io
import json
import shutil
import tempfile
import tokenize
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap import config, contract_file, file_write, flow_ids, model_load, repo_files, step_refs
from systemap import journey_coverage as judgement
from systemap.agent import Agent, AgentError
from systemap.config import ConfigError
from systemap.evidence import owners
from systemap.model import Journey, Meaning, Model, Step
from systemap.source_facts import entry_identity, entry_label
from systemap.terminal_text import has_control, printable

QUESTION = """Examine the repository and write one sequence for its system map.

A sequence contains the ordered steps that start at an entry point.
Each step shows the components that act and the artifact that moves.
Use the writing profile above for the identifier, label, and step sentences.
Use the project glossary supplied in the language policy.

Read the source code from the entry point below. Write only JSON with this shape:

{"id": "short-id", "label": "short sequence name",
 "steps": [{"edge": ["CardA", "CardB"], "acts": ["CardA"], "measures": [],
            "say": "one sentence from the acting component"}]}

Requirements:
- Keep every edge identical to a listed flow.
- If a listed flow has a fifth value, that value is its id. For that flow, write
  "flow": "ID", not "edge".
- You can add "source_refs": ["module:symbol@sha256"] to a step. Each record must be
  in a module of an acting or measured component, with the current source digest.
- Use only listed component identifiers in acts and measures.
- Use measures for a component that monitors or records the step. Otherwise, use an empty list.
- Write four to eight steps.
- Write one sentence per step about the action and its result.
- Write only steps that the source code supports.
"""

# The refusal of agent text with a character that `terminal_text.printable` replaces.
CONTROL = "contains a control character or a Unicode line separator. Write one line of text"

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
    skip: Collection[str] = (),
) -> list[dict[str, str]]:
    """Return entry points without recorded sequence coverage, outside the `skip` modules."""
    return judgement.ways_in_without_journey(
        meaning, facts, skip=skip, owner=owner, covered=covered
    )


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
            [f.src, f.dst, f.artifact, meaning.relation(f), *([f.id] if f.id else [])]
            for f in model.flows
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


def _steps(
    raw: Any, model: Model, problems: list[str], facts: dict[str, Any] | None = None
) -> tuple[Step, ...]:
    out: list[Step] = []
    if not isinstance(raw, list):
        problems.append("steps must be a list")
        return ()
    for k, step in enumerate(raw, start=1):
        made, problem = _step(step, model, facts)
        if made is None:
            problems.append(f"step {k} {problem}")
        else:
            out.append(made)
    return tuple(out)


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _step(raw: Any, model: Model, facts: dict[str, Any] | None) -> tuple[Step | None, str]:
    """Make one step from the agent answer, or give None and the problem."""
    step = _parsed(raw)
    if step is None:
        return None, "must have lists of component identifiers and a sentence"
    if has_control(step.say):
        return None, f"has the sentence '{printable(step.say)}', which {CONTROL}"
    if len(step.edge) != 2:
        return (
            None,
            f"has an edge with {len(step.edge)} values. An edge has two component identifiers",
        )
    if not step.flow and step.edge not in {f.edge for f in model.flows}:
        return None, f"traces {' -> '.join(step.edge) or 'nothing'}, which is not a flow"
    found, problem = flow_ids.step_flow(step, model.flows)
    if found is None:
        return None, problem
    cards = {c.id: c for c in model.components}
    unknown = sorted({*step.acts, *step.measures, *found.edge} - cards.keys())
    if unknown:
        return None, f"has unknown component identifiers: {', '.join(unknown)}"
    if step.source_refs and facts is None:
        return None, "has source_refs, but no facts are available to examine them"
    members = [cards[c] for c in dict.fromkeys((*step.acts, *step.measures))]
    reasons = step_refs.reasons(step.source_refs, members, facts or {})
    if reasons:
        return None, "; ".join(reasons)
    return dataclasses.replace(step, edge=found.edge), ""


def _parsed(raw: Any) -> Step | None:
    """Read the fields of one step. Give None if a field has an incorrect type."""
    if not isinstance(raw, dict):
        return None
    flow, refs, say = raw.get("flow", ""), raw.get("source_refs", []), raw.get("say")
    lists = all(_strings(raw.get(key)) for key in ("acts", "measures"))
    if not lists or not _strings(raw.get("edge", [])) or not _strings(refs):
        return None
    if not isinstance(flow, str) or not isinstance(say, str) or not say.strip():
        return None
    return Step(
        acts=tuple(raw["acts"]),
        measures=tuple(raw["measures"]),
        edge=tuple(raw.get("edge", [])) or flow_ids.NO_EDGE,
        say=say,
        flow=flow,
        source_refs=tuple(refs),
    )


def read_answer(
    text: str, model: Model, group: Group, facts: dict[str, Any] | None = None
) -> Draft:
    """Parse the draft sequence or give the reasons for refusal.

    The facts are necessary to examine the source records of the steps."""
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
    steps = _steps(raw.get("steps"), model, problems, facts)
    if not steps:
        problems.append("no sequence step could be used")
    ident = str(raw.get("id") or entry["name"]).strip()
    label = str(raw.get("label") or group.label).strip()
    problems += name_problems(ident, label)
    if problems:
        return Draft(entry=entry, problems=tuple(problems), answer=text)
    journey = Journey(
        id=ident,
        label=label,
        steps=steps,
        starts=group.starts,
        covers=tuple(entry_identity(point) for point in group.ways_in),
        drafted=True,
    )
    return Draft(entry=entry, journey=journey, answer=text)


def name_problems(ident: str, label: str) -> list[str]:
    """Refuse an id that is not a slug, and a label with a control character.

    The id and the label go into finding lines, and the id is a part of a finding
    identifier. A terminal can use a control character as a command."""
    problems = []
    if not ident:
        problems.append("the answer has no sequence id. Give a short id, such as read-request")
    elif not flow_ids.ID_FORM.fullmatch(ident):
        problems.append(
            f"the sequence id '{printable(ident)}' is not correct. An id contains only "
            "letters, digits, '_', '.', and '-'. It starts with a letter, a digit, or '_'"
        )
    if has_control(label):
        problems.append(f"the sequence label '{printable(label)}' {CONTROL}")
    return problems


def write_one(
    agent: Agent,
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    group: Group,
    taken: Collection[str] = (),
) -> Draft:
    """Ask the agent for one sequence and validate the returned steps.

    The agent cache keeps only an answer that gives a sequence. `taken` gives the ids of
    the sequences that the command added to this map before."""
    question = GROUP_QUESTION if group.whole else QUESTION
    supplied = context(model, meaning, facts, group)
    supplied["source_snapshot"] = _source_snapshot(agent.root, facts)
    answer = agent.ask(
        question,
        supplied,
        accept=lambda text: read_answer(text, model, group, facts).journey is not None,
    )
    return refuse_used_id(read_answer(answer, model, group, facts), meaning, taken)


def refuse_used_id(draft: Draft, meaning: Meaning, taken: Collection[str] = ()) -> Draft:
    """Refuse a draft with the id of a sequence in the map or of a previous draft.

    The page selects a sequence by its id. Thus each id must identify one sequence."""
    if draft.journey is None:
        return draft
    used = {journey.id for journey in meaning.journeys} | set(taken)
    if draft.journey.id not in used:
        return draft
    problem = (
        f"the map has a sequence with the id {draft.journey.id}. Give each sequence its own id"
    )
    return Draft(entry=draft.entry, problems=(problem,), answer=draft.answer)


def _source_snapshot(root: Path, facts: dict[str, Any]) -> str:
    """Hash current source bytes for the sequence answer cache.

    A source file of the facts that systemap cannot read gives AgentError with the file.
    """
    digest = hashlib.sha256()
    for relative in sorted({record["file"] for record in facts.get("components", {}).values()}):
        try:
            content = repo_files.read_bytes(root, relative)
        except OSError as exc:
            raise AgentError(
                f"the source file {relative} of the facts is not available: "
                f"{repo_files.reason(exc)}. Run systemap extract. Then run the command again."
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


# The model classes that an inserted sequence calls.
SEQUENCE_CLASSES = ("Journey", "Step")


def with_imports(source: str) -> str:
    """Add an import from systemap for each sequence class that no import of the module
    gives. The source must parse.

    The new import comes after the first group of import statements. Thus the names are
    defined before the sequences use them."""
    body = ast.parse(source).body
    given = {
        alias.asname or alias.name.split(".")[0]
        for statement in body
        if isinstance(statement, ast.Import | ast.ImportFrom)
        for alias in statement.names
    }
    missing = [name for name in SEQUENCE_CLASSES if name not in given]
    if not missing or "*" in given:
        return source
    lines = source.splitlines(keepends=True)
    anchor = _first_imports_end(body)
    added = f"from systemap import {', '.join(missing)}\n"
    return "".join([*lines[:anchor], added, *lines[anchor:]])


def _first_imports_end(body: list[ast.stmt]) -> int:
    """Give the last line of the first group of import statements, after the docstring."""
    start = 1 if body and _docstring(body[0]) else 0
    anchor = (body[0].end_lineno or 0) if start else 0
    for statement in body[start:]:
        if not isinstance(statement, ast.Import | ast.ImportFrom):
            break
        anchor = statement.end_lineno or anchor
    return anchor


def _docstring(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def proposal_problem(path: Path, label: str, source: str, ids: Collection[str], root: Path) -> str:
    """Give the problem of a proposed model text, or an empty string.

    The model reader reads a copy of the model files in a temporary folder, with the
    proposed text in place of the file at `path`. The reader is the reader of each other
    command (`config.load_model`). The map files must be in the root. The loaded MEANING
    must contain each sequence id."""
    try:
        found = {journey.id for journey in _proposed_meaning(path, label, source, root).journeys}
    except ConfigError as exc:
        return f"The model reader does not accept the changed model: {exc}"
    missing = [one for one in ids if one not in found]
    if not missing:
        return ""
    return (
        f"{label}: the changed model does not contain the sequence {', '.join(missing)}. "
        "Make sure that MEANING uses the sequence list of the model file."
    )


def _proposed_meaning(path: Path, label: str, source: str, root: Path) -> Meaning:
    with tempfile.TemporaryDirectory(prefix="systemap-journeys-") as folder:
        copy = Path(folder).resolve()
        for each in _model_files(path, label, root):
            shutil.copyfile(each, copy / each.name)
        file_write.write_atomic(copy, copy / path.name, source)
        return config.load_model(copy / path.name, label, copy)[1]


def _model_files(path: Path, label: str, root: Path) -> tuple[Path, ...]:
    """Give the model file, the contract file, and the files that they can import
    (`contract_file.map_files`)."""
    try:
        return contract_file.map_files(path, label, root)
    except model_load.ModelFileError as exc:
        raise ConfigError(str(exc)) from exc


def _journey_assignment_offset(
    tokens: list[tokenize.TokenInfo], lines: list[str], name: str
) -> int | None:
    for index, token in enumerate(tokens[:-2]):
        if token.type != tokenize.NAME or token.string != name:
            continue
        at = _after_annotation(tokens, index + 1)
        if [t.string for t in tokens[at : at + 2]] != ["=", "("]:
            continue
        opened = tokens[at + 1]
        return sum(len(line) for line in lines[: opened.end[0] - 1]) + opened.end[1]
    return None


# The change in bracket depth for each bracket token.
_BRACKETS = {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}


def _after_annotation(tokens: list[tokenize.TokenInfo], index: int) -> int:
    """Give the index of the `=` after a `: annotation` part, or `index` without one.

    The annotation ends at the first `=` outside brackets on the same logical line."""
    if tokens[index].string != ":":
        return index
    depth = 0
    for at in range(index + 1, len(tokens)):
        token = tokens[at]
        if token.type == tokenize.NEWLINE or (depth == 0 and token.string == "="):
            return at
        depth += _BRACKETS.get(token.string, 0) if token.type == tokenize.OP else 0
    return index


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
        "        drafted=True,  # before you remove this line, compare each step with the source",
        "        steps=(",
    ]
    for step in journey.steps:
        acts = ", ".join(json.dumps(c, ensure_ascii=False) for c in step.acts)
        measures = ", ".join(json.dumps(c, ensure_ascii=False) for c in step.measures)
        out += [
            "            Step(",
            f"                acts=({acts}{',' if len(step.acts) == 1 else ''}),",
            f"                measures=({measures}{',' if len(step.measures) == 1 else ''}),",
            _step_flow_line(step),
            f"                say={json.dumps(step.say, ensure_ascii=False)},",
        ]
        if step.source_refs:
            refs = ", ".join(json.dumps(ref, ensure_ascii=False) for ref in step.source_refs)
            out.append(f"                source_refs=({refs},),")
        out.append("            ),")
    out += ["        ),", "    ),"]
    return out


def _step_flow_line(step: Step) -> str:
    """Give the source line that names the flow of a step: its id, or else its edge."""
    if step.flow:
        return f"                flow={json.dumps(step.flow, ensure_ascii=False)},"
    return (
        f"                edge=({json.dumps(step.edge[0], ensure_ascii=False)}, "
        f"{json.dumps(step.edge[1], ensure_ascii=False)}),"
    )
