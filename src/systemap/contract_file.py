"""The contract reader gives the rules of a map from its contract file and its model file.

In the 2.x releases, a map can give its rules in the contract file or in the model file.
The model file of an earlier map gives them, until `systemap refresh` or `systemap
extract` moves them one time (`contract_move`). If the two files give rules, the reader
refuses the map, because the two files do not tell which rules apply.

The reader reads the contract file with the reader of the model file (`model_load`). Thus
it runs no code from the file without SYSTEMAP_TRUST_MODEL_CODE=1. A missing contract
file gives no rules.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from systemap import model_fields, model_load
from systemap.contract import NAME, Contract, has_rules, path_for
from systemap.model import Model

Loader = Callable[[Path, str], dict[str, Any]]


def label_for(model_label: str) -> str:
    """Give the label of the contract file in messages, from the label of the model file."""
    return path_for(Path(model_label.replace("\\", "/"))).as_posix()


def read(model_path: Path, model_label: str, load: Loader = model_load.load) -> Contract | None:
    """Give the contract in the folder of the model file, or None without a contract file.

    A contract file that does not give a CONTRACT value of the correct type gives a
    ModelFileError."""
    path = path_for(model_path)
    if not path.exists():
        return None
    label = label_for(model_label)
    if not path.is_file():
        raise model_load.ModelFileError(f"{label}: The contract file is not a regular file.")
    found = load(path, label).get(NAME)
    problem = model_fields.problem(found, Contract, NAME)
    if problem:
        raise model_load.ModelFileError(
            f"{label}: {problem}. Give CONTRACT = Contract(invariants=..., import_rules=...)."
        )
    assert isinstance(found, Contract)
    return found


def merged(model_path: Path, model_label: str, model: Any, load: Loader = model_load.load) -> Any:
    """Give the model with the rules of its contract file.

    A value that is not a Model stays the same: the caller refuses it. If the two files
    give rules, give a ModelFileError that names the two files."""
    if not isinstance(model, Model):
        return model
    found = read(model_path, model_label, load)
    if found is None or not has_rules(found):
        return model
    if has_rules(model):
        label = label_for(model_label)
        raise model_load.ModelFileError(
            f"{model_label} and {label} give invariants or import rules. Only one file "
            f"can give the rules. Put all the invariants and import rules in {label}, and "
            f"remove them from {model_label}."
        )
    return dataclasses.replace(
        model, invariants=tuple(found.invariants), import_rules=tuple(found.import_rules)
    )


def own(model_path: Path, model_label: str, model: Model) -> Model:
    """Give the model without the rules that its contract file gives: the values of the
    model file only."""
    found = read(model_path, model_label)
    if found is None or not has_rules(found):
        return model
    return dataclasses.replace(model, invariants=(), import_rules=())


def files(model_path: Path, model_label: str) -> tuple[Path, ...]:
    """Give the contract file and each file that it imports, or no file.

    The paths are resolved paths. A contract file that the reader refuses gives a
    ModelFileError."""
    path = path_for(model_path)
    if not path.is_file():
        return ()
    return model_load.files(path, label_for(model_label))


def map_files(model_path: Path, model_label: str) -> tuple[Path, ...]:
    """Give the model file, the contract file, and each file that they can import.

    With permission to run the model code, each Python file in the folder can be an
    import. Without this permission, the reader gives the files that the two files import."""
    if os.environ.get(model_load.TRUST) == "1":
        folder = model_path.parent
        return tuple(sorted(p for p in folder.glob(model_load.MODEL_FILES) if p.is_file()))
    found = model_load.files(model_path, model_label) + files(model_path, model_label)
    return tuple(dict.fromkeys(found))
