"""`systemap audit` gives the kind-name warnings with the current judgement lines.

The P2 migrations change gave `systemap judgement` the current lines for its warnings:
an item that is an exact current line gets no warning. `jev_cli.cmd_audit` called
`decision_kinds.warnings` without the current lines. Thus a current judgement line whose
text looks like a decision line with a previous kind name got a false warning in audit.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_audit_findings import Fake, audit_args, two_cards

from systemap import jev_cli, judgement_json

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
    with_current_line(monkeypatch)
    answer(two_cards, CURRENT)
    capsys.readouterr()
    assert jev_cli.cmd_audit(audit_args(two_cards, dry_run=True), send=Fake()) == 0
    assert "warning:" not in capsys.readouterr().err


def test_an_earlier_decision_line_still_gets_the_warning_in_audit(
    two_cards: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with_current_line(monkeypatch)
    answer(two_cards, EARLIER)
    capsys.readouterr()
    assert jev_cli.cmd_audit(audit_args(two_cards, dry_run=True), send=Fake()) == 0
    assert capsys.readouterr().err.splitlines() == [
        'warning: [judgement] answered uses the previous name "jev sentence". '
        'Change it to "decision sentence". Only this release reads the previous names.'
    ]


def test_audit_calculates_no_judgement_lines_without_a_previous_name(
    two_cards: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(judgement_json, "current_lines", lambda *args: calls.append(1) or [])
    answer(two_cards, "decision sentence: Reader's sentence may not describe its modules")
    assert jev_cli.cmd_audit(audit_args(two_cards, dry_run=True), send=Fake()) == 0
    assert calls == []
    assert "warning:" not in capsys.readouterr().err
