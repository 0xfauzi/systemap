"""The kinds of the provider findings have neutral names. 3.1.0 does not read the
previous names.

Acceptance values:

- A configuration with an exact answer that uses a previous name ("jev sentence"), and
  the digest that the previous release recorded, does not close the new line ("decision
  sentence"). `audit` and `judgement` print no warning. The judgement report gives the
  item as a stale answer, and the row gives the new name.
- A configuration with an answer that uses the new name closes the line with no warning.
  The digest that the previous release recorded stays correct.
- The evidence digest of a line is the same for the previous name and the new name.
- A family answer with a previous name (`kind = "jev flow"`) gives a configuration error.
- With an injected OpenAI transport, the delta suggestions name OpenAI. With an
  injected Jev transport, they name Jev.
- `delta --jev`, `delta --no-jev`, `suggest --jev` and `audit --kind "jev flow"` give a
  usage error with exit code 2 and send no request. The help does not name `--jev`.
- `systemap explain` does not know a previous name.

The transports are injected. No test calls Jev or OpenAI.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_decision_golden import Recorder, roots
from test_delta_jev import Fake, renamed, use
from test_jev_on_request import Counter, counter, renamed_ts
from test_openai_provider import Decisions, counted

from systemap import audit, decision_kinds, explain, facts_file, jev, judgement, nest
from systemap.cli import main
from systemap.config import Answer, ConfigError
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
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    assert facts
    return judgement.evidence_for_tree(nest.load(cfg), facts, cfg.root, [line])[line]


def _audit(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    recorder = Recorder()
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    monkeypatch.setattr(jev, "http_send", lambda key, base=jev.API: recorder)
    code = main(
        [
            "--root",
            str(root),
            "audit",
            "--kind",
            "decision sentence",
            "--brief",
            "--provider",
            "jev",
        ]
    )
    out, err = capsys.readouterr()
    return code, out, err


def test_without_an_answer_the_new_line_is_open(
    roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = _audit(roots["asked"], monkeypatch, capsys)
    assert code == 0
    assert f"  {NEW}" in out.splitlines()
    assert "warning:" not in err


def test_an_earlier_name_does_not_close_the_new_line_and_the_report_gives_the_new_name(
    roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = roots["asked"]
    _answer(root, OLD, _previous_digest(root, OLD))
    code, out, err = _audit(root, monkeypatch, capsys)
    assert code == 0
    assert f"  {NEW}" in out.splitlines()
    assert "answered" not in out.splitlines()[0]
    assert "warning:" not in err
    assert main(["--root", str(root), "judgement"]) == 0
    out, err = capsys.readouterr()
    assert (
        f"  stale answer: '{OLD}' has the previous kind name \"jev sentence\", which systemap "
        f"does not read. Change it to '{NEW}' in [judgement] answered."
    ) in out.splitlines()
    assert "warning:" not in err


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
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    assert facts
    tree = nest.load(cfg)
    owner_new = "decision owner: pkg.stray is claimed by no card"
    owner_old = "jev owner: pkg.stray is claimed by no card"
    now = audit.evidence(tree, facts, cfg.root, [NEW, owner_new])
    assert now[NEW] == _previous_digest(root, OLD)
    assert now[owner_new] == _previous_digest(root, owner_old)
    # An answer with the previous names is an audit answer that matches no audit line.
    previous = Answer(items=(OLD, owner_old), reason="r")
    assert audit.is_audit_answer(previous)
    assert audit.apply([audit.Line(NEW), audit.Line(owner_new)], [previous], audit.KINDS)[2] == [
        OLD,
        owner_old,
    ]


def test_an_earlier_family_kind_is_a_configuration_error(
    roots: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root = roots["asked"]
    toml = root / "systemap.toml"
    entry = '{ kind = "jev flow", policy = true, reason = "A standing rule." }'
    text = toml.read_text(encoding="utf-8")
    toml.write_text(text + f"\n[judgement]\nanswered = [\n    {entry},\n]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="kind must be one of"):
        load_config(root)
    assert main(["--root", str(root), "judgement"]) == 2
    assert "kind must be one of" in capsys.readouterr().err


def test_a_nested_line_with_an_earlier_name_does_not_migrate() -> None:
    line = "Core: decision flow: A -> B ('x'): the code where they meet may not carry it"
    earlier = "Core: jev flow: A -> B ('x'): z"
    assert audit.migrated(earlier) == earlier
    assert decision_kinds.previous_line(line).startswith("Core: jev flow: ")
    assert decision_kinds.kind_of(earlier) is None
    assert decision_kinds.renamed(earlier) == ("jev flow", decision_kinds.FLOW)


def test_the_judgement_line_kinds_do_not_change() -> None:
    line = "single module: Scaffold contains only pkg.scaffold"
    assert audit.migrated(line) == line
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


# ---- the previous option names give a usage error -------------------------------------


def _requests(counter: Counter, root: Path, *argv: str) -> list[tuple[str, str, object]]:
    counter.requests.clear()
    (root / ".systemap/jev-cache.json").unlink(missing_ok=True)
    main(["--root", str(root), *argv])
    return list(counter.requests)


@pytest.mark.parametrize("fixture", ["renamed", "renamed_ts"])
def test_jev_and_no_jev_give_a_usage_error_in_delta(
    fixture: str,
    request: pytest.FixtureRequest,
    counter: Counter,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = request.getfixturevalue(fixture)
    assert _requests(counter, root, "delta", "--base", "HEAD~1", "--decide")
    assert _requests(counter, root, "delta", "--base", "HEAD~1", "--no-decide") == []
    capsys.readouterr()
    for option in ("--jev", "--no-jev"):
        counter.requests.clear()
        with pytest.raises(SystemExit) as stop:
            main(["--root", str(root), "delta", "--base", "HEAD~1", option])
        assert stop.value.code == 2
        assert f"unrecognized arguments: {option}" in capsys.readouterr().err
        assert counter.requests == []


def test_jev_gives_a_usage_error_in_suggest(
    roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = roots["asked"]
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    recorder = Recorder()
    monkeypatch.setattr(jev, "http_send", lambda key, base=jev.API: recorder)
    with pytest.raises(SystemExit) as stop:
        main(["--root", str(root), "suggest", "--jev"])
    assert stop.value.code == 2
    assert "unrecognized arguments: --jev" in capsys.readouterr().err
    assert recorder.bodies == []


def test_audit_kind_with_an_earlier_name_gives_a_usage_error(
    roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = roots["asked"]
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    recorder = Recorder()
    monkeypatch.setattr(jev, "http_send", lambda key, base=jev.API: recorder)
    with pytest.raises(SystemExit) as stop:
        main(["--root", str(root), "audit", "--kind", "jev flow", "--provider", "jev"])
    assert stop.value.code == 2
    assert "argument --kind: invalid choice: 'jev flow'" in capsys.readouterr().err
    assert recorder.bodies == []


def test_the_help_does_not_name_the_earlier_options(capsys: pytest.CaptureFixture[str]) -> None:
    for command in ("delta", "suggest", "audit"):
        with pytest.raises(SystemExit):
            main([command, "--help"])
        out = " ".join(capsys.readouterr().out.split())
        assert "--jev" not in out and "jev flow" not in out and "3.1.0" not in out
        assert "--decide" in out or command == "audit"


# ---- the explanations ------------------------------------------------------------------


def test_each_new_kind_has_three_sentences_and_explain_does_not_know_an_earlier_name() -> None:
    for old, new in decision_kinds.PREVIOUS.items():
        lesson = explain.lesson(new)
        assert lesson is not None and lesson.means and lesson.why and lesson.do
        assert "Jev" not in lesson.means + lesson.why + lesson.do
        assert explain.lesson(old) is None
        assert explain.whole(old)[0] == f"explain: there is no line kind with the name {old!r}."
        assert old not in explain.whole(old)[1]
        assert explain.whole(new)[0] == new
