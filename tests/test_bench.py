"""The benchmark harness: the summary line parser, the table, the script's usage.

`bench/` is not part of the package (standard library scripts, loaded here
by path), so these tests are what keeps it honest: the parser reads a
captured stream-json shape, the table renders the committed results, and
the committed table is what the script renders.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bench-session.jsonl"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"bench_{name}", ROOT / "bench" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


summary = load("summary")
table = load("table")


def test_summary_reads_model_turns_minutes_dollars_and_the_first_tool() -> None:
    got = summary.summarize(FIXTURE.read_text().splitlines())
    assert got == {
        "model": "claude-opus-5[1m]",
        "turns": 42,
        "minutes": 32.8,
        "dollars": 3.14,
        "run": "finished",
        "tool_calls": 6,
        "check_calls": 2,
        "refresh_calls": 1,
        "first_tool": 'Skill {"skill": "systemap"}',
        "first_tool_ok": True,
    }


def test_summary_records_a_session_that_was_cut_off_or_never_ended() -> None:
    lines = FIXTURE.read_text().splitlines()
    without_result = [line for line in lines if '"type":"result"' not in line]
    got = summary.summarize(without_result)
    assert got["run"] == "cut off (no result event)"
    assert got["turns"] == 8 and got["minutes"] is None and got["dollars"] is None
    assert got["first_tool_ok"] is True
    cut = [
        line.replace(
            '"subtype":"success","is_error":false', '"subtype":"error_max_turns","is_error":true'
        )
        for line in lines
    ]
    assert summary.summarize(cut)["run"] == "cut off (error_max_turns)"
    # A session whose first call was not the skill is recorded as such.
    swapped = [line for line in lines if '"toolu_1"' not in line]
    got = summary.summarize(swapped)
    assert got["first_tool_ok"] is False
    assert got["first_tool"].startswith("Bash ")
    assert summary.summarize([])["model"] == "" and summary.summarize([])["turns"] is None


def test_summary_script_writes_one_line_and_appends_it(tmp_path: Path) -> None:
    out = tmp_path / "results.jsonl"
    proc = subprocess.run(
        [
            "python3",
            str(ROOT / "bench" / "summary.py"),
            str(FIXTURE),
            "--repository",
            "https://github.com/acme/demo",
            "--mode",
            "first-map",
            "--systemap",
            "0.9.0",
            "--ref",
            "abc1234",
            "--modules",
            "144",
            "--check",
            "clean",
            "--judgement",
            "clean",
            "--wall-seconds",
            "2000",
            "--append",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    line = json.loads(proc.stdout)
    assert out.read_text() == proc.stdout
    assert line["repository"] == "https://github.com/acme/demo"
    assert line["mode"] == "first-map" and line["modules"] == 144
    assert line["dollars"] == 3.14 and line["turns"] == 42 and line["minutes"] == 32.8
    assert line["model"] == "claude-opus-5[1m]" and line["systemap"] == "0.9.0"
    assert line["check"] == "clean" and line["judgement"] == "clean" and line["run"] == "finished"
    assert line["first_tool_ok"] is True and line["wall_seconds"] == 2000
    assert line["date"].endswith("+00:00")


def test_table_renders_one_row_per_repository_per_mode_with_the_latest_run() -> None:
    lines = [
        json.dumps(
            {
                "date": "2026-08-26T10:00:00+00:00",
                "repository": "https://github.com/acme/demo",
                "mode": "first-map",
                "systemap": "0.9.0",
                "model": "claude-opus-5[1m]",
                "modules": 144,
                "turns": 42,
                "minutes": 32.8,
                "dollars": 3.14,
                "check": "clean",
                "judgement": "clean",
                "run": "finished",
                "first_tool_ok": True,
            }
        ),
        json.dumps(
            {
                "date": "2026-08-25T10:00:00+00:00",
                "repository": "https://github.com/acme/demo",
                "mode": "first-map",
                "systemap": "0.8.0",
                "modules": 140,
                "dollars": 9.0,
                "turns": 90,
                "minutes": 60.0,
                "model": "claude-opus-5[1m]",
                "check": "failed",
                "judgement": "open",
                "run": "cut off (error_max_turns)",
                "first_tool_ok": False,
            }
        ),
        json.dumps(
            {
                "date": "2026-08-26T11:00:00+00:00",
                "repository": "https://github.com/acme/demo",
                "mode": "maintenance",
                "systemap": "0.9.0",
                "modules": 144,
                "turns": 9,
                "minutes": 4.5,
                "dollars": 0.8,
                "model": "claude-opus-5[1m]",
                "check": "clean",
                "judgement": "clean",
                "run": "finished",
                "first_tool_ok": True,
                "base": "main",
            }
        ),
        json.dumps(
            {"date": "2026-08-26T12:00:00+00:00", "repository": "systemap", "mode": "first-map"}
        ),
    ]
    rows = table.rows(lines)
    assert [(r["repository"], r["mode"], r.get("systemap")) for r in rows] == [
        ("https://github.com/acme/demo", "first-map", "0.9.0"),
        ("https://github.com/acme/demo", "maintenance", "0.9.0"),
        ("systemap", "first-map", None),
    ]
    text = table.render(rows)
    assert text.startswith("# Benchmarks\n")
    assert "| repository | mode | modules | systemap | model | turns | minutes | dollars |" in text
    assert (
        "| https://github.com/acme/demo | first-map | 144 | 0.9.0 | claude-opus-5[1m] | 42 | 32.8 "
        "| 3.14 | 0.022 | clean | clean | finished | yes | 2026-08-26 |"
    ) in text
    assert (
        "| https://github.com/acme/demo | maintenance | 144 | 0.9.0 | claude-opus-5[1m] | 9 | 4.5 "
        "| 0.8 | - | clean | clean | finished | yes | 2026-08-26 |"
    ) in text
    assert (
        "| systemap | first-map | - | - | - | - | - | - | - | - | - | - | - | 2026-08-26 |" in text
    )
    assert "0.8.0" not in text, "the older run of the same repository and mode is not a row"
    assert table.render([]).endswith(table.EMPTY + "\n")


def test_the_committed_table_is_what_the_script_renders() -> None:
    results = ROOT / "bench" / "results.jsonl"
    lines = results.read_text().splitlines() if results.is_file() else []
    expected = table.render(table.rows(lines))
    assert (ROOT / "docs" / "benchmarks.md").read_text() == expected, (
        "docs/benchmarks.md is stale; run: python3 bench/table.py"
    )
    proc = subprocess.run(
        ["python3", str(ROOT / "bench" / "table.py"), "--check"], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not on PATH")
def test_run_script_parses_and_prints_its_usage() -> None:
    script = ROOT / "bench" / "run.sh"
    assert subprocess.run(["bash", "-n", str(script)], capture_output=True).returncode == 0
    proc = subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout.startswith("Usage: bench/run.sh <repo-url-or-path> <first-map|maintenance>")
    for flag in ("--ref REF", "--base REF", "--from SPEC", "--model NAME", "--max-turns N"):
        assert flag in proc.stdout, flag
    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert proc.returncode == 2 and "Usage:" in proc.stderr
    proc = subprocess.run(
        ["bash", str(script), "https://example.invalid/x.git", "maintenance"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2 and "maintenance needs --base REF" in proc.stderr
    text = script.read_text()
    # The recipe as documented: the sentence, the permission mode, the tool list.
    assert "Map this repository with systemap. Follow the systemap skill." in text
    assert "--permission-mode acceptEdits" in text
    assert "--output-format stream-json --verbose" in text
    assert 'allowed="Skill,Read,Edit,Write,Glob,Grep,TodoWrite"' in text
    for cmd in (
        "systemap",
        "uv",
        "uvx",
        "python3",
        "git",
        "ls",
        "cat",
        "grep",
        "rg",
        "find",
        "head",
        "tail",
        "sed",
        "wc",
        "mkdir",
    ):
        listed = " " + text.split("for cmd in ", 1)[1].split(";", 1)[0] + " "
        assert f" {cmd} " in listed, cmd
    assert "first_tool_ok" in text
