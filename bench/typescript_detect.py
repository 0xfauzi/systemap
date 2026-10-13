"""Measure TypeScript language detection with a large node_modules directory.

Acceptance value, written before the change: for each measured call, the median time
with 40,000 files in node_modules must be at most 1.2 times the median time of the same
fixture without node_modules.

The fixtures:

- `config_only`: the repository root has tsconfig.json and package.json. No TypeScript
  source is outside node_modules. The node_modules directory is at the root. Thus a
  walk that enters node_modules reads all of it before it gives its result.
- `workspace`: the package root `packages/web` has 40 modules in `src` and a
  node_modules directory.

The measured calls:

- `discover_typescript_roots(config_only)`
- `TYPESCRIPT_REPOSITORY.detect(config_only)`, without folders
- `TYPESCRIPT_REPOSITORY.detect(config_only, [config_only])`
- `TYPESCRIPT_REPOSITORY.detect(workspace, [workspace/packages/web])`

The script makes the fixtures in a temporary directory and removes them.

    uv run python bench/typescript_detect.py
"""

from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from systemap.typescript_config import discover_typescript_roots
from systemap.typescript_repo import TYPESCRIPT_REPOSITORY

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
        suffix = ".d.ts" if index % 2 else ".ts"
        (lib / f"f{index % 100}{suffix}").write_text("export const x = 1;\n", encoding="utf-8")


def _config_only(root: Path, with_packages: bool) -> Path:
    root.mkdir()
    (root / "package.json").write_text('{"name":"tool"}', encoding="utf-8")
    (root / "tsconfig.json").write_text('{"include":["lib"]}', encoding="utf-8")
    (root / "lib").mkdir()
    (root / "lib" / "index.js").write_text("export const one = 1;\n", encoding="utf-8")
    if with_packages:
        _packages(root)
    return root


def _workspace(root: Path, with_packages: bool) -> Path:
    package = root / "packages" / "web"
    (package / "src").mkdir(parents=True)
    (root / "package.json").write_text('{"name":"mono","private":true}', encoding="utf-8")
    (package / "tsconfig.json").write_text('{"include":["src"]}', encoding="utf-8")
    for index in range(MODULES):
        (package / "src" / f"m{index}.ts").write_text(
            f"export const v{index} = {index};\n", encoding="utf-8"
        )
    if with_packages:
        _packages(package)
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
    alone = _config_only(base / "config_only", with_packages)
    workspace = _workspace(base / "workspace", with_packages)
    web = workspace / "packages" / "web"
    calls: dict[str, Callable[[], object]] = {
        "discover_config_only": lambda: discover_typescript_roots(alone),
        "detect_config_only": lambda: TYPESCRIPT_REPOSITORY.detect(alone),
        "detect_config_only_folder": lambda: TYPESCRIPT_REPOSITORY.detect(alone, [alone]),
        "detect_workspace_folder": lambda: TYPESCRIPT_REPOSITORY.detect(workspace, [web]),
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
    for record in (*without.values(), *with_packages.values()):
        record["seconds"] = round(_seconds(record), 7)
    accepted = all(ratio <= LIMIT for ratio in ratios.values())
    same = all(without[name]["result"] == with_packages[name]["result"] for name in without)
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
