"""The documented procedure gives the values that an observed flow needs.

The skill reference and docs/reference.md tell the agent to read `source_sha256` from the
facts file and to run `systemap review --flow 'SRC->DST'` for the review digest. This test
does that procedure on a fixture project.

Acceptance: the two documents give the procedure, and after it the flow is `observed`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import config, evidence, extract
from systemap.cli import main

ROOT = Path(__file__).resolve().parents[1]
MARKS = (
    "gives the `source_sha256` of each module in `components`",
    "`systemap review --flow 'SRC->DST'` writes the current `review_digest` of one flow",
)
DOCS = (ROOT / "src/systemap/skill/references/schema.md", ROOT / "docs/reference.md")


@pytest.mark.parametrize("doc", DOCS, ids=lambda doc: doc.name)
def test_the_documented_procedure_gives_the_values_for_an_observed_flow(
    tmp_path: Path, doc: Path
) -> None:
    text = doc.read_text(encoding="utf-8")
    for mark in MARKS:
        assert mark in text, f"{doc} has no procedure for the flow review values"
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    cfg = config.load(tmp_path)
    facts = json.loads(cfg.facts_path.read_text(encoding="utf-8"))
    hashes = {name: record["source_sha256"] for name, record in facts["components"].items()}
    refs = (f"pkg.reader@{hashes['pkg.reader']}", f"pkg.writer@{hashes['pkg.writer']}")
    model_text = cfg.model_path.read_text(encoding="utf-8").replace(
        'Flow("Reader", "Writer", "request", "data")',
        f'Flow("Reader", "Writer", "request", "data", source_refs={refs!r})',
    )
    cfg.model_path.write_text(model_text, encoding="utf-8")
    assert main(["--root", str(tmp_path), "review", "--flow", "Reader->Writer"]) == 0

    model, meaning = config.load_model(cfg.model_path)
    states = evidence.of_model(model, meaning, extract.build(cfg))
    assert states[("Reader", "Writer")].state == evidence.OBSERVED
