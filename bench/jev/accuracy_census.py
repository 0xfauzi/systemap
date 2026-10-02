"""Count exposure to known accuracy limits in the eight local mapped repositories.

This is a census of syntax and stored map claims, not semantic accuracy.
Before execution: acceptance is exact accounting of every discovered source
file, with all read/parse failures recorded and no agent or service calls.
No threshold is tuned and no proposed production behavior is accepted here.

Run: uv run python bench/jev/accuracy_census.py
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from common import DEV_REPOS, HOLDOUT_REPOS

from systemap import config, evidence, extract, judgement, nest

HERE = Path(__file__).parent


def nested_definitions(nodes: list[ast.stmt]) -> list[str]:
    out: list[str] = []
    for node in nodes:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if not node.name.startswith("_"):
                out.append(node.name)
        elif isinstance(node, ast.If | ast.Try | ast.With | ast.For | ast.While):
            out += nested_definitions(node.body)
            out += nested_definitions(getattr(node, "orelse", []))
    return out


def class_patterns(tree: ast.Module) -> tuple[list[str], list[str]]:
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    ]
    constructors = [
        c.name
        for c in classes
        if any(isinstance(n, ast.FunctionDef) and n.name == "__init__" for n in c.body)
    ]
    fields = [c.name for c in classes if any(isinstance(n, ast.AnnAssign) for n in c.body)]
    return constructors, fields


def source_patterns(raw: str) -> dict[str, Any]:
    tree = ast.parse(raw)
    constructors, fields = class_patterns(tree)
    nested = [
        n
        for n in tree.body
        if not isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    ]
    conditional = nested_definitions(nested)
    type_checks = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and ast.unparse(node.test) in {"TYPE_CHECKING", "typing.TYPE_CHECKING"}
    ]
    return {
        "constructor_classes": constructors,
        "annotated_classes": fields,
        "conditional_definitions": conditional,
        "type_checking_blocks": len(type_checks),
    }


def source_paths(cfg: config.Config) -> list[Path]:
    return [
        path
        for directory, _name in cfg.roots
        for path in sorted(directory.rglob("*.py"))
        if not any(p in extract.SKIP_PARTS for p in path.parts)
    ]


def patterns(cfg: config.Config) -> dict[str, Any]:
    out: dict[str, Any] = {
        "files": 0,
        "unreadable": [],
        "unparsed": [],
        "patterns": {},
        "sha256": {},
    }
    for path in source_paths(cfg):
        rel = str(path.relative_to(cfg.root))
        out["files"] += 1
        try:
            raw = path.read_text(encoding="utf-8")
            out["sha256"][rel] = hashlib.sha256(raw.encode()).hexdigest()
            found = source_patterns(raw)
        except (OSError, UnicodeError) as exc:
            out["unreadable"].append([rel, str(exc)])
            continue
        except (SyntaxError, ValueError) as exc:
            out["unparsed"].append([rel, str(exc)])
            continue
        if any(found.values()):
            out["patterns"][rel] = found
    return out


def coverage_census(tree: nest.Tree, facts: dict[str, Any]) -> dict[str, Any]:
    points = facts["entry_points"]
    by_identity: dict[tuple[str, str], list[str]] = defaultdict(list)
    for p in points:
        by_identity[(p["kind"], p["name"])].append(p["module"])
    clashes = [
        {"kind": k, "name": n, "modules": mods}
        for (k, n), mods in by_identity.items()
        if len(set(mods)) > 1
    ]
    meanings = [m.meaning for m in tree.maps]
    text = "\n".join(judgement._journey_text(m) for m in meanings)
    all_walks = [j for m in meanings for j in m.journeys]
    starts = {j.starts for j in all_walks if j.starts}
    word_only = [
        p
        for p in points
        if p["name"] not in starts
        and extract.entry_label(p) not in starts
        and evidence.mentioned(p["name"], text)
    ]
    return {
        "entry_points": len(points),
        "identity_collisions": clashes,
        "journeys": len(all_walks),
        "with_explicit_start": sum(bool(j.starts) for j in all_walks),
        "empty_journeys": [j.id for j in all_walks if not j.steps],
        "word_only_matches": word_only,
    }


def evidence_census(tree: nest.Tree, facts: dict[str, Any], cfg: config.Config) -> dict[str, int]:
    counts = dict(imports=0, shared_module=0, mechanism_word=0, declared=0, external=0)
    for m in tree.maps:
        for ev in evidence.of_model(m.model, m.meaning, facts, cfg.observed_by).values():
            if ev.mechanism:
                counts["mechanism_word"] += 1
            elif ev.shared:
                counts["shared_module"] += 1
            elif ev.state == evidence.OBSERVED:
                counts["imports"] += 1
            else:
                counts[ev.state] += 1
    return counts


def pilot_census(name: str, root: Path) -> dict[str, Any]:
    folder = HERE / "data" / ("" if name in DEV_REPOS else "holdout")
    cases = json.loads((folder / "review-accuracy.json").read_text())
    cases = [c for c in cases if c["repo"] == name]
    cached = json.loads((folder / f"facts-{name}.json").read_text())["components"]
    bad: list[str] = []
    changed: list[str] = []
    for c in cases:
        digest = hashlib.sha1(c["source"].encode(), usedforsecurity=False).hexdigest()[:12]
        if digest != cached[c["module"]]["sha"]:
            bad.append(c["module"])
        if (root / c["file"]).read_text() != c["source"]:
            changed.append(c["module"])
    return {
        "condition_order": ["planted" if c["planted"] else "unchanged" for c in cases],
        "source_vs_facts_mismatch": bad,
        "source_changed_since_pilot": changed,
    }


def main() -> None:
    rows: dict[str, Any] = {}
    for name, root in {**DEV_REPOS, **HOLDOUT_REPOS}.items():
        if root is None:
            rows[name] = {"unavailable": True}
            continue
        cfg = config.load(root)
        tree = nest.load(cfg)
        facts = extract.build(cfg)
        source = patterns(cfg)
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        rows[name] = dict(
            root=str(root),
            revision=revision,
            interpreter=sys.version,
            model_sha256={
                m.rel: hashlib.sha256(m.path.read_bytes()).hexdigest() for m in tree.maps
            },
            source=source,
            coverage=coverage_census(tree, facts),
            evidence=evidence_census(tree, facts, cfg),
            pilot=pilot_census(name, root),
        )
        count_patterns = {
            k: sum(
                len(v[k]) if isinstance(v[k], list) else v[k] for v in source["patterns"].values()
            )
            for k in (
                "constructor_classes",
                "annotated_classes",
                "conditional_definitions",
                "type_checking_blocks",
            )
        }
        print(
            json.dumps(
                dict(
                    repo=name,
                    files=source["files"],
                    unparsed=len(source["unparsed"]),
                    patterns=count_patterns,
                    evidence=rows[name]["evidence"],
                    coverage={
                        k: v for k, v in rows[name]["coverage"].items() if not isinstance(v, list)
                    },
                    collision_groups=len(rows[name]["coverage"]["identity_collisions"]),
                    word_only_matches=len(rows[name]["coverage"]["word_only_matches"]),
                    pilot=rows[name]["pilot"],
                )
            )
        )
    path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results/no-jev-accuracy-census.json.gz"
    )
    payload = (json.dumps(rows, indent=2) + "\n").encode()
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(payload, mtime=0))
    else:
        path.write_bytes(payload)
    print(path)


if __name__ == "__main__":
    main()
