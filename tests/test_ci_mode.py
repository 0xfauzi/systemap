"""The workflow that init writes: advisory by default, strict on request.

In advisory mode a map finding (exit code 1) gives a warning annotation and the step
passes. In strict mode it fails the step with an error annotation. When systemap cannot
run (exit code 2 or more), the step fails in both modes. The behaviour test runs each
generated step in bash with a fake uvx.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import scaffold
from systemap.cli import main

STARTER = {"pkg/__init__.py": "", "pkg/a.py": "def run() -> None:\n    pass\n"}


def _init(tmp_path: Path, *options: str) -> str:
    write_tree(tmp_path, STARTER)
    assert main(["--root", str(tmp_path), "init", *options]) == 0
    return (tmp_path / ".github/workflows/systemap.yml").read_text(encoding="utf-8")


def test_init_writes_an_advisory_workflow_by_default(tmp_path: Path) -> None:
    workflow = _init(tmp_path)
    assert "\nenv:\n" in workflow
    assert "  SYSTEMAP_CI: advisory\n" in workflow and "SYSTEMAP_CI: strict" not in workflow


def test_strict_ci_writes_a_strict_workflow(tmp_path: Path) -> None:
    workflow = _init(tmp_path, "--strict-ci")
    assert "  SYSTEMAP_CI: strict\n" in workflow and "SYSTEMAP_CI: advisory" not in workflow


def test_no_ci_and_strict_ci_together_are_an_option_error(tmp_path: Path) -> None:
    write_tree(tmp_path, STARTER)
    with pytest.raises(SystemExit) as stop:
        main(["--root", str(tmp_path), "init", "--no-ci", "--strict-ci"])
    assert stop.value.code == 2
    assert not (tmp_path / ".github").exists()


def _steps(workflow: str) -> dict[str, str]:
    """The run block of each step, by step name."""
    found = re.findall(
        r"      - name: ([^\n]+)\n(?:        [^\n]*\n)*?        run: \|\n((?:          .*\n)+)",
        workflow,
    )
    return {name: re.sub(r"^          ", "", body, flags=re.M) for name, body in found}


def _run(body: str, cwd: Path, fake_code: int, mode: str) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash is not None
    bin_dir = cwd / "bin"
    bin_dir.mkdir(exist_ok=True)
    uvx = bin_dir / "uvx"
    uvx.write_text(f"#!/bin/sh\nexit {fake_code}\n", encoding="utf-8")
    uvx.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "SYSTEMAP_CI": mode,
        "GITHUB_OUTPUT": str(cwd / "github_output"),
        "BASE": "base",
        "HEAD": "head",
        "PR": "1",
    }
    return subprocess.run(
        [bash, "-e", "-c", body], cwd=cwd, env=env, capture_output=True, text=True, timeout=30
    )


CHECK_STEPS = (
    "Source facts match",
    "Map consistency checks",
    "Judgement answers",
    "Rendered page matches",
)


@pytest.mark.skipif(os.name == "nt" or shutil.which("bash") is None, reason="needs a POSIX bash")
@pytest.mark.parametrize(
    ("mode", "code", "passes", "level"),
    [
        ("advisory", 0, True, ""),
        ("advisory", 1, True, "::warning "),
        ("advisory", 2, False, "::error "),
        ("strict", 0, True, ""),
        ("strict", 1, False, "::error "),
        ("strict", 2, False, "::error "),
    ],
)
def test_each_check_step_obeys_the_mode(
    tmp_path: Path, mode: str, code: int, passes: bool, level: str
) -> None:
    steps = _steps(
        scaffold.files("demo", "pkg", [("pkg", "pkg")], language="python")[
            ".github/workflows/systemap.yml"
        ]
    )
    for name in CHECK_STEPS:
        result = _run(steps[name], tmp_path, code, mode)
        assert (result.returncode == 0) is passes, (name, result.stdout, result.stderr)
        if level:
            assert result.stdout.startswith(level), (name, result.stdout)
        else:
            assert "::" not in result.stdout, (name, result.stdout)
    # The delta job: the first step keeps the exit code, the second step decides.
    delta = _run(steps["Map change results"], tmp_path, code, mode)
    assert delta.returncode == 0, delta.stderr
    result = _run(steps["Map is current"], tmp_path, 0, mode)
    assert (result.returncode == 0) is passes, (result.stdout, result.stderr)
    if level:
        assert result.stdout.startswith(level), result.stdout
