"""The answer writer adds or renews exact answers and keeps the other text of the file.

Acceptance values:

1. For each form of the judgement table, the TOML parser gives the previous data with
   only the new answers added, and the comments of the file stay.
2. An answer for a line that has an exact answer replaces that answer. The list does not
   get a second answer for the same line.
3. A configuration with an answer without citations stays correct, and an answer with
   citations keeps them.
4. If the writer cannot keep the other values, it writes nothing. If UTF-8 cannot encode
   the text of an answer, the writer also writes nothing.
5. The writer keeps the line end that the file uses (result `followup-answer-newlines`).
   For each form, a file with CRLF line ends has 0 LF without a CR after the write, and a
   file with LF line ends has 0 CR after the write.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from systemap import answer_write, config
from systemap.config import ConfigError

ENTRY = {
    "item": 'single module: A contains "only" x',
    "evidence": "0" * 64,
    "reason": "r # not a comment",
    "citations": [{"file": "a.py", "start_line": 1, "end_line": 2, "sha256": "1" * 64}],
}
OLD = '{ item = "a", reason = "b" }'
FORMS = {
    "list": f"[judgement]\nanswered = [\n    {OLD},  # note\n]\n[flows]\nobserved_by = []\n",
    "no comma": '[judgement]\nanswered = [\n    { item = "a]", reason = "b" }\n]\n',
    "one line": f"[judgement]\nanswered = [{OLD}]\n",
    "empty": "[judgement]\nanswered = []\n",
    "no key": "[judgement] # c\nrequire_reviews = true\n\n[flows]\nobserved_by = []\n",
    "no table": 'name = "x"\n[[figures]]\nout = "a.svg"\n',
    "crlf": f"[judgement]\r\nanswered = [\r\n    {OLD},\r\n]\r\n",
    "multi-line": '[judgement]\nanswered = [\n  { items = [\n   "a",\n   "b",\n  ], reason = """x\n]""" },\n]\n',
    "literal": "[judgement]\nanswered = [\n  { item = 'a\\', reason = '''b]''' },\n]\n",
}


def answers(text: str) -> list[object]:
    return list(tomllib.loads(text).get("judgement", {}).get("answered", []))


@pytest.mark.parametrize("form", list(FORMS))
def test_each_form_gets_the_answer_and_keeps_its_text(tmp_path: Path, form: str) -> None:
    """Acceptance 1."""
    text = FORMS[form]
    (tmp_path / "systemap.toml").write_bytes(text.encode("utf-8"))
    answer_write.add(tmp_path, "systemap.toml", [ENTRY])
    new = (tmp_path / "systemap.toml").read_bytes().decode("utf-8")
    assert answers(new) == [*answers(text), ENTRY]
    before, after = tomllib.loads(text), tomllib.loads(new)
    before.pop("judgement", None), after.pop("judgement", None)
    assert before == after
    for comment in ("# note", "# c"):
        assert (comment in text) == (comment in new)


def test_an_answer_for_the_same_line_replaces_the_old_answer(tmp_path: Path) -> None:
    """Acceptance 2: the evidence, reason, and citations change in place."""
    line = ENTRY["item"]
    text = (
        "# answers\n[judgement]\nanswered = [\n"
        '    { item = "other", reason = "keep" },\n'
        f'    {{ item = {json.dumps(line)}, reason = "old", evidence = "{"2" * 64}" }},\n'
        "]\n"
    )
    (tmp_path / "systemap.toml").write_text(text, encoding="utf-8")
    answer_write.add(tmp_path, "systemap.toml", [ENTRY])
    new = (tmp_path / "systemap.toml").read_text(encoding="utf-8")
    assert answers(new) == [{"item": "other", "reason": "keep"}, ENTRY]
    assert new.startswith("# answers\n")


def test_citations_are_optional_and_kept(tmp_path: Path) -> None:
    """Acceptance 3."""
    (tmp_path / "systemap.toml").write_text(FORMS["list"], encoding="utf-8")
    assert config.load(tmp_path).judgement_answered[0].citations == ()
    answer_write.add(tmp_path, "systemap.toml", [ENTRY])
    cited = config.load(tmp_path).judgement_answered[1].citations
    assert cited == (("a.py", 1, 2, "1" * 64),)


def test_incorrect_citations_give_a_configuration_error(tmp_path: Path) -> None:
    """A citation with a reversed line span is a configuration error."""
    bad = (
        '{ item = "a", reason = "b", citations = [{ file = "a.py", start_line = 3, end_line = 2, sha256 = "'
        + "1" * 64
        + '" }] }'
    )
    (tmp_path / "systemap.toml").write_text(f"[judgement]\nanswered = [{bad}]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="start_line must not be more than end_line"):
        config.load(tmp_path)


def test_a_table_of_arrays_form_is_refused_and_nothing_changes(tmp_path: Path) -> None:
    """Acceptance 4: the writer cannot add to an inline table, so it writes nothing."""
    text = 'judgement = { answered = [{ item = "a", reason = "b" }] }\n'
    (tmp_path / "systemap.toml").write_text(text, encoding="utf-8")
    with pytest.raises(answer_write.AnswerWriteError, match="It wrote no file"):
        answer_write.add(tmp_path, "systemap.toml", [ENTRY])
    assert (tmp_path / "systemap.toml").read_text(encoding="utf-8") == text


def test_text_that_utf8_cannot_encode_is_refused_and_nothing_changes(tmp_path: Path) -> None:
    """Acceptance 4: a lone surrogate gives AnswerWriteError, not UnicodeEncodeError (llm-3)."""
    text = FORMS["empty"]
    (tmp_path / "systemap.toml").write_text(text, encoding="utf-8")
    entry = {**ENTRY, "reason": "x\ud800y"}
    with pytest.raises(answer_write.AnswerWriteError, match="UTF-8 cannot encode"):
        answer_write.add(tmp_path, "systemap.toml", [entry])
    assert (tmp_path / "systemap.toml").read_text(encoding="utf-8") == text


def test_the_decisions_settings_are_validated(tmp_path: Path) -> None:
    """`[decisions] max_contradicted` must be an integer of 1 or more."""
    toml = tmp_path / "systemap.toml"
    toml.write_text("[decisions]\nmax_contradicted = 1\n", encoding="utf-8")
    assert config.load(tmp_path).max_contradicted == 1
    toml.write_text("[decisions]\nmax_contradicted = 0\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="max_contradicted"):
        config.load(tmp_path)
    toml.write_text('[judgement]\nrequire_reviews = "yes"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="require_reviews"):
        config.load(tmp_path)


def _line_ends(raw: bytes) -> tuple[int, int]:
    """Give the number of CRLF line ends and the number of LF line ends without a CR."""
    crlf = raw.count(b"\r\n")
    return crlf, raw.count(b"\n") - crlf


@pytest.mark.parametrize("form", list(FORMS))
def test_a_crlf_file_keeps_crlf_line_ends(tmp_path: Path, form: str) -> None:
    """Acceptance 5: the added rows also have CRLF line ends."""
    text = FORMS[form].replace("\r\n", "\n").replace("\n", "\r\n")
    (tmp_path / "systemap.toml").write_bytes(text.encode("utf-8"))
    answer_write.add(tmp_path, "systemap.toml", [ENTRY])
    raw = (tmp_path / "systemap.toml").read_bytes()
    crlf, lf = _line_ends(raw)
    assert (crlf > text.count("\r\n"), lf) == (True, 0)
    assert answers(raw.decode("utf-8")) == [*answers(text), ENTRY]


@pytest.mark.parametrize("form", list(FORMS))
def test_an_lf_file_keeps_lf_line_ends(tmp_path: Path, form: str) -> None:
    """Acceptance 5: the added rows also have LF line ends."""
    text = FORMS[form].replace("\r\n", "\n")
    (tmp_path / "systemap.toml").write_bytes(text.encode("utf-8"))
    answer_write.add(tmp_path, "systemap.toml", [ENTRY])
    raw = (tmp_path / "systemap.toml").read_bytes()
    assert raw.count(b"\r") == 0
    assert _line_ends(raw)[1] > text.count("\n")
