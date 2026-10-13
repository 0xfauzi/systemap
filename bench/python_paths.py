"""Measure the Python file list with a large node_modules directory.

Acceptance value, written before the change: for each measured call, the median time
with 40,000 files in node_modules must be at most 1.2 times the median time of the same
fixture without node_modules.

The fixtures:

- `package`: the package root `src/app` has 40 modules and a node_modules directory.
  Half of the files in node_modules are `.py` files and half are `.js` files.
- `no_source`: the folder has no Python file outside node_modules. Thus a walk that
  enters node_modules reads all of it before it gives its result.

The measured calls:

- `list(python_paths(package/src/app))`
- `PYTHON_REPOSITORY.detect(package, [package/src/app])`
- `PYTHON_REPOSITORY.detect(no_source, [no_source])`

The script makes the fixtures in a temporary directory and removes them.

    uv run python bench/python_paths.py
"""

from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from systemap.python_repo import PYTHON_REPOSITORY, python_paths

MODULES = 40
PACKAGE_FILES = 40_000
RUNS = 11
LIMIT = 1.2
# The minimum time of one sample.
SAMPLE_SECONDS = 0.02


def _packages(folder: Path) -> None:
    for index in range(PACKAGE_FILES):
        lib = folder / "node_modules" / f"pkg{index // 100}" / "lib"
        lib.mkdir(parents=True, exist_ok=True)
        suffix = ".py" if index % 2 else ".js"
        (lib / f"f{index % 100}{suffix}").write_text("x = 1\n", encoding="utf-8")


def _package(root: Path, with_packages: bool) -> Path:
    app = root / "src" / "app"
    app.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    for index in range(MODULES):
        (app / f"m{index}.py").write_text(f"V{index} = {index}\n", encoding="utf-8")
    if with_packages:
        _packages(app)
    return app


def _no_source(root: Path, with_packages: bool) -> Path:
    root.mkdir()
    (root / "README.md").write_text("text\n", encoding="utf-8")
    if with_packages:
        _packages(root)
    return root


def _sample(action: Callable[[], object]) -> float:
    """Give the mean time of one call in a loop of at least SAMPLE_SECONDS.

    A call without node_modules takes some microseconds. One call is then too short for
    the clock and the other work of the computer."""
    calls = 0
    started = time.perf_counter()
    while True:
        action()
        calls += 1
        elapsed = time.perf_counter() - started
        if elapsed >= SAMPLE_SECONDS:
            return elapsed / calls


def _median(action: Callable[[], object]) -> float:
    return statistics.median(_sample(action) for _ in range(RUNS))


def _measure(base: Path, with_packages: bool) -> dict[str, dict[str, float | object]]:
    package = base / "package"
    app = _package(package, with_packages)
    empty = _no_source(base / "no_source", with_packages)
    calls: dict[str, Callable[[], object]] = {
        "python_paths_package": lambda: sorted(p.relative_to(app) for p in python_paths(app)),
        "detect_package_folder": lambda: PYTHON_REPOSITORY.detect(package, [app]),
        "detect_no_source_folder": lambda: PYTHON_REPOSITORY.detect(empty, [empty]),
    }
    return {name: {"seconds": _median(call), "result": call()} for name, call in calls.items()}


def _seconds(record: dict[str, float | object]) -> float:
    value = record["seconds"]
    assert isinstance(value, float)
    return value


def main() -> int:
    with tempfile.TemporaryDirectory() as small, tempfile.TemporaryDirectory() as large:
        without = _measure(Path(small), with_packages=False)
        with_packages = _measure(Path(large), with_packages=True)
    # The ratio uses the times before they are rounded. A call without node_modules
    # takes some microseconds, so a rounded time has too few digits.
    ratios = {
        name: round(_seconds(with_packages[name]) / _seconds(without[name]), 3) for name in without
    }
    # The file lists are compared in full. The output gives only their lengths.
    same = all(without[name]["result"] == with_packages[name]["result"] for name in without)
    for record in (*without.values(), *with_packages.values()):
        record["seconds"] = round(_seconds(record), 7)
        found = record["result"]
        record["result"] = len(found) if isinstance(found, list) else found
    accepted = all(ratio <= LIMIT for ratio in ratios.values())
    result = {
        "node_modules_files": PACKAGE_FILES,
        "runs": RUNS,
        "without_node_modules": without,
        "with_node_modules": with_packages,
        "ratios": ratios,
        "same_results": same,
        "acceptance": f"each ratio <= {LIMIT}",
        "accepted": accepted and same,
    }
    sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
    return 0 if accepted and same else 1


if __name__ == "__main__":
    raise SystemExit(main())
