"""The agent runner reads the output of the configured command with a limit.

Each test uses a fixture agent: a short Python program that this test starts.
No test starts a coding agent.
"""

from __future__ import annotations

import shlex
import sys
import tracemalloc
from pathlib import Path

import pytest

from systemap import agent


def fixture_agent(code: str) -> str:
    """Give the command that operates the Python program in code."""
    return shlex.join([sys.executable, "-c", code])


def peak_bytes(command: str, cwd: Path) -> tuple[int, str | Exception]:
    """Operate the command and give the peak Python memory and the result."""
    tracemalloc.start()
    try:
        result: str | Exception = agent.shell_run(command, "the question", cwd, 60.0)
    except agent.AgentError as exc:
        result = exc
    finally:
        _now, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return peak, result


FLOOD = (
    "import sys\n"
    "chunk = b'x' * 65536\n"
    "for _ in range({count}):\n"
    "    sys.{stream}.buffer.write(chunk)\n"
    "sys.stdout.write('done')\n"
)


def test_output_above_the_limit_stops_the_agent(tmp_path: Path) -> None:
    """change-15: the fixture agent writes 50 x OUTPUT_CAP bytes to stdout.

    The acceptance value: AgentError, and a peak Python memory of less than
    4 x OUTPUT_CAP during the call."""
    count = 50 * agent.OUTPUT_CAP // 65536 + 1
    peak, result = peak_bytes(fixture_agent(FLOOD.format(count=count, stream="stdout")), tmp_path)
    assert isinstance(result, agent.AgentError), f"{len(result)} characters, peak {peak} bytes"
    assert f"more than {agent.OUTPUT_CAP:,} bytes" in str(result)
    assert peak < 4 * agent.OUTPUT_CAP, peak


def test_a_large_error_output_keeps_only_its_end(tmp_path: Path) -> None:
    """change-15: the fixture agent writes 50 x OUTPUT_CAP bytes to stderr and exits 0.

    The acceptance value: the stdout text, and a peak Python memory of less than
    4 x OUTPUT_CAP during the call."""
    count = 50 * agent.OUTPUT_CAP // 65536 + 1
    peak, result = peak_bytes(fixture_agent(FLOOD.format(count=count, stream="stderr")), tmp_path)
    assert result == "done"
    assert peak < 4 * agent.OUTPUT_CAP, peak


# The fixture agent obeys the protocol: it reads and writes UTF-8 bytes. The Python text
# streams use the locale encoding on Windows, thus the fixture does not use them.
UPPER = (
    "import sys\n"
    "text = sys.stdin.buffer.read().decode('utf-8')\n"
    "sys.stdout.buffer.write(text.upper().encode('utf-8'))\n"
)


def test_output_below_the_limit_is_the_answer(tmp_path: Path) -> None:
    """The fixture agent writes its stdin back. The answer is that text, unchanged."""
    assert agent.shell_run(fixture_agent(UPPER), "réponse", tmp_path, 60.0) == "RÉPONSE"


def test_the_question_and_the_answer_are_utf8_in_a_different_locale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """win-1: the acceptance value is "RÉPONSE" and the UTF-8 bytes of "réponse" on stdin.

    The agent process has the cp1252 encoding for its text streams, as on Windows.
    The runner sends UTF-8 bytes and reads UTF-8 bytes, whatever the locale."""
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    assert agent.shell_run(fixture_agent(UPPER), "réponse", tmp_path, 60.0) == "RÉPONSE"
    echo = "import sys\nsys.stdout.write(sys.stdin.buffer.read().hex())\n"
    assert agent.shell_run(fixture_agent(echo), "réponse", tmp_path, 60.0) == (
        "réponse".encode().hex()
    )


def test_a_failed_agent_gives_the_end_of_its_error_output(tmp_path: Path) -> None:
    code = "import sys\nsys.stderr.write('start ' + 'x' * 5000 + ' the cause')\nsys.exit(3)\n"
    with pytest.raises(agent.AgentError, match="exit code 3: x+ the cause$"):
        agent.shell_run(fixture_agent(code), "", tmp_path, 60.0)


def test_an_agent_that_does_not_stop_gives_a_time_error(tmp_path: Path) -> None:
    code = "import time\ntime.sleep(30)\n"
    with pytest.raises(agent.AgentError, match="did not answer within 1s"):
        agent.shell_run(fixture_agent(code), "", tmp_path, 1.0)
