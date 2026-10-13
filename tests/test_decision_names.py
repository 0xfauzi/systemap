"""The kinds of the provider findings have neutral names. The previous names stay for one
release.

Acceptance values:

- A configuration with an exact answer that uses an previous name ("jev sentence"), and
  the digest that the previous release recorded, closes the new line ("decision
  sentence"). `audit` prints one warning. `judgement` prints one warning.
- A configuration with an answer that uses the new name closes the line with no warning.
- The evidence digest of a line is the same for the previous name and the new name.
  A group answer with previous names and its previous digest stays correct.
- With an injected OpenAI transport, the delta suggestions name OpenAI. With an
  injected Jev transport, they name Jev.
- `--jev` and `--decide` send identical requests (Python and TypeScript fixtures).
  `--no-jev` and `--no-decide` send zero requests. `suggest --jev` and
  `suggest --decide` send identical requests.
- `systemap explain` gives the same text for an previous name and its new name.

The transports are injected. No test calls Jev or OpenAI.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_decision_golden import Recorder, roots
from test_delta_jev import Fake, renamed, use
from test_jev_on_request import Counter, counter, renamed_ts
from test_openai_provider import Decisions, counted

from systemap import audit, decision_kinds, explain, extract, jev, judgement, nest
from systemap.cli import main
from systemap.config import Answer
from systemap.config import load as load_config

__all__ = ["counted", "counter", "renamed", "renamed_ts", "roots"]

NEW = "decision sentence: Reader's sentence may not describe its modules"
OLD = "jev sentence: Reader's sentence may not describe its modules"


def _answer(root: Path, item: str, digest: str) -> None:
    toml = root / "systemap.toml"
    entry = f'{{ item = "{item}", evidence = "{digest}", reason = "The sentence is correct." }}'
    text = toml.read_text(encoding="utf-8")
    assert "\n[judgement]" not in text
    toml.write_text(text + f"\n[judgement]\nanswered = [\n    {entry},\n]\n", encoding="utf-8")


def _previous_digest(root: Path, line: str) -> str:
    """Give the digest as the previous release made it: from the printed line itself."""
    cfg = load_config(root)
    facts = extract.read_facts(cfg.facts_path)
    assert facts
    return judgement.evidence_for_tree(nest.load(cfg), facts, cfg.root, [line])[line]


def _audit(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    recorder = Recorder()
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    monkeypatch.setattr(jev, "http_send", lambda key, base=jev.API: recorder)
    code = main(["--root", str(root), "audit", "--kind", "decision sentence", "--brief"])
    out, err = capsys.readouterr()
    return code, out, err


def test_without_an_answer_the_new_line_is_open(
    roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = _audit(roots["asked"], monkeypatch, capsys)
    assert code == 0
    assert f"  {NEW}" in out.splitlines()
    assert "warning:" not in err


def test_an_earlier_name_with_its_previous_digest_closes_the_new_line(
    roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = roots["asked"]
    _answer(root, OLD, _previous_digest(root, OLD))
    code, out, err = _audit(root, monkeypatch, capsys)
    assert code == 0
    assert NEW not in out and "pending answer" not in out and "stale answer" not in out
    assert "1 answered" in out.splitlines()[0]
    warnings = [line for line in err.splitlines() if line.startswith("warning:")]
    assert warnings == [
        'warning: [judgement] answered uses the previous name "jev sentence". '
        'Change it to "decision sentence". Only this release reads the previous names.'
    ]
    assert main(["--root", str(root), "judgement"]) == 0
    assert capsys.readouterr().err.count("warning:") == 1


def test_a_new_name_closes_the_line_with_no_warning(
    roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = roots["asked"]
    # The digest of the new line is the digest that the previous release recorded.
    _answer(root, NEW, _previous_digest(root, OLD))
    code, out, err = _audit(root, monkeypatch, capsys)
    assert code == 0
    assert NEW not in out and "pending answer" not in out
    assert "1 answered" in out.splitlines()[0]
    assert "warning:" not in err
    main(["--root", str(root), "judgement"])
    assert "warning:" not in capsys.readouterr().err


def test_the_digest_is_the_same_for_the_two_names(roots: dict[str, Path]) -> None:
    root = roots["asked"]
    cfg = load_config(root)
    facts = extract.read_facts(cfg.facts_path)
    assert facts
    tree = nest.load(cfg)
    owner_new = "decision owner: pkg.stray is claimed by no card"
    owner_old = "jev owner: pkg.stray is claimed by no card"
    now = audit.evidence(tree, facts, cfg.root, [NEW, owner_new])
    assert now[NEW] == _previous_digest(root, OLD)
    assert now[owner_new] == _previous_digest(root, owner_old)
    # A group digest covers the configured item text. The previous group stays correct.
    previous = {OLD: now[NEW], owner_old: now[owner_new]}
    group = Answer(
        items=(OLD, owner_old),
        reason="r",
        evidence=judgement.answer_digest([OLD, owner_old], previous),
    )
    found = [audit.Line(NEW), audit.Line(owner_new)]
    result = audit.apply_reviewed(found, [group], now, audit.KINDS)
    assert (result.open, result.answered, result.pending, result.stale) == ([], 2, [], [])


def test_an_earlier_family_kind_closes_the_new_lines_and_a_nested_line_migrates() -> None:
    line = audit.Line(
        "Core: decision flow: A -> B ('x'): the code where they meet may not carry it"
    )
    family = Answer((), "standing rule", kind="jev flow", policy=True)
    result = audit.apply_reviewed([line], [family], {}, audit.KINDS)
    assert result.open == [] and result.answered == 1
    assert (
        audit.migrated("Core: jev flow: A -> B ('x'): z") == "Core: decision flow: A -> B ('x'): z"
    )
    assert decision_kinds.previous_line(line.text).startswith("Core: jev flow: ")
    assert decision_kinds.warnings([family]) == [
        'warning: [judgement] answered uses the previous name "jev flow". '
        'Change it to "decision flow". Only this release reads the previous names.'
    ]


def test_the_judgement_line_kinds_do_not_change() -> None:
    line = "single module: Scaffold contains only pkg.scaffold"
    assert decision_kinds.current_line(line) == line
    assert decision_kinds.previous_line(line) == line
    assert decision_kinds.kind_of(line) is None
    assert not audit.is_audit_answer(Answer((line,), "r"))


# ---- the provider name in the printed text ---------------------------------------------


def test_the_delta_suggestions_name_openai(
    renamed: Path, counted: Decisions, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["--root", str(renamed), "delta", "--base", "HEAD~1", "--decide", "--provider", "openai"])
    out = capsys.readouterr().out
    assert counted.requests
    assert "OpenAI suggestions. They do not change the delta lines or the exit code" in out
    assert "Jev" not in out


def test_the_delta_suggestions_name_jev(
    renamed: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = Fake()
    use(monkeypatch, fake)
    main(["--root", str(renamed), "delta", "--base", "HEAD~1", "--decide"])
    out = capsys.readouterr().out
    assert fake.posts
    assert "Jev suggestions. They do not change the delta lines or the exit code" in out
    assert "decision move: pkg.ledger -> pkg.records_store (read as the same module by Jev" in out
    assert "OpenAI" not in out


# ---- the previous option names send the same requests -----------------------------------


def _requests(counter: Counter, root: Path, *argv: str) -> list[tuple[str, str, object]]:
    counter.requests.clear()
    (root / ".systemap/jev-cache.json").unlink(missing_ok=True)
    main(["--root", str(root), *argv])
    return list(counter.requests)


@pytest.mark.parametrize("fixture", ["renamed", "renamed_ts"])
def test_jev_and_decide_send_identical_delta_requests(
    fixture: str,
    request: pytest.FixtureRequest,
    counter: Counter,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = request.getfixturevalue(fixture)
    by_decide = _requests(counter, root, "delta", "--base", "HEAD~1", "--decide")
    by_jev = _requests(counter, root, "delta", "--base", "HEAD~1", "--jev")
    assert by_decide and by_decide == by_jev
    assert _requests(counter, root, "delta", "--base", "HEAD~1", "--no-decide") == []
    assert _requests(counter, root, "delta", "--base", "HEAD~1", "--no-jev") == []
    capsys.readouterr()


def test_jev_and_decide_send_identical_suggest_requests(
    roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = roots["asked"]
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    sent: dict[str, list[str]] = {}
    for option in ("--decide", "--jev"):
        recorder = Recorder()
        monkeypatch.setattr(jev, "http_send", lambda key, base=jev.API, r=recorder: r)
        (root / ".systemap/jev-cache.json").unlink(missing_ok=True)
        assert main(["--root", str(root), "suggest", option]) == 0
        # Requests go in parallel, so the send order can change. The answers keep the
        # order of the questions, so the bodies are compared as a sorted list.
        sent[option] = sorted(recorder.bodies)
    assert sent["--decide"] and sent["--decide"] == sent["--jev"]
    capsys.readouterr()


def test_the_help_names_the_earlier_options(capsys: pytest.CaptureFixture[str]) -> None:
    for command in ("delta", "suggest"):
        with pytest.raises(SystemExit):
            main([command, "--help"])
        out = " ".join(capsys.readouterr().out.split())
        assert "--decide" in out and "--jev" in out
        assert "previous name" in out and "one release" in out


# ---- the explanations ------------------------------------------------------------------


def test_each_new_kind_has_three_sentences_and_each_earlier_name_points_to_it() -> None:
    for old, new in decision_kinds.PREVIOUS.items():
        lesson = explain.lesson(new)
        assert lesson is not None and lesson.means and lesson.why and lesson.do
        assert "Jev" not in lesson.means + lesson.why + lesson.do
        assert explain.lesson(old) is lesson
        assert explain.whole(old)[1] == f"  new name: {new}"
        assert explain.whole(old)[2:] == explain.whole(new)[1:]
