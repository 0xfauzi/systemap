"""Names with a control character, and two `export * from` statements (audit findings
rest-5, g1full-4 and llm-6).

Before the repair, a newline or ESC in a file name, a TypeScript string export name, a
package.json name or bin key, or a pyproject.toml script key went into the facts and into
the finding lines. `systemap check` printed six forged lines that started with "missing
source review:" for the fixture of the first test. A module with two unresolved
`export * from` statements gave one record, for the last statement only. Each acceptance
value is in the docstring of its test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import (
    config,
    control_names,
    extract,
    file_names,
    source_facts,
    typescript_config,
    unknown_causes,
)
from systemap.cli import main
from systemap.config import ConfigError

HOSTILE = "\nmissing source review: Core has no source_review digest. \x1b[31m'q\"\nFORGED"
# The file name has no `"`, so that a JSON string in the test needs no escape.
FILE_PART = HOSTILE.replace('"', "")
TS_CONFIG = 'language = "typescript"\n[package_roots]\n"src" = "web"\n'
FORGED = ("missing source review:", "FORGED")


def _file(path: Path, text: str) -> None:
    """Write a file with a control character in its name. Skip the test if the file
    system refuses the name."""
    if sys.platform == "win32":
        pytest.skip("the file system does not keep a control character in a name")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(text, encoding="utf-8")
    except OSError:
        pytest.skip("the file system does not keep a control character in a name")


def _ts_tree(root: Path) -> None:
    export = json.dumps("x" + HOSTILE)
    package = {"name": "web" + HOSTILE, "exports": "./dist/a.js", "bin": {"t" + HOSTILE: "./b.js"}}
    write_tree(
        root,
        {
            "package.json": json.dumps(package),
            "tsconfig.json": '{"compilerOptions":{}}',
            "src/index.ts": "export function serve(): void {}\n",
            "src/a.ts": f'export {{ a as {export} }} from "./missing";\nexport const b = 1;\n',
            "src/s.ts": 'export * from "./gone1";\nexport * from "./gone2";\n',
        },
    )
    _file(root / "src" / f"f{FILE_PART}.ts", "export const d = 1;\n")


def _with_card(root: Path, modules: str, entry: str) -> None:
    """Give the starter model one component that claims `modules`."""
    model = root / "map" / "model.py"
    card = (
        f'(Component(id="Core", does="keeps values", implemented_by=({modules}), '
        f'region="a", entry="{entry}", x=56, y=120),)'
    )
    text = model.read_text(encoding="utf-8")
    text = text.replace("COMPONENTS: tuple[Component, ...] = ()", f"COMPONENTS = {card}")
    text = text.replace("PLAIN: dict[str, str] = {}", 'PLAIN = {"Core": "holds values"}')
    model.write_text(text, encoding="utf-8")


def _output(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> str:
    capsys.readouterr()
    main(["--root", str(root), *argv])
    found = capsys.readouterr()
    return found.out + found.err


def _facts(root: Path) -> dict[str, Any]:
    return extract.build(config.load(root))


def test_hostile_typescript_names_give_no_forged_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: `extract`, `check`, `judgement`, `judgement --brief` and `judgement
    --json` give no line that starts with a forged text, and no ESC character. Before
    the repair, `check` gave six forged lines."""
    _ts_tree(tmp_path)
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    (tmp_path / "systemap.toml").write_text(TS_CONFIG, encoding="utf-8")
    _with_card(tmp_path, '"web.*",', "b")
    commands = (["extract"], ["check"], ["judgement"], ["judgement", "--brief"])
    for argv in [*commands, ["judgement", "--json"]]:
        text = _output(tmp_path, capsys, *argv)
        assert "\x1b" not in text, argv
        assert not [line for line in text.split("\n") if line.startswith(FORGED)], argv
    brief = _output(tmp_path, capsys, "judgement", "--brief")
    assert "cause: name" in brief
    assert "unknown surface: module web.s (src/s.ts): the re-export target './gone1'" in brief


def test_a_file_name_with_a_control_character_is_a_record_with_the_cause_name(
    tmp_path: Path,
) -> None:
    """Acceptance: the module identifier and the file show the escapes. The record has
    the cause `name`. Before the repair, the identifier contained the newline."""
    write_tree(tmp_path, {"systemap.toml": '[package_roots]\n"pkg" = "pkg"\n'})
    write_tree(tmp_path, {"pkg/__init__.py": "def main() -> None: ...\n"})
    _file(tmp_path / "pkg" / "m\nx\x1b.py", "def f() -> None: ...\n")
    components = _facts(tmp_path)["components"]
    record = components["pkg.m\\u000ax\\u001b"]
    assert record["file"] == "pkg/m\\u000ax\\u001b.py"
    assert record["completeness"]["cause"] == unknown_causes.NAME
    assert (
        record["parse_error"]["reason"] == f"source could not be read: {file_names.CONTROL_REASON}"
    )
    assert not [module for module in components if "\n" in module]


