"""Compare import targets with TypeScript on pinned, uninstalled repositories.

Acceptance stated before execution: every compiler-resolved dependency whose
target is in systemap's extracted inventory must have the same target. Zero
wrong targets and zero missing targets are allowed on this eligible set.
Count unresolved, external and unextracted targets separately. This measures
dependency extraction only, not semantic map or journey accuracy. Repositories
are read-only. Missing npm dependencies limit the compiler's resolution too.

Run: uv run python bench/jev/typescript_import_census.py CHECKOUTS TYPESCRIPT_JS
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from typescript_accuracy_review import HERE, ROOT, oracle

from systemap import config, extract, typescript_config
from systemap.typescript import TYPESCRIPT

REVISIONS = {
    "hono": "90d02fb1645c12a65d27f39594d2129db2065ba7",
    "ky": "0d59458a0a58e1c3d7c6db0ab17ed5c7cd671e47",
    "zod": "2bf7b0630d5378033e90bcee82cb32b0fe04628e",
}


def prediction(
    item: dict[str, Any], module: str, repo: Path, paths: dict[str, Path], context: Any
) -> list[str]:
    form = item["kind"]
    specifier = json.dumps(item["specifier"])
    source = {
        "static": f"import * as imported from {specifier};",
        "require": f"import imported = require({specifier});",
        "dynamic": f"const loaded = import({specifier});",
    }[form]
    uses = TYPESCRIPT.internal_uses(
        source, set(), set(paths), module=module, repo=repo, paths=paths, context=context
    )
    return sorted(paths[target].relative_to(repo).as_posix() for target in uses)


def compare_imports(
    imports: list[dict[str, Any]],
    repo: Path,
    facts: dict[str, Any],
    paths: dict[str, Path],
    context: Any,
) -> tuple[Counter[str], list[dict[str, Any]]]:
    modules = {p.relative_to(repo).as_posix(): module for module, p in paths.items()}
    counts: Counter[str] = Counter()
    problems = []
    for item in imports:
        target = item["resolved"]
        counts["all_literal_imports"] += 1
        if target is None:
            counts["unresolved"] += 1
            continue
        if target not in modules:
            counts["outside_inventory"] += 1
            continue
        counts["eligible"] += 1
        problem = compare_target(item, modules[item["importer"]], repo, facts, paths, context)
        if problem is None:
            counts["matched"] += 1
        else:
            counts[problem["status"]] += 1
            counts["explicit_unknown" if problem["unknown"] else "silent_gap"] += 1
            problems.append(problem)
    return counts, problems


def compare_target(
    item: dict[str, Any],
    module: str,
    repo: Path,
    facts: dict[str, Any],
    paths: dict[str, Path],
    context: Any,
) -> dict[str, Any] | None:
    got = prediction(item, module, repo, paths, context)
    graph = facts["components"][module]
    actual = [paths[m].relative_to(repo).as_posix() for m in graph["uses"]]
    if item["resolved"] in actual:
        return None
    status = "wrong" if got and got != [item["resolved"]] else "missing"
    return {
        **item,
        "isolated_resolution": got,
        "systemap": actual,
        "status": status,
        "unknown": graph.get("unknown", []),
    }


def measure(repo: Path, compiler: str) -> dict[str, Any]:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    if revision != REVISIONS[repo.name]:
        raise ValueError(f"wrong revision: {repo.name} {revision}")
    roots = (
        [("packages/zod/src", "zod")]
        if repo.name == "zod"
        else typescript_config.discover_typescript_roots(repo)
    )
    cfg = config.Config(
        root=repo, name=repo.name, package_roots=tuple(roots), language="typescript"
    )
    facts = extract.build(cfg)
    paths = {module: repo / record["file"] for module, record in facts["components"].items()}
    modules = {p.relative_to(repo).as_posix(): module for module, p in paths.items()}
    context = TYPESCRIPT.context(repo, paths, cfg.test_dirs, cfg.test_patterns)
    truth = oracle(repo, compiler, scan=list(modules))
    counts, problems = compare_imports(truth["imports"], repo, facts, paths, context)
    return {
        "repository": repo.name,
        "revision": revision,
        "roots": roots,
        "compiler_version": truth["version"],
        "modules": len(modules),
        "counts": dict(counts),
        "compiler_diagnostic_codes": dict(Counter(d["code"] for d in truth["diagnostics"])),
        "extraction_unknowns": extract.unknown_fact_lines(facts),
        "problems": problems,
    }


def main() -> None:
    folder, compiler = Path(sys.argv[1]), sys.argv[2]
    results = []
    for name in REVISIONS:
        result = measure(folder / name, compiler)
        results.append(result)
        print(name, json.dumps(result["counts"]), flush=True)
    output = {
        "systemap_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "repositories": results,
        "note": "Compiler-resolvable dependencies within extracted modules only. Npm dependencies were not installed.",
    }
    path = HERE / "results/typescript-import-census.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    print(path)


if __name__ == "__main__":
    main()
