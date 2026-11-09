"""`systemap audit` gives no kind-name warning, and `judgement` gives the new name.

In 3.0.0, `audit` gave a warning for each previous kind name in `[judgement] answered`.
From 3.1.0, systemap does not read the previous names. Acceptance values:

1. `audit` gives no warning for an item with a previous kind name.
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
8. `audit` gives a reviewed line of a family answer with a previous kind name as a
   stale answer.
9. An `items` group from 3.0.0 with a current item and an item with a previous name is
   pending in `audit`, and its current lines are open. After the change of the name,
   the group stays pending until the maintainer records the new digest.
10. `judgement --json` gives each item and reviewed line with a previous kind name one
    time in `stale_answers`. With `--map`, it gives only the items of that map.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from test_audit_findings import Fake, audit_args, two_cards
from test_scoped_maps import CHOSEN, SIBLING, built

from systemap import answer_migrations, audit, decision_kinds, jev_cli, judgement, judgement_json
from systemap.cli import main
from systemap.config import Answer

__all__ = ["built", "two_cards"]

# A current line that looks like a decision line with the previous kind name "jev flow".
CURRENT = "unknown surface: jev flow: extends 'x': the configuration package could not be read"
# A decision line with a previous kind name. It is not a current line.
EARLIER = "jev sentence: Reader's sentence may not describe its modules"


def answer(root: Path, item: str) -> None:
    toml = root / "systemap.toml"
    entry = f'{{ item = "{item}", reason = "The line is correct." }}'
    text = toml.read_text(encoding="utf-8")
    toml.write_text(text + f"\n[judgement]\nanswered = [\n    {entry},\n]\n", encoding="utf-8")


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


REVIEWED = "decision sentence: Reader's sentence may not describe its modules"


def test_audit_gives_a_reviewed_line_with_a_previous_name() -> None:
    """Acceptance 8."""
    family = Answer(
        items=(), kind=decision_kinds.SENTENCE, policy=True, reason="r", reviewed=(EARLIER,)
    )
    found = [audit.Line(REVIEWED)]
    result = audit.apply_reviewed(found, [family], {REVIEWED: "d"}, audit.KINDS)
    assert result.stale == [EARLIER]
    rows = audit.report([], 0, result.stale, "usage", teach=False)
    assert f"  stale answer: {answer_migrations.stale(EARLIER)}" in rows


def test_a_group_from_3_0_0_with_a_previous_name_is_pending_in_audit() -> None:
    """Acceptance 9. 3.0.0 gave the earlier item the evidence of its current line."""
    evidence = {CURRENT_ITEM: "dA", REVIEWED: "dB"}
    recorded = judgement.answer_digest((CURRENT_ITEM, EARLIER), {CURRENT_ITEM: "dA", EARLIER: "dB"})
    found = [audit.Line(CURRENT_ITEM), audit.Line(REVIEWED)]
    group = Answer(items=(CURRENT_ITEM, EARLIER), reason="r", evidence=recorded)
    result = audit.apply_reviewed(found, [group], evidence, audit.KINDS)
    assert [x.text for x in result.open] == [CURRENT_ITEM, REVIEWED]
    assert result.stale == [EARLIER]
    assert len(result.pending) == 1 and "must have a new source review" in result.pending[0]
    changed = Answer(items=(CURRENT_ITEM, REVIEWED), reason="r", evidence=recorded)
    result = audit.apply_reviewed(found, [changed], evidence, audit.KINDS)
    assert [x.text for x in result.open] == [CURRENT_ITEM, REVIEWED]
    assert result.stale == [] and len(result.pending) == 1
    new = judgement.answer_digest((CURRENT_ITEM, REVIEWED), evidence)
    current = Answer(items=(CURRENT_ITEM, REVIEWED), reason="r", evidence=new)
    result = audit.apply_reviewed(found, [current], evidence, audit.KINDS)
    assert (result.open, result.pending) == ([], [])


def _json_stale(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> list[str]:
    capsys.readouterr()
    main(["--root", str(root), "judgement", "--json", *argv])
    stale: list[str] = json.loads(capsys.readouterr().out)["stale_answers"]
    return stale


def test_judgement_json_gives_each_previous_name_one_time(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 10."""
    toml = two_cards / "systemap.toml"
    entries = (
        f'{{ item = "{EARLIER}", reason = "The line is correct." }},\n'
        '    { kind = "decision sentence", policy = true, reason = "r", '
        f'reviewed = ["{EARLIER}"] }},'
    )
    text = toml.read_text(encoding="utf-8")
    toml.write_text(text + f"\n[judgement]\nanswered = [\n    {entries}\n]\n", encoding="utf-8")
    assert _json_stale(two_cards, capsys).count(EARLIER) == 1


def test_judgement_json_with_a_map_gives_the_previous_names_of_that_map(
    built: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 10, with `--map`."""
    root = tmp_path / "copy"
    shutil.copytree(built, root)
    rest = "jev flow: A -> B ('x'): the code where they meet may not carry it"
    chosen, sibling = f"{CHOSEN}: {rest}", f"{SIBLING}: {rest}"
    toml = root / "systemap.toml"
    entries = "".join(
        f'\n[[judgement.answered]]\nitem = "{item}"\nreason = "A test."\n'
        for item in (chosen, sibling)
    )
    toml.write_text(toml.read_text(encoding="utf-8") + entries, encoding="utf-8")
    assert _json_stale(root, capsys, "--map", CHOSEN) == [chosen]
    assert sorted(_json_stale(root, capsys)) == sorted([chosen, sibling])
