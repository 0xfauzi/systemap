"""The nested parts of a map: the file names of each nested map and of the part plan.

All model files of a tree are in the folder of the top model, because a model file can
import a different file only from its own folder. The stem of a nested map is its map ID
in lower case, with `_` in place of each `/`. The file name is the stem with `.py`. A
`map=` value is relative to the model file of the parent map, which is in the same
folder. Thus the file name is also the `map=` value.

For example, the map `Gateway/Routes` has the file name `gateway_routes.py`.

The part plan and the result files are in the folder `parts` beside the top model. Git
tracks this folder, so that the plan and the result files are in each worktree branch.
The plan of the top map is `parts/plan.json`. The plan of the nested parts in the map
`Gateway` is `parts/gateway_plan.json`. The result file of the map `Gateway` is
`parts/gateway.json`.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

SUFFIX = ".py"
# The folder of the part plans and of the result files, beside the top model file.
FOLDER = "parts"
PLAN = "plan.json"
# The stems that a nested map cannot have: the default model file, the contract file of
# the default model file, and the plan of the top map.
RESERVED = ("model", "contract", "plan")
# The stem endings that a nested map cannot have: a contract file adds `_contract`
# (`contract.path_for`), and the plan of a nested map adds `_plan`.
RESERVED_ENDS = ("_contract", "_plan")


def map_id(parent: str, card: str) -> str:
    """Give the ID of the map that a component of the parent map opens."""
    return f"{parent}/{card}" if parent else card


def stem(map_id: str) -> str:
    """Give the stem of the model file of a nested map."""
    return map_id.lower().replace("/", "_")


def file_name(map_id: str) -> str:
    """Give the file name of a nested map, which is also its `map=` value."""
    return stem(map_id) + SUFFIX


def folder(top_model: Path) -> Path:
    """Give the folder of the part plans and of the result files."""
    return top_model.parent / FOLDER


def plan_path(top_model: Path, map_id: str) -> Path:
    """Give the file of the part plan for the nested parts of a map. `""` is the top map."""
    name = f"{stem(map_id)}_{PLAN}" if map_id else PLAN
    return folder(top_model) / name


def result_path(top_model: Path, map_id: str) -> Path:
    """Give the result file of a nested part."""
    return folder(top_model) / f"{stem(map_id)}.json"


def stem_problems(map_ids: Iterable[str]) -> list[str]:
    """Give one line for each map ID of one plan that has a stem that is not permitted.

    A stem cannot be reserved, cannot end in a reserved ending, and cannot be the same
    as a different stem of the plan. The prefix `<stem>_` of a nested part cannot be the
    start of a different stem of the plan. All comparisons use the lower-case form,
    because a file system can ignore the case of a file name."""
    stems = {map_id: stem(map_id) for map_id in sorted(set(map_ids))}
    out: list[str] = []
    for map_id, own in stems.items():
        out += _reserved(map_id, own)
        out += _overlaps(map_id, own, stems)
    return out


def _reserved(map_id: str, own: str) -> list[str]:
    """Give the lines for a stem that is reserved or that has a reserved ending."""
    out = [f"{map_id}: the stem {own} is reserved for a file of the top map."]
    out = out if own in RESERVED else []
    return out + [
        f"{map_id}: the stem {own} ends in {end}, which is reserved."
        for end in RESERVED_ENDS
        if own.endswith(end)
    ]


def _overlaps(map_id: str, own: str, stems: dict[str, str]) -> list[str]:
    """Give the lines for a stem that is the same as a different stem, or whose prefix
    `<stem>_` is the start of a different stem."""
    out: list[str] = []
    for other, theirs in stems.items():
        if other == map_id:
            continue
        if theirs == own and map_id < other:
            out.append(f"{map_id}: the stem {own} is also the stem of {other}.")
        elif theirs.startswith(own + "_"):
            out.append(
                f"{map_id}: the file prefix {own}_ is the start of the stem {theirs} of {other}."
            )
    return out
