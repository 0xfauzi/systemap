"""The evidence digest of an exact answer contains only the evidence that its line names.

Acceptance values:

1. A change to the claims of a different component does not change the evidence of a line.
2. A change to a `source_review` value does not change the evidence of a line. This
   includes `systemap review` of a different component and a new value of the named
   component.
   A new source digest in a flow source record (`source_refs`) also does not change it.
3. A change to the source of a named module changes the evidence of the line.
4. A change to a claim of a named component (its `does` text) changes the evidence.
5. Acceptance values 1 to 4 hold for a Python fixture and a TypeScript fixture.
6. The `single module` answers of this repository stay valid after a `systemap review` of a
   different component.
7. A line that names no component and no module keeps the full evidence: the model file
   and all module facts.
"""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import pytest
from conftest import init_two_cards, write_tree

from systemap import config, extract, judgement, nest
from systemap.cli import main

REPOSITORY = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "typescript-app"
SOURCE = {
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "from pkg.reader import read\n\n\ndef write(request: str) -> str:\n    return read(request)\n",
}
# The named component, its module, its file, a new source, and the other component.
CASES = {
    "python": (
        "Reader",
        "pkg.reader",
        "pkg/reader.py",
        "def read(source: str) -> str:\n    return source.strip()\n",
        "Writer",
    ),
    "typescript": (
        "Service",
        "acme.web.service",
        "src/service.ts",
        None,
        "Application",
    ),
}
# The TypeScript fixture has one component. This component takes one of its modules.
SERVICE = """    Component(
        id="Service",
        does="Keeps the users of the application.",
        implemented_by=("acme.web.service",),
        entry="serve",
        region="application",
        x=420,
        y=120,
    ),
"""


@pytest.fixture(params=["python", "typescript"])
def project(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """A mapped project with two components, one of them with a single module."""
    if request.param == "python":
        write_tree(tmp_path, SOURCE)
        init_two_cards(tmp_path, "--no-ci")
    else:
        shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
        model = tmp_path / "map" / "model.py"
        text = model.read_text(encoding="utf-8")
        text = text.replace('            "acme.web.service",\n', "")
        text = text.replace("COMPONENTS = (\n", "COMPONENTS = (\n" + SERVICE)
        text = text.replace(
            '"Application": "the application"',
            '"Application": "the application", "Service": "the users"',
        )
        model.write_text(text, encoding="utf-8")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return tmp_path


def case(root: Path) -> tuple[str, str, str, str | None, str]:
    return CASES[config.load(root).language]


def line_of(root: Path) -> str:
    card, module, *_rest = case(root)
    return f"single module: {card} contains only {module}"


def evidence(root: Path, line: str) -> str:
    cfg = config.load(root)
    tree = nest.load(cfg)
    facts = extract.build(cfg)
    assert line in judgement.run_tree(tree, facts)
    return judgement.evidence_for_tree(tree, facts, root, [line])[line]


def replace_in_model(root: Path, old: str, new: str) -> None:
    path = root / "map" / "model.py"
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def does_of(root: Path, card_id: str) -> str:
    card = nest.load(config.load(root)).top.model.component(card_id)
    assert card is not None
    return card.does


def test_a_different_component_does_not_change_the_evidence(project: Path) -> None:
    """Acceptance 1 and 5."""
    line = line_of(project)
    before = evidence(project, line)
    other = case(project)[4]
    sentence = does_of(project, other)
    replace_in_model(project, sentence, sentence.replace(".", " and more."))
    assert evidence(project, line) == before


def test_a_source_review_value_does_not_change_the_evidence(project: Path) -> None:
    """Acceptance 2 and 5."""
    line = line_of(project)
    before = evidence(project, line)
    card, _module, _file, _new, other = case(project)
    assert main(["--root", str(project), "review", other]) == 0
    assert evidence(project, line) == before
    assert main(["--root", str(project), "review", card]) == 0
    assert evidence(project, line) == before


def test_the_source_of_a_named_module_changes_the_evidence(project: Path) -> None:
    """Acceptance 3 and 5."""
    line = line_of(project)
    before = evidence(project, line)
    _card, _module, name, new, _other = case(project)
    path = project / name
    path.write_text(new or path.read_text(encoding="utf-8") + "\nexport const added = 1;\n")
    assert evidence(project, line) != before


def test_a_claim_of_a_named_component_changes_the_evidence(project: Path) -> None:
    """Acceptance 4 and 5."""
    line = line_of(project)
    before = evidence(project, line)
    card = case(project)[0]
    sentence = does_of(project, card)
    replace_in_model(project, sentence, sentence.replace(".", " and more."))
    assert evidence(project, line) != before


def test_a_line_without_names_keeps_the_full_evidence(tmp_path: Path) -> None:
    """Acceptance 7: a change to a different component changes the evidence of this line."""
    write_tree(tmp_path, SOURCE)
    init_two_cards(tmp_path, "--no-ci")
    cfg = config.load(tmp_path)
    tree = nest.load(cfg)
    facts = extract.build(cfg)
    line = "thin layer: nothing shows 0 components"
    before = judgement.evidence_for_tree(tree, facts, tmp_path, [line])[line]
    replace_in_model(tmp_path, "Takes a request", "Takes one request")
    after = judgement.evidence_for_tree(nest.load(cfg), facts, tmp_path, [line])[line]
    assert after != before


def test_the_answers_of_this_repository_stay_valid_after_a_different_review(
    tmp_path: Path,
) -> None:
    """Acceptance 6: a new `source_review` value of a different component keeps the digests.

    The test writes the changed model file in a temporary directory, not in the repository.
    """
    cfg = config.load(REPOSITORY)
    tree = nest.load(cfg)
    facts = extract.read_facts(cfg.facts_path)
    assert facts is not None
    lines = [
        item
        for answer in cfg.judgement_answered
        for item in answer.items
        if item.startswith("single module: ")
    ]
    assert len(lines) == 6
    before = judgement.evidence_for_tree(tree, facts, REPOSITORY, lines)
    named = {line.split()[2] for line in lines}
    top = tree.top
    other = next(c for c in top.model.components if c.id not in named and c.source_review)
    reviewed = "0" * 64
    copy = tmp_path / "model.py"
    text = top.path.read_text(encoding="utf-8")
    assert text.count(other.source_review) == 1
    copy.write_text(text.replace(other.source_review, reviewed), encoding="utf-8")
    components = tuple(
        dataclasses.replace(c, source_review=reviewed) if c.id == other.id else c
        for c in top.model.components
    )
    model = dataclasses.replace(top.model, components=components)
    changed = dataclasses.replace(top, path=copy, model=model)
    after = judgement.evidence_for_tree(
        nest.Tree((changed, *tree.maps[1:])), facts, REPOSITORY, lines
    )
    assert after == before


def test_a_source_digest_in_a_flow_record_does_not_change_the_evidence(tmp_path: Path) -> None:
    """Acceptance 2: the location in a source record is a claim, but its digest is not."""
    write_tree(tmp_path, SOURCE)
    init_two_cards(tmp_path, "--no-ci")
    line = "single module: Reader contains only pkg.reader"
    old = 'Flow("Reader", "Writer", "request", "data")'
    replace_in_model(tmp_path, old, old[:-1] + f', source_refs=("pkg.reader@{"a" * 64}",))')
    before = evidence(tmp_path, line)
    replace_in_model(tmp_path, "a" * 64, "b" * 64)
    assert evidence(tmp_path, line) == before
    replace_in_model(tmp_path, f"pkg.reader@{'b' * 64}", f"pkg.writer@{'b' * 64}")
    assert evidence(tmp_path, line) != before
