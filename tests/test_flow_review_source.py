"""A flow review digest contains the source records: a module change makes it stale (issue 49).

Acceptance values, for a Python fixture and a TypeScript fixture:

1. After `systemap review --flow`, the flow review is current: `flow_review.state` is
   `current`, the evidence state is `observed`, `decisions pending` gives no `flow_review`
   request, and `judgement --json` gives no line and no earlier review for the flow.
2. A change to a module in the source records, with the same claim, makes the review stale.
   `decisions pending` gives a `flow_review` request.
3. After the source records get the new module digests with no new review, the review
   stays stale. `decisions pending` gives a `flow_review` request with a digest, and
   `judgement --json` gives an open `flow review` line for the flow.
4. A flow without source records never has a current review, also with a review digest.
5. A flow with a source record that does not agree with the facts never has a current
   review. Its request has no digest and is blocked.
6. A review digest from systemap 2.0.0 gives the state `earlier`, not `stale`.
   `judgement` gives the label "review earlier than source tracking" as a row, and
   `judgement --json` gives the flow in `earlier_flow_reviews`. `systemap extract` records
   the source records one time. The component digests do not change. After that, a
   change to the source in the source records makes the review stale.

The tests send no request to a model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import card_review, config, evidence, extract, facts_file, flow_review, nest
from systemap.cli import main
from systemap.model import Flow

PYTHON = {
    "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": (
        "from pkg.reader import read\n\n\ndef write(request: str) -> str:\n"
        "    return read(request)\n"
    ),
}
PYTHON_EDIT = ("pkg/reader.py", "def read(source: str) -> str:\n    return source.strip()\n")

TYPESCRIPT = {
    "package.json": '{"name":"web"}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "src/reader.ts": "export function read(source: string): string { return source }\n",
    "src/writer.ts": (
        'import { read } from "./reader";\n'
        "export function write(request: string): string { return read(request) }\n"
    ),
}
TYPESCRIPT_EDIT = (
    "src/reader.ts",
    "export function read(source: string): string { return source.trim() }\n",
)

CASES = {
    "python": (PYTHON, PYTHON_EDIT, "pkg"),
    "typescript": (TYPESCRIPT, TYPESCRIPT_EDIT, "web"),
}

MODEL = '''"""The map of the fixture."""

from systemap.model import Component, Flow, Meaning, Model

MODEL = Model(
    canvas=(600, 300),
    containers=(),
    regions=(),
    components=(
        Component(id="Reader", does="Reads the input.", implemented_by=("{package}.reader",), x=80, y=130),
        Component(id="Writer", does="Writes the output.", implemented_by=("{package}.writer",), x=370, y=130),
    ),
    flows=(
        Flow("Reader", "Writer", "request", "data", source_refs={refs}{review}),
    ),
    flow_kinds=(),
    invariants=(),
)

MEANING = Meaning(
    plain={{"Reader": "the reader", "Writer": "the writer"}},
    relations={{("Reader", "Writer"): "The reader gives one request to the writer."}},
)
'''


@pytest.fixture(params=["python", "typescript"])
def case(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def _write_model(root: Path, package: str, refs: tuple[str, ...], review: str = "") -> None:
    text = MODEL.format(
        package=package,
        refs=repr(refs),
        review=f', review_digest="{review}"' if review else "",
    )
    (root / "map").mkdir(exist_ok=True)
    (root / "map/model.py").write_text(text, encoding="utf-8")


def _facts(root: Path) -> dict[str, Any]:
    return extract.build(config.load(root))


def _refs(root: Path, package: str) -> tuple[str, ...]:
    """The source records of the two endpoint modules, with the current digests."""
    modules = _facts(root)["components"]
    return tuple(
        f"{package}.{name}@{modules[f'{package}.{name}']['source_sha256']}"
        for name in ("reader", "writer")
    )


def _project(root: Path, case: str) -> str:
    """Write the fixture with current source records and no review. Give the package."""
    tree, _edit, package = CASES[case]
    write_tree(root, tree)
    _write_model(root, package, ())
    _write_model(root, package, _refs(root, package))
    return package


def _cli(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    code = main(["--root", str(root), *argv])
    return code, capsys.readouterr().out


def _flow(root: Path) -> tuple[Flow, nest.Map]:
    m = nest.load(config.load(root)).top
    return m.model.flows[0], m


def _state(root: Path) -> str:
    flow, m = _flow(root)
    return flow_review.state(flow, m.meaning, _facts(root))


def _evidence(root: Path) -> evidence.Evidence:
    flow, m = _flow(root)
    return evidence.of_model(m.model, m.meaning, _facts(root)).of(flow)


def _flow_requests(root: Path, capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    code, out = _cli(root, capsys, "decisions", "pending", "--json")
    assert code == 0
    return [r for r in json.loads(out)["requests"] if r["type"] == "flow_review"]


def _judged(root: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    _code, out = _cli(root, capsys, "judgement", "--json")
    found: dict[str, Any] = json.loads(out)
    return found


def _edit_source(root: Path, case: str, capsys: pytest.CaptureFixture[str]) -> None:
    name, text = CASES[case][1]
    (root / name).write_text(text, encoding="utf-8")
    assert _cli(root, capsys, "extract")[0] == 0


def _reviewed(root: Path, case: str, capsys: pytest.CaptureFixture[str]) -> str:
    package = _project(root, case)
    assert _cli(root, capsys, "extract")[0] == 0
    assert _cli(root, capsys, "review", "--flow", "Reader->Writer")[0] == 0
    return package


def test_a_current_review_gives_no_request_and_no_line(
    tmp_path: Path, case: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 1."""
    _reviewed(tmp_path, case, capsys)
    flow, m = _flow(tmp_path)
    assert flow.review_digest == flow_review.digest(flow, m.meaning, _facts(tmp_path))
    assert flow.review_digest != flow_review.claim_digest(flow, m.meaning)
    assert _state(tmp_path) == flow_review.CURRENT
    found = _evidence(tmp_path)
    assert found.state == evidence.OBSERVED and not found.earlier_review
    assert found.says.startswith("current source review:")
    assert _flow_requests(tmp_path, capsys) == []
    judged = _judged(tmp_path, capsys)
    assert judged["earlier_flow_reviews"] == []
    assert not [row for row in judged["open"] if "Reader->Writer" in row["line"]]


