"""systemap review writes the current review digest of one named target into the model.

Acceptance:
- After `systemap review X`, `card_review.state` for X is `current`. The model file
  differs from before only in the `source_review` value of X.
- After `systemap review --flow A->B`, the review digest of the flow agrees with the flow
  claim. The file that defines the flow differs only in that value.
- A target with no usable source snapshot gives exit 1, and the file does not change.
- An unknown target gives exit 1, and the file does not change.
- A model that the reader cannot read as data gives exit 1, and the file does not change.
- `--dry-run` prints the digest and the file, and it writes nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import STARTER_MODULES, TWO_CARD_MODEL, init_two_cards, write_tree

from systemap import card_review, config, evidence, extract, model_edit, model_load, nest
from systemap.cli import main


def _project(tmp_path: Path, model: str = TWO_CARD_MODEL) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    path = tmp_path / "map/model.py"
    path.write_text(model, encoding="utf-8")
    return path


def _top(root: Path) -> nest.Map:
    return nest.load(config.load(root)).top


def _facts(root: Path) -> dict[str, object]:
    return extract.build(config.load(root))


def _review(root: Path, *argv: str) -> int:
    return main(["--root", str(root), "review", *argv])


def _changed_lines(before: str, after: str) -> list[tuple[str, str]]:
    """Give the line pairs that differ. Both texts must have the same number of lines."""
    old, new = before.splitlines(), after.splitlines()
    assert len(old) == len(new)
    return [(a, b) for a, b in zip(old, new, strict=True) if a != b]


def _flow_project(tmp_path: Path) -> tuple[Path, Path]:
    """Put the flows in a second file, with a source record for each endpoint module."""
    path = _project(tmp_path)
    facts = _facts(tmp_path)
    refs = tuple(
        f"pkg.{name}@{facts['components'][f'pkg.{name}']['source_sha256']}"  # type: ignore[index]
        for name in ("reader", "writer")
    )
    flows = (
        '"""The flows."""\n\nfrom __future__ import annotations\n\n'
        "from systemap import Flow\n\n"
        "# the one flow\n"
        "FLOWS = (\n"
        '    Flow("Reader", "Writer", "request", "data",\n'
        f"         source_refs={refs!r}),  # a comment that stays\n"
        ")\n"
    )
    (tmp_path / "map/flows.py").write_text(flows, encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'FLOWS = (Flow("Reader", "Writer", "request", "data"),)', "FLOWS = flows.FLOWS"
    )
    text = text.replace("from systemap import (", "import flows\n\nfrom systemap import (")
    path.write_text(text, encoding="utf-8")
    return path, tmp_path / "map/flows.py"


def test_review_writes_only_the_source_review_of_the_named_component(tmp_path: Path) -> None:
    """Acceptance: the state is `current`. The file differs only in the value of Reader."""
    path = _project(tmp_path)
    before = path.read_text(encoding="utf-8")
    assert _review(tmp_path, "Reader") == 0
    m = _top(tmp_path)
    facts = _facts(tmp_path)
    reader = m.model.component("Reader")
    writer = m.model.component("Writer")
    assert reader is not None and writer is not None
    assert card_review.state(reader, m.model, m.meaning, facts) == card_review.CURRENT
    assert card_review.state(writer, m.model, m.meaning, facts) == card_review.MISSING
    digest = card_review.digest(reader, m.model, m.meaning, facts)
    after = path.read_text(encoding="utf-8")
    added = f'        source_review="{digest}",\n'
    at = before.index('        x=80,\n        y=130,\n    ),\n    Component(\n        id="Writer"')
    at += len("        x=80,\n        y=130,\n")
    assert after == before[:at] + added + before[at:]

    # A second review after a source change replaces the value in place.
    (tmp_path / "pkg/reader.py").write_text(
        "def read(source: str) -> str:\n    return source.strip()\n", encoding="utf-8"
    )
    m = _top(tmp_path)
    facts = _facts(tmp_path)
    reader = m.model.component("Reader")
    assert reader is not None
    assert card_review.state(reader, m.model, m.meaning, facts) == card_review.STALE
    assert _review(tmp_path, "Reader") == 0
    new = card_review.digest(reader, m.model, m.meaning, facts)
    again = path.read_text(encoding="utf-8")
    assert _changed_lines(after, again) == [(added.rstrip("\n"), f'        source_review="{new}",')]
    m = _top(tmp_path)
    reader = m.model.component("Reader")
    assert reader is not None
    assert card_review.state(reader, m.model, m.meaning, facts) == card_review.CURRENT


def test_review_flow_writes_only_the_review_digest_in_the_file_that_defines_the_flow(
    tmp_path: Path,
) -> None:
    """Acceptance: the flow review digest is current. Only that value changes, in flows.py."""
    path, flows = _flow_project(tmp_path)
    model_before = path.read_text(encoding="utf-8")
    flows_before = flows.read_text(encoding="utf-8")
    assert _review(tmp_path, "--flow", "Reader->Writer") == 0
    assert path.read_text(encoding="utf-8") == model_before
    m = _top(tmp_path)
    flow = m.model.flows[0]
    digest = evidence.flow_claim_digest(flow, m.meaning)
    assert flow.review_digest == digest
    states = evidence.of_model(m.model, m.meaning, _facts(tmp_path))
    assert states[flow.edge].state == evidence.OBSERVED
    after = flows.read_text(encoding="utf-8")
    old_line = next(line for line in flows_before.splitlines() if "source_refs=" in line)
    new_line = old_line.replace(")),  # a comment", "),\n         review_digest=X),  # a comment")
    new_line = new_line.replace("X", f'"{digest}"')
    assert after == flows_before.replace(old_line, new_line)


def test_review_refuses_a_target_without_a_usable_source_snapshot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: exit 1, and the file does not change."""
    path = _project(tmp_path)
    (tmp_path / "pkg/reader.py").write_text("def read(:\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert _review(tmp_path, "Reader") == 1
    assert path.read_text(encoding="utf-8") == before
    assert "has no current digest" in capsys.readouterr().err


def test_review_refuses_a_flow_without_current_source_records(tmp_path: Path) -> None:
    """Acceptance: exit 1, and the file does not change."""
    path = _project(tmp_path)
    before = path.read_text(encoding="utf-8")
    assert _review(tmp_path, "--flow", "Reader->Writer") == 1
    assert path.read_text(encoding="utf-8") == before


@pytest.mark.parametrize(
    "argv", [("Nobody",), ("--flow", "Reader->Nobody"), ("--flow", "Writer->Reader")]
)
def test_review_refuses_an_unknown_target(tmp_path: Path, argv: tuple[str, ...]) -> None:
    """Acceptance: exit 1, and the file does not change."""
    path = _project(tmp_path)
    before = path.read_text(encoding="utf-8")
    assert _review(tmp_path, *argv) == 1
    assert path.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("trust", ["", "1"])
def test_review_refuses_a_model_that_is_not_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, trust: str
) -> None:
    """Acceptance: exit 1, and the file does not change, with or without permission."""
    tail = "\nfrom dataclasses import replace\n\nMEANING = replace(MEANING, plain={})\n"
    path = _project(tmp_path, TWO_CARD_MODEL + tail)
    if trust:
        monkeypatch.setenv(model_load.TRUST, trust)
    else:
        monkeypatch.delenv(model_load.TRUST, raising=False)
    before = path.read_text(encoding="utf-8")
    assert _review(tmp_path, "Reader") == 1
    assert path.read_text(encoding="utf-8") == before


