"""The command `systemap claims`: the map claims about one component or one module.

Each case starts from the two-card map after one refresh. The command reads the model and
the stored facts, and it calls no decision provider.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import init_two_cards, write_tree

from systemap import claims_cli
from systemap.cli import main

MODULES = {
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}
RULE = (
    'ImportRule("reader-alone", "forbid_import", src=("Reader",), dst=("Writer",), '
    'reason="The reader does not use the writer.")'
)


def current(root: Path, *rules: str) -> None:
    write_tree(root, MODULES)
    init_two_cards(root, "--no-ci")
    if rules:
        path = root / "map/contract.py"
        old = "IMPORT_RULES: tuple[ImportRule, ...] = ()"
        text = path.read_text(encoding="utf-8")
        assert old in text
        path.write_text(
            text.replace(old, f"IMPORT_RULES = ({', '.join(rules)},)"), encoding="utf-8"
        )
    assert main(["--root", str(root), "refresh"]) == 0


def found(root: Path, name: str, capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    capsys.readouterr()
    assert main(["--root", str(root), "claims", name, "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["query"] == name
    records: list[dict[str, object]] = result["found"]
    return records


def test_a_component_id_gives_its_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    (record,) = found(tmp_path, "Reader", capsys)
    assert record["component"] == "Reader"
    assert record["map"] == "."
    assert record["region"] == "core"
    assert record["does"] == "Reads the input and turns it into a request."
    assert record["modules"] == ["pkg.reader"]


def test_a_module_name_and_a_file_path_give_the_component(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    by_id = found(tmp_path, "Writer", capsys)
    assert found(tmp_path, "pkg.writer", capsys) == by_id
    assert found(tmp_path, "pkg/writer.py", capsys) == by_id
    assert found(tmp_path, "./pkg/writer.py", capsys) == by_id


def test_flows_have_the_component_at_the_correct_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    (reader,) = found(tmp_path, "Reader", capsys)
    (writer,) = found(tmp_path, "Writer", capsys)
    out = reader["flows_out"]
    assert isinstance(out, list) and out
    assert all(flow["src"] == "Reader" for flow in out)
    assert writer["flows_in"] == [flow for flow in out if flow["dst"] == "Writer"]


def test_an_import_rule_shows_for_its_source_and_its_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path, RULE)
    (reader,) = found(tmp_path, "Reader", capsys)
    (writer,) = found(tmp_path, "Writer", capsys)
    assert reader["import_rules"] == [
        {
            "id": "reader-alone",
            "kind": "forbid_import",
            "result": "pass",
            "effect": "must not import Writer",
            "reason": "The reader does not use the writer.",
        }
    ]
    (rule,) = writer["import_rules"]  # type: ignore[misc]
    assert rule["effect"] == "Reader must not import this component"


def test_a_rule_against_the_code_shows_the_result_fail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    (tmp_path / "pkg/reader.py").write_text(
        "from pkg import writer\n\n\ndef read(source: str) -> str:\n    return writer.write(source)\n",
        encoding="utf-8",
    )
    path = tmp_path / "map/contract.py"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("IMPORT_RULES: tuple[ImportRule, ...] = ()", f"IMPORT_RULES = ({RULE},)"),
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), "extract"]) == 0
    (reader,) = found(tmp_path, "Reader", capsys)
    (rule,) = reader["import_rules"]  # type: ignore[misc]
    assert rule["result"] == "fail"


def test_the_text_output_has_each_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path, RULE)
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "claims", "Reader"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Reader")
    assert "component in the map ., region core" in out
    assert "modules (1): pkg.reader" in out
    assert "import rules (1):" in out
    assert "  reader-alone (forbid_import, pass): must not import Writer." in out
    assert "flows to this component (" in out
    assert "flows from this component (" in out
    assert "sequences (" in out


def test_an_unknown_name_gives_the_nearest_names_and_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "claims", "Reeder"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "No component and no module has the name Reeder." in captured.err
    assert "The nearest names are Reader, pkg.reader." in captured.err


def test_no_facts_gives_the_action_and_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, MODULES)
    init_two_cards(tmp_path, "--no-ci")
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "claims", "Reader"]) == 1
    assert "run: systemap extract" in capsys.readouterr().err


def test_the_command_writes_no_file(tmp_path: Path) -> None:
    current(tmp_path)
    before = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}
    assert main(["--root", str(tmp_path), "claims", "Reader"]) == 0
    after = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}
    assert after == before


def test_rule_effects_for_each_kind() -> None:
    from systemap.model import ImportRule

    cycle = ImportRule("c", "forbid_cycle", src=("A", "B"))
    everything = ImportRule("e", "forbid_cycle")
    allow = ImportRule("a", "allow_imports", src=("A",), dst=("B",))
    alone = ImportRule("o", "allow_imports", src=("A",))
    assert claims_cli._rule_text(cycle, "A") == "must not be in an import cycle of A, B"
    assert claims_cli._rule_text(cycle, "C") == ""
    assert (
        claims_cli._rule_text(everything, "C") == "must not be in an import cycle of the components"
    )
    assert claims_cli._rule_text(allow, "A") == "can import only its own modules and B"
    assert claims_cli._rule_text(allow, "B") == ""
    assert claims_cli._rule_text(alone, "A") == "can import only its own modules"
