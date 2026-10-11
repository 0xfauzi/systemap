"""`systemap delta` with and without Jev.

Jev answers are suggestions. The delta lines and the exit code come only from the
source facts, the model, and the configured answers, so a run with Jev, a run without
a key, and a run where Jev fails give the same decisions. A move candidate closes when
the model no longer specifies the removed module and claims the added module.

Every transport is an injected fake. No test opens a socket.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import card_review, config, delta, delta_jev, jev, nest
from systemap.cli import main

CONFIG = """
[package_roots]
"pkg" = "pkg"
"""

MODEL = """
from systemap import Component, Container, Flow, Meaning, Model, Region

CONTAINERS = (Container(id="system", label="SYSTEM", box=(16, 16, 700, 400)),)
REGIONS = (Region(id="core", label="CORE", box=(40, 60, 640, 320), container="system"),)
COMPONENTS = (
    Component(id="Reader", does="Reads.", implemented_by=("pkg.reader",), region="core",
              x=60, y=90),
    Component(id="Ledger", does="Keeps the payments.", implemented_by=(LEDGER,),
              region="core", x=250, y=90),
)
FLOWS = (Flow("Reader", "Ledger", "payment", "data"),)
MODEL = Model(canvas=(740, 440), containers=CONTAINERS, regions=REGIONS,
              components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={c.id: c.id.lower() for c in COMPONENTS},
    relations={("Reader", "Ledger"): "The reader gives each payment to the ledger."},
)
"""

READER = "from pkg.ledger import record_payment\n\n\ndef read() -> None:\n    record_payment(1)\n"
LEDGER = '''"""The ledger keeps payments."""


def record_payment(amount: int) -> int:
    return amount


def balance() -> int:
    return 0
'''
# The same public names with other bodies, in a file with a different name.
STORE = '''"""The store keeps payments."""


def record_payment(amount: int) -> int:
    return amount * 2


def balance() -> int:
    return 1
'''


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return proc.stdout.strip()


def model_source(ledger: str, reviews: dict[str, str] | None = None) -> str:
    text = MODEL.replace("(LEDGER,)", f'("{ledger}",)')
    for cid, digest in (reviews or {}).items():
        text = text.replace(f'id="{cid}", ', f'id="{cid}", source_review="{digest}", ', 1)
    return text


@pytest.fixture
def renamed(tmp_path: Path) -> Path:
    """pkg/ledger.py becomes pkg/records_store.py with the same names and other bodies.
    Delta cannot pair the two modules, so it gives a move candidate."""
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": READER,
            "pkg/ledger.py": LEDGER,
            "systemap.toml": CONFIG,
            "map/model.py": model_source("pkg.ledger"),
        },
    )
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    (tmp_path / "pkg/ledger.py").unlink()
    write_tree(
        tmp_path,
        {"pkg/records_store.py": STORE, "pkg/reader.py": READER.replace("ledger", "records_store")},
    )
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "head")
    return tmp_path


class Fake:
    """Answer each move question with `pick`, and each owner question with Reader."""

    def __init__(self, pick: str = "pkg.records_store", broken: bool = False) -> None:
        self.pick = pick
        self.broken = broken
        self.posts: list[dict[str, Any]] = []

    def __call__(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if path == "/models":
            return {"models": [{"name": "jev-latest", "release_date": "2026-09-10"}]}
        assert body is not None
        self.posts.append(body)
        if self.broken:
            return {"model": "jev-fake", "answers": {"other": {}}}
        answers = {}
        for name, question in body["questions"].items():
            choice = self.pick if name == "became" else "Reader"
            probs = {option: 0.0 for option in question["criteria"]}
            probs[choice] = 0.95
            answers[name] = {
                "type": "choice",
                "choice": choice,
                "confidence": 0.9 if name == "became" else 0.95,
                "probabilities": probs,
            }
        return {"model": "jev-fake", "answers": answers, "usage": {}}


def use(monkeypatch: pytest.MonkeyPatch, fake: Fake) -> None:
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    monkeypatch.setattr(jev, "http_send", lambda key, base=jev.API: fake)


def run(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(["--root", str(root), "delta", "--base", "HEAD~1", "--brief", *argv])
    out, err = capsys.readouterr()
    return code, out, err


def decisions(out: str) -> list[str]:
    lines = out.splitlines()
    if not any(line.startswith("A decision is necessary") for line in lines):
        return []
    start = next(i for i, line in enumerate(lines) if line.startswith("A decision is necessary"))
    return [line for line in lines[start + 1 :] if line.startswith("  ")][
        : int(lines[start].split("(")[1].split(")")[0])
    ]


# ---- finding 2 and python F4: the same decisions with and without Jev ------------


def test_jev_does_not_change_the_decisions_or_the_exit_code(
    renamed: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    without = run(renamed, capsys)
    assert without[0] == 1
    assert any(
        line.startswith("  move candidate: pkg.ledger and pkg.records_store")
        for line in decisions(without[1])
    )
    fake = Fake()
    use(monkeypatch, fake)
    with_jev = run(renamed, capsys)
    assert fake.posts, "Jev was asked"
    assert with_jev[0] == without[0]
    assert decisions(with_jev[1]) == decisions(without[1])
    assert (
        "  jev move: pkg.ledger -> pkg.records_store (read as the same module by Jev, "
        "confidence 0.90)" in with_jev[1].splitlines()
    )
    assert "Jev suggestions. They do not change the decisions or the exit code (2):" in with_jev[1]
    # A Jev answer that does not fit the question gives a reason, and the same result.
    (renamed / ".systemap/jev-cache.json").unlink()
    use(monkeypatch, Fake(broken=True))
    broken = run(renamed, capsys)
    assert broken[0] == without[0]
    assert decisions(broken[1]) == decisions(without[1])
    assert "delta --jev: Jev gave an incorrect answer to became" in broken[1]


def test_a_model_change_closes_a_move_candidate(
    renamed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The maintainer reads both files, moves the claim, and records the source reviews.
    (renamed / "map/model.py").write_text(model_source("pkg.records_store"), encoding="utf-8")
    cfg = config.load(renamed)
    head = delta.facts_at(cfg, delta.resolve(renamed, "HEAD"))
    top = nest.load(cfg).top
    reviews = {
        c.id: card_review.digest(c, top.model, top.meaning, head) or ""
        for c in top.model.components
    }
    (renamed / "map/model.py").write_text(
        model_source("pkg.records_store", reviews), encoding="utf-8"
    )
    code, out, _err = run(renamed, capsys)
    assert code == 0, out
    assert (
        "  move candidate: pkg.ledger and pkg.records_store have some of the same public names. "
        "No component specifies pkg.ledger in implemented_by. pkg.records_store has a claim in Ledger"
    ) in out.splitlines()
    assert "No decision is necessary." in out


def test_a_move_candidate_stays_open_while_the_model_specifies_the_removed_module(
    renamed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _err = run(renamed, capsys)
    assert code == 1
    assert "Examine the source before you accept a pair as a move." in out


# ---- finding 1: owners for the modules that no component claims -------------------


def test_delta_jev_asks_for_an_owner_of_each_unclaimed_module(
    renamed: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(
        renamed, {"pkg/stray.py": '"""A stray."""\n\n\ndef stray() -> None:\n    return None\n'}
    )
    git(renamed, "add", "-A")
    git(renamed, "commit", "-q", "-m", "stray")
    fake = Fake()
    use(monkeypatch, fake)
    code, out, _err = run(renamed, capsys, "--jev")
    assert code == 1
    owners = [p["state"]["module"]["module"] for p in fake.posts if "owner" in p["questions"]]
    assert owners == ["pkg.stray"]
    assert (
        "  jev owner: pkg.stray is claimed by no card (reads like Reader; confidence 0.95)"
        in out.splitlines()
    )


def test_unclaimed_modules_come_from_the_delta_lines_not_their_text(renamed: Path) -> None:
    cfg = config.load(renamed)
    tree = nest.load(cfg)
    base = delta.facts_at(cfg, delta.resolve(renamed, "HEAD~1"))
    head = delta.facts_at(cfg, delta.resolve(renamed, "HEAD"))
    d = delta.compute_tree(cfg, tree, base, head)
    assert delta_jev.unclaimed(d) == {"": ["pkg.records_store"]}


# ---- finding 11 and 17: the reasons for no answer, and no message without a question --


def test_the_comment_puts_the_reason_for_no_answer_under_its_own_heading(
    renamed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["--root", str(renamed), "delta", "--base", "HEAD~1", "--jev", "--format", "markdown"]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "**Jev on the unclaimed modules**" not in out
    assert (
        "**Jev did not answer**\n\n- delta --jev: set TYPESAFE_API_KEY to call Jev. No data was sent"
        in out
    )


def test_delta_jev_with_nothing_to_ask_sends_nothing_and_says_nothing(
    renamed: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--root", str(renamed), "delta", "--base", "HEAD", "--jev"])
    out = capsys.readouterr().out
    assert code == 0
    assert "delta --jev" not in out
