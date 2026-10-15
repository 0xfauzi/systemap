"""The contract is separate from the map (issue 98).

The contract file (`map/contract.py`) holds the invariants and the import rules. The map
files hold the other model values. Acceptance values, for a Python fixture and a
TypeScript fixture where the behavior applies to both languages:

1. `systemap init` writes `map/contract.py` with an empty CONTRACT, and a model file
   without invariants. The new map loads. init prints one suggested CODEOWNERS line for
   `map/contract.py`, and it writes no CODEOWNERS file. If the model file is present,
   init writes no contract file.
2. The first `systemap extract` moves the invariants and the import rules of
   `map/model.py` to `map/contract.py`. The loaded MODEL and MEANING are equal before and
   after the move. The model file loses only the moved text: the assignments with their
   comments, the keywords, and the imported names that it does not use after the move.
   A second `extract` and a `refresh` write neither file. An empty contract file from
   init gets the moved rules.
3. If the model file and the contract file each contain rules, each command gives a
   configuration error that names the two files.
4. A contract rule without a reason gives one `contract reason` line in `check` and in
   `judgement`. The exit code of `check` does not change. A rule with a reason gives no
   line.
5. The move changes no source review digest, no flow review digest, and no evidence
   digest of a line that names a component. An answer that is current before the move is
   current after the move, also for a line with the full evidence.
6. Each nested map gets its own contract file beside its model file
   (`map/gateway.py` -> `map/gateway_contract.py`).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from conftest import TWO_CARD_MODEL, init_two_cards, write_tree
from test_answer_evidence import FIXTURE, SOURCE

from systemap import (
    answer_write,
    card_review,
    config,
    contract,
    extract,
    flow_review,
    judgement,
    judgement_evidence,
    judgement_json,
    nest,
)
from systemap.cli import main

SCRIPT = '[project]\nname = "pkg"\nversion = "0"\n'
RULE = 'ImportRule("reader-alone", "forbid_import", src=("Reader",), dst=("Writer",))'
# The Python model: the two-card model with a comment above INVARIANTS and an import rule.
PY_BLOCK = (
    "# The rules of the writer.\n"
    "INVARIANTS = (\n"
    '    Invariant(1, "The writer never reads the input itself.", governs=("Writer",)),\n'
    ")\n\n"
    f"IMPORT_RULES = ({RULE},)\n\n"
)
PY_OLD = (
    TWO_CARD_MODEL.replace("    Flow,\n", "    Flow,\n    ImportRule,\n    Invariant,\n")
    .replace("FLOW_KINDS = ()\n\n", "FLOW_KINDS = ()\n\n" + PY_BLOCK)
    .replace(
        "    flow_kinds=FLOW_KINDS,\n)",
        "    flow_kinds=FLOW_KINDS,\n    invariants=INVARIANTS,\n    import_rules=IMPORT_RULES,\n)",
    )
)
# The moved model is the two-card model of the other tests.
PY_NEW = TWO_CARD_MODEL
# The TypeScript model: the rules are literal values in the MODEL call.
TS_RULES = (
    'invariants=(Invariant(1, "The application serves each user.", governs=("Application",)),),\n'
    '    import_rules=(ImportRule("one-part", "forbid_cycle"),),\n'
)
TS_IMPORT = "from systemap.model import Component, Container, Meaning, Model, Region\n"


@pytest.fixture(params=["python", "typescript"])
def old_map(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """A map from before the contract file: the rules are in map/model.py."""
    if request.param == "python":
        write_tree(tmp_path, {**SOURCE, "pyproject.toml": SCRIPT})
        init_two_cards(tmp_path, "--no-ci")
        (tmp_path / "map/model.py").write_text(PY_OLD, encoding="utf-8")
    else:
        shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
        path = tmp_path / "map/model.py"
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            TS_IMPORT, TS_IMPORT.replace("Container,", "Container, ImportRule, Invariant,")
        )
        path.write_text(text.replace("invariants=(),\n", TS_RULES), encoding="utf-8")
    (tmp_path / "map/contract.py").unlink(missing_ok=True)
    return tmp_path


def run(root: Path, *argv: str) -> int:
    return main(["--root", str(root), *argv])


def loaded(root: Path) -> nest.Tree:
    return nest.load(config.load(root))


def read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


# ---- 1. init -------------------------------------------------------------------------


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_init_writes_an_empty_contract_and_suggests_a_codeowners_line(
    language: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 1."""
    if language == "python":
        write_tree(tmp_path, {**SOURCE, "pyproject.toml": SCRIPT})
    else:
        write_tree(tmp_path, {"package.json": '{"name": "web"}\n', "tsconfig.json": "{}\n"})
        write_tree(tmp_path, {"src/index.ts": "export const a = 1;\n"})
    assert run(tmp_path, "init", "--no-ci") == 0
    out = capsys.readouterr().out
    assert "wrote map/contract.py" in out
    assert "/map/contract.py @" in out
    assert not (tmp_path / "CODEOWNERS").exists()
    assert not (tmp_path / ".github/CODEOWNERS").exists()
    assert "invariants=" not in read(tmp_path, "map/model.py")
    assert "CONTRACT = Contract(" in read(tmp_path, "map/contract.py")
    tree = loaded(tmp_path)
    assert tree.top.model.invariants == () and tree.top.model.import_rules == ()


