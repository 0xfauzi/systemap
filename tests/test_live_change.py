"""The comparison of the working tree with the merge base of a base ref and HEAD.

Acceptance: an edit that is not in a commit, an untracked new module, and a commit
since the merge base each mark their component as changed. When the same change is
in a commit, the comparison of that commit gives the same changed components.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import change, config, extract, nest

CONFIG = """
[package_roots]
"pkg" = "pkg"
"""

SOURCE = {
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read() -> str:\n    return 'text'\n",
    "pkg/writer.py": """
        from pkg.reader import read


        def write() -> str:
            return read()
    """,
    "pkg/store.py": "def keep(text: str) -> None:\n    return None\n",
}

MODEL = """
from systemap import Component, Container, Flow, Journey, Meaning, Model, Region, Step

CONTAINERS = (Container(id="system", label="SYSTEM", box=(16, 16, 700, 400)),)
REGIONS = (Region(id="core", label="CORE", box=(40, 60, 640, 320), container="system"),)
COMPONENTS = (
    Component(id="Reader", does="Reads the text.", implemented_by=("pkg.reader",),
              entry="read", region="core", x=60, y=90),
    Component(id="Writer", does="Writes the text.", implemented_by=("pkg.writer",),
              entry="write", region="core", x=250, y=90),
    Component(id="Store", does="Keeps the text.", implemented_by=("pkg.store",), kind="store",
              region="core", x=440, y=90),
    Component(id="Audit", does="Examines the text.", implemented_by=("pkg.audit",),
              entry="check", region="core", x=60, y=200),
)
FLOWS = (
    Flow("Reader", "Writer", "text", "data"),
    Flow("Writer", "Store", "records", "data"),
    Flow("Writer", "Audit", "text", "control"),
)
MODEL = Model(canvas=(740, 440), containers=CONTAINERS, regions=REGIONS,
              components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"Reader": "reader", "Writer": "writer", "Store": "store", "Audit": "audit"},
    relations={("Reader", "Writer"): "The reader gives the text.",
               ("Writer", "Store"): "The writer keeps the records.",
               ("Writer", "Audit"): "The writer asks the audit."},
    journeys=(
        Journey(id="write-text", label="Write the text", starts="Reader", steps=(
            Step(("Reader",), (), ("Reader", "Writer"), "The reader gives the text."),
            Step(("Writer",), (), ("Writer", "Store"), "The writer keeps the text."),
        )),
    ),
)
"""


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


def commit(root: Path, files: dict[str, str], message: str) -> None:
    write_tree(root, files)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


def make_repo(root: Path) -> Path:
    """A repository with one commit on `main` and a `work` branch at the same commit."""
    git(root, "init", "-q", "-b", "main")
    commit(root, {**SOURCE, "systemap.toml": CONFIG, "map/model.py": MODEL}, "base")
    git(root, "checkout", "-q", "-b", "work")
    return root


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


def direct(root: Path, head: str = change.WORKING_TREE) -> set[str]:
    cfg = config.load(root)
    tree = nest.load(cfg)
    found = change.compute(cfg, tree.top.model, "main", extract.build(cfg), head)
    assert found["comparison_base"] == git(root, "merge-base", "main", "HEAD")
    return set(found["direct"])


def test_a_clean_working_tree_has_no_change(repo: Path) -> None:
    cfg = config.load(repo)
    found = change.compute(
        cfg, nest.load(cfg).top.model, "main", extract.build(cfg), change.WORKING_TREE
    )
    assert found["has_change"] is False
    assert found["head"] == change.WORKING_TREE
    assert found["head_revision"] == git(repo, "rev-parse", "HEAD")


def test_an_edit_that_is_not_in_a_commit_marks_its_component(repo: Path) -> None:
    # A new public name: the surface of the module changes.
    write_tree(
        repo,
        {"pkg/reader.py": SOURCE["pkg/reader.py"] + "\n\ndef peek() -> str:\n    return 'text'\n"},
    )
    assert direct(repo) == {"Reader"}
    cfg = config.load(repo)
    found = change.compute(
        cfg, nest.load(cfg).top.model, "main", extract.build(cfg), change.WORKING_TREE
    )
    assert found["per_component"]["Reader"]["surface"]["added"]["operations"] == ["peek"]
    # A staged edit is also an edit that is not in a commit.
    git(repo, "add", "pkg/reader.py")
    assert direct(repo) == {"Reader"}


def test_an_untracked_new_module_marks_its_component(repo: Path) -> None:
    write_tree(repo, {"pkg/audit.py": "def check(text: str) -> bool:\n    return bool(text)\n"})
    assert git(repo, "status", "--porcelain") == "?? pkg/audit.py"
    assert direct(repo) == {"Audit"}


def test_a_commit_since_the_merge_base_marks_its_component(repo: Path) -> None:
    commit(repo, {"pkg/store.py": "def keep(text: str) -> int:\n    return 0\n"}, "store")
    assert direct(repo) == {"Store"}
    # A commit on the base branch after the merge base is not part of the change.
    git(repo, "checkout", "-q", "main")
    commit(repo, {"pkg/writer.py": "def write() -> str:\n    return ''\n"}, "on main")
    git(repo, "checkout", "-q", "work")
    assert direct(repo) == {"Store"}


def test_a_file_with_a_new_time_and_the_same_text_is_not_a_change(repo: Path) -> None:
    path = repo / "pkg/reader.py"
    path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    assert direct(repo) == set()


def test_the_systemap_cache_is_not_a_changed_file(repo: Path) -> None:
    write_tree(repo, {".systemap/facts/abc.json": "{}", "notes.txt": "a note"})
    cfg = config.load(repo)
    found = change.compute(
        cfg, nest.load(cfg).top.model, "main", extract.build(cfg), change.WORKING_TREE
    )
    assert found["files"] == 1, "notes.txt is a changed file, the cache is not"
    assert found["direct"] == set()


def test_the_working_tree_and_the_commit_of_the_same_change_agree(repo: Path) -> None:
    commit(repo, {"pkg/store.py": "def keep(text: str) -> int:\n    return 0\n"}, "store")
    write_tree(repo, {"pkg/reader.py": "def read() -> bytes:\n    return b'text'\n"})
    write_tree(repo, {"pkg/audit.py": "def check(text: str) -> bool:\n    return bool(text)\n"})
    working = direct(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "all")
    assert working == direct(repo, "HEAD") == {"Reader", "Store", "Audit"}
    assert direct(repo) == working
