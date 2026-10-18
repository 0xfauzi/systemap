"""Write model files again with literal values only.

systemap reads a model file without running its code (model_load), and it refuses a model
file that needs code, for example a helper function or a comprehension. This command runs
each refused model file one time, with the permission of the person who runs it
(SYSTEMAP_TRUST_MODEL_CODE=1), and writes the same model with literal values and calls of
the model classes. It writes a file only if the reader that runs no code gives the same
model from the new text.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import os
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from systemap import config, contract_file, model_load, model_write, nest
from systemap.config import ConfigError

WIDTH = 96
NOTE = (
    "systemap convert wrote this file with literal values only. "
    "systemap reads it without running code."
)
HEAD = '''"""{doc}"""

from __future__ import annotations

from systemap import (  # type: ignore[import-not-found, unused-ignore]
{names}
)

'''


class ConvertError(ConfigError):
    """The command cannot write a model file again. The message gives the reason."""


def _fields(value: Any) -> Iterator[tuple[str, Any]]:
    """Give the fields of a model record that differ from their default values."""
    for field in dataclasses.fields(value):
        current = getattr(value, field.name)
        if field.default is not dataclasses.MISSING and current == field.default:
            continue
        if field.default_factory is not dataclasses.MISSING and current == field.default_factory():
            continue
        yield field.name, current


def _join(open_: str, parts: list[str], close: str, indent: int, single: bool = False) -> str:
    """Give the parts on one line if they fit, else one part on each line."""
    tail = "," if single and len(parts) == 1 else ""
    flat = f"{open_}{', '.join(parts)}{tail}{close}"
    if indent + len(flat) <= WIDTH and "\n" not in flat:
        return flat
    pad = " " * (indent + 4)
    body = "".join(f"{pad}{part},\n" for part in parts)
    return f"{open_}\n{body}{' ' * indent}{close}"


def literal(value: Any, indent: int, names: set[str]) -> str:
    """Give the Python text of a model value: literal values and model class calls."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        names.add(type(value).__name__)
        parts = [f"{key}={literal(item, indent + 4, names)}" for key, item in _fields(value)]
        return _join(f"{type(value).__name__}(", parts, ")", indent)
    if isinstance(value, tuple):
        parts = [literal(item, indent + 4, names) for item in value]
        return _join("(", parts, ")", indent, single=True)
    if isinstance(value, list):
        return _join("[", [literal(item, indent + 4, names) for item in value], "]", indent)
    if isinstance(value, dict):
        parts = [
            f"{literal(key, indent + 4, names)}: {literal(item, indent + 4, names)}"
            for key, item in value.items()
        ]
        return _join("{", parts, "}", indent)
    if value is None or isinstance(value, bool | int | float | str):
        return repr(value)
    raise ConvertError(
        f"systemap cannot write a value of type {type(value).__name__} as a literal value."
    )


def source_text(doc: str, model: Any, meaning: Any) -> str:
    """Give the text of a model file with literal values only."""
    names = {"Meaning", "Model"}
    model_text = literal(model, 0, names)
    meaning_text = literal(meaning, 0, names)
    text = f"{doc.strip()}\n\n{NOTE}" if doc.strip() else NOTE
    head = HEAD.format(
        doc=text.replace('"""', '\\"\\"\\"'),
        names="\n".join(f"    {name}," for name in sorted(names)),
    )
    return f"{head}MODEL = {model_text}\n\nMEANING = {meaning_text}\n"


def _same(path: Path, label: str, text: str, model: Any, meaning: Any) -> None:
    """Read the new text with the reader that runs no code and compare the two models."""
    descriptor, name = tempfile.mkstemp(prefix=".convert-", suffix=".py", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(text)
        names = model_load.read(temporary, label, path.parent)
    finally:
        temporary.unlink(missing_ok=True)
    if repr(names.get("MODEL")) != repr(model) or repr(names.get("MEANING")) != repr(meaning):
        raise ConvertError(
            f"{label}: the new text does not give the same model. systemap wrote no file."
        )


def _siblings(path: Path) -> list[str]:
    """Give the files beside a model file that the old model file imported."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    out = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            out += [a.name for a in stmt.names if (path.parent / f"{a.name}.py").is_file()]
    return out


def _refused(m: nest.Map) -> bool:
    try:
        model_load.read(m.path, m.rel, m.root)
    except model_load.ModelFileError:
        return True
    return False


def convert(cfg: config.Config) -> list[str]:
    """Write each refused model file again. Give one line for each map."""
    if os.environ.get(model_load.TRUST) != "1":
        try:
            nest.load(cfg)
        except ConfigError as exc:
            raise ConvertError(
                f"{exc}\nThis command must run each model file one time to write it again. "
                f"If you trust the code in this repository, set {model_load.TRUST}=1. "
                "Then run systemap convert again."
            ) from exc
        return ["All model files have literal values only. There is nothing to write."]
    staged: dict[Path, str] = {}
    lines: list[str] = []
    for m in nest.load(cfg).maps:
        if not _refused(m):
            lines.append(f"{m.rel}: literal values only, not changed")
            continue
        doc = ast.get_docstring(ast.parse(m.path.read_text(encoding="utf-8-sig"))) or ""
        model = contract_file.own(m.path, m.rel, m.model, m.root)
        text = source_text(doc, model, m.meaning)
        _same(m.path, m.rel, text, model, m.meaning)
        staged[m.path] = text
        lines.append(f"{m.rel}: wrote the same model with literal values only")
        lines += [
            f"  {m.rel} does not import {name}.py now. Remove it if nothing else uses it."
            for name in _siblings(m.path)
        ]
    if staged:
        model_write.write_models(staged)
    return lines


def cmd_convert(args: argparse.Namespace) -> int:
    from systemap.cli import _root, say

    say(*convert(config.load(_root(args))))
    return 0


def add_parsers(sub: Any, add_root: Callable[[argparse.ArgumentParser], None]) -> None:
    s = sub.add_parser(
        "convert",
        help="Write the model files again with literal values only.",
        description=(
            "systemap reads a model file without running its code, and it refuses a model "
            "file that needs code. This command runs each refused model file one time. "
            f"So it needs {model_load.TRUST}=1, which you set only if you trust the code in "
            "the repository. Then it writes the same model with literal values only. It "
            "writes a file only if systemap reads the new file to the same model."
        ),
    )
    add_root(s)
    s.set_defaults(func=cmd_convert)
