"""The result file of a nested part, and its examination against the part plan.

A part agent writes its verdicts, answers, boundary requests, and questions in the result
file `parts/<stem>.json`. The agent of the parent map examines each result file before
it submits the verdicts:

- The map and the two digests must be the same as in the plan.
- Each file in `files` must be in the write set of the part: its model file, its
  contract file, the model files with its file prefix, and its result file. The write set
  of a part with nested parts also has the plan and the result files of these nested
  parts: the JSON files with the prefix `<stem>_` in the folder of the result file. A
  name must be a relative path without `.` or `..` and without a different folder after
  the prefix.
- An answer under `answers` must have the form `item` or `items`. The other answer
  forms apply across maps. A part agent can propose one under `proposed_answers`. Only
  the agent of the parent map records it.
- Each boundary request must have one of the request kinds.
"""

from __future__ import annotations

import json
import posixpath
from typing import Any

from systemap import file_write, parts
from systemap.config import Config

FORMS = ("item", "items")
REQUEST_KINDS = ("move_module", "add_flow", "remove_flow", "artifact")
LISTS = (
    "files",
    "open_lines",
    "verdicts",
    "answers",
    "proposed_answers",
    "boundary_requests",
    "questions",
)
TEXTS = ("map", "base_commit", "facts_digest", "contract_digest")


def _in_write_set(name: str, part: dict[str, Any]) -> bool:
    if posixpath.isabs(name) or posixpath.normpath(name) != name:
        return False
    fixed = (part["model_file"], part["contract_file"], part["result_file"])
    nested = posixpath.join(posixpath.dirname(part["result_file"]), part["stem"] + "_")
    return name in fixed or any(
        name.startswith(prefix) and "/" not in name[len(prefix) :] and name.endswith(suffix)
        for prefix, suffix in ((part["file_prefix"], parts.SUFFIX), (nested, ".json"))
    )


def _shape(data: dict[str, Any]) -> list[str]:
    """Give the problems of the keys and of the value types."""
    out = [f"the key {key} is missing" for key in (*TEXTS, *LISTS) if key not in data]
    out += [
        f"the value of {key} is not a text"
        for key in TEXTS
        if key in data and not isinstance(data[key], str)
    ]
    out += [
        f"the value of {key} is not a list"
        for key in LISTS
        if key in data and not isinstance(data[key], list)
    ]
    if "check_exit" not in data or not isinstance(data["check_exit"], int):
        out.append("the value of check_exit is missing or is not a number")
    return out


def _answers(data: dict[str, Any]) -> list[str]:
    """Refuse an answer form that applies across maps."""
    out = []
    for row in data.get("answers") or []:
        form = row.get("form") if isinstance(row, dict) else None
        if form not in FORMS:
            line = row.get("line", "") if isinstance(row, dict) else ""
            out.append(
                f"the answer for {line or 'a line'} has the form {form}. A part agent records "
                "answers only in the forms item and items. Put the answer under "
                "proposed_answers."
            )
    return out


def _requests(data: dict[str, Any]) -> list[str]:
    kinds = ", ".join(REQUEST_KINDS)
    return [
        f"a boundary request has the kind {row.get('kind') if isinstance(row, dict) else None}. "
        f"The request kinds are {kinds}."
        for row in data.get("boundary_requests") or []
        if not isinstance(row, dict) or row.get("kind") not in REQUEST_KINDS
    ]


def problems(data: Any, plan: dict[str, Any], part: dict[str, Any]) -> list[str]:
    """Give the problems of a result file against the plan and the record of its part."""
    if not isinstance(data, dict):
        return ["the result file does not contain a JSON object"]
    out = _shape(data)
    if out:
        return out
    if data["map"] != part["map"]:
        out.append(f"the result file is for the map {data['map']}, not for {part['map']}")
    for key in ("facts_digest", "contract_digest"):
        if data[key] != plan[key]:
            out.append(f"the {key} is not the {key} of the plan. Send the part back.")
    out += [
        f"the file {name} is not in the write set of the part"
        for name in data["files"]
        if not isinstance(name, str) or not _in_write_set(name, part)
    ]
    return out + _answers(data) + _requests(data)


def read(cfg: Config, part: dict[str, Any]) -> Any:
    """Read the result file of a part. A missing file gives None.

    A file that is not JSON gives ValueError."""
    stored = file_write.read_text(cfg.root, cfg.root / part["result_file"])
    return None if stored is None else json.loads(stored)


def examine(cfg: Config, plan: dict[str, Any]) -> dict[str, list[str]]:
    """Give the problems of the result file of each part of the plan, in plan order."""
    by_map = {r["map"]: r for r in plan["parts"]}
    out: dict[str, list[str]] = {}
    for map_id in plan["order"]:
        part = by_map[map_id]
        try:
            data = read(cfg, part)
        except ValueError as exc:
            out[map_id] = [f"the result file {part['result_file']} is not JSON: {exc}"]
            continue
        if data is None:
            out[map_id] = [f"the result file {part['result_file']} is missing"]
        else:
            out[map_id] = problems(data, plan, part)
    return out
