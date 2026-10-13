"""The review command records the current review digest of one component or one flow.

A person or an agent examines the source and all the claims of the target first. The
command does not examine claims. It calculates the digest from the current source and
the current claims, and it writes that digest into the model file:

- `systemap review ID` writes `source_review` of the component ID.
- `systemap review --flow 'SRC->DST'` writes `review_digest` of that flow.

One call writes one target. The command has no option for all targets, because a person or an agent
must examine each claim separately. The command writes the value as literal data into the file
that defines the target, and it keeps all other text of that file. It writes the file only
if the reader that runs no code gives the same model with only the new value.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap import (
    card_review,
    config,
    evidence,
    extraction,
    model_edit,
    model_load,
    model_write,
    nest,
)
from systemap.config import ArgumentError, ConfigError
from systemap.model import Edge, Meaning, Model

ARROW = "->"
NOT_DATA = (
    "systemap review writes only into a model file that systemap reads as data. "
    "Use systemap convert. Then use systemap review again."
)


class ReviewError(Exception):
    """The command cannot write the review digest. The message gives the cause."""


@dataclass(frozen=True)
class Target:
    """One review target: a component ID, or the source and the target of a flow."""

    component: str = ""
    edge: Edge | None = None

    @property
    def cls(self) -> str:
        return "Flow" if self.edge else "Component"

    @property
    def key(self) -> str:
        return "review_digest" if self.edge else "source_review"

    @property
    def label(self) -> str:
        return (
            f"flow {self.edge[0]}{ARROW}{self.edge[1]}"
            if self.edge
            else (f"component {self.component}")
        )

    def defined_by(self, call: ast.Call) -> bool:
        """Find if a model class call in the source defines this target."""
        if self.edge:
            ends = (model_edit.literal(call, 0, "src"), model_edit.literal(call, 1, "dst"))
            return ends == self.edge
        return model_edit.literal(call, 0, "id") == self.component


def flow_target(text: str) -> Target:
    """Read the value of --flow. The form is SRC->DST.

    A value without -> is kept for a flow identifier in a subsequent version.
    """
    src, arrow, dst = text.partition(ARROW)
    src, dst = src.strip(), dst.strip()
    if not arrow or not src or not dst:
        raise ArgumentError(
            f"--flow {text}: give the flow as SRC->DST, for example --flow 'Reader->Writer'."
        )
    return Target(edge=(src, dst))


def review(
    cfg: config.Config,
    map_id: str,
    target: Target,
    dry_run: bool,
    facts: dict[str, Any] | None = None,
) -> list[str]:
    """Write the current digest of one target. Give the lines for the person.

    Without `facts`, the command extracts the facts from the source in the working tree.
    """
    m = _map(cfg, map_id)
    model, meaning = _data(m)
    facts = facts if facts is not None else extraction.build(cfg)
    digest = _digest(m, model, meaning, facts, target)
    path, source, call = _definition(m, target)
    rel = cfg.rel(path)
    lines = [f"review: {m.prefix}{target.label}: {target.key} = {digest}"]
    expected = _with_value(model, target, digest)
    lines += _stale_ends(model, expected, meaning, facts, target)
    if model == expected:
        return [*lines, f"The value in {rel} is the current digest. The command wrote nothing."]
    text = model_edit.set_keyword(source, call, target.key, digest)
    _same(m, path, text, expected, meaning)
    if dry_run:
        return [*lines, f"--dry-run: the command did not write {rel}."]
    model_write.write_models({path: text})
    return [*lines, f"The command wrote {rel}."]


def _map(cfg: config.Config, map_id: str) -> nest.Map:
    try:
        tree = nest.load(cfg)
    except ConfigError as exc:
        if isinstance(exc.__cause__, model_load.ModelFileError):
            raise ReviewError(f"{exc}\n{NOT_DATA}") from exc
        raise
    if not tree.has(map_id):
        raise nest.unknown_map(tree, map_id, ArgumentError)
    return tree.get(map_id)


def _data(m: nest.Map) -> tuple[Model, Meaning]:
    """Read the model with the reader that runs no code, also with permission for code."""
    try:
        names = model_load.read(m.path, m.rel)
    except model_load.ModelFileError as exc:
        raise ReviewError(f"{exc}\n{NOT_DATA}") from exc
    model, meaning = names.get("MODEL"), names.get("MEANING")
    if not isinstance(model, Model) or not isinstance(meaning, Meaning):
        raise ReviewError(f"{m.rel}: the data does not give MODEL and MEANING. {NOT_DATA}")
    return model, meaning


def _digest(
    m: nest.Map, model: Model, meaning: Meaning, facts: dict[str, Any], target: Target
) -> str:
    if target.edge:
        return _flow_digest(m, model, meaning, facts, target.edge)
    card = next((c for c in model.components if c.id == target.component), None)
    if card is None:
        raise ReviewError(f"{m.rel}: the map has no component {target.component}.")
    digest = card_review.digest(card, model, meaning, facts)
    if digest is None:
        raise ReviewError(
            f"{m.prefix}component {card.id} has no current digest. The component claims no "
            "module, a claimed module is missing, or the parser cannot read it. Correct "
            "implemented_by or the source. Then examine the claims again."
        )
    return digest


def _flow_digest(
    m: nest.Map, model: Model, meaning: Meaning, facts: dict[str, Any], edge: Edge
) -> str:
    flow = next((f for f in model.flows if f.edge == edge), None)
    name = f"{edge[0]}{ARROW}{edge[1]}"
    if flow is None:
        raise ReviewError(f"{m.rel}: the map has no flow {name}.")
    if not flow.source_refs:
        raise ReviewError(
            f"{m.prefix}flow {name} has no source_refs. Record the source records that you "
            "examined. Then use systemap review again."
        )
    unresolved = evidence.of_model(model, meaning, facts)[edge].unresolved_refs
    if unresolved:
        raise ReviewError(
            f"{m.prefix}flow {name} has source records that do not agree with the current "
            f"source: {', '.join(unresolved)}. Examine the source. Then correct source_refs."
        )
    return evidence.flow_claim_digest(flow, meaning)


def _definition(m: nest.Map, target: Target) -> tuple[Path, str, ast.Call]:
    """Find the one literal call that defines the target in the model files of the map."""
    found: list[tuple[Path, str, ast.Call]] = []
    for path in model_load.files(m.path, m.rel):
        source = path.read_bytes().decode("utf-8-sig")
        tree = ast.parse(source, str(path))
        found += [
            (path, source, call)
            for call in model_edit.calls(tree, target.cls)
            if target.defined_by(call)
        ]
    if len(found) != 1:
        where = ", ".join(sorted({path.name for path, _source, _call in found}))
        raise ReviewError(
            f"{m.rel}: the command found {len(found)} literal {target.cls} calls for "
            f"{target.label}{f' in {where}' if where else ''}. It must find one. Write the "
            f"target as one {target.cls} call with literal values."
        )
    return found[0]


def _with_value(model: Model, target: Target, digest: str) -> Model:
    if target.edge:
        flows = tuple(
            dataclasses.replace(f, review_digest=digest) if f.edge == target.edge else f
            for f in model.flows
        )
        return dataclasses.replace(model, flows=flows)
    cards = tuple(
        dataclasses.replace(c, source_review=digest) if c.id == target.component else c
        for c in model.components
    )
    return dataclasses.replace(model, components=cards)


def _stale_ends(
    model: Model, new: Model, meaning: Meaning, facts: dict[str, Any], target: Target
) -> list[str]:
    """Tell which endpoint reviews become stale. Their claims include the flow digest."""
    if not target.edge:
        return []
    out = []
    for before, after in zip(model.components, new.components, strict=True):
        if before.id not in target.edge:
            continue
        old = card_review.state(before, model, meaning, facts)
        if old == card_review.CURRENT and card_review.state(after, new, meaning, facts) != old:
            out.append(
                f"review: the source review of component {before.id} becomes stale, because "
                f"its claims include this flow. Examine {before.id} again. Then use "
                f"systemap review {before.id}."
            )
    return out


def _same(m: nest.Map, path: Path, text: str, model: Model, meaning: Meaning) -> None:
    """Read the new text with the reader that runs no code, in a copy of the model files."""
    with tempfile.TemporaryDirectory(prefix="systemap-review-") as folder:
        copy = Path(folder)
        for each in model_load.files(m.path, m.rel):
            shutil.copyfile(each, copy / each.name)
        (copy / path.name).write_text(text, encoding="utf-8", newline="")
        try:
            names = model_load.read(copy / m.path.name, m.rel)
        except model_load.ModelFileError as exc:
            raise ReviewError(f"{exc}\nThe command wrote no file.") from exc
    if names.get("MODEL") != model or names.get("MEANING") != meaning:
        raise ReviewError(
            f"{m.rel}: the new text does not give the same model with only the new value. "
            "The command wrote no file."
        )


def cmd_review(args: argparse.Namespace) -> int:
    from systemap.cli import _root, say

    target = flow_target(args.flow) if args.flow is not None else Target(args.component)
    say(*review(config.load(_root(args)), args.map, target, bool(args.dry_run)))
    return 0


def add_parsers(sub: Any, add_root: Callable[[argparse.ArgumentParser], None]) -> None:
    s = sub.add_parser(
        "review",
        help="Record the current review digest of one component or one flow.",
        description=(
            "Examine the source and all the claims of the target first. This command does "
            "not examine claims. It writes the current digest of one target into the model "
            "file that defines the target. A component gets source_review. A flow gets "
            "review_digest. The command has no option for all targets, because a person or "
            "an agent must examine each claim separately."
        ),
    )
    add_root(s)
    target = s.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "component",
        nargs="?",
        default=None,
        metavar="COMPONENT",
        help="Give the ID of the component that you examined.",
    )
    target.add_argument(
        "--flow",
        default=None,
        metavar="SRC->DST",
        help=(
            "Give the flow that you examined. Put the value between quotation marks, "
            "because the shell reads > as a redirection: --flow 'Reader->Writer'."
        ),
    )
    s.add_argument(
        "--map",
        default="",
        metavar="ID",
        help="Select a nested map by component ID. The default is the top map.",
    )
    s.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the digest and the file. Do not write the file.",
    )
    s.set_defaults(func=cmd_review)
