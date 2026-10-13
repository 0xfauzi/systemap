"""Measure TypeScript extraction time with a large node_modules directory in a package root.

Acceptance value, written before the change: with 40,000 files in
`packages/web/node_modules`, the median `extract.build` time must be at most 1.2 times
the median time of the same fixture without node_modules. The package root is
`packages/web`, so the node_modules directory is below the package root, as in an npm
or pnpm workspace.

The script also gives the median time of `TYPESCRIPT.source_paths` for the two
fixtures. It makes the fixtures in a temporary directory and removes them.

    uv run python bench/typescript_discovery.py
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from systemap import config, extract
from systemap.typescript import TYPESCRIPT

MODULES = 40
PACKAGE_FILES = 40_000
RUNS = 5
LIMIT = 1.2


def _fixture(root: Path, with_packages: bool) -> None:
    (root / "systemap.toml").write_text(
        'language = "typescript"\n[package_roots]\n"packages/web" = "web"\n', encoding="utf-8"
    )
    (root / "package.json").write_text('{"name":"mono","private":true}', encoding="utf-8")
    package = root / "packages" / "web"
    (package / "src").mkdir(parents=True)
    (package / "package.json").write_text('{"name":"web"}', encoding="utf-8")
    (package / "tsconfig.json").write_text('{"include":["src"]}', encoding="utf-8")
    for index in range(MODULES):
        previous = f'import {{ v{index - 1} }} from "./m{index - 1}";\n' if index else ""
        (package / "src" / f"m{index}.ts").write_text(
            f"{previous}export const v{index} = {index};\n", encoding="utf-8"
        )
    if with_packages:
        for index in range(PACKAGE_FILES):
            folder = package / "node_modules" / f"pkg{index // 100}" / "lib"
            folder.mkdir(parents=True, exist_ok=True)
            suffix = ".d.ts" if index % 2 else ".ts"
            (folder / f"f{index % 100}{suffix}").write_text(
                "export const x = 1;\n", encoding="utf-8"
            )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)


def _median(action: object) -> float:
    times = []
    for _ in range(RUNS):
        started = time.perf_counter()
        action()  # type: ignore[operator]
        times.append(time.perf_counter() - started)
    return statistics.median(times)


def _measure(root: Path) -> dict[str, float]:
    package = root / "packages" / "web"
    build = _median(lambda: extract.build(config.load(root)))
    paths = _median(lambda: list(TYPESCRIPT.source_paths(package, root, (), ())))
    return {"build_seconds": round(build, 4), "source_paths_seconds": round(paths, 4)}


def main() -> int:
    with tempfile.TemporaryDirectory() as small, tempfile.TemporaryDirectory() as large:
        _fixture(Path(small), with_packages=False)
        _fixture(Path(large), with_packages=True)
        without = _measure(Path(small))
        with_packages = _measure(Path(large))
    ratio = with_packages["build_seconds"] / without["build_seconds"]
    result = {
        "modules": MODULES,
        "node_modules_files": PACKAGE_FILES,
        "runs": RUNS,
        "without_node_modules": without,
        "with_node_modules": with_packages,
        "build_ratio": round(ratio, 3),
        "acceptance": f"build_ratio <= {LIMIT}",
        "accepted": ratio <= LIMIT,
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0 if ratio <= LIMIT else 1


if __name__ == "__main__":
    raise SystemExit(main())
