"""The ownership evaluation must refuse changed snapshots and incomplete results."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bench" / "jev" / "review_accuracy_v2.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("review_accuracy_v2", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


def fixture_repo(root: Path) -> None:
    (root / "pkg").mkdir()
    (root / "map").mkdir()
    (root / "pkg" / "__init__.py").write_text('"""Package marker."""\n')
    (root / "pkg" / "a.py").write_text("def read():\n    return 'input'\n")
    (root / "pkg" / "b.py").write_text("def write():\n    return 'output'\n")
    (root / "map" / "model.py").write_text(
        "from systemap import Component, Meaning, Model\n"
        "MODEL = Model((600, 400), (), (), (\n"
        "    Component('Reader', 'Reads input.', implemented_by=('pkg.a',), entry='read'),\n"
        "    Component('Writer', 'Writes output.', implemented_by=('pkg.b',), entry='write'),\n"
        "), (), ())\n"
        "MEANING = Meaning(plain={'Reader': 'input reader', 'Writer': 'output writer'})\n"
    )
    (root / "systemap.toml").write_text(
        'name = "fixture"\nmodel = "map/model.py"\n[package_roots]\n"pkg" = "pkg"\n'
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )


def workflow_binding(snapshot: Path, parent: Path) -> dict:
    destination = parent / "workflow-input"
    identity = review.workflow_input.prepare(
        snapshot,
        destination,
        review.verify(snapshot),
        review.read_json(snapshot / "facts.json"),
        [],
    )
    return {"workflow_input": destination.name, "workflow_input_sha256": identity}


def label_for(case: dict, owner: str) -> dict:
    return {
        "id": case["id"],
        "status": "adjudicated",
        "acceptable_cards": [owner],
        "snapshot_id": case["snapshot_id"],
        "source_sha256": case["source_sha256"],
        "reviewer": "independent-reviewer",
        "blind_to_predictions": True,
        "evidence": [
            {
                "file": case["file"],
                "symbol": "read" if case["module"] == "pkg.a" else "write",
                "reason": "The function performs this card's stated job.",
            }
        ],
    }


def test_freeze_preserves_dirty_source_and_rejects_tampering(tmp_path: Path) -> None:
    repo, snapshot = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    fixture_repo(repo)
    (repo / "pkg" / "a.py").write_text("def read():\n    return 'changed input'\n")
    (repo / "pkg" / "extra.py").write_text("def extra():\n    return 1\n")
    review.freeze(repo, snapshot)
    manifest = review.verify(snapshot)
    assert "pkg/extra.py" in manifest["files"]
    assert (snapshot / "tree/pkg/a.py").read_text() == (repo / "pkg/a.py").read_text()
    rows, counts = review.repository_cases(snapshot)
    assert counts["unclaimed_modules"] == 1
    assert next(row for row in rows if row["module"] == "pkg.extra")["reference_owner"] is None
    (snapshot / "tree/pkg/a.py").write_text("def read(): return 'tampered'\n")
    with pytest.raises(ValueError, match="snapshot files changed"):
        review.verify(snapshot)


def test_freeze_keeps_raw_hash_and_normalized_source_hash(tmp_path: Path) -> None:
    repo, snapshot = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    fixture_repo(repo)
    (repo / "pkg" / "a.py").write_bytes(b"def read():\r\n    return 'input'\r\n")
    review.freeze(repo, snapshot)
    manifest = review.verify(snapshot)
    cases, _counts = review.repository_cases(snapshot)
    case = next(row for row in cases if row["module"] == "pkg.a")
    assert manifest["files"]["pkg/a.py"] == review.digest((repo / "pkg/a.py").read_bytes())
    assert case["source_sha256"] == review.digest(case["source"].encode())
    assert manifest["files"]["pkg/a.py"] != case["source_sha256"]


def test_verify_requires_original_extractor_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, snapshot = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    fixture_repo(repo)
    review.freeze(repo, snapshot)
    monkeypatch.setattr(review, "extractor_sources_sha256", lambda: "0" * 64)
    with pytest.raises(ValueError, match="systemap source"):
        review.verify(snapshot)


def test_freeze_failure_leaves_no_partial_snapshot(tmp_path: Path) -> None:
    repo, snapshot = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    fixture_repo(repo)
    (repo / "pkg" / "linked.py").symlink_to(tmp_path / "outside.py")
    with pytest.raises(ValueError, match="symlink leaves"):
        review.freeze(repo, snapshot)
    assert not snapshot.exists()


def test_freeze_refuses_source_omitted_by_gitignore(tmp_path: Path) -> None:
    repo, snapshot = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    fixture_repo(repo)
    (repo / ".gitignore").write_text("pkg/hidden.py\n")
    (repo / "pkg" / "hidden.py").write_text("def hidden():\n    return 1\n")
    with pytest.raises(ValueError, match="Git omitted an extraction input"):
        review.freeze(repo, snapshot)
    assert not snapshot.exists()


def test_freeze_refuses_unparsed_source(tmp_path: Path) -> None:
    repo, snapshot = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    fixture_repo(repo)
    (repo / "pkg" / "broken.py").write_text("def broken(:\n")
    with pytest.raises(ValueError, match="unresolved source"):
        review.freeze(repo, snapshot)
    assert not snapshot.exists()


def test_label_and_review_packets_keep_fields_separate(tmp_path: Path) -> None:
    repo, snapshot, cases_dir = tmp_path / "repo", tmp_path / "snapshot", tmp_path / "cases"
    repo.mkdir()
    fixture_repo(repo)
    review.freeze(repo, snapshot)
    built = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "build",
            str(snapshot),
            "--out",
            str(cases_dir),
            "--seed",
            "fixed-seed",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "label packet:" in built.stdout and "review packet:" in built.stdout
    case_set = review.read_json(cases_dir / "cases.json")
    label_packet = review.read_json(cases_dir / "label-cases.json")
    review_packet = review.read_json(cases_dir / "review-cases.json")
    cases = case_set["cases"]
    assert len(cases) == 2
    assert case_set["exclusions"]["empty_markers_excluded"] == 1
    case_hash = review.digest(review.canonical(case_set))
    assert label_packet["case_set_sha256"] == case_hash
    assert review_packet["case_set_sha256"] == case_hash
    assert all(
        {"reference_owner", "planted", "candidate"}.isdisjoint(row) for row in label_packet["cases"]
    )
    assert all(
        "candidate" in row and {"reference_owner", "planted"}.isdisjoint(row)
        for row in review_packet["cases"]
    )
    assert [row["id"] for row in label_packet["cases"]] == [row["id"] for row in cases]
    assert [row["id"] for row in review_packet["cases"]] == [row["id"] for row in cases]
    assert all(set(row["cards"]) == {"Reader", "Writer", review.NONE} for row in cases)
    labels = [label_for(row, row["reference_owner"]) for row in cases]
    answers = [
        {
            "id": row["id"],
            "snapshot_id": row["snapshot_id"],
            "candidate": row["candidate"],
            "decision": "wrong" if row["planted"] else "fits",
            "better_card": row["reference_owner"] if row["planted"] else None,
        }
        for row in cases
    ]
    labels_file, answers_file = tmp_path / "labels.json", tmp_path / "answers.json"
    review.write_json(
        labels_file, {"format": review.FORMAT, "case_set_sha256": case_hash, "labels": labels}
    )
    review.write_json(
        answers_file, {"format": review.FORMAT, "case_set_sha256": case_hash, "answers": answers}
    )
    report = review.score(cases_dir / "cases.json", labels_file, answers_file)["total"]
    assert report["true_errors_detected"] == 1
    assert report["incorrect_confident_claims"] == 0
    answers.pop()
    review.write_json(
        answers_file, {"format": review.FORMAT, "case_set_sha256": case_hash, "answers": answers}
    )
    with pytest.raises(ValueError, match="each case exactly once"):
        review.score(cases_dir / "cases.json", labels_file, answers_file)


def test_workflow_scores_only_adjudicated_ownership(tmp_path: Path) -> None:
    repo, snapshot, cases_dir = tmp_path / "repo", tmp_path / "snapshot", tmp_path / "cases"
    repo.mkdir()
    fixture_repo(repo)
    review.freeze(repo, snapshot)
    review.build([snapshot], cases_dir, "fixed-seed", None)
    case_set = review.read_json(cases_dir / "cases.json")
    cases = case_set["cases"]
    target = next(row for row in cases if row["module"] == "pkg.a")
    target["reference_owner"] = "Writer"  # Synthetic reference error for the scorer contract.
    review.write_json(cases_dir / "cases.json", case_set)
    labels = [label_for(row, row["reference_owner"]) for row in cases]
    corrected = next(row for row in labels if row["id"] == target["id"])
    corrected["acceptable_cards"] = ["Reader"]
    other = next(row for row in labels if row["id"] != target["id"])
    other["status"] = "ambiguous"
    other["acceptable_cards"] = ["Reader", "Writer"]
    labels_file = tmp_path / "labels.json"
    review.write_json(
        labels_file,
        {
            "format": review.FORMAT,
            "case_set_sha256": review.digest(review.canonical(case_set)),
            "labels": labels,
        },
    )
    facts = review.read_json(snapshot / "facts.json")
    owners = {
        module: None
        for module, record in facts["components"].items()
        if not review.extract.is_empty_marker(record)
    }
    owners[target["module"]] = "Intake"
    run_file = tmp_path / "run.json"
    instructions = tmp_path / "instructions.md"
    instructions.write_text("Map the frozen fixture.\n")
    review.write_json(
        run_file,
        {
            "snapshot_id": review.verify(snapshot)["snapshot_id"],
            **workflow_binding(snapshot, tmp_path),
            "instructions_file": instructions.name,
            "instructions_sha256": review.digest(instructions.read_bytes()),
            "agent": "recorded test run",
            "cards": {"Intake": "Reads input", "Writer": "Writes output"},
            "owners": owners,
            "flows": [],
            "journeys": [],
            "invariants": [],
            "unresolved_claims": [],
        },
    )
    run = review.read_json(run_file)
    alignment_file = tmp_path / "alignment.json"
    alignment = {
        "format": review.FORMAT,
        "snapshot_id": run["snapshot_id"],
        "run_sha256": review.digest(review.canonical(run)),
        "alignments": [
            {
                "card": card,
                "status": "existing",
                "reference_card": reference,
                "reviewer": "independent-card-reviewer",
                "blind_to_scores": True,
                "evidence": "The job and owned source match the reference card.",
            }
            for card, reference in (("Intake", "Reader"), ("Writer", "Writer"))
        ],
    }
    review.write_json(alignment_file, alignment)
    report = review.score_workflow(
        snapshot, cases_dir / "cases.json", labels_file, run_file, alignment_file
    )
    assert report["inventory"]["modules"] == len(owners)
    assert report["ownership"]["ambiguous_unscored"] == 1
    assert report["ownership"]["true_error_corrections"] == 1
    assert report["unscored_claim_types"] == ["flows", "journeys", "invariants"]
    alignment["run_sha256"] = "0" * 64
    review.write_json(alignment_file, alignment)
    with pytest.raises(ValueError, match="different workflow run"):
        review.score_workflow(
            snapshot, cases_dir / "cases.json", labels_file, run_file, alignment_file
        )
    result = json.loads(run_file.read_text())
    result["owners"].pop(target["module"])
    review.write_json(run_file, result)
    with pytest.raises(ValueError, match="every extracted module"):
        review.validate_workflow(snapshot, run_file)


def test_new_card_label_rejects_existing_owner_and_leaves_new_card_pending(
    tmp_path: Path,
) -> None:
    repo, snapshot, cases_dir = tmp_path / "repo", tmp_path / "snapshot", tmp_path / "cases"
    repo.mkdir()
    fixture_repo(repo)
    review.freeze(repo, snapshot)
    review.build([snapshot], cases_dir, "fixed-seed", None)
    case_set = review.read_json(cases_dir / "cases.json")
    cases = case_set["cases"]
    target = next(row for row in cases if row["module"] == "pkg.a")
    labels = [label_for(row, row["reference_owner"]) for row in cases]
    new = next(row for row in labels if row["id"] == target["id"])
    new.update(status="new_card", acceptable_cards=[], proposed_card="Dedicated input reader")
    labels_file = tmp_path / "labels.json"
    review.write_json(
        labels_file,
        {
            "format": review.FORMAT,
            "case_set_sha256": review.digest(review.canonical(case_set)),
            "labels": labels,
        },
    )
    facts = review.read_json(snapshot / "facts.json")
    owners = {
        module: "Replacement"
        for module, record in facts["components"].items()
        if not review.extract.is_empty_marker(record)
    }
    instructions = tmp_path / "instructions.md"
    instructions.write_text("Map the frozen fixture.\n")
    run_file = tmp_path / "run.json"
    run = {
        "snapshot_id": review.verify(snapshot)["snapshot_id"],
        **workflow_binding(snapshot, tmp_path),
        "instructions_file": instructions.name,
        "instructions_sha256": review.digest(instructions.read_bytes()),
        "agent": "recorded test run",
        "cards": {"Replacement": "Owns a module"},
        "owners": owners,
        "flows": [],
        "journeys": [],
        "invariants": [],
        "unresolved_claims": [],
    }
    review.write_json(run_file, run)
    alignment_file = tmp_path / "alignment.json"
    alignment = {
        "format": review.FORMAT,
        "snapshot_id": run["snapshot_id"],
        "run_sha256": review.digest(review.canonical(run)),
        "alignments": [
            {
                "card": "Replacement",
                "status": "existing",
                "reference_card": "Reader",
                "reviewer": "independent-card-reviewer",
                "blind_to_scores": True,
                "evidence": "This card still carries the Reader job.",
            }
        ],
    }
    review.write_json(alignment_file, alignment)
    report = review.score_workflow(
        snapshot, cases_dir / "cases.json", labels_file, run_file, alignment_file
    )
    assert report["ownership"]["new_card_existing_owner_wrong_confident"] == 1
    alignment["alignments"][0]["status"] = "new"
    alignment["alignments"][0]["reference_card"] = None
    review.write_json(alignment_file, alignment)
    report = review.score_workflow(
        snapshot, cases_dir / "cases.json", labels_file, run_file, alignment_file
    )
    assert report["ownership"]["new_card_new_unscored"] == 1
    assert report["ownership"].get("new_card_existing_owner_wrong_confident", 0) == 0


def test_freeze_retains_dirty_tracked_deletions(tmp_path: Path) -> None:
    repo, snapshot = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    fixture_repo(repo)
    (repo / "pkg/b.py").unlink()
    review.freeze(repo, snapshot)
    manifest = review.verify(snapshot)
    assert "pkg/b.py" not in manifest["files"]
    facts = review.read_json(snapshot / "facts.json")
    assert set(facts["components"]) == {"pkg", "pkg.a"}


def test_freeze_refuses_deletion_during_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, snapshot = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    fixture_repo(repo)
    original = review.copy_visible_file

    def copy_then_delete(root, target, rel, visible):
        result = original(root, target, rel, visible)
        if rel == Path("pkg/b.py"):
            (root / rel).unlink()
        return result

    monkeypatch.setattr(review, "copy_visible_file", copy_then_delete)
    with pytest.raises(ValueError, match="source changed|source tree changed"):
        review.freeze(repo, snapshot)
    assert not snapshot.exists()


def test_workflow_input_excludes_reference_artefacts(tmp_path: Path) -> None:
    repo, snapshot, destination = tmp_path / "repo", tmp_path / "snapshot", tmp_path / "input"
    repo.mkdir()
    fixture_repo(repo)
    (repo / "docs/map").mkdir(parents=True)
    (repo / "docs/map/map.json").write_text('{"Reader": "pkg.a"}')
    (repo / "docs/map/index.html").write_text("Reader owns pkg.a")
    (repo / "cases.json").write_text('{"reference_owner": "Reader"}')
    (repo / "tests").mkdir()
    (repo / "tests/test_reader.py").write_text(
        "from pkg.a import read\ndef test_read(): assert read() == 'input'\n"
    )
    (repo / "tests/conftest.py").write_text("FIXTURE = 'test support'\n")
    (repo / "package.json").write_text('{"name": "fixture"}')
    review.freeze(repo, snapshot)
    identity = review.workflow_input.prepare(
        snapshot,
        destination,
        review.verify(snapshot),
        review.read_json(snapshot / "facts.json"),
        ["package.json"],
    )
    files = {
        p.relative_to(destination / "tree").as_posix()
        for p in (destination / "tree").rglob("*")
        if p.is_file()
    }
    assert files == {
        "pkg/__init__.py",
        "pkg/a.py",
        "pkg/b.py",
        "source-config.json",
        "package.json",
        "tests/test_reader.py",
        "tests/conftest.py",
    }
    assert (snapshot / "tree/map/model.py").is_file()
    result = {"workflow_input": "input", "workflow_input_sha256": identity}
    review.workflow_input.verify(
        snapshot,
        review.verify(snapshot),
        review.read_json(snapshot / "facts.json"),
        result,
        tmp_path / "run.json",
    )
    with pytest.raises(ValueError, match="reference artefacts"):
        review.workflow_input.prepare(
            snapshot,
            tmp_path / "bad",
            review.verify(snapshot),
            review.read_json(snapshot / "facts.json"),
            ["map/model.py"],
        )


@pytest.mark.parametrize("tamper", ["source", "extra_map", "manifest", "missing_binding"])
def test_workflow_refuses_changed_or_unbound_input(tmp_path: Path, tamper: str) -> None:
    repo, snapshot = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    fixture_repo(repo)
    review.freeze(repo, snapshot)
    result = workflow_binding(snapshot, tmp_path)
    supplied = tmp_path / "workflow-input"
    if tamper == "source":
        (supplied / "tree/pkg/a.py").write_text("def read(): return 'tampered'\n")
    elif tamper == "extra_map":
        (supplied / "tree/model.py").write_text((snapshot / "tree/map/model.py").read_text())
    elif tamper == "manifest":
        manifest = review.read_json(supplied / "manifest.json")
        manifest["files"]["pkg/a.py"] = "0" * 64
        review.write_json(supplied / "manifest.json", manifest)
        result["workflow_input_sha256"] = review.digest(review.canonical(manifest))
    else:
        result.pop("workflow_input_sha256")
    with pytest.raises(ValueError, match="workflow input"):
        review.workflow_input.verify(
            snapshot,
            review.verify(snapshot),
            review.read_json(snapshot / "facts.json"),
            result,
            tmp_path / "run.json",
        )


@pytest.mark.parametrize("alias", ["source", "config"])
def test_workflow_refuses_symlink_alias_to_reference_artefacts(tmp_path: Path, alias: str) -> None:
    repo, snapshot = tmp_path / "repo", tmp_path / "snapshot"
    repo.mkdir()
    fixture_repo(repo)
    configs = []
    if alias == "source":
        (repo / "map/helper.py").write_text("REFERENCE_OWNER = 'Reader'\n")
        (repo / "pkg/leaked.py").symlink_to("../map/helper.py")
    else:
        (repo / "map/package.json").write_text('{"reference_owner": "Reader"}')
        (repo / "package.json").symlink_to("map/package.json")
        configs = ["package.json"]
    review.freeze(repo, snapshot)
    with pytest.raises(ValueError, match="reference artefacts"):
        review.workflow_input.prepare(
            snapshot,
            tmp_path / "input",
            review.verify(snapshot),
            review.read_json(snapshot / "facts.json"),
            configs,
        )
