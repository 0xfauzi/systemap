"""Untrusted text goes to the terminal only as visible characters (llm-1, g1ts-7, llm-4).

A model, a coding agent, and a commit subject can supply ESC, OSC 8, BEL, or U+2028.
Before the fix, `systemap history` printed a commit subject with raw ESC and BEL, and it
divided the subject in two at U+2028. `systemap journeys` wrote an agent id with ESC and a
line break into the model, and `decisions submit` recorded a summary with ESC. `judgement`
then printed the stored text raw on each later run.

Acceptance values:

1. `printable` gives `\\uXXXX` for each C0 and C1 control character, DEL, U+2028, U+2029,
   and an unpaired surrogate. Other text, which includes a backslash, does not change.
2. The output of `history`, `journeys`, `decisions submit`, and `judgement` has no raw
   control character for the hostile fixtures. Each hostile character shows as an escape.
3. `journeys` refuses an id that is not a slug, an empty id, and a label or step sentence
   with a control character. `decisions submit` refuses a summary with a control character.
   The two commands write nothing for such an answer.
4. A JSON output with an escaped character gives the same value when a program reads it.

The tests use recorded answers and an injected agent. They call no model.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree
from test_decisions import SOURCE, cite, pending, submit
from test_journeys import (
    ANSWER,
    alone,
    answering,
    args_for,
    read,
    route,
    two_card_model,
    with_agent,
)
from test_trend import commit

from systemap import journeys, judgement
from systemap.cli import main, say
from systemap.config import Config, load
from systemap.jev_cli import cmd_journeys
from systemap.terminal_text import has_control, lines, printable

RAW = re.compile("[\x00-\x09\x0b-\x1f\x7f-\x9f\u2028\u2029]")
OSC8 = "\x1b]8;;http://example.invalid\x07link\x1b]8;;\x07"
HOSTILE = f"ship {OSC8} \x1b[31mred\x1b[0m\x07 \u2028end"


def test_printable_gives_an_escape_for_each_control_character() -> None:
    assert printable("a\x1b[2Jb") == "a\\u001b[2Jb"
    assert printable("bell\x07") == "bell\\u0007"
    assert printable("x\u2028y\u2029z") == "x\\u2028y\\u2029z"
    assert (
        printable("\x00\t\n\r\x7f\x85\x9b") == "\\u0000\\u0009\\u000a\\u000d\\u007f\\u0085\\u009b"
    )
    assert printable("name\udcff") == "name\\udcff"
    assert has_control("a\u2028") and not has_control("plain")


def test_normal_text_does_not_change() -> None:
    normal = "C:\\path\\to file, Größe, 日本語, a -> b, ü, \\u001b as text"
    assert printable(normal) == normal
    assert lines("one\ntwo") == "one\ntwo"
    assert lines("one\x1b\ntwo\u2028") == "one\\u001b\ntwo\\u2028"


def test_an_escape_in_a_json_output_keeps_the_value(capsys: pytest.CaptureFixture[str]) -> None:
    value = {"line": "a\u2028b\x85c\x1b"}
    say(json.dumps(value, ensure_ascii=False))
    out = capsys.readouterr().out
    assert not RAW.search(out)
    assert json.loads(out) == value


def test_history_shows_a_hostile_commit_subject_as_escapes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Before the fix: 7 raw characters, and `end` showed as a second commit line."""
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    commit(tmp_path, "the first map")
    model = tmp_path / "map/model.py"
    write_tree(
        tmp_path,
        {
            "pkg/shipping.py": "def ship(s: str) -> str:\n    return s\n",
            "map/model.py": model.read_text(encoding="utf-8").replace(
                '("pkg.writer",)', '("pkg.writer", "pkg.shipping")'
            ),
        },
    )
    commit(tmp_path, HOSTILE)
    capsys.readouterr()
    assert (
        main(["--root", str(tmp_path), "history", "--since", "30 years ago", "--every", "1"]) == 0
    )
    out = capsys.readouterr().out
    assert not RAW.search(out)
    added = [line for line in out.splitlines() if "added by commit:" in line]
    assert added == [f"      added by commit: {printable(HOSTILE)}"]


@pytest.mark.parametrize(
    ("ident", "problem"),
    [
        ("j-\x1b[2J\nforged: line", "the sequence id 'j-\\u001b[2J\\u000aforged: line' is not"),
        ("   ", "the answer has no sequence id"),
        ("read and write", "the sequence id 'read and write' is not correct"),
        ("-start", "the sequence id '-start' is not correct"),
    ],
)
def test_a_sequence_id_that_is_not_a_slug_is_refused(ident: str, problem: str) -> None:
    draft = read({**ANSWER, "id": ident})
    assert draft.journey is None
    assert any(p.startswith(problem) for p in draft.problems), draft.problems


