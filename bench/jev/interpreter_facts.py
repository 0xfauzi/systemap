"""Measure issue 136: do the stored module facts change with the Python interpreter?

The script has three modes:

- `repo ROOT`: extract the repository at ROOT with the current interpreter and print the
  `components` section of the facts as JSON.
- `files LIST`: parse each source file of LIST (one path on each line) with
  `extract.parse_surface` and print one JSON line for each file that parses. The line has
  the `api`, `constants`, `functions`, `classes`, `errors` and `types` facts.
- `segments LIST`: for each constants preview of each file of LIST, compare the preview
  of `ast.unparse` with a preview from the source text (`ast.get_source_segment`). Print
  the number of previews and the number that the source text changes.
- `compare A B`: compare two outputs of the same mode. Print the number of modules or
  files that differ, for each fact, and the total number of stored values that differ.

Acceptance values, written before the run on 2026-11-03:

1. With the change, the extraction of a copy of this repository at the 3.0.0 release
   (main, 231993f) gives the same `components` section on 3.11, 3.12.3, 3.12.13 and
   3.13: 0 modules differ.
2. On 3.11, the change gives the `components` section of main for that copy: 0 stored
   values change for a user on 3.11. If the change of the `constants` previews cannot
   meet this value, the run reports a failure and the number of changed values.
3. For the files of the 3.12.13 standard library (without `test/`, `lib2to3/` and
   `site-packages/`) that each of the four interpreters parses, the change gives the
   same facts on the four interpreters: 0 files differ. On 3.11, 0 files differ from the
   facts of main.
4. `segments` has no acceptance value. Its count decides the change of the previews: a
   preview from the source text does not depend on the interpreter, but acceptance 2
   requires 0 changed values on 3.11. Thus if the source text changes more than 0
   previews on 3.11, the change keeps `ast.unparse` and corrects the interpreters on
   which it differs.

Measure main first, then the change. Run from the repository root:

    uv run --isolated --python 3.12.3 python bench/jev/interpreter_facts.py repo COPY > a.json
    uv run --isolated --python 3.13 python bench/jev/interpreter_facts.py compare a.json b.json
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

from systemap import config, extract, extraction

FIELDS = ("api", "constants", "functions", "classes", "errors", "types")


def repo(root: Path) -> None:
    facts = extraction.build(config.load(root))
    print(json.dumps({"python": sys.version.split()[0], "items": facts["components"]}))


def files(listing: Path) -> None:
    items: dict[str, Any] = {}
    for path in listing.read_text(encoding="utf-8").splitlines():
        if not path.strip():
            continue
        try:
            raw = Path(path).read_text(encoding="utf-8")
            surface = extract.parse_surface(raw)
        except (UnicodeDecodeError, RecursionError, MemoryError):
            continue
        if surface is not None:
            items[path] = {field: surface[field] for field in FIELDS}
    print(json.dumps({"python": sys.version.split()[0], "items": items}))


def _preview_values(tree: ast.Module) -> list[ast.expr]:
    """Give the value of each constants preview of a module, once for each name."""
    values: list[ast.expr] = []
    for node in extract._active_statements(tree.body):
        if not isinstance(node, ast.Assign | ast.AnnAssign) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        values += [
            node.value
            for target in targets
            if isinstance(target, ast.Name) and extract.UPPER_NAME.fullmatch(target.id)
        ]
    return values


def segments(listing: Path) -> None:
    total = changed = 0
    for path in listing.read_text(encoding="utf-8").splitlines():
        try:
            raw = Path(path).read_text(encoding="utf-8")
            tree = ast.parse(raw)
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError, RecursionError):
            continue
        for value in _preview_values(tree):
            total += 1
            text = ast.get_source_segment(raw, value) or ""
            changed += text[:80] != ast.unparse(value)[:80]
    print(f"{sys.version.split()[0]}: {total} previews, {changed} change with the source text")


def _values(record: dict[str, Any], field: str) -> list[str]:
    return [json.dumps(value, sort_keys=True) for value in record.get(field, [])]


def _differences(name: str, a: dict[str, Any], b: dict[str, Any]) -> list[tuple[str, int, str]]:
    """Give the field, the number of changed values and one example for each changed fact."""
    out: list[tuple[str, int, str]] = []
    for field in FIELDS:
        va, vb = _values(a, field), _values(b, field)
        if va == vb:
            continue
        pairs = [(x, y) for x, y in zip(va, vb, strict=False) if x != y]
        x, y = pairs[0] if pairs else ("", "")
        example = f"{name} {field}:\n  {x[:160]}\n  {y[:160]}"
        out.append((field, len(pairs) + abs(len(va) - len(vb)), example))
    return out


def compare(left_path: Path, right_path: Path) -> None:
    left = json.loads(left_path.read_text(encoding="utf-8"))
    right = json.loads(right_path.read_text(encoding="utf-8"))
    shared = sorted(set(left["items"]) & set(right["items"]))
    per_field: dict[str, int] = {}
    changed_values = 0
    differ: set[str] = set()
    examples: list[str] = []
    for name in shared:
        for field, changed, example in _differences(
            name, left["items"][name], right["items"][name]
        ):
            per_field[field] = per_field.get(field, 0) + 1
            differ.add(name)
            changed_values += changed
            examples += [example] if len(examples) < 6 else []
    other = sorted(set(left["items"]) ^ set(right["items"]))
    print(f"{left['python']} against {right['python']}: {len(shared)} shared items")
    print(f"items that differ: {len(differ)}; stored values that differ: {changed_values}")
    print(f"items in one output only: {len(other)}")
    for field, count in sorted(per_field.items()):
        print(f"  {field}: {count} items")
    for example in examples:
        print(example)


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    if mode == "repo":
        repo(Path(args[0]))
    elif mode == "files":
        files(Path(args[0]))
    elif mode == "segments":
        segments(Path(args[0]))
    elif mode == "compare":
        compare(Path(args[0]), Path(args[1]))
    else:
        raise SystemExit(f"unknown mode: {mode}")