def test_a_script_key_with_a_control_character_is_an_issue_and_not_an_entry_point(
    tmp_path: Path,
) -> None:
    """Acceptance: the console script `t\\nx` is not an entry point. It gives one issue
    with the cause `name` and the escaped name. The script `ok` stays. Before the repair,
    the entry point list contained `t\\nx`."""
    write_tree(
        tmp_path,
        {
            "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
            "pkg/__init__.py": "def main() -> None: ...\n\ndef other() -> None: ...\n",
            "pyproject.toml": '[project]\nname = "pkg"\nversion = "0"\n[project.scripts]\n'
            '"t\\nx" = "pkg:other"\nok = "pkg:main"\n',
        },
    )
    facts = _facts(tmp_path)
    names = [point["name"] for point in facts["entry_points"]]
    assert "ok" in names
    assert not [name for name in names if "\n" in name]
    (issue,) = facts["entry_point_issues"]
    assert (issue["name"], issue["cause"]) == ("t\\u000ax", unknown_causes.NAME)
    lines = source_facts.unknown_fact_lines(facts)
    assert (
        "unknown surface: console_script t\\u000ax -> other: " + control_names.ENTRY_REASON in lines
    )


def test_a_string_export_name_with_a_control_character_is_a_record(tmp_path: Path) -> None:
    """Acceptance: the public names do not contain `x\\ny`. One unknown record has the
    cause `name`. The other names stay."""
    write_tree(tmp_path, {"systemap.toml": TS_CONFIG, "tsconfig.json": "{}"})
    write_tree(tmp_path, {"src/a.ts": 'const a = 1;\nexport { a as "x\\ny", a as z };\n'})
    record = _facts(tmp_path)["components"]["web.a"]
    assert [entry["name"] for entry in record["names"]] == ["z"]
    assert [entry["name"] for entry in record["api"]] == ["z"]
    (problem,) = [item for item in record["unknown"] if item["cause"] == unknown_causes.NAME]
    assert problem["reason"] == "the export name 'x\\ny' contains a control character."


def test_each_unresolved_star_reexport_gives_its_own_record(tmp_path: Path) -> None:
    """Acceptance (llm-6): two `export * from` statements with two missing targets give
    two records, one for each line. Before the repair, only the last statement gave a
    record."""
    write_tree(tmp_path, {"systemap.toml": TS_CONFIG, "tsconfig.json": "{}"})
    write_tree(tmp_path, {"src/s.ts": 'export * from "./gone1";\nexport * from "./gone2";\n'})
    record = _facts(tmp_path)["components"]["web.s"]
    found = [(item["line"], item["cause"]) for item in record["unknown"]]
    assert found == [(1, unknown_causes.TARGET), (2, unknown_causes.TARGET)]


def test_one_name_from_two_missing_targets_gives_two_records(tmp_path: Path) -> None:
    """Acceptance: `export { a } from` two missing targets gives two records."""
    write_tree(tmp_path, {"systemap.toml": TS_CONFIG, "tsconfig.json": "{}"})
    text = 'export { a } from "./x";\nexport { a } from "./y";\n'
    write_tree(tmp_path, {"src/s.ts": text})
    record = _facts(tmp_path)["components"]["web.s"]
    reasons = [item["reason"] for item in record["unknown"]]
    assert ["'./x'" in reasons[0], "'./y'" in reasons[1], len(reasons)] == [True, True, 2]


def test_a_removed_entry_point_moves_same_as_to_the_next_entry_point() -> None:
    """Acceptance: no kept entry point refers to a removed entry point."""
    first = {"kind": "console_script", "name": "a\n", "module": "m", "target": "f"}
    ids = source_facts.entry_identity(first)
    second = {"kind": "console_script", "name": "b", "module": "m", "target": "f", "same_as": ids}
    third = {"kind": "main_function", "name": "f", "module": "m", "target": "f", "same_as": ids}
    kept, issues = control_names.refuse_entry_points([{**first, "same_as": ""}, second, third], [])
    assert [point["name"] for point in kept] == ["b", "f"]
    assert [point["same_as"] for point in kept] == ["", source_facts.entry_identity(second)]
    assert [issue["name"] for issue in issues] == ["a\\u000a"]


def test_a_name_without_a_control_character_does_not_change() -> None:
    """Acceptance: the rules do not change a normal name, a normal surface, or an issue."""
    assert file_names.shown("pkg/ok_é.py") == "pkg/ok_é.py"
    assert file_names.valid("ok_é.py")
    record: dict[str, Any] = {"names": [{"name": "run"}], "unknown": []}
    control_names.refuse_surface_names(record)
    assert record == {"names": [{"name": "run"}], "unknown": []}
    issue = {"kind": "package_bin", "name": "t", "target": "b.js", "reason": "r"}
    assert control_names.refuse_entry_points([], [issue]) == ([], [issue])


def test_a_package_root_name_with_a_control_character_is_a_config_error(tmp_path: Path) -> None:
    """Acceptance: `[package_roots]` with a newline in a name stops the load. The package
    name of package.json with a control character does not become the root name."""
    write_tree(tmp_path, {"systemap.toml": '[package_roots]\n"pkg" = "pkg\\nx"\n'})
    write_tree(tmp_path, {"pkg/__init__.py": ""})
    with pytest.raises(ConfigError, match="cannot contain a control character"):
        config.load(tmp_path)
    write_tree(tmp_path, {"package.json": json.dumps({"name": "web" + HOSTILE})})
    assert typescript_config.typescript_name(tmp_path) == tmp_path.name.replace("-", "_")