def test_init_writes_no_contract_beside_an_existing_model(tmp_path: Path) -> None:
    """Acceptance 1: a present model file keeps its rules, and init adds no contract."""
    write_tree(tmp_path, {**SOURCE, "pyproject.toml": SCRIPT, "map/model.py": PY_OLD})
    assert run(tmp_path, "init", "--no-ci") == 0
    assert not (tmp_path / "map/contract.py").exists()


# ---- 2. the one-time move ------------------------------------------------------------


def test_the_first_extract_moves_the_rules_one_time(
    old_map: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 2."""
    before = loaded(old_map).top
    old_text = read(old_map, "map/model.py")
    assert run(old_map, "extract") == 0
    assert "contract: the command moved 1 invariant and 1 import rule" in capsys.readouterr().out
    after = loaded(old_map).top
    assert (after.model, after.meaning) == (before.model, before.meaning)
    moved = read(old_map, "map/contract.py")
    assert "CONTRACT = Contract(invariants=INVARIANTS, import_rules=IMPORT_RULES)" in moved
    new_text = read(old_map, "map/model.py")
    if config.load(old_map).language == "python":
        assert new_text == PY_NEW
        assert "# The rules of the writer.\nINVARIANTS: tuple[Invariant, ...] = (" in moved
    else:
        expected = old_text.replace("    " + TS_RULES, "").replace(
            "Container, ImportRule, Invariant,", "Container,"
        )
        assert new_text == expected
    for command in ("extract", "refresh"):
        run(old_map, command)
        assert read(old_map, "map/model.py") == new_text
        assert read(old_map, "map/contract.py") == moved
        assert "contract: the command moved" not in capsys.readouterr().out


def test_the_move_fills_an_empty_contract_from_init(tmp_path: Path) -> None:
    """Acceptance 2: init wrote an empty contract, and then the agent wrote old rules."""
    write_tree(tmp_path, {**SOURCE, "pyproject.toml": SCRIPT})
    init_two_cards(tmp_path, "--no-ci")
    (tmp_path / "map/model.py").write_text(PY_OLD, encoding="utf-8")
    (tmp_path / "map/contract.py").write_text(contract.text("map/model.py"), encoding="utf-8")
    empty = read(tmp_path, "map/contract.py")
    before = loaded(tmp_path).top.model
    assert run(tmp_path, "extract") == 0
    assert loaded(tmp_path).top.model == before
    assert read(tmp_path, "map/model.py") == PY_NEW
    assert read(tmp_path, "map/contract.py") != empty


def test_a_model_that_the_move_cannot_edit_gives_a_warning_and_no_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The careful edit refuses a moved name that the map also uses, and writes no file."""
    write_tree(tmp_path, {**SOURCE, "pyproject.toml": SCRIPT})
    init_two_cards(tmp_path, "--no-ci")
    (tmp_path / "map/contract.py").unlink()
    text = PY_OLD.replace("PLAIN = {", "RULES = INVARIANTS\n\nPLAIN = {")
    (tmp_path / "map/model.py").write_text(text, encoding="utf-8")
    assert run(tmp_path, "extract") == 0
    err = capsys.readouterr().err
    assert "warning: the command cannot move the contract of map/model.py" in err
    assert not (tmp_path / "map/contract.py").exists()
    assert read(tmp_path, "map/model.py") == text


# ---- 3. two files with rules -----------------------------------------------------------


def test_rules_in_the_model_and_in_the_contract_are_a_configuration_error(old_map: Path) -> None:
    """Acceptance 3."""
    assert run(old_map, "extract") == 0
    contract_text = read(old_map, "map/contract.py")
    shutil.copyfile(old_map / "map/model.py", old_map / "map/new.py")
    if config.load(old_map).language == "python":
        (old_map / "map/model.py").write_text(PY_OLD, encoding="utf-8")
    else:
        path = old_map / "map/model.py"
        text = path.read_text(encoding="utf-8")
        text = text.replace(TS_IMPORT, TS_IMPORT.replace("Container,", "Container, Invariant,"))
        path.write_text(
            text.replace(
                "flow_kinds=(),\n", "flow_kinds=(),\n    " + TS_RULES.split("\n")[0] + "\n"
            ),
            encoding="utf-8",
        )
    assert read(old_map, "map/contract.py") == contract_text
    with pytest.raises(config.ConfigError) as caught:
        loaded(old_map)
    assert "map/model.py" in str(caught.value) and "map/contract.py" in str(caught.value)
    assert run(old_map, "check") == 2


# ---- 4. a rule without a reason --------------------------------------------------------


def test_a_rule_without_a_reason_gives_a_contract_reason_line(
    old_map: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4."""
    assert run(old_map, "refresh") == 0
    capsys.readouterr()
    rule = "reader-alone" if config.load(old_map).language == "python" else "one-part"
    expected = [
        "contract reason: invariant 1 has no reason",
        f"contract reason: import rule {rule} has no reason",
    ]
    cfg = config.load(old_map)
    lines = judgement.run_tree(loaded(old_map), extract.build(cfg))
    assert [line for line in lines if line.startswith("contract reason")] == expected
    code = run(old_map, "check")
    out = capsys.readouterr().out
    assert code == 0
    assert "contract reason: 2 findings" in out
    assert all(f"  {line.removeprefix('contract reason: ')}" in out for line in expected)
    path = old_map / "map/contract.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace("governs=(", 'reason="The documentation states it.", governs=(')
    text = text.replace(RULE, RULE[:-1] + ', reason="The design note states it.")')
    text = text.replace('"forbid_cycle")', '"forbid_cycle", reason="The design note states it.")')
    path.write_text(text, encoding="utf-8")
    assert contract.unreasoned(loaded(old_map).top.model) == []


def test_a_contract_reason_line_has_no_value_that_changes() -> None:
    """The identity rule of AGENTS.md: the line has the kind, the rule, and no position."""
    from systemap.model import ImportRule, Invariant, Model

    model = Model(
        canvas=(0, 0),
        containers=(),
        regions=(),
        components=(),
        flows=(),
        flow_kinds=(),
        invariants=(Invariant(3, "A rule.", reason=" "), Invariant(4, "B.", reason="Cause.")),
        import_rules=(ImportRule("r1", "forbid_cycle"),),
    )
    assert contract.unreasoned(model) == [
        "contract reason: invariant 3 has no reason",
        "contract reason: import rule r1 has no reason",
    ]


# ---- 5. digests and answers ------------------------------------------------------------


def review_digests(root: Path, facts: dict[str, Any]) -> dict[str, str | None]:
    """Give the source review digest of each component and the review digest of each flow."""
    m = loaded(root).top
    out = {c.id: card_review.digest(c, m.model, m.meaning, facts) for c in m.model.components}
    return out | {f.key: flow_review.digest(f, m.meaning, facts) for f in m.model.flows}


def named_lines(root: Path, lines: list[str]) -> list[str]:
    """Give the lines that name a component of the top map."""
    ids = [c.id for c in loaded(root).top.model.components]
    return [line for line in lines if any(judgement_evidence.names(i, line) for i in ids)]


def test_the_move_changes_no_digest_and_keeps_answers_current(old_map: Path) -> None:
    """Acceptance 5."""
    cfg = config.load(old_map)
    facts = extract.build(cfg)
    reviews = review_digests(old_map, facts)
    lines = judgement.run_tree(loaded(old_map), facts)
    named = named_lines(old_map, lines)
    full = [line for line in lines if line not in named]
    assert named and full
    before = judgement.evidence_for_tree(loaded(old_map), facts, old_map, lines)
    answers = [{"item": line, "reason": "A test.", "evidence": before[line]} for line in lines]
    answer_write.add(old_map, cfg.source, answers)
    cfg = config.load(old_map)
    assert judgement_json.evaluate(loaded(old_map), facts, cfg).result.pending == []
    assert run(old_map, "extract") == 0
    assert (old_map / "map/contract.py").is_file()
    assert review_digests(old_map, facts) == reviews
    after = judgement.evidence_for_tree(loaded(old_map), facts, old_map, lines)
    assert {line: after[line] for line in named} == {line: before[line] for line in named}
    assert all(after[line] != before[line] for line in full)
    cfg = config.load(old_map)
    assert judgement_json.evaluate(loaded(old_map), facts, cfg).result.pending == []


def test_a_reason_is_not_a_claim_of_a_component() -> None:
    """A new reason changes no source review digest and no answer evidence."""
    from systemap.model import Invariant

    rule = Invariant(1, "A rule.", governs=("A",))
    assert contract.claim(rule) == contract.claim(Invariant(1, "A rule.", ("A",), "A cause."))
    assert set(contract.claim(rule)) == {"n", "text", "governs"}


# ---- 6. nested maps --------------------------------------------------------------------


def test_each_nested_map_gets_its_own_contract_file(tmp_path: Path) -> None:
    """Acceptance 6."""
    from test_nested import CONFIG, GATEWAY, STYLE, TOP, TREE

    rules = 'invariants=(Invariant(1, "The app records each request.", governs=("App",)),),\n'
    gateway = GATEWAY.replace("Container, Flow", "Container, Flow, Invariant").replace(
        "flow_kinds=())", "flow_kinds=(), " + rules.rstrip(",\n") + ")"
    )
    models = {"map/model.py": TOP, "map/gateway.py": gateway, "map/style.py": STYLE}
    write_tree(tmp_path, {**TREE, "systemap.toml": CONFIG, **models})
    assert run(tmp_path, "place") == 0
    before = loaded(tmp_path).get("Gateway").model
    assert before.invariants
    assert run(tmp_path, "extract") == 0
    assert (tmp_path / "map/gateway_contract.py").is_file()
    assert not (tmp_path / "map/contract.py").exists()
    assert not (tmp_path / "map/style_contract.py").exists()
    assert "Invariant(" not in read(tmp_path, "map/gateway.py")
    assert loaded(tmp_path).get("Gateway").model == before
    assert contract.path_for(Path("map/model.py")) == Path("map/contract.py")
    assert contract.path_for(Path("map/gateway.py")) == Path("map/gateway_contract.py")
