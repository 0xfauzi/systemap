"""How the system got here: the tree sampled back through time.

`systemap history` reads the facts at each sampled commit against today's
map, and prints what moved between them: cards that grew, crossing imports
that appeared, ways in added or removed, and the commits that wrote the
modules which appeared.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import config, history, nest, trend
from systemap.cli import main

GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]


def commit(root: Path, message: str) -> str:
    subprocess.run([*GIT, "-C", str(root), "add", "-A"], check=True)
    subprocess.run([*GIT, "-C", str(root), "commit", "-qm", message], check=True)
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Two commits: a two-card map, then a module added to the writer's card."""
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    commit(tmp_path, "the first map")
    write_tree(
        tmp_path,
        {
            "pkg/shipping.py": "from pkg.reader import read\n\n\ndef ship(s: str) -> str:\n    return read(s)\n",
            "map/model.py": (tmp_path / "map/model.py")
            .read_text()
            .replace(
                'implemented_by=("pkg.writer",)', 'implemented_by=("pkg.writer", "pkg.shipping")'
            ),
        },
    )
    commit(tmp_path, "shipping, written into the writer")
    return tmp_path


def windows_of(root: Path) -> list[trend.Window]:
    cfg = config.load(root)
    shas = history.sample(root, "30 years ago", 1)
    return trend.walk(cfg, nest.load(cfg).top.model, shas)


def test_a_card_that_grew_is_counted_in_todays_cards(repo: Path) -> None:
    found = windows_of(repo)
    assert len(found) == 1
    window = found[0]
    assert window.modules == 1 and window.grew == {"Writer": 1}
    assert "pkg/shipping.py" in window.new_files
    assert window.size == 2, "one module, one card, one step each"


def test_the_window_names_the_commit_that_wrote_the_new_modules(repo: Path) -> None:
    window = trend.with_causes(repo, windows_of(repo)[0])
    assert window.caused_by == ("shipping, written into the writer",)


def test_a_crossing_is_a_pair_the_map_draws_no_flow_between(sample: object) -> None:
    """An import between two cards counts only where the map draws nothing."""
    from conftest import sample_model

    model, _meaning = sample_model()
    facts = {
        "components": {
            "pkg.reader": {"uses": {"pkg.parser": 1}},  # Reader -> Parser is drawn
            "pkg.ledger": {"uses": {"pkg.reader": 1}},  # Ledger -> Reader is not
        }
    }
    owner = {"pkg.reader": "Reader", "pkg.parser": "Parser", "pkg.ledger": "Ledger"}
    assert trend._crossings(facts["components"], owner, model) == {("Ledger", "Reader")}


def test_a_quiet_stretch_says_so_rather_than_printing_a_chart(repo: Path) -> None:
    commit_free = trend.report([], repo, "1 year ago", 14, 5)
    assert "nothing the map can see changed in that time" in commit_free[1]


def test_the_command_prints_the_largest_windows_and_what_wrote_them(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--root", str(repo), "history", "--since", "30 years ago", "--every", "1"]) == 0
    out = capsys.readouterr().out
    assert "windows moved the map" in out
    assert "cards: Writer +1" in out
    assert "written by: shipping, written into the writer" in out
    assert "read in today's cards" in out


def test_one_commit_is_not_a_trend(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    first = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    argv = ["--root", str(repo), "history", "--since", "30 years ago", "--ref", first]
    assert main(argv) == 0
    assert "ask for a longer time" in capsys.readouterr().out


def test_the_facts_at_a_commit_are_read_once(repo: Path) -> None:
    cfg = config.load(repo)
    sha = history.sample(repo, "30 years ago", 1)[0]
    cached = history.cache_dir(cfg) / f"{sha}.json"
    assert not cached.exists()
    history.facts_at(cfg, sha)
    assert cached.exists(), "a commit never changes, so its facts are kept"
    written = cached.stat().st_mtime_ns
    history.facts_at(cfg, sha)
    assert cached.stat().st_mtime_ns == written, "the second read does not extract again"