def test_a_source_change_with_the_same_claim_opens_the_review(
    tmp_path: Path, case: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 2: the claim is the same, and only a module in the source records changes."""
    _reviewed(tmp_path, case, capsys)
    _edit_source(tmp_path, case, capsys)
    assert _state(tmp_path) == flow_review.STALE
    assert _evidence(tmp_path).state != evidence.OBSERVED
    (request,) = _flow_requests(tmp_path, capsys)
    assert request["target"] == "Reader->Writer"
    assert request["claim_digest"] is None
    assert "do not agree with the current source" in request["blocked"]


def test_new_ref_digests_without_a_review_keep_the_review_open(
    tmp_path: Path, case: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 3: the step that judgement asks for does not record a review."""
    package = _reviewed(tmp_path, case, capsys)
    old, _m = _flow(tmp_path)
    _edit_source(tmp_path, case, capsys)
    _write_model(tmp_path, package, _refs(tmp_path, package), old.review_digest)
    flow, _m = _flow(tmp_path)
    assert flow.source_refs != old.source_refs
    assert flow.review_digest == old.review_digest
    assert _state(tmp_path) == flow_review.STALE
    found = _evidence(tmp_path)
    assert found.claim_changed and not found.unresolved_refs
    assert found.state != evidence.OBSERVED
    (request,) = _flow_requests(tmp_path, capsys)
    assert request["claim_digest"] and request["blocked"] == ""
    lines = [row["line"] for row in _judged(tmp_path, capsys)["open"]]
    assert any(line.startswith("flow review: Reader -> Writer (request)") for line in lines)
    # A new review makes the flow current again.
    assert _cli(tmp_path, capsys, "review", "--flow", "Reader->Writer")[0] == 0
    assert _state(tmp_path) == flow_review.CURRENT
    assert _flow_requests(tmp_path, capsys) == []


def test_a_flow_without_source_refs_is_never_current(
    tmp_path: Path, case: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4: also a review digest of the claim does not make the flow current."""
    package = _project(tmp_path, case)
    _write_model(tmp_path, package, ())
    flow, m = _flow(tmp_path)
    _write_model(tmp_path, package, (), flow_review.claim_digest(flow, m.meaning))
    flow, m = _flow(tmp_path)
    facts = _facts(tmp_path)
    assert flow_review.digest(flow, m.meaning, facts) is None
    assert flow_review.state(flow, m.meaning, facts) == flow_review.MISSING
    assert _evidence(tmp_path).state != evidence.OBSERVED
    assert _cli(tmp_path, capsys, "extract")[0] == 0
    assert _cli(tmp_path, capsys, "review", "--flow", "Reader->Writer")[0] == 1
    assert _judged(tmp_path, capsys)["earlier_flow_reviews"] == []


def test_refs_that_do_not_agree_with_the_facts_are_never_current(
    tmp_path: Path, case: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 5: each accepted form of the review digest stays not current."""
    package = _project(tmp_path, case)
    assert _cli(tmp_path, capsys, "extract")[0] == 0
    wrong = (f"{package}.reader@{'0' * 64}",)
    _write_model(tmp_path, package, wrong)
    flow, m = _flow(tmp_path)
    for review in (
        flow_review.claim_digest(flow, m.meaning),
        flow_review.earlier_digest(flow, m.meaning),
    ):
        _write_model(tmp_path, package, wrong, review)
        assert _state(tmp_path) == flow_review.STALE
        found = _evidence(tmp_path)
        assert found.unresolved_refs == wrong and found.state != evidence.OBSERVED
        (request,) = _flow_requests(tmp_path, capsys)
        assert request["claim_digest"] is None and request["blocked"]
        assert _judged(tmp_path, capsys)["earlier_flow_reviews"] == []


def _component_digests(root: Path) -> list[str | None]:
    m = nest.load(config.load(root)).top
    facts = _facts(root)
    return [card_review.digest(c, m.model, m.meaning, facts) for c in m.model.components]


def test_a_review_before_source_tracking_has_a_label_and_one_record(
    tmp_path: Path, case: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 6."""
    package = _project(tmp_path, case)
    flow, m = _flow(tmp_path)
    _write_model(tmp_path, package, flow.source_refs, flow_review.claim_digest(flow, m.meaning))
    before = _component_digests(tmp_path)
    # The stored facts without the one record, as before the first extract after an upgrade.
    cfg = config.load(tmp_path)
    facts_file.write_facts(cfg.facts_path, _facts(tmp_path), tmp_path)
    assert _state(tmp_path) == flow_review.EARLIER
    found = _evidence(tmp_path)
    assert found.state == evidence.OBSERVED and found.earlier_review
    assert found.says.startswith(flow_review.EARLIER_LABEL)
    assert _flow_requests(tmp_path, capsys) == []
    judged = _judged(tmp_path, capsys)
    assert judged["earlier_flow_reviews"] == [{"map": "", "flow": "Reader->Writer"}]
    assert not [row for row in judged["open"] if "Reader->Writer" in row["line"]]
    _code, text = _cli(tmp_path, capsys, "judgement")
    assert f"{flow_review.EARLIER_LABEL}: Reader->Writer" in text.splitlines()

    # The one record: extract writes the earlier-review digest. A second extract writes nothing.
    _code, out = _cli(tmp_path, capsys, "extract")
    assert "recorded the source records of 1 flow reviews" in out
    flow, m = _flow(tmp_path)
    assert flow.review_digest == flow_review.earlier_digest(flow, m.meaning)
    assert _state(tmp_path) == flow_review.EARLIER
    assert _component_digests(tmp_path) == before
    _code, out = _cli(tmp_path, capsys, "extract")
    assert "recorded" not in out

    # After the record, new source records open the review again.
    _edit_source(tmp_path, case, capsys)
    _write_model(tmp_path, package, _refs(tmp_path, package), flow.review_digest)
    assert _state(tmp_path) == flow_review.STALE
    assert len(_flow_requests(tmp_path, capsys)) == 1
    assert _judged(tmp_path, capsys)["earlier_flow_reviews"] == []


def test_the_record_changes_only_the_digests_of_two_flows_in_one_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The one record writes the digest of each flow, and it keeps all other text.

    The model file is Python data for each source language. Thus one fixture is sufficient.
    """
    _project(tmp_path, "python")
    path = tmp_path / "map/model.py"
    flow, _m = _flow(tmp_path)
    text = path.read_text(encoding="utf-8")
    one = f'Flow("Reader", "Writer", "request", "data", source_refs={flow.source_refs!r})'
    two = (
        f'Flow("Reader", "Writer", "request", "data", source_refs={flow.source_refs!r}, '
        'id="submit"),\n        '
        f'Flow("Reader", "Writer", "cancel", "control", source_refs={flow.source_refs!r}, '
        'id="cancel")'
    )
    assert one in text
    text = text.replace(one, two)
    text = text.replace(
        '{("Reader", "Writer"): "The reader gives one request to the writer."}',
        '{"submit": "The reader gives a request.", "cancel": "The reader stops a request."}',
    )
    path.write_text(text, encoding="utf-8")
    m = nest.load(config.load(tmp_path)).top
    digests = [flow_review.claim_digest(f, m.meaning) for f in m.model.flows]
    for f, value in zip(m.model.flows, digests, strict=True):
        call = f'id="{f.id}")'
        text = text.replace(call, f'id="{f.id}", review_digest="{value}")')
    path.write_text(text, encoding="utf-8")
    _code, out = _cli(tmp_path, capsys, "extract")
    assert "recorded the source records of 2 flow reviews" in out
    m = nest.load(config.load(tmp_path)).top
    earlier = [flow_review.earlier_digest(f, m.meaning) for f in m.model.flows]
    assert [f.review_digest for f in m.model.flows] == earlier
    expected = text
    for old, new in zip(digests, earlier, strict=True):
        expected = expected.replace(old, new)
    assert path.read_text(encoding="utf-8") == expected


def test_a_claim_digest_from_2_0_0_is_stale_from_2_1_0(
    tmp_path: Path, case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 2.0.0 claim digest is an earlier review in 2.0 releases only, then stale."""
    package = _project(tmp_path, case)
    flow, m = _flow(tmp_path)
    _write_model(tmp_path, package, flow.source_refs, flow_review.claim_digest(flow, m.meaning))
    cfg = config.load(tmp_path)
    facts_file.write_facts(cfg.facts_path, _facts(tmp_path), tmp_path)
    monkeypatch.setattr(flow_review, "VERSION", "2.0.9")
    assert _state(tmp_path) == flow_review.EARLIER
    monkeypatch.setattr(flow_review, "VERSION", "2.1.0")
    assert _state(tmp_path) == flow_review.STALE
    flow, m = _flow(tmp_path)
    assert not flow_review.needs_record(flow, m.meaning)