def test_a_label_or_a_sentence_with_a_control_character_is_refused() -> None:
    label = read({**ANSWER, "label": "Read \x1b[31m red"})
    assert label.journey is None
    assert label.problems == (
        "the sequence label 'Read \\u001b[31m red' contains a control character or a "
        "Unicode line separator. Write one line of text",
    )
    step = {**ANSWER["steps"][0], "say": "The reader \u2028passes a request on."}
    said = read({**ANSWER, "steps": [step]})
    assert said.journey is None
    assert said.problems[0].startswith(
        "step 1 has the sentence 'The reader \\u2028passes a request on.', which contains"
    )


@pytest.fixture
def two_cards(tmp_path: Path) -> Config:
    route = 'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/read")\ndef read(source: str) -> str:\n    return source\n'
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES, "pkg/reader.py": route})
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return load(tmp_path)


def test_journeys_writes_no_hostile_answer_and_prints_escapes(
    two_cards: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Before the fix: the command wrote the id with ESC and a line break, and printed it."""
    cfg = with_agent(two_cards)
    before = cfg.model_path.read_bytes()
    hostile = {**ANSWER, "id": "j-\x1b]0;title\x07\nforged", "label": f"x {OSC8}"}
    run, _asked = answering(json.dumps(hostile))
    capsys.readouterr()
    assert cmd_journeys(args_for(cfg), run_command=run) == 1
    out = capsys.readouterr().out
    assert not RAW.search(out)
    assert "\\u001b]0;title\\u0007\\u000aforged" in out
    assert cfg.model_path.read_bytes() == before


def test_judgement_shows_stored_hostile_text_as_escapes() -> None:
    """A model from an earlier run can hold the text. The finding line does not change."""
    line = "drafted journey: old (a \x1b[31mred\x07 \u2028x) has no maintainer source review"
    out = "\n".join(judgement.report([line], teach=False))
    assert not RAW.search(out)
    assert "a \\u001b[31mred\\u0007 \\u2028x" in out


@pytest.fixture
def mapped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    write_tree(tmp_path, SOURCE)
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    capsys.readouterr()
    return tmp_path


def _judgement_request(root: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    return next(r for r in pending(root, capsys) if r["type"] == "judgement" and r["files"])


def test_decisions_refuses_a_summary_with_a_control_character(
    mapped: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Before the fix: the command recorded the summary with ESC and exited 0."""
    request = _judgement_request(mapped, capsys)
    toml = (mapped / "systemap.toml").read_bytes()
    item = {
        "request_id": request["id"],
        "verdict": "supported",
        "citations": [cite(mapped, request["files"][0]["file"])],
        "summary": "The source \x1b[31magrees\u2028.",
    }
    code, out, err = submit(mapped, capsys, item)
    assert code == 1
    assert "result 1: the summary contains a control character" in err
    assert not RAW.search(out + err)
    assert (mapped / "systemap.toml").read_bytes() == toml
    assert not (mapped / ".systemap/decisions.json").exists()


def test_decisions_shows_a_hostile_request_id_as_escapes(
    mapped: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Before the fix: the error message had 3 raw control characters."""
    item = {"request_id": "\x1b]0;owned\x07\x1b[2J", "verdict": "supported", "citations": []}
    code, out, err = submit(mapped, capsys, {**item, "summary": "s"})
    assert code == 1
    assert not RAW.search(out + err)
    assert "result 1: \\u001b]0;owned\\u0007\\u001b[2J is not a current decision request" in err


@pytest.mark.parametrize("name", ["GET /a", "pkg.reader:read"])
def test_an_answer_with_no_id_takes_the_entry_name_as_before(name: str) -> None:
    # Before the fix, the slug rule refused these normal entry names.
    noid = {key: value for key, value in ANSWER.items() if key != "id"}
    draft = journeys.read_answer(json.dumps(noid), two_card_model(), alone(route(name)))
    assert draft.problems == ()
    assert draft.journey is not None and draft.journey.id == name


def test_an_answer_with_no_id_and_an_entry_name_with_a_control_character_is_refused() -> None:
    noid = {key: value for key, value in ANSWER.items() if key != "id"}
    entry = alone(route("GET /a\x1b[2J"))
    draft = journeys.read_answer(json.dumps(noid), two_card_model(), entry)
    assert draft.journey is None
    assert draft.problems == (
        "the entry point name 'GET /a\\u001b[2J' contains a control character or a "
        "Unicode line separator. Give a short sequence id, such as read-request",
    )
