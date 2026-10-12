"""The Jev requests, the cache keys, and the output of each question kind stay the same.

Acceptance values:

- For each question kind, the Jev request bodies are byte-identical to the bodies in
  `fixtures/decision_golden.json`. The bodies were recorded before the change to
  the provider layer. A body is the text `json.dumps(body)`, which `jev.http_send` sends.
- For each question kind, the cache keys are identical to the recorded keys.
- For each question kind, the output lines are identical to the recorded lines.

The question kinds are the five audit kinds, triage, plan, `suggest --jev`, and
`delta --jev` (move and owner questions). The transport is an injected recording
transport. It gives fixed answers that cause findings. No test opens a socket.

To record the file again, set SYSTEMAP_RECORD_GOLDEN=1. Record only before a change
to the provider layer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import jev
from systemap.cli import main

GOLDEN = Path(__file__).parent / "fixtures" / "decision_golden.json"
RECORD = os.environ.get("SYSTEMAP_RECORD_GOLDEN") == "1"
MODELS = {"models": [{"name": "jev-latest", "release_date": "2026-09-10"}]}
# A fixed probability for each predicate question name. These values cause findings.
NOUL = {"describes": 0.1, "holds": 0.1, "governs": 0.9, "same": 0.5}
STRAY = '"""A module that no component claims."""\n\n\ndef stray() -> None:\n    return None\n'
INTAKE = '"""Takes the input."""\n\n\ndef take(source: str) -> str:\n    return source\n'


def _number(state: Any) -> int:
    blob = json.dumps(state, sort_keys=True).encode()
    return int(hashlib.sha256(blob).hexdigest()[:8], 16)


def _answer(name: str, question: dict[str, Any], state: Any) -> dict[str, Any]:
    if question["type"] == "noul":
        return {"type": "noul", "noul": NOUL[name]}
    options = list(question["criteria"])
    if name == "became":
        # The first new module, at a confidence that prints a `jev move` line.
        return {"type": "choice", "choice": options[0], "confidence": 0.9}
    h = _number(state)
    pick = options[h % len(options)]
    rest = 0.04 / max(1, len(options) - 1)
    probs = {o: (0.96 if o == pick else rest) for o in options}
    confidence = 0.95 if h % 2 else 0.6
    return {"type": "choice", "choice": pick, "confidence": confidence, "probabilities": probs}


class Recorder:
    """Keep the text of each request body and give fixed answers."""

    def __init__(self) -> None:
        self.bodies: list[str] = []

    def __call__(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if path == "/models":
            return MODELS
        assert method == "POST" and path == "/systemone" and body is not None
        self.bodies.append(json.dumps(body))
        answers = {
            name: _answer(name, question, body["state"])
            for name, question in body["questions"].items()
        }
        return {"model": "jev-golden", "answers": answers, "usage": {}}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        check=True,
    )


def _two_cards(root: Path) -> None:
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(root, "--no-ci")
    toml = root / "systemap.toml"
    text = re.sub(r'(?m)^name = ".*"$', 'name = "golden"', toml.read_text(encoding="utf-8"))
    toml.write_text(text, encoding="utf-8")


@pytest.fixture
def roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """One project for audit, triage, plan and suggest. One git project for delta."""
    asked = tmp_path / "asked"
    _two_cards(asked)
    write_tree(asked, {"pkg/stray.py": STRAY})
    assert main(["--root", str(asked), "extract"]) == 0
    changed = tmp_path / "changed"
    _two_cards(changed)
    _git(changed, "init", "-q")
    _git(changed, "add", "-A")
    _git(changed, "commit", "-q", "-m", "base")
    (changed / "pkg/reader.py").unlink()
    writer = STARTER_MODULES["pkg/writer.py"].replace(
        "pkg.reader import read", "pkg.intake import take"
    )
    write_tree(
        changed,
        {
            "pkg/intake.py": INTAKE,
            "pkg/stray.py": STRAY,
            "pkg/writer.py": writer.replace("read(request)", "take(request)"),
        },
    )
    _git(changed, "add", "-A")
    _git(changed, "commit", "-q", "-m", "head")
    monkeypatch.chdir(tmp_path)
    return {"asked": asked, "changed": changed}


COMMANDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "jev mis-fold": ("asked", ("audit", "--kind", "jev mis-fold")),
    "jev owner": ("asked", ("audit", "--kind", "jev owner")),
    "jev sentence": ("asked", ("audit", "--kind", "jev sentence")),
    "jev flow": ("asked", ("audit", "--kind", "jev flow")),
    "jev governs": ("asked", ("audit", "--kind", "jev governs")),
    "triage": ("asked", ("triage", "Reading a file with a BOM leaves the BOM in the request")),
    "plan": ("asked", ("plan", "read the input in parts")),
    "suggest": ("asked", ("suggest", "--jev")),
    "delta": ("changed", ("delta", "--base", "HEAD~1", "--jev")),
}


def _run(
    kind: str,
    roots: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> dict[str, Any]:
    which, argv = COMMANDS[kind]
    root = roots[which]
    cache = root / ".systemap/jev-cache.json"
    cache.unlink(missing_ok=True)
    recorder = Recorder()
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    monkeypatch.setattr(jev, "http_send", lambda key, base=jev.API: recorder)
    code = main(["--root", str(root), *argv])
    out = capsys.readouterr().out
    out = out.replace(str(root), "<root>").replace(time.strftime("%Y%m%d"), "<day>")
    # The commit hashes change with the commit time.
    out = re.sub(r"\(([0-9a-f]{7,40})\)", "(<commit>)", out)
    held = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    return {
        "code": code,
        "bodies": sorted(recorder.bodies),
        "keys": sorted(held.get("entries", {})),
        "out": out.splitlines(),
    }


@pytest.mark.parametrize("kind", list(COMMANDS))
def test_requests_cache_keys_and_lines_are_identical(
    kind: str,
    roots: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    got = _run(kind, roots, monkeypatch, capsys)
    assert got["bodies"], f"{kind} sent no request"
    golden = json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.exists() else {}
    if RECORD:
        golden[kind] = got
        GOLDEN.write_text(json.dumps(golden, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return
    assert kind in golden, "no recorded value: record with SYSTEMAP_RECORD_GOLDEN=1"
    want = golden[kind]
    assert got["bodies"] == want["bodies"]
    assert got["keys"] == want["keys"]
    assert got["out"] == want["out"]
    assert got["code"] == want["code"]


def test_the_dry_run_count_of_characters_is_identical(
    roots: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """The dry run gives the same question count and character count without a key."""
    kinds = [x for kind in COMMANDS if kind.startswith("jev ") for x in ("--kind", kind)]
    code = main(["--root", str(roots["asked"]), "audit", "--dry-run", *kinds])
    got = {"code": code, "out": capsys.readouterr().out.splitlines()}
    golden = json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.exists() else {}
    if RECORD:
        golden["dry run"] = got
        GOLDEN.write_text(json.dumps(golden, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return
    assert golden["dry run"] == got
