"""`systemap audit` gives no kind-name warning, and `judgement` gives the new name.

In 3.0.0, `audit` gave a warning for each previous kind name in `[judgement] answered`.
From 3.1.0, systemap does not read the previous names. Acceptance values:

1. `audit` gives no warning for an item with a previous kind name, and for a current
   judgement line whose text looks like such an item.
2. `audit` calculates no judgement lines for the answers.
3. `judgement` gives an item with a previous kind name as a stale answer. The row gives
   the new name.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_audit_findings import Fake, audit_args, two_cards

from systemap import jev_cli, judgement_json
from systemap.cli import main

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
        'systemap does not read. Change "jev sentence" to "decision sentence" in '
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
