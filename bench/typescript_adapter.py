"""Measure the TypeScript adapter on the pinned repositories in issue #9.

Acceptance numbers declared before this experiment: all seven repositories
must extract (the original five plus nest and excalidraw); every top-level
export in a parsed module must yield a name or explicit unknown; at least 90%
of each repository's test files must be attributed to a module; date-fns
extraction, including facts serialization, must finish in at most 60 seconds.
The pinned commits and repository settings are also recorded in PR #12.

Run one repository per process so a native parser crash cannot hide the other
results: uv run python bench/typescript_adapter.py NAME /path/to/checkouts
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

from systemap import config, extract
from systemap import typescript as ts
from systemap import typescript_surface as surface

REVISIONS = {
    "ky": "0d59458a0a58e1c3d7c6db0ab17ed5c7cd671e47",
    "taxonomy": "298a8857c7128a0d121e7f699dfd729f23b3966d",
    "hono": "90d02fb1645c12a65d27f39594d2129db2065ba7",
    "zod": "2bf7b0630d5378033e90bcee82cb32b0fe04628e",
    "date-fns": "717ce0a807ea4c6b540d015b5c408723175b2838",
    "nest": "b58554ea5857445841674963211e4f3f41b0a3a4",
    "excalidraw": "5db42c3ddbbdc44d10120ab2f18e0864d083e268",
}
DEFAULT_CONFIG = 'language = "typescript"\n'
ZOD_CONFIG = 'language = "typescript"\n\n[package_roots]\n"packages/zod/src" = "zod"\n'
SKIP_PARTS = {".git", ".venv", "node_modules", "build", "dist"}


def _test_file(name: str, relative: str) -> bool:
    path = Path(relative)
    if any(part in SKIP_PARTS for part in path.parts) or path.name.endswith(".d.ts"):
        return False
    if name == "ky":
        return (
            relative.startswith("test/")
            and not relative.startswith("test/helpers/")
            and path.suffix == ".ts"
        )
    if name == "date-fns":
        return path.name in {"test.ts", "test.tsx"} or path.name.endswith((".test.ts", ".test.tsx"))
    suffixes = (".spec.ts", ".spec.tsx") if name == "nest" else (".test.ts", ".test.tsx")
    return path.name.endswith(suffixes)


def _test_counts(
    name: str, repo: Path, paths: dict[str, Path], cfg: config.Config
) -> tuple[int, int]:
    context = ts.TYPESCRIPT.context(repo, paths, cfg.test_dirs, cfg.test_patterns)
    files = sorted(
        path
        for path in repo.rglob("*")
        if path.is_file() and _test_file(name, path.relative_to(repo).as_posix())
    )
    attributed = sum(bool(ts._test_file_guards(path, repo, paths, context)) for path in files)
    return attributed, len(files)


def _export_counts(repo: Path) -> tuple[int, int, int]:
    accounted = total = unparsed = 0
    for path in repo.rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        relative = path.relative_to(repo)
        if path.name.endswith(".d.ts") or any(part in SKIP_PARTS for part in relative.parts):
            continue
        root = surface._root(path.read_text(encoding="utf-8"), path.as_posix())
        if root is None:
            unparsed += 1
            continue
        kinds = surface._declared_kinds(root)
        for node in root.named_children:
            if node.type != "export_statement":
                continue
            total += 1
            one: dict[str, Any] = {
                "functions": [],
                "classes": [],
                "errors": [],
                "constants": [],
                "names": [],
                "unknown": [],
            }
            surface._record_export(node, one, kinds)
            accounted += bool(one["names"] or one["unknown"])
    return accounted, total, unparsed


def measure(name: str, checkout_dir: Path) -> dict[str, Any]:
    repo = checkout_dir / name
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    if actual != REVISIONS[name]:
        raise ValueError(f"{name} is at {actual}, expected {REVISIONS[name]}")
    expected_config = ZOD_CONFIG if name == "zod" else DEFAULT_CONFIG
    settings = repo / "systemap.toml"
    if settings.exists() and settings.read_text(encoding="utf-8") != expected_config:
        raise ValueError(f"{name} has settings different from PR #12")
    settings.write_text(expected_config, encoding="utf-8")
    cfg = config.load(repo)
    started = time.perf_counter()
    facts = extract.build(cfg)
    with tempfile.TemporaryDirectory() as temp:
        extract.write_facts(Path(temp) / "facts.json", facts)
    elapsed = time.perf_counter() - started
    paths = {module: repo / item["file"] for module, item in facts["components"].items()}
    attributed, tests = _test_counts(name, repo, paths, cfg)
    accounted, exports, unparsed = _export_counts(repo)
    return {
        "repository": name,
        "commit": actual,
        "modules": len(paths),
        "extract_seconds": round(elapsed, 3),
        "exports_accounted": accounted,
        "exports_total": exports,
        "unparsed_modules": unparsed,
        "tests_attributed": attributed,
        "tests_total": tests,
        "unknown_lines": len(extract.unknown_fact_lines(facts)),
        "tree_sitter": version("tree-sitter"),
        "tree_sitter_typescript": version("tree-sitter-typescript"),
        "python": platform.python_version(),
        "platform": platform.platform(),
    }


if __name__ == "__main__":
    print(json.dumps(measure(sys.argv[1], Path(sys.argv[2])), sort_keys=True))
