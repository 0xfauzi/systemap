"""`systemap audit` gives no kind-name warning, and `judgement` gives the new name.

In 3.0.0, `audit` gave a warning for each previous kind name in `[judgement] answered`.
From 3.1.0, systemap does not read the previous names. Acceptance values:

1. `audit` gives no warning for an item with a previous kind name, and for a current
   judgement line whose text looks like such an item.
2. `audit` calculates no judgement lines for the answers.
3. `judgement` and `audit` give an item with a previous kind name as a stale answer.
   The row gives the current line.
4. A current decision item in the same answer as an item with a previous name stays an
   audit item. `judgement` does not give it as a stale answer.
5. A judgement line with "jev flow: " after its kind, and a `jev move` item, get no new
   name.
6. `judgement` gives a reviewed line of a family answer with a previous kind name as a
   stale answer.
7. An item with a previous kind name gets no "Change it to" warning for an earlier form,
   because that change does not make the item current. `judgement` gives the item one
   time, also if the answer is not an audit answer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_audit_findings import Fake, audit_args, two_cards

from systemap import answer_migrations, audit, decision_kinds, jev_cli, judgement_json
from systemap.cli import main
from systemap.config import Answer

__all__ = ["two_cards"]

# A current line that looks like a decision line with the previous kind name "jev flow".
CURRENT = "unknown surface: jev flow: extends 'x': the configuration package could not be read"
# A decision line with a previous kind name. It is not a current line.
EARLIER = "jev sentence: Reader's sentence may not describe its modules"


def answer(root: Path, item: str) -> None:
    toml = root / "systemap.toml"
    entry = f'{{ item = "{item}", reason = "The line is correct." }}'
    text = toml.read_text(encoding="utf-8")
    toml.write_text(text + f"\n[judgement]\nanswered = [\n    {entry},\n]\n", encoding="utf-8")


def with_current_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """Add CURRENT to the judgement lines. The fixture has no line of this form."""
    real = judgement_json.current_lines
    monkeypatch.setattr(judgement_json, "current_lines", lambda *args: [*real(*args), CURRENT])


def test_an_exact_current_line_gets_no_previous_name_warning_in_audit(
    two_cards: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 1."""
    with_current_line(monkeypatch)
    answer(two_cards, CURRENT)
    capsys.readouterr()
    assert jev_cli.cmd_audit(audit_args(two_cards, dry_run=True), send=Fake()) == 0
    assert "warning:" not in capsys.readouterr().err


def test_an_earlier_decision_line_gets_no_warning_in_audit(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 1."""
    answer(two_cards, EARLIER)
    capsys.readouterr()
    assert jev_cli.cmd_audit(audit_args(two_cards, dry_run=True), send=Fake()) == 0
    assert "warning:" not in capsys.readouterr().err


def test_judgement_gives_the_new_name_for_an_earlier_decision_line(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 3."""
    answer(two_cards, EARLIER)
    capsys.readouterr()
    main(["--root", str(two_cards), "judgement"])
    captured = capsys.readouterr()
    assert (
        f"  stale answer: '{EARLIER}' has the previous kind name \"jev sentence\", which "
        "systemap does not read. Change it to "
        "'decision sentence: Reader's sentence may not describe its modules' in "
        "[judgement] answered."
    ) in captured.out.splitlines()
    assert "previous name" not in captured.err


def test_audit_calculates_no_judgement_lines(
    two_cards: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 2."""
    calls: list[int] = []
    monkeypatch.setattr(judgement_json, "current_lines", lambda *args: calls.append(1) or [])
    answer(two_cards, EARLIER)
    assert jev_cli.cmd_audit(audit_args(two_cards, dry_run=True), send=Fake()) == 0
    assert calls == []
    assert "warning:" not in capsys.readouterr().err


CURRENT_ITEM = "decision sentence: Writer's sentence may not describe its modules"


def test_a_current_item_beside_a_previous_name_stays_an_audit_item(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4."""
    mixed = Answer(items=(CURRENT_ITEM, EARLIER), reason="r", evidence="d")
    assert audit.is_audit_answer(mixed)
    found = [audit.Line(CURRENT_ITEM)]
    open_lines, answered, stale = audit.apply(found, [mixed], audit.KINDS)
    assert (open_lines, answered, stale) == ([], 1, [EARLIER])
    toml = two_cards / "systemap.toml"
    entry = f'{{ items = ["{CURRENT_ITEM}", "{EARLIER}"], reason = "The lines are correct." }}'
    text = toml.read_text(encoding="utf-8")
    toml.write_text(text + f"\n[judgement]\nanswered = [\n    {entry},\n]\n", encoding="utf-8")
    capsys.readouterr()
    main(["--root", str(two_cards), "judgement"])
    rows = [r for r in capsys.readouterr().out.splitlines() if "stale answer:" in r]
    assert len(rows) == 1 and EARLIER in rows[0]


def test_a_lookalike_line_and_a_move_item_get_no_new_name() -> None:
    """Acceptance 5."""
    assert decision_kinds.renamed(CURRENT) is None
    assert decision_kinds.renamed("jev move: pkg.a moved to pkg.b") is None
    assert decision_kinds.renamed("Core: " + EARLIER) == ("jev sentence", "decision sentence")
    assert answer_migrations.stale(CURRENT).endswith(
        "is now missing. Remove it from [judgement] answered."
    )


def test_judgement_gives_a_reviewed_line_with_a_previous_name(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 6."""
    toml = two_cards / "systemap.toml"
    entry = (
        '{ kind = "decision sentence", policy = true, reason = "The lines are correct.", '
        f'reviewed = ["{EARLIER}"] }}'
    )
    text = toml.read_text(encoding="utf-8")
    toml.write_text(text + f"\n[judgement]\nanswered = [\n    {entry},\n]\n", encoding="utf-8")
    capsys.readouterr()
    main(["--root", str(two_cards), "judgement"])
    out = capsys.readouterr().out.splitlines()
    assert (
        f"  stale answer: '{EARLIER}' has the previous kind name \"jev sentence\", which "
        "systemap does not read. Change it to "
        "'decision sentence: Reader's sentence may not describe its modules' in "
        "[judgement] answered."
    ) in out


def test_a_previous_name_gets_no_form_warning_and_one_stale_row(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 7."""
    control = "jev sentence: Reader\nWriter"
    assert answer_migrations.warnings([Answer(items=(control,), reason="r")]) == []
    toml = two_cards / "systemap.toml"
    other = "single module: Reader contains only pkg.reader"
    entry = f'{{ items = ["{other}", "{EARLIER}"], reason = "The lines are correct." }}'
    text = toml.read_text(encoding="utf-8")
    toml.write_text(text + f"\n[judgement]\nanswered = [\n    {entry},\n]\n", encoding="utf-8")
    capsys.readouterr()
    main(["--root", str(two_cards), "judgement"])
    out = capsys.readouterr().out.splitlines()
    assert sum(EARLIER in row for row in out if "stale answer:" in row) == 1


def test_the_audit_report_gives_the_current_line_for_a_previous_name() -> None:
    """Acceptance 3, for `audit`. Another stale item keeps its row."""
    rows = audit.report([], 0, [EARLIER, CURRENT_ITEM], "usage", teach=False)
    assert (
        f"  stale answer: '{EARLIER}' has the previous kind name \"jev sentence\", which "
        "systemap does not read. Change it to "
        "'decision sentence: Reader's sentence may not describe its modules' in "
        "[judgement] answered."
    ) in rows
    assert f"  stale answer: {CURRENT_ITEM}" in rows
