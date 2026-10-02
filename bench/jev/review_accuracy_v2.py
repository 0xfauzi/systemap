"""Freeze and score source-reviewed ownership cases without running an agent.

Acceptance before execution: a frozen tree must retain every Git-visible file
byte for byte; a changed or incomplete snapshot, label set, or answer set must
fail validation. Semantic acceptance needs independent labels and a separately
preregistered comparison. No agent or service is called by this program.

    uv run --project bench/jev python bench/jev/review_accuracy_v2.py freeze REPO OUT
    uv run --project bench/jev python bench/jev/review_accuracy_v2.py build OUT... --seed SEED
    uv run --project bench/jev python bench/jev/review_accuracy_v2.py verify OUT
    uv run --project bench/jev python bench/jev/review_accuracy_v2.py score CASES LABELS ANSWERS

The frozen directory contains tree/, facts.json, and manifest.json. Build
writes cases.json, label-cases.json, and review-cases.json. Labels and answers
are separate files supplied after independent review and a workflow run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import workflow_input

from systemap import config, extract, nest
from systemap.model import claimed

FORMAT = 1
NONE = "none of these"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_digest(path: Path) -> str:
    """Match the extractor's digest of decoded, newline-normalized source."""
    return digest(path.read_text(encoding="utf-8").encode())


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True).stdout


def visible_files(root: Path) -> list[Path]:
    raw = git(root, "ls-files", "-co", "--exclude-standard", "-z")
    paths = sorted({Path(p.decode()) for p in raw.split(b"\0") if p})
    if any(p.is_absolute() or ".." in p.parts for p in paths):
        raise ValueError("Git returned a path outside the repository")
    return [p for p in paths if (root / p).exists() or (root / p).is_symlink()]


def copy_tree(root: Path, target: Path) -> tuple[dict[str, str], dict[str, str]]:
    files: dict[str, str] = {}
    symlinks: dict[str, str] = {}
    visible = visible_files(root)
    visible_set = set(visible)
    for rel in visible:
        copied = copy_visible_file(root, target, rel, visible_set)
        (symlinks if (root / rel).is_symlink() else files)[rel.as_posix()] = copied
    return files, symlinks


def copy_visible_file(root: Path, target: Path, rel: Path, visible: set[Path]) -> str:
    source = root / rel
    destination = target / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        link = Path(os.readlink(source))
        resolved = (source.parent / link).resolve()
        if link.is_absolute() or not resolved.is_relative_to(root):
            raise ValueError(f"symlink leaves source repository: {rel}")
        target_rel = resolved.relative_to(root)
        included = target_rel in visible or any(path.is_relative_to(target_rel) for path in visible)
        if not included or not resolved.exists():
            raise ValueError(f"symlink target is absent from snapshot: {rel}")
        destination.symlink_to(link)
        return link.as_posix()
    if not source.is_file():
        raise ValueError(f"missing or non-file Git path: {rel}")
    raw = source.read_bytes()
    destination.write_bytes(raw)
    if source.read_bytes() != raw:
        raise ValueError(f"source changed while freezing: {rel}")
    return digest(raw)


def extractor_sources_sha256() -> str:
    package = Path(extract.__file__).parent
    files = {
        path.relative_to(package).as_posix(): digest(path.read_bytes())
        for path in sorted(package.rglob("*.py"))
    }
    return digest(canonical(files))


def source_unchanged(root: Path, files: dict[str, str], symlinks: dict[str, str]) -> bool:
    if {p.as_posix() for p in visible_files(root)} != set(files) | set(symlinks):
        return False
    return all(
        digest((root / rel).read_bytes()) == expected for rel, expected in files.items()
    ) and all(os.readlink(root / rel) == target for rel, target in symlinks.items())


def require_complete_inventory(cfg: config.Config, facts: dict[str, Any]) -> None:
    discovered = set(extract._source_paths(cfg, extract.language_for(cfg)))
    recorded = set(facts["components"])
    if discovered != recorded:
        missing = sorted(discovered - recorded)
        extra = sorted(recorded - discovered)
        raise ValueError(f"extraction inventory differs: missing={missing}, extra={extra}")
    issues = extract.inventory_issue_lines(facts)
    if issues:
        raise ValueError("extraction has unresolved source: " + "; ".join(issues[:5]))


