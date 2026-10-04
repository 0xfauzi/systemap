"""The page preserves known facts and names uncertainty without substituting data.

Acceptance: zero lost unknown issues or valid symbol records; both resolved
commits and the actual comparison base are present; every invalid comparison
raises rather than returning a successful empty result.
"""

from __future__ import annotations

import copy
import dataclasses
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample

from systemap import change, extract, page_data
from systemap.model import Component


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def committed_sample(sample: Sample) -> str:
    root = sample.cfg.root
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "Page data test")
    git(root, "config", "user.email", "page-data@example.test")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    return git(root, "rev-parse", "HEAD")


def test_source_record_keeps_unknowns_and_public_name_provenance(sample: Sample) -> None:
    facts = copy.deepcopy(sample.facts)
    issue = {"line": 7, "reason": "The export could not be classified.", "source": "export value"}
    record = facts["components"]["pkg.reader"]
    record["unknown"] = [issue]
    record["names"] = [{"name": "Request", "kind": "class", "reexport_of": "pkg.types"}]
    record["external"] = ["other.package"]
    record["imported_by"] = ["pkg.writer"]
    source = page_data.sources(sample.model, facts)["Reader"]["modules"][0]
    assert source["unknown"] == [issue]
    assert source["public_names"] == record["names"]
    assert source["names"] == ["Request"]
    assert source["external"] == ["other.package"]
    assert source["imported_by"] == ["pkg.writer"]


def test_symbol_claims_have_source_records_and_missing_claims_are_explicit(sample: Sample) -> None:
    component = Component(
        "Symbol",
        "Defines one operation.",
        implemented_by=("pkg.reader:read", "pkg.reader:missing", "pkg.missing", "pkg.writer.*"),
    )
    model = dataclasses.replace(sample.model, components=(component,))
    source = page_data.sources(model, sample.facts)["Symbol"]
    assert {m["id"] for m in source["modules"]} == {"pkg.reader", "pkg.writer"}
    assert source["unresolved_claims"] == ["pkg.reader:missing", "pkg.missing"]
    assert source["symbol_claims"] == [
        {"module": "pkg.reader", "name": "read"},
        {"module": "pkg.reader", "name": "missing"},
    ]


def test_older_facts_do_not_turn_public_names_into_an_empty_surface(sample: Sample) -> None:
    record = dict(sample.facts["components"]["pkg.reader"])
    record.pop("names")
    facts = {"components": {"pkg.reader": record}}
    source = page_data.sources(sample.model, facts)["Reader"]["modules"][0]
    assert "read" in source["names"]
    assert {"name": "Request", "kind": "class"} in source["public_names"]


def test_provenance_names_head_without_claiming_the_working_tree_is_clean(sample: Sample) -> None:
    facts = dict(sample.facts)
    facts["built_at_commit"] = "recorded-head"
    provenance = page_data.provenance(sample.cfg, facts, "map/child.py")
    assert provenance["revision"] == "recorded-head"
    assert provenance["model_file"] == "map/child.py"
    assert provenance["facts_file"] == f"{sample.cfg.out_dir}/{sample.cfg.facts_file}"
    assert provenance["extraction"] == "working tree"
    assert provenance["uncommitted"] == "not recorded"
    assert provenance["unknown"] == extract.unknown_fact_lines(facts)


def test_a_requested_zero_change_comparison_keeps_its_resolved_revisions(sample: Sample) -> None:
    revision = committed_sample(sample)
    result = change.compute(sample.cfg, sample.model, "main", sample.facts)
    assert not result["has_change"]
    data = page_data.comparison(result)
    assert data["base_revision"] == data["head_revision"] == revision
    assert data["comparison_base"] == revision
    assert data["direct"] == []
    assert page_data.comparison({}) == {}


@pytest.mark.parametrize("base,head", [("absent-ref", "HEAD"), ("HEAD", "absent-ref")])
def test_an_unresolved_revision_fails_instead_of_becoming_no_comparison(
    sample: Sample, base: str, head: str
) -> None:
    committed_sample(sample)
    with pytest.raises(change.ChangeError, match="unknown revision absent-ref"):
        change.compute(sample.cfg, sample.model, base, sample.facts, head)


def test_unrelated_histories_fail_instead_of_becoming_no_comparison(sample: Sample) -> None:
    committed_sample(sample)
    git(sample.cfg.root, "checkout", "--orphan", "unrelated")
    git(sample.cfg.root, "commit", "-qm", "unrelated root")
    with pytest.raises(change.ChangeError, match="no common ancestor"):
        change.compute(sample.cfg, sample.model, "main", sample.facts, "unrelated")


def test_comparison_names_the_merge_base_and_preserves_unparsed_modules(sample: Sample) -> None:
    base = committed_sample(sample)
    root = sample.cfg.root
    git(root, "checkout", "-qb", "feature")
    (root / "pkg/reader.py").write_text("def broken(\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "unparsed source")
    head = git(root, "rev-parse", "HEAD")
    git(root, "checkout", "-q", "main")
    (root / "note.txt").write_text("The base branch moved.\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "later base")
    requested_base = git(root, "rev-parse", "HEAD")
    data = page_data.comparison(
        change.compute(sample.cfg, sample.model, "main", sample.facts, "feature")
    )
    assert data["base_revision"] == requested_base
    assert data["head_revision"] == head
    assert data["comparison_base"] == base
    assert data["unparsed"] == ["pkg.reader"]


def test_comparison_keeps_unknown_surface_details_and_unknown_import_reach() -> None:
    issue = {"line": 3, "reason": "Unknown export"}
    parts: dict[str, Any] = {"Api": {"unknown": {"pkg.api": {"base": [], "head": [issue]}}}}
    data = page_data.comparison(
        {
            "has_change": True,
            "base": "base",
            "head": "head",
            "direct": {"Api"},
            "adjacent": set(),
            "per_component": parts,
            "reach_known": False,
            "unparsed": [],
        }
    )
    assert data["parts"] == parts
    assert data["reach_known"] is False
