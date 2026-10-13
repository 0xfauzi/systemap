"""Git and agent output is UTF-8, whatever the locale of the process.

Each test runs a child Python process with the C locale and UTF-8 mode off, as on a
server without a UTF-8 locale. On Windows the locale is often cp1252, with the same
effect. Every subprocess text call here gives its encoding.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE = 'NAME = "Café"\n'
SUBJECT = "Add the café reader"
QUOTE = "the user’s file А Ł"


def run(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/reader.py").write_text(SOURCE, encoding="utf-8")
    run(tmp_path, "init", "-q")
    run(tmp_path, "add", "-A")
    run(tmp_path, "commit", "-q", "-m", SUBJECT)
    return tmp_path


def in_c_locale(code: str) -> object:
    """Run code in a child process without a UTF-8 locale. It prints JSON with ASCII only."""
    env = {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONUTF8": "0",
        "PYTHONCOERCECLOCALE": "0",
        "PYTHONIOENCODING": "ascii:backslashreplace",
    }
    done = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_a_file_at_a_revision_is_read_as_utf8(repo: Path) -> None:
    code = (
        "import json, pathlib; from systemap import change_text; "
        f"print(json.dumps(change_text.at(pathlib.Path({str(repo)!r}), 'HEAD', ['pkg/reader.py'])['pkg/reader.py'].raw))"
    )
    assert in_c_locale(code) == SOURCE


def test_git_log_subjects_are_read_as_utf8(repo: Path) -> None:
    code = (
        "import json, pathlib; from systemap import history; "
        f"print(json.dumps(history.git(pathlib.Path({str(repo)!r}), 'log', '--format=%s')))"
    )
    assert in_c_locale(code) == SUBJECT + "\n"


def test_agent_output_is_read_as_utf8(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    script.write_text(
        "import sys\n"
        "sys.stdin.buffer.read()\n"
        f"sys.stdout.buffer.write({QUOTE!r}.encode('utf-8'))\n",
        encoding="utf-8",
    )
    command = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
    code = (
        "import json, pathlib; from systemap import agent; "
        f"print(json.dumps(agent.shell_run({command!r}, 'a question \\u2019', "
        f"pathlib.Path({str(tmp_path)!r}), 30)))"
    )
    assert in_c_locale(code) == QUOTE