def freeze(root: Path, out: Path) -> None:
    root = root.resolve()
    out = out.resolve()
    if out == root or out.is_relative_to(root):
        raise ValueError("snapshot output must be outside its source repository")
    if out.exists():
        raise ValueError(f"snapshot output already exists: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}-", dir=out.parent))
    try:
        extractor_digest = extractor_sources_sha256()
        tree = staging / "tree"
        tree.mkdir()
        files, symlinks = copy_tree(root, tree)
        if "systemap.toml" not in files and "pyproject.toml" not in files:
            raise ValueError("no project configuration copied")
        cfg = config.load(tree)
        facts = extract.build(cfg)
        require_complete_inventory(cfg, facts)
        original = extract.build(config.load(root))
        require_complete_inventory(config.load(root), original)
        for field in ("components", "entry_points", "entry_point_issues", "test_file_issues"):
            if original.get(field) != facts.get(field):
                raise ValueError(f"source changed or Git omitted an extraction input: {field}")
        if extractor_digest != extractor_sources_sha256():
            raise ValueError("extractor source changed while freezing")
        if not source_unchanged(root, files, symlinks):
            raise ValueError("source tree changed while freezing")
        write_json(staging / "facts.json", facts)
        manifest = {
            "format": FORMAT,
            "repo": cfg.name,
            "head": git(root, "rev-parse", "HEAD").decode().strip(),
            "files": files,
            "symlinks": symlinks,
            "facts_sha256": digest((staging / "facts.json").read_bytes()),
            "python": sys.version.split()[0],
            "extractor_sources_sha256": extractor_digest,
        }
        manifest["snapshot_id"] = digest(canonical(manifest))
        write_json(staging / "manifest.json", manifest)
        verify(staging)
        os.replace(staging, out)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def verify(out: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = read_json(out / "manifest.json")
    if manifest.get("format") != FORMAT:
        raise ValueError("unknown snapshot format")
    recorded_id = manifest["snapshot_id"]
    unsigned = {k: v for k, v in manifest.items() if k != "snapshot_id"}
    if recorded_id != digest(canonical(unsigned)):
        raise ValueError("snapshot manifest changed")
    if manifest.get("python") != sys.version.split()[0]:
        raise ValueError("snapshot requires the Python version used to extract it")
    if manifest.get("extractor_sources_sha256") != extractor_sources_sha256():
        raise ValueError("snapshot requires the systemap source used to extract it")
    verify_tree(out, manifest)
    return manifest


def verify_tree(out: Path, manifest: dict[str, Any]) -> None:
    paths = list((out / "tree").rglob("*"))
    verify_snapshot_links(out, paths, manifest["symlinks"])
    expected = manifest["files"]
    actual = {
        p.relative_to(out / "tree").as_posix(): digest(p.read_bytes())
        for p in paths
        if p.is_file() and not p.is_symlink()
    }
    if actual != expected:
        raise ValueError("snapshot files changed, appeared, or disappeared")
    if digest((out / "facts.json").read_bytes()) != manifest["facts_sha256"]:
        raise ValueError("snapshot facts changed")
    verify_snapshot_facts(out, expected, manifest["symlinks"])


def verify_snapshot_links(out: Path, paths: list[Path], expected: dict[str, str]) -> None:
    links = {
        p.relative_to(out / "tree").as_posix(): os.readlink(p) for p in paths if p.is_symlink()
    }
    if links != expected:
        raise ValueError("snapshot symlinks changed")
    for rel in links:
        resolved = (out / "tree" / rel).resolve()
        if not resolved.is_relative_to((out / "tree").resolve()) or not resolved.exists():
            raise ValueError(f"snapshot symlink target is missing or outside: {rel}")


def verify_snapshot_facts(out: Path, files: dict[str, str], links: dict[str, str]) -> None:
    for module, record in read_json(out / "facts.json")["components"].items():
        rel = record.get("file")
        if rel:
            if rel not in files and rel not in links:
                raise ValueError(f"facts name a file outside the snapshot: {module}: {rel}")
            if record.get("source_sha256") != source_digest(out / "tree" / rel):
                raise ValueError(f"facts and source disagree for {module}")


def card_brief(card: Any, plain: str) -> str:
    parts = [f"{plain}." if plain else "", card.does]
    if card.interface:
        parts.append(f"Interface: {card.interface}")
    return " ".join(part for part in parts if part)


def repository_cases(out: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    manifest = verify(out)
    tree = out / "tree"
    cfg = config.load(tree)
    maps = nest.load(cfg)
    top = maps.top
    facts = read_json(out / "facts.json")
    records = facts["components"]
    cards = [c for c in top.model.components if c.kind != "actor"]
    card_text = {c.id: card_brief(c, top.meaning.plain.get(c.id, "")) for c in cards}
    owners: dict[str, str] = {}
    modules = sorted(m for m, r in records.items() if not extract.is_empty_marker(r))
    for card in cards:
        for module in claimed(card, modules):
            owners.setdefault(module, card.id)
    rows = []
    for module in modules:
        owner = owners.get(module)
        record = records[module]
        rel = record.get("file")
        if not rel or not (tree / rel).is_file():
            continue
        rows.append(
            {
                "id": f"{manifest['repo']}:{module}",
                "snapshot_id": manifest["snapshot_id"],
                "repo": manifest["repo"],
                "module": module,
                "file": rel,
                "source_sha256": source_digest(tree / rel),
                "source": (tree / rel).read_text(encoding="utf-8"),
                "cards": {
                    **card_text,
                    NONE: "No existing card describes this module's primary job.",
                },
                "reference_owner": owner,
            }
        )
    return rows, {
        "empty_markers_excluded": len(records) - len(modules),
        "unclaimed_modules": len(set(modules) - set(owners)),
        "nested_maps_unscored": len(maps.maps) - 1,
    }


def build(snapshots: list[Path], destination: Path, seed: str, count: int | None) -> None:
    if destination.exists():
        raise ValueError(f"case output already exists: {destination}")
    rng = random.Random(seed)
    groups = [repository_cases(snapshot) for snapshot in snapshots]
    exclusions = {
        "empty_markers_excluded": sum(c["empty_markers_excluded"] for _rows, c in groups),
        "unclaimed_modules": sum(c["unclaimed_modules"] for _rows, c in groups),
        "nested_maps_unscored": sum(c["nested_maps_unscored"] for _rows, c in groups),
    }
    pool = select_cases(groups, rng, count)
    destination.mkdir(parents=True)
    write_case_packets(destination, seed, exclusions, pool)


def select_cases(
    groups: list[tuple[list[dict[str, Any]], dict[str, int]]],
    rng: random.Random,
    count: int | None,
) -> list[dict[str, Any]]:
    pool = [row for rows, _counts in groups for row in rows]
    if len({row["id"] for row in pool}) != len(pool):
        raise ValueError("duplicate repository or module identity")
    if count is not None:
        if count < 1 or count > len(pool):
            raise ValueError("count must be between one and the available module count")
        pool = rng.sample(pool, count)
    rng.shuffle(pool)
    planted_ids = {row["id"] for row in rng.sample(pool, len(pool) // 2)}
    for row in pool:
        owner = row["reference_owner"]
        other = sorted(set(row["cards"]) - {owner, NONE})
        row["planted"] = owner is not None and row["id"] in planted_ids and bool(other)
        row["candidate"] = rng.choice(other) if row["planted"] else owner or NONE
    rng.shuffle(pool)
    return pool


def write_case_packets(
    destination: Path, seed: str, exclusions: dict[str, int], pool: list[dict[str, Any]]
) -> None:
    case_set = {"format": FORMAT, "seed": seed, "exclusions": exclusions, "cases": pool}
    write_json(destination / "cases.json", case_set)
    case_hash = digest(canonical(case_set))
    shared = {"format": FORMAT, "case_set_sha256": case_hash, "exclusions": exclusions}
    label_hidden = {"reference_owner", "planted", "candidate"}
    label_cases = [{k: v for k, v in row.items() if k not in label_hidden} for row in pool]
    review_hidden = {"reference_owner", "planted"}
    review_cases = [{k: v for k, v in row.items() if k not in review_hidden} for row in pool]
    write_json(destination / "label-cases.json", {**shared, "cases": label_cases})
    write_json(destination / "review-cases.json", {**shared, "cases": review_cases})


def validate_labels(cases: list[dict[str, Any]], labels: list[dict[str, Any]]) -> None:
    by_id = {row["id"]: row for row in cases}
    if len(by_id) != len(cases) or {row.get("id") for row in labels} != set(by_id):
        raise ValueError("labels must cover each case exactly once")
    if len(labels) != len(cases):
        raise ValueError("duplicate label id")
    for label in labels:
        validate_label(by_id[label["id"]], label)


def validate_label(case: dict[str, Any], label: dict[str, Any]) -> None:
    validate_label_status(case, label)
    if label.get("snapshot_id") != case["snapshot_id"]:
        raise ValueError(f"label snapshot differs: {label['id']}")
    if label.get("source_sha256") != case["source_sha256"]:
        raise ValueError(f"label source differs: {label['id']}")
    if not label.get("reviewer") or label.get("blind_to_predictions") is not True:
        raise ValueError(f"label lacks blind reviewer provenance: {label['id']}")
    status = label["status"]
    validate_label_evidence(case, label, status)
    if status == "new_card" and not label.get("proposed_card"):
        raise ValueError(f"new card label needs a proposed job: {label['id']}")


def validate_label_status(case: dict[str, Any], label: dict[str, Any]) -> None:
    status = label.get("status")
    owners = label.get("acceptable_cards")
    if status not in {"adjudicated", "ambiguous", "new_card", "unresolved"}:
        raise ValueError(f"invalid label status: {label['id']}")
    if not isinstance(owners, list) or len(owners) != len(set(owners)):
        raise ValueError(f"invalid acceptable cards: {label['id']}")
    if any(owner not in case["cards"] or owner == NONE for owner in owners):
        raise ValueError(f"unknown acceptable card: {label['id']}")
    expected_length = {"adjudicated": 1, "ambiguous": 2, "new_card": 0}
    if status in expected_length and (
        len(owners) < expected_length[status]
        or (status != "ambiguous" and len(owners) != expected_length[status])
    ):
        raise ValueError(f"label status and acceptable cards disagree: {label['id']}")


def validate_label_evidence(case: dict[str, Any], label: dict[str, Any], status: str) -> None:
    evidence = label.get("evidence")
    if status != "unresolved" and not isinstance(evidence, list):
        raise ValueError(f"label lacks source evidence: {label['id']}")
    if status != "unresolved" and not evidence:
        raise ValueError(f"label lacks source evidence: {label['id']}")
    for item in evidence or []:
        if not isinstance(item, dict) or item.get("file") != case["file"]:
            raise ValueError(f"evidence file differs: {label['id']}")
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol not in case["source"]:
            raise ValueError(f"evidence symbol is absent from source: {label['id']}")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise ValueError(f"evidence needs a reason: {label['id']}")


def validate_answers(cases: list[dict[str, Any]], answers: list[dict[str, Any]]) -> None:
    by_id = {row["id"]: row for row in cases}
    if len(answers) != len(cases) or {row.get("id") for row in answers} != set(by_id):
        raise ValueError("answers must cover each case exactly once")
    for answer in answers:
        validate_answer(by_id[answer["id"]], answer)


def validate_answer(case: dict[str, Any], answer: dict[str, Any]) -> None:
    if answer.get("snapshot_id") != case["snapshot_id"]:
        raise ValueError(f"answer snapshot differs: {answer['id']}")
    if answer.get("candidate") != case["candidate"]:
        raise ValueError(f"answer candidate differs: {answer['id']}")
    decision = answer.get("decision")
    replacement = answer.get("better_card")
    if decision not in {"fits", "wrong", "abstain"}:
        raise ValueError(f"invalid decision: {answer['id']}")
    if decision == "wrong" and replacement not in case["cards"]:
        raise ValueError(f"wrong answer needs a listed replacement: {answer['id']}")
    if decision != "wrong" and replacement is not None:
        raise ValueError(f"unexpected replacement: {answer['id']}")


def score(cases_file: Path, labels_file: Path, answers_file: Path) -> dict[str, Any]:
    case_set = read_json(cases_file)
    label_set = read_json(labels_file)
    answer_set = read_json(answers_file)
    if any(value.get("format") != FORMAT for value in (case_set, label_set, answer_set)):
        raise ValueError("case, label, and answer formats must match")
    case_sha = digest(canonical(case_set))
    if label_set.get("case_set_sha256") != case_sha:
        raise ValueError("labels belong to a different case set")
    if answer_set.get("case_set_sha256") != case_sha:
        raise ValueError("answers belong to a different case set")
    cases = case_set["cases"]
    labels = label_set["labels"]
    answers = answer_set["answers"]
    validate_labels(cases, labels)
    validate_answers(cases, answers)
    by_label = {row["id"]: row for row in labels}
    by_answer = {row["id"]: row for row in answers}
    totals: dict[str, int] = defaultdict(int)
    per_repo: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for case in cases:
        label = by_label[case["id"]]
        answer = by_answer[case["id"]]
        for bucket in (totals, per_repo[case["repo"]]):
            count_answer(bucket, case, label, answer)
    for bucket in (totals, *per_repo.values()):
        bucket["incorrect_confident_claims"] = (
            bucket["false_accepts"] + bucket["false_challenges"] + bucket["wrong_replacements"]
        )
    return {
        "case_set_sha256": case_sha,
        "total": dict(totals),
        "by_repo": {k: dict(v) for k, v in per_repo.items()},
    }


def count_answer(
    bucket: dict[str, int], case: dict[str, Any], label: dict[str, Any], answer: dict[str, Any]
) -> None:
    bucket["cases"] += 1
    status = label["status"]
    if status in {"ambiguous", "unresolved"}:
        bucket[status] += 1
        if answer["decision"] == "abstain":
            bucket["abstained"] += 1
        return
    error = (
        case["candidate"] != NONE
        if status == "new_card"
        else case["candidate"] not in label["acceptable_cards"]
    )
    bucket["true_errors" if error else "acceptable_assignments"] += 1
    decision = answer["decision"]
    if decision == "abstain":
        bucket["abstained"] += 1
    elif decision == "fits":
        bucket["false_accepts" if error else "correct_accepts"] += 1
    elif error:
        bucket["true_errors_detected"] += 1
        replacement = answer["better_card"]
        correct = (status == "new_card" and replacement == NONE) or (
            status == "adjudicated" and replacement in label["acceptable_cards"]
        )
        bucket["correct_replacements" if correct else "wrong_replacements"] += 1
    else:
        bucket["false_challenges"] += 1


def validate_workflow(snapshot: Path, result_file: Path) -> dict[str, int]:
    """Check a full map run's inventory without claiming semantic accuracy."""
    manifest = verify(snapshot)
    result = read_json(result_file)
    if result.get("snapshot_id") != manifest["snapshot_id"]:
        raise ValueError("workflow result uses a different source snapshot")
    validate_workflow_instructions(result, result_file)
    facts = read_json(snapshot / "facts.json")
    workflow_input.verify(snapshot, manifest, facts, result, result_file)
    records = facts["components"]
    expected = {m for m, record in records.items() if not extract.is_empty_marker(record)}
    owners = result.get("owners")
    if not isinstance(owners, dict) or set(owners) != expected:
        raise ValueError("workflow must report every extracted module, including omissions")
    validate_workflow_claims(result, owners)
    return {
        "modules": len(expected),
        "empty_markers_excluded": len(records) - len(expected),
        "omitted": sum(v is None for v in owners.values()),
    }


def validate_workflow_instructions(result: dict[str, Any], result_file: Path) -> None:
    instruction_hash = result.get("instructions_sha256")
    instruction_file = result.get("instructions_file")
    if not result.get("agent") or not isinstance(instruction_hash, str):
        raise ValueError("workflow result lacks instructions or agent identity")
    if not re.fullmatch(r"[0-9a-f]{64}", instruction_hash):
        raise ValueError("workflow instructions hash is not SHA-256")
    if not isinstance(instruction_file, str) or not instruction_file:
        raise ValueError("workflow result lacks its instructions file")
    relative = Path(instruction_file)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("workflow instructions path must be relative to the result")
    instructions = result_file.parent / relative
    if not instructions.is_file() or digest(instructions.read_bytes()) != instruction_hash:
        raise ValueError("workflow instructions differ from their recorded hash")


def validate_workflow_claims(result: dict[str, Any], owners: dict[str, Any]) -> None:
    cards = result.get("cards")
    if (
        not isinstance(cards, dict)
        or not cards
        or any(
            not isinstance(cid, str) or not isinstance(job, str) or not job.strip()
            for cid, job in cards.items()
        )
    ):
        raise ValueError("workflow must describe every card it uses")
    if any(owner is not None and owner not in cards for owner in owners.values()):
        raise ValueError("workflow owners must be listed card IDs or null")
    for field in ("flows", "journeys", "invariants", "unresolved_claims"):
        if not isinstance(result.get(field), list):
            raise ValueError(f"workflow result lacks {field} claims")


def validate_alignment(
    cases: list[dict[str, Any]], run: dict[str, Any], alignment: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    if alignment.get("format") != FORMAT:
        raise ValueError("unknown card alignment format")
    if alignment.get("snapshot_id") != run["snapshot_id"]:
        raise ValueError("card alignment uses a different snapshot")
    if alignment.get("run_sha256") != digest(canonical(run)):
        raise ValueError("card alignment uses a different workflow run")
    rows = alignment.get("alignments")
    if not isinstance(rows, list) or len(rows) != len(run["cards"]):
        raise ValueError("card alignment must cover every workflow card exactly once")
    by_card = {row.get("card") for row in rows if isinstance(row, dict)}
    if by_card != set(run["cards"]):
        raise ValueError("card alignment must cover every workflow card exactly once")
    reference_cards = {cid for case in cases for cid in case["cards"] if cid != NONE}
    for row in rows:
        validate_alignment_row(row, reference_cards)
    return {row["card"]: row for row in rows}


def validate_alignment_row(row: dict[str, Any], reference_cards: set[str]) -> None:
    card = row["card"]
    status = row.get("status")
    reference = row.get("reference_card")
    if status not in {"existing", "new", "ambiguous"}:
        raise ValueError(f"invalid card alignment status: {card}")
    if status == "existing" and reference not in reference_cards:
        raise ValueError(f"card alignment names an unknown reference card: {card}")
    if status != "existing" and reference is not None:
        raise ValueError(f"new or ambiguous card alignment names a reference card: {card}")
    if not isinstance(row.get("reviewer"), str) or not row["reviewer"].strip():
        raise ValueError(f"card alignment lacks reviewer: {card}")
    if row.get("blind_to_scores") is not True:
        raise ValueError(f"card alignment lacks blind review declaration: {card}")
    if not isinstance(row.get("evidence"), str) or not row["evidence"].strip():
        raise ValueError(f"card alignment lacks evidence: {card}")


def score_workflow(
    snapshot: Path,
    cases_file: Path,
    labels_file: Path,
    result_file: Path,
    alignment_file: Path,
) -> dict[str, Any]:
    inventory = validate_workflow(snapshot, result_file)
    manifest = verify(snapshot)
    case_set = read_json(cases_file)
    label_set = read_json(labels_file)
    if case_set.get("format") != FORMAT or label_set.get("format") != FORMAT:
        raise ValueError("case and label formats must match")
    if label_set.get("case_set_sha256") != digest(canonical(case_set)):
        raise ValueError("labels belong to a different case set")
    cases = [row for row in case_set["cases"] if row["snapshot_id"] == manifest["snapshot_id"]]
    if not cases:
        raise ValueError("no labelled cases belong to this snapshot")
    labels = [row for row in label_set["labels"] if row["id"] in {c["id"] for c in cases}]
    validate_labels(cases, labels)
    run = read_json(result_file)
    aligned = validate_alignment(cases, run, read_json(alignment_file))
    owners = run["owners"]
    label_by_id = {label["id"]: label for label in labels}
    counts: dict[str, int] = defaultdict(int)
    for case in cases:
        count_workflow_case(counts, case, label_by_id[case["id"]], owners, aligned)
    return {
        "snapshot_id": manifest["snapshot_id"],
        "inventory": inventory,
        "ownership": dict(counts),
        "unscored_claim_types": ["flows", "journeys", "invariants"],
    }


def count_workflow_case(
    counts: dict[str, int],
    case: dict[str, Any],
    label: dict[str, Any],
    owners: dict[str, Any],
    aligned: dict[str, dict[str, Any]],
) -> None:
    status = label["status"]
    counts["labelled_cases"] += 1
    owner = owners[case["module"]]
    if owner is None:
        counts["labelled_omissions"] += 1
    if status in {"ambiguous", "unresolved"}:
        counts[f"{status}_unscored"] += 1
        return
    if status == "new_card":
        count_new_card_case(counts, case, owner, aligned)
        return
    acceptable = set(label["acceptable_cards"])
    baseline_correct = case["reference_owner"] in acceptable
    counts["baseline_correct" if baseline_correct else "baseline_wrong"] += 1
    if owner is None:
        return
    match = aligned[owner]
    if match["status"] != "existing":
        counts[f"workflow_{match['status']}_unscored"] += 1
        return
    if match["reference_card"] in acceptable:
        counts["workflow_correct"] += 1
        if not baseline_correct:
            counts["true_error_corrections"] += 1
    else:
        counts["workflow_wrong_confident"] += 1
        if baseline_correct:
            counts["regressions"] += 1


def count_new_card_case(
    counts: dict[str, int],
    case: dict[str, Any],
    owner: str | None,
    aligned: dict[str, dict[str, Any]],
) -> None:
    counts["new_card_cases"] += 1
    if case["reference_owner"] is not None:
        counts["baseline_wrong"] += 1
    if owner is None:
        return
    match = aligned[owner]["status"]
    if match == "existing":
        counts["new_card_existing_owner_wrong_confident"] += 1
        counts["workflow_wrong_confident"] += 1
    else:
        counts[f"new_card_{match}_unscored"] += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    frozen = commands.add_parser("freeze")
    frozen.add_argument("repo", type=Path)
    frozen.add_argument("out", type=Path)
    checked = commands.add_parser("verify")
    checked.add_argument("snapshot", type=Path)
    built = commands.add_parser("build")
    built.add_argument("snapshots", nargs="+", type=Path)
    built.add_argument("--out", required=True, type=Path)
    built.add_argument("--seed", required=True)
    built.add_argument("--count", type=int)
    scored = commands.add_parser("score")
    scored.add_argument("cases", type=Path)
    scored.add_argument("labels", type=Path)
    scored.add_argument("answers", type=Path)
    prepared = commands.add_parser("prepare-workflow")
    prepared.add_argument("snapshot", type=Path)
    prepared.add_argument("out", type=Path)
    prepared.add_argument("--config", action="append", default=[])
    workflow = commands.add_parser("validate-workflow")
    workflow.add_argument("snapshot", type=Path)
    workflow.add_argument("result", type=Path)
    workflow_score = commands.add_parser("score-workflow")
    workflow_score.add_argument("snapshot", type=Path)
    workflow_score.add_argument("cases", type=Path)
    workflow_score.add_argument("labels", type=Path)
    workflow_score.add_argument("result", type=Path)
    workflow_score.add_argument("alignment", type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.repo, args.out)
        print((args.out / "manifest.json").resolve())
    elif args.command == "verify":
        print(verify(args.snapshot)["snapshot_id"])
    elif args.command == "build":
        build(args.snapshots, args.out, args.seed, args.count)
        print(f"label packet: {(args.out / 'label-cases.json').resolve()}")
        print(f"review packet: {(args.out / 'review-cases.json').resolve()}")
    elif args.command == "score":
        print(json.dumps(score(args.cases, args.labels, args.answers), indent=2))
    elif args.command == "prepare-workflow":
        manifest = verify(args.snapshot)
        print(
            workflow_input.prepare(
                args.snapshot,
                args.out,
                manifest,
                read_json(args.snapshot / "facts.json"),
                args.config,
            )
        )
    elif args.command == "validate-workflow":
        print(json.dumps(validate_workflow(args.snapshot, args.result), indent=2))
    else:
        print(
            json.dumps(
                score_workflow(args.snapshot, args.cases, args.labels, args.result, args.alignment),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