def test_review_dry_run_prints_the_digest_and_the_file_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: the output has the digest and the file. The file does not change."""
    path = _project(tmp_path)
    before = path.read_text(encoding="utf-8")
    assert _review(tmp_path, "--dry-run", "Reader") == 0
    assert path.read_text(encoding="utf-8") == before
    m = _top(tmp_path)
    reader = m.model.component("Reader")
    assert reader is not None
    digest = card_review.digest(reader, m.model, m.meaning, _facts(tmp_path))
    out = capsys.readouterr().out
    assert str(digest) in out and "map/model.py" in out


def test_review_takes_one_target_only(tmp_path: Path) -> None:
    """Acceptance: no target, two targets, or a flow without `->` gives an option error."""
    _project(tmp_path)
    with pytest.raises(SystemExit):
        _review(tmp_path)
    with pytest.raises(SystemExit):
        _review(tmp_path, "Reader", "--flow", "Reader->Writer")
    assert _review(tmp_path, "--flow", "Reader") == 2


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            'X = (C(id="a", does="b"),)\n',
            'X = (C(id="a", does="b", k="v"),)\n',
        ),
        (
            'X = (C(id="a", does="b",),)\n',
            'X = (C(id="a", does="b", k="v",),)\n',
        ),
        (
            'X = (\n    C(\n        id="a",\n        does="b"  # note\n    ),\n)\n',
            'X = (\n    C(\n        id="a",\n        does="b",  # note\n        k="v",\n    ),\n)\n',
        ),
        (
            'X = (\n    C("a", "b",\n      k="old"),  # note\n)\n',
            'X = (\n    C("a", "b",\n      k="v"),  # note\n)\n',
        ),
        (
            'X = (\n    C("a", "b",\n      j=1),\n)\n',
            'X = (\n    C("a", "b",\n      j=1,\n      k="v"),\n)\n',
        ),
        (
            'X = (C(id="é", does="éé", k="old"),)\n',
            'X = (C(id="é", does="éé", k="v"),)\n',
        ),
    ],
)
def test_set_keyword_keeps_the_rest_of_the_source(source: str, expected: str) -> None:
    """Acceptance: only the keyword value changes, or one keyword is added."""
    import ast

    call = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call))
    assert model_edit.set_keyword(source, call, "k", "v") == expected


TYPESCRIPT_TREE = {
    "tsconfig.json": '{"compilerOptions":{}}',
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "src/reader.ts": "export function read(source: string): string { return source }\n",
    "src/writer.ts": (
        'import { read } from "./reader";\n'
        "export function write(request: string): string { return read(request) }\n"
    ),
}


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_review_works_the_same_for_each_source_language(tmp_path: Path, language: str) -> None:
    """Acceptance: for a Python and a TypeScript repository, the component state and the
    flow state are current after one review each. An unknown target gives exit 1."""
    if language == "python":
        _project(tmp_path)
        prefix = "pkg"
    else:
        write_tree(tmp_path, TYPESCRIPT_TREE)
        (tmp_path / "map").mkdir()
        model = TWO_CARD_MODEL.replace('"pkg.', '"web.')
        (tmp_path / "map/model.py").write_text(model, encoding="utf-8")
        prefix = "web"
    facts = _facts(tmp_path)
    refs = tuple(
        f"{prefix}.{name}@{facts['components'][f'{prefix}.{name}']['source_sha256']}"  # type: ignore[index]
        for name in ("reader", "writer")
    )
    path = tmp_path / "map/model.py"
    text = path.read_text(encoding="utf-8").replace(
        'Flow("Reader", "Writer", "request", "data")',
        f'Flow("Reader", "Writer", "request", "data", source_refs={refs!r})',
    )
    path.write_text(text, encoding="utf-8")
    assert _review(tmp_path, "Writer") == 0
    assert _review(tmp_path, "--flow", "Reader -> Writer") == 0
    m = _top(tmp_path)
    writer = m.model.component("Writer")
    # The claims of Writer include the flow digest, so its review becomes stale.
    assert card_review.state(writer, m.model, m.meaning, facts) == card_review.STALE
    assert _review(tmp_path, "Writer") == 0
    m = _top(tmp_path)
    writer = m.model.component("Writer")
    assert card_review.state(writer, m.model, m.meaning, facts) == card_review.CURRENT
    states = evidence.of_model(m.model, m.meaning, facts)
    assert states[("Reader", "Writer")].state == evidence.OBSERVED
    before = path.read_text(encoding="utf-8")
    assert _review(tmp_path, "Nobody") == 1
    assert path.read_text(encoding="utf-8") == before
