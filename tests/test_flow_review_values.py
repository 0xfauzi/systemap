"""The documented command gives the values that an observed flow needs.

The skill reference and docs/reference.md give one command. It prints the
`source_sha256` of each module and the `review_digest` of each flow. This test runs that
command on a fixture project and records the printed values in a flow claim.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import config, evidence, extract

ROOT = Path(__file__).resolve().parents[1]
MARK = "prints the `source_sha256` of each module and the `review_digest` of each flow"
DOCS = (ROOT / "src/systemap/skill/references/schema.md", ROOT / "docs/reference.md")


def documented_command(doc: Path) -> str:
    """Give the Python text of the command after the mark in a document."""
    text = doc.read_text(encoding="utf-8")
    assert MARK in text, f"{doc} has no command for the flow review values"
    after = text[text.index(MARK) :]
    start = after.index("<<'PY'\n") + len("<<'PY'\n")
    return after[start : after.index("\nPY\n", start)]


@pytest.mark.parametrize("doc", DOCS, ids=lambda doc: doc.name)
def test_the_documented_command_gives_the_values_for_an_observed_flow(
    tmp_path: Path, doc: Path
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    printed = subprocess.run(
        [sys.executable, "-"],
        input=documented_command(doc),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.splitlines()
    hashes = {line.split()[1]: line.split()[-1] for line in printed if line.startswith("source")}
    digests = [line.split()[-1] for line in printed if line.startswith("review_digest Reader ->")]
    assert set(hashes) == {"pkg", "pkg.reader", "pkg.writer"}
    assert len(digests) == 1

    cfg = config.load(tmp_path)
    model, meaning = config.load_model(cfg.model_path)
    (flow,) = model.flows
    reviewed = dataclasses.replace(
        flow,
        source_refs=(f"pkg.reader@{hashes['pkg.reader']}", f"pkg.writer@{hashes['pkg.writer']}"),
        review_digest=digests[0],
    )
    model = dataclasses.replace(model, flows=(reviewed,))
    states = evidence.of_model(model, meaning, extract.build(cfg))
    assert states[("Reader", "Writer")].state == evidence.OBSERVED
