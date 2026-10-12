"""`systemap delta` reads committed blobs, and accepts the same answers as judgement.

- Git attributes such as `export-subst` and `export-ignore` do not change the facts
  at a commit.
- A family answer for a new crossing import must have `policy = true`, and an exact
  answer must have the current evidence digest, as in `systemap judgement`.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import config, delta, extract, judgement, nest
from systemap.cli import main


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


CONFIG = """
[package_roots]
"pkg" = "pkg"
"""

MODEL = """
from systemap import Component, Container, Meaning, Model, Region

CONTAINERS = (Container(id="system", label="SYSTEM", box=(16, 16, 700, 400)),)
REGIONS = (Region(id="core", label="CORE", box=(40, 60, 640, 320), container="system"),)
COMPONENTS = (
    Component(id="Reader", does="Reads.", implemented_by=("pkg.reader", "pkg._version"),
              region="core", x=60, y=90),
    Component(id="Writer", does="Writes.", implemented_by=("pkg.writer", "pkg.ledger"),
              region="core", x=250, y=90),
)
MODEL = Model(canvas=(740, 440), containers=CONTAINERS, regions=REGIONS,
              components=COMPONENTS, flows=(), flow_kinds=())
MEANING = Meaning(plain={"Reader": "reader", "Writer": "writer"})
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "def read() -> str:\n    return 'x'\n",
            "pkg/writer.py": "def write() -> None:\n    return None\n",
            "pkg/ledger.py": "def record() -> None:\n    return None\n",
            "pkg/_version.py": 'GIT_FULL = "$Format:%H$"\n\n\ndef version() -> str:\n    return GIT_FULL\n',
            ".gitattributes": "pkg/_version.py export-subst\npkg/ledger.py export-ignore\n",
            "systemap.toml": CONFIG,
            "map/model.py": MODEL,
        },
    )
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


# ---- python F7: the committed blobs, as they are ---------------------------------


def test_the_facts_at_a_commit_ignore_export_attributes(repo: Path) -> None:
    cfg = config.load(repo)
    at_commit = delta.facts_at(cfg, delta.resolve(repo, "HEAD"))["components"]
    in_tree = extract.build(cfg)["components"]
    assert "pkg.ledger" in at_commit, "export-ignore does not remove a module"
    assert at_commit["pkg._version"]["sha"] == in_tree["pkg._version"]["sha"]


def test_a_change_to_one_module_does_not_change_a_substituted_one(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "pkg/reader.py").write_text("def read() -> str:\n    return 'y'\n", encoding="utf-8")
    (repo / "pkg/ledger.py").write_text(
        "def record_all() -> None:\n    return None\n", encoding="utf-8"
    )
    git(repo, "commit", "-q", "-am", "edit")
    assert main(["--root", str(repo), "delta", "--base", "HEAD~1", "--brief"]) == 1
    out = capsys.readouterr().out
    assert "pkg._version" not in out
    assert "source review: Writer has changed code in pkg.ledger." in out


# ---- python F11: the answer rule of judgement ------------------------------------


def crossing_commit(repo: Path) -> None:
    (repo / "pkg/writer.py").write_text(
        "from pkg.reader import read\n\n\ndef write() -> str:\n    return read()\n",
        encoding="utf-8",
    )
    git(repo, "commit", "-q", "-am", "writer reads")


def answer(repo: Path, entry: str) -> None:
    (repo / "systemap.toml").write_text(
        CONFIG + f"\n[judgement]\nanswered = [{entry}]\n", encoding="utf-8"
    )


def crossing_in_delta(repo: Path, capsys: pytest.CaptureFixture[str]) -> bool:
    main(["--root", str(repo), "delta", "--base", "HEAD~1", "--brief"])
    return "new crossing import: pkg.writer" in capsys.readouterr().out


def test_a_family_answer_needs_policy_in_delta_as_in_judgement(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    crossing_commit(repo)
    answer(repo, '{ crossing_from = "Writer", reason = "a test" }')
    assert crossing_in_delta(repo, capsys)
    answer(repo, '{ crossing_from = "Writer", policy = true, reason = "a test" }')
    assert not crossing_in_delta(repo, capsys)


def test_an_exact_answer_needs_the_judgement_evidence_digest_in_delta(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    crossing_commit(repo)
    assert main(["--root", str(repo), "extract"]) == 0
    capsys.readouterr()
    cfg = config.load(repo)
    facts = extract.read_facts(cfg.facts_path)
    assert facts is not None
    tree = nest.load(cfg)
    line = next(
        x for x in judgement.run_tree(tree, facts, (), cfg.observed_by) if "crossing import" in x
    )
    digest = judgement.evidence_for_tree(tree, facts, repo, [line])[line]
    answer(repo, f'{{ item = "{line}", evidence = "{"0" * 64}", reason = "a test" }}')
    assert crossing_in_delta(repo, capsys)
    answer(repo, f'{{ item = "{line}", evidence = "{digest}", reason = "a test" }}')
    assert not crossing_in_delta(repo, capsys)
    assert main(["--root", str(repo), "judgement", "--strict", "--brief"]) == 1
    out = capsys.readouterr().out
    assert not re.search(r"pending answer: .*crossing import", out)
