"""systemap audit, triage and the --jev flags: the questions, the thresholds, the
answers file shared with judgement, and the CLI end to end on recorded answers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, Sample, init_two_cards, write_tree
from jev_replay import Recording, serve

from systemap import audit, jev, jev_cli, nest
from systemap.cli import main
from systemap.config import Answer, ConfigError
from systemap.config import load as load_config


def tree_of(sample: Sample) -> nest.Tree:
    top = nest.Map(
        id="",
        path=sample.cfg.model_path,
        rel="map/model.py",
        model=sample.model,
        meaning=sample.meaning,
        theme=sample.theme,
    )
    return nest.Tree((top,))


def answer(key: str, **fields: Any) -> dict[str, Any]:
    return {key: fields}


# ---- the plan: which questions an audit asks ------------------------------------


def test_plan_asks_one_question_per_module_card_flow_and_invariant_pair(sample: Sample) -> None:
    plan = audit.make_plan(tree_of(sample), sample.facts, sample.cfg)
    kinds = sorted({a.key.split("|")[1] for a in plan.asks})
    assert kinds == ["flow", "governs", "owner", "sentence"]
    owners = sorted(a.key for a in plan.asks if "|owner|" in a.key)
    # the package root is an empty marker and is not asked about
    assert owners == [
        "|owner|pkg.ledger",
        "|owner|pkg.parser",
        "|owner|pkg.reader",
        "|owner|pkg.writer",
    ]
    # flows between cards whose modules import each other: parser uses reader, writer uses ledger;
    # the user is an actor, and parser -> writer and ledger -> parser share no import
    flows = sorted(a.key.split("|")[2] for a in plan.asks if "|flow|" in a.key)
    assert flows == ["Reader->Parser:parse", "Writer->Ledger:record"]
    # invariant 1 governs Writer; invariant 2 governs Writer and Ledger; actors are never asked
    governs = sorted(a.key.split("|", 2)[2] for a in plan.asks if "|governs|" in a.key)
    assert governs == ["1|Ledger", "1|Parser", "1|Reader", "2|Parser", "2|Reader"]


def test_flow_state_holds_the_lines_where_the_two_cards_meet(sample: Sample) -> None:
    plan = audit.make_plan(tree_of(sample), sample.facts, sample.cfg)
    ask = next(a for a in plan.asks if a.key == "|flow|Reader->Parser:parse")
    assert ask.state["claim"]["sentence"] == "The reader calls the parser on each request."
    assert any("pkg.parser:" in line and "Request" in line for line in ask.state["code"])


def test_unclaimed_modules_are_asked_about_on_the_top_map(sample: Sample) -> None:
    write_tree(
        sample.cfg.root, {"pkg/stray.py": '"""A stray."""\n\ndef stray() -> None:\n    pass\n'}
    )
    from systemap import extract

    facts = extract.build(sample.cfg)
    plan = audit.make_plan(tree_of(sample), facts, sample.cfg)
    stray = next(a for a in plan.asks if a.key == "|owner|pkg.stray")
    assert plan.reads[stray.key][3] == ""  # no card claims it


# ---- reading answers: each threshold, on both sides ------------------------------


def _owner_read(sample: Sample, module: str, card: str) -> tuple[Any, ...]:
    return ("owner", tree_of(sample).top, module, card)


def test_misfold_fires_below_the_threshold_only(sample: Sample) -> None:
    read = _owner_read(sample, "pkg.parser", "Parser")
    low = answer(
        "owner", choice="Reader", confidence=0.9, probabilities={"Parser": 0.04, "Reader": 0.93}
    )
    high = answer(
        "owner", choice="Reader", confidence=0.6, probabilities={"Parser": 0.05, "Reader": 0.9}
    )
    line = audit.owner_line(read, low)
    assert line is not None
    assert line.text == "jev mis-fold: Parser claims pkg.parser, which reads like Reader"
    assert line.detail[0].startswith("P(Parser) 0.04")
    assert audit.owner_line(read, high) is None


def test_unclaimed_module_gets_one_card_when_confident_else_three(sample: Sample) -> None:
    read = _owner_read(sample, "pkg.stray", "")
    sure = answer("owner", choice="Writer", confidence=0.9, probabilities={"Writer": 0.95})
    unsure = answer(
        "owner",
        choice="Writer",
        confidence=0.4,
        probabilities={"Writer": 0.4, "Parser": 0.3, "Reader": 0.2, "Ledger": 0.1},
    )
    none = answer("owner", choice=audit.NONE, confidence=0.95, probabilities={audit.NONE: 0.97})
    assert audit.owner_line(read, sure).text.endswith("it reads like Writer")  # type: ignore[union-attr]
    assert audit.owner_line(read, unsure).text.endswith("closest: Writer, Parser, Reader")  # type: ignore[union-attr]
    assert audit.owner_line(read, none).text.endswith("it reads like none of the cards")  # type: ignore[union-attr]


def test_sentence_flow_and_governs_thresholds(sample: Sample) -> None:
    top = tree_of(sample).top
    flow = sample.model.flows[1]
    inv = sample.model.invariants[0]
    assert audit.sentence_line(("sentence", top, "Reader"), answer("describes", noul=0.19))
    assert audit.sentence_line(("sentence", top, "Reader"), answer("describes", noul=0.2)) is None
    assert audit.flow_line(("flow", top, flow), answer("holds", noul=0.19))
    assert audit.flow_line(("flow", top, flow), answer("holds", noul=0.2)) is None
    got = audit.governs_line(("governs", top, inv, "Reader"), answer("governs", noul=0.8))
    assert (
        got is not None
        and got.text == "jev governs: invariant 1 may govern Reader, which it does not name"
    )
    assert audit.governs_line(("governs", top, inv, "Reader"), answer("governs", noul=0.79)) is None


# ---- answers live beside judgement's, and each command reads only its own --------


def test_audit_answers_are_told_apart_from_judgement_answers() -> None:
    mine = Answer(
        items=("jev sentence: Reader's sentence may not describe its modules",), reason="r"
    )
    sub = Answer(
        items=("Gateway: jev flow: A -> B ('x'): the code where they meet may not carry it",),
        reason="r",
    )
    family = Answer(items=(), reason="r", kind="jev governs")
    theirs = Answer(items=("single module: Reader is only pkg.reader",), reason="r")
    assert (
        audit.is_audit_answer(mine) and audit.is_audit_answer(sub) and audit.is_audit_answer(family)
    )
    assert not audit.is_audit_answer(theirs)
    assert not audit.is_audit_answer(Answer(items=(), reason="r", kind="crossing import"))


def test_apply_suppresses_answered_lines_and_reports_stale_answers() -> None:
    found = [
        audit.Line("jev sentence: Reader's sentence may not describe its modules"),
        audit.Line("jev governs: invariant 1 may govern Reader, which it does not name"),
    ]
    given = [
        Answer(items=(found[0].text,), reason="it does"),
        Answer(items=(), reason="rule scope", kind="jev governs"),
        Answer(
            items=("jev flow: A -> B ('x'): the code where they meet may not carry it",),
            reason="old",
        ),
        Answer(items=(), reason="no mis-folds any more", kind="jev mis-fold"),
        Answer(items=("single module: Reader is only pkg.reader",), reason="judgement's"),
    ]
    open_lines, answered, stale = audit.apply(found, given)
    assert open_lines == [] and answered == 2
    assert stale == [
        "jev flow: A -> B ('x'): the code where they meet may not carry it",
        'kind = "jev mis-fold"',
    ]


def test_config_accepts_audit_kinds_and_a_jev_table(tmp_path: Path) -> None:
    (tmp_path / "systemap.toml").write_text(
        '[jev]\nmodel = "jev-preview"\ncache = "cache/jev.json"\n'
        '[judgement]\nanswered = [{ kind = "jev flow", reason = "the joins are events" }]\n'
    )
    cfg = load_config(tmp_path)
    assert cfg.jev_model == "jev-preview"
    assert cfg.jev_cache_path == tmp_path / "cache/jev.json"
    assert cfg.judgement_answered[0].kind == "jev flow"
    (tmp_path / "systemap.toml").write_text('[jev]\nmodels = "x"\n')
    with pytest.raises(ConfigError, match="jev has unknown key: models"):
        load_config(tmp_path)


# ---- the client: cache, release, retries, refusals ----------------------------------


MODELS = {"models": [{"name": "jev-latest", "release_date": "2026-09-10"}]}


class Counting:
    """A transport that answers every question the same way, and counts."""

    def __init__(self, models: dict[str, Any] = MODELS) -> None:
        self.models = models
        self.posts = 0

    def __call__(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if path == "/models":
            return self.models
        self.posts += 1
        assert body is not None
        answers = {q: {"type": "noul", "noul": 0.5} for q in body["questions"]}
        return {
            "model": "jev-1",
            "answers": answers,
            "usage": {"input_tokens": 10, "output_tokens": 2},
        }


def test_cache_answers_a_second_run_and_a_new_release_invalidates_it(tmp_path: Path) -> None:
    asks = [
        jev.Ask(str(i), {"n": i}, {"q": {"type": "noul", "instructions": "?"}}) for i in range(3)
    ]
    cache = tmp_path / "jev.json"
    first = Counting()
    jev.Jev(first, cache=jev.Cache(cache)).ask(asks)
    assert first.posts == 3
    again = Counting()
    client = jev.Jev(again, cache=jev.Cache(cache))
    client.ask(asks)
    assert again.posts == 0 and client.usage.cached == 3
    newer = Counting({"models": [{"name": "jev-latest", "release_date": "2026-10-01"}]})
    jev.Jev(newer, cache=jev.Cache(cache)).ask(asks)
    assert newer.posts == 3


def test_a_model_the_api_does_not_offer_is_refused_before_anything_is_asked() -> None:
    client = jev.Jev(Counting(), model="jev-9")
    with pytest.raises(jev.JevError, match="model jev-9 is not offered; the API lists: jev-latest"):
        client.ask([jev.Ask("a", {}, {})])


def test_retries_then_succeeds_or_raises_with_the_status() -> None:
    calls = {"n": 0}

    def flaky(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] < 3:
            raise jev._Retryable(529, '{"detail": {"message": "overloaded"}}')
        return {"ok": True}

    assert jev.with_retries(flaky, pause=0)("GET", "/models", None) == {"ok": True}

    def down(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        raise jev._Retryable(429, '{"detail": {"message": "slow down"}}')

    with pytest.raises(jev.JevError, match="Jev answered 429: slow down"):
        jev.with_retries(down, attempts=2, pause=0)("GET", "/models", None)


def test_no_key_sends_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(jev.KEY_ENV, raising=False)
    with pytest.raises(jev.JevError, match="set TYPESAFE_API_KEY to ask Jev; nothing was sent"):
        jev.from_env("jev-latest", tmp_path / "c.json")


# ---- recorded answers from the real API, through the real CLI ----------------------


def test_audit_on_recorded_answers(sample: Sample) -> None:
    recording = Recording("jev_sample")
    client = jev.Jev(recording.send)
    found = audit.run(tree_of(sample), sample.facts, sample.cfg, client)
    # What the real model said about the sample, recorded. Every module reads like its own
    # card. Both flows are doubted: Reader -> Parser rightly (nothing in pkg.reader calls the
    # parser; the parser only imports Request), Writer -> Ledger because the evidence is the
    # lines naming an imported name, and `ledger.record(parts)` names none: a limit of the
    # measured method, said in audit.py's docstring.
    assert [x.text for x in found] == [
        "jev flow: Reader -> Parser ('parse'): the code where they meet may not carry it",
        "jev flow: Writer -> Ledger ('record'): the code where they meet may not carry it",
    ]
    assert client.usage.sent == 15 or recording.recording


@pytest.fixture
def two_cards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    # The name is in every question; pinned, so the recorded answers match on any machine.
    toml = tmp_path / "systemap.toml"
    toml.write_text(re.sub(r'(?m)^name = ".*"$', 'name = "two-cards"', toml.read_text()))
    assert main(["--root", str(tmp_path), "extract"]) == 0
    monkeypatch.setenv(jev.KEY_ENV, "recorded")
    return tmp_path


def test_audit_cli_end_to_end_over_http(
    two_cards: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    recording = Recording("jev_two_cards")
    with serve(recording) as url:
        monkeypatch.setenv(jev.BASE_ENV, url)
        assert main(["--root", str(two_cards), "audit"]) == 0
        first = capsys.readouterr().out
        assert main(["--root", str(two_cards), "audit"]) == 0
        second = capsys.readouterr().out
    assert first.splitlines()[0].startswith("audit: ")
    assert "from the cache" in second and "jev: 0 sent" in second
    assert (two_cards / ".systemap/jev-cache.json").exists()


def test_audit_dry_run_sends_no_question(
    two_cards: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    recording = Recording("jev_two_cards")
    with serve(recording) as url:
        monkeypatch.setenv(jev.BASE_ENV, url)
        assert main(["--root", str(two_cards), "audit", "--dry-run"]) == 0
    assert recording.sent == [("GET", "/models")]
    assert "audit --dry-run: " in capsys.readouterr().out


def test_audit_without_a_key_says_so_and_exits_1(
    two_cards: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(jev.KEY_ENV)
    assert main(["--root", str(two_cards), "audit"]) == 1
    assert "set TYPESAFE_API_KEY" in capsys.readouterr().out


def test_triage_names_the_cards_with_their_modules(
    two_cards: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    recording = Recording("jev_two_cards")
    with serve(recording) as url:
        monkeypatch.setenv(jev.BASE_ENV, url)
        text = "Reading a file with a BOM leaves the BOM in the first request's body"
        assert main(["--root", str(two_cards), "triage", text]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("triage: confidence ")
    assert any("pkg.reader" in line or "pkg.writer" in line for line in out)


def test_judgement_ignores_audit_answers(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    toml = two_cards / "systemap.toml"
    toml.write_text(
        toml.read_text()
        + '\n[judgement]\nanswered = [{ item = "jev sentence: Reader\'s sentence may not describe its modules", reason = "r" }]\n'
    )
    main(["--root", str(two_cards), "judgement"])
    assert "stale" not in capsys.readouterr().out


# ---- delta --jev and suggest --jev: the pieces that read the report and the pairs ---


def test_unclaimed_modules_are_read_off_delta_lines() -> None:
    lines = [
        "added: pkg.new, claimed by no card; name it in a card's implemented_by in map/model.py, or ignore it",
        "Gateway: added: pkg.gate.x, claimed by no card; the map inside Gateway claims exactly",
        "moved: pkg.a -> pkg.b (same content); no card claims pkg.b: name it in a card's implemented_by",
        "added: pkg.claimed, claimed by Reader",
    ]
    assert jev_cli.unclaimed_in(lines) == ["pkg.new", "pkg.gate.x", "pkg.b"]


def test_groups_are_connected_components_largest_first() -> None:
    mods = ["a", "b", "c", "d", "e"]
    assert jev_cli.groups(mods, [("a", "b"), ("b", "c"), ("d", "e")]) == [
        ["a", "b", "c"],
        ["d", "e"],
    ]


def test_pair_candidates_chain_each_package_and_add_imports() -> None:
    facts = {
        "components": {
            "p.a": {"imports": ["q.x"]},
            "p.b": {"imports": []},
            "p.c": {"imports": []},
            "q.x": {"imports": []},
        }
    }
    assert jev_cli.pair_candidates(facts, ["p.a", "p.b", "p.c", "q.x"]) == [
        ("p.a", "p.b"),
        ("p.a", "q.x"),
        ("p.b", "p.c"),
    ]


def test_recordings_hold_real_responses() -> None:
    for name in ("jev_sample", "jev_two_cards"):
        data = json.loads((Path(__file__).parent / "fixtures" / f"{name}.json").read_text())
        posts = [v for v in data.values() if "answers" in v]
        assert posts and all(v["model"].startswith("jev-") for v in posts)
