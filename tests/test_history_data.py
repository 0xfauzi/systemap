"""The history data of the atlas page (`history_data`, docs/design/atlas.md, stage 6).

The tests make small Git repositories in a temporary folder, with fixed commit times. They
use the project of tests/test_nest_join.py. No test calls Jev or a coding agent.

Acceptance values, written before the first run on 2026-11-19:

1. The data has one row for each component with a change and PARTS (12) cells in each row.
   A cell has the count of file changes, the changed lines (added and removed lines), and
   the short names of the new modules. The root commit is not used. A file that is not a
   module of the facts (a document) has no component.
2. The parts go from the first used commit to the last used commit. A commit at the end of
   the time is in the last part. `history_days` uses only the commits in the days before
   the last commit, and the first part starts at that time.
3. A shallow clone: the boundary commit is not used, and the data says `shallow`.
4. The cache: a second read with the same HEAD does not run `git log`. A new commit runs it
   again.
5. With no Git repository, or with no Git program, `render` writes the atlas page with no
   History view, gives one notice line, and its exit code is 0.
6. `[render] history = false` gives no history data and runs no Git command for it. A
   wrong value of `history` or `history_days` is a configuration error.
7. The output check: after `render`, a new commit and a change of the clock time do not make
   the page stale. With `history = false` after a render with history, the page is stale.
8. A file belongs to the component whose module claims cover its module in the facts, the
   first component in model order.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_nest_join import CONFIG, NESTED, SOURCE, TOP

from systemap import config, facts_file, git_command, history_data, nest
from systemap.cli import main

DAY = 86_400
T0 = 1_790_000_000  # a fixed commit time in 2026


def _git(root: Path, *args: str, at: int | None = None) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    if at is not None:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{at} +0000"
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def _commit(root: Path, files: dict[str, str], at: int) -> None:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "work", at=at)


def _project(root: Path, setting: str = '[render]\npage = "atlas"\n') -> Path:
    """The project of test_nest_join in a Git repository: a root commit with all files, and
    then commits at T0, T0 + 1 day and T0 + 11 days."""
    write_tree(
        root,
        {
            "systemap.toml": CONFIG + setting,
            "map/model.py": TOP,
            "map/gateway.py": NESTED,
            **SOURCE,
        },
    )
    extra = (root / "pkg/gateway/extra.py").read_text(encoding="utf-8")
    (root / "pkg/gateway/extra.py").unlink()
    _git(root, "init", "-q", "-b", "main")
    _commit(root, {}, T0 - 30 * DAY)
    _commit(root, {"pkg/auth.py": "def token() -> str:\n    return 'u'\n"}, T0)
    _commit(
        root,
        {"pkg/gateway/extra.py": extra, "README.md": "Words.\n"},
        T0 + DAY,
    )
    _commit(root, {"pkg/store.py": "def get() -> str:\n    return 't'\n"}, T0 + 11 * DAY)
    for command in ("place", "extract"):
        assert main(["--root", str(root), command]) == 0
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "map", at=T0 + 12 * DAY)
    return root


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return _project(tmp_path / "p")


def _of(root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    cfg = config.load(root)
    tree = nest.load(cfg)
    return history_data.of_tree(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))


def test_the_cells_count_the_changes_of_each_component(project: Path) -> None:
    """Acceptance 1 and 2."""
    data, notes = _of(project)
    assert notes == []
    assert data is not None
    assert data["commits"] == 4  # the root commit is not used
    assert data["shallow"] is False
    assert sorted(data["cells"]) == ["Auth", "Gateway", "Store"]
    assert all(len(row) == history_data.PARTS for row in data["cells"].values())
    auth, gate, store = (data["cells"][k] for k in ("Auth", "Gateway", "Store"))
    assert auth[0] == [1, 2, []]
    assert gate[1] == [1, 2, ["extra"]]  # the parts are 1 day long: T0 + 1 day is part 1
    assert store[11] == [1, 2, []]  # T0 + 11 days
    assert sum(x[0] for row in data["cells"].values() for x in row) == 3  # README has no part
    assert data["from"] == data["parts"][0][0]
    assert data["to"] == data["parts"][-1][1]
    assert len(data["parts"]) == history_data.PARTS


def test_the_commit_at_the_end_is_in_the_last_part() -> None:
    log = history_data.Log(
        "h",
        False,
        (
            history_data.Commit("a", 0, False, (("f.py", 3),), ()),
            history_data.Commit("b", 12 * DAY, False, (("f.py", 4),), ("f.py",)),
        ),
    )
    data = history_data.build(log, {"f.py": ("F", "f")})
    assert data is not None
    assert data["cells"]["F"][0] == [1, 3, []]
    assert data["cells"]["F"][11] == [1, 4, ["f"]]
    assert data["parts"][0] == ["1 Jan", "2 Jan"]


def test_history_days_uses_only_the_last_days(project: Path) -> None:
    """Acceptance 2: the last used commit is at T0 + 12 days."""
    (project / "systemap.toml").write_text(
        CONFIG + '[render]\npage = "atlas"\nhistory_days = 2\n', encoding="utf-8"
    )
    data, _ = _of(project)
    assert data is not None
    assert data["commits"] == 2  # T0 + 11 days and T0 + 12 days
    assert sorted(data["cells"]) == ["Store"]


def test_a_shallow_clone_leaves_out_its_boundary(project: Path, tmp_path: Path) -> None:
    """Acceptance 3."""
    clone = tmp_path / "c"
    _git(tmp_path, "clone", "-q", "--depth", "3", f"file://{project}", str(clone))
    assert main(["--root", str(clone), "extract"]) == 0
    data, _ = _of(clone)
    assert data is not None
    assert data["shallow"] is True
    assert data["commits"] == 2  # T0 + 11 days and "map"; the commit at T0 + 1 day is the boundary
    assert sorted(data["cells"]) == ["Store"]
    log = history_data.read_log(clone)
    assert [c.root for c in log.commits] == [False, False, True]


def test_the_cache_keeps_the_log_of_the_same_head(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 4."""
    calls: list[str] = []
    real = git_command.run

    def run(cwd: Path, *args: str, **kw: Any) -> Any:
        calls.append(args[0])
        return real(cwd, *args, **kw)

    monkeypatch.setattr(git_command, "run", run)
    first = history_data.read_log(project)
    assert calls.count("log") == 1
    assert (project / ".systemap" / "history.json").is_file()
    second = history_data.read_log(project)
    assert calls.count("log") == 1
    assert second == first
    _commit(project, {"pkg/log.py": "X = 1\n"}, T0 + 13 * DAY)
    third = history_data.read_log(project)
    assert calls.count("log") == 2
    assert len(third.commits) == len(first.commits) + 1


def test_a_broken_cache_is_read_again(project: Path) -> None:
    first = history_data.read_log(project)
    (project / ".systemap" / "history.json").write_text("{", encoding="utf-8")
    assert history_data.read_log(project) == first


def test_without_git_the_page_has_no_history(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 5: no repository, and no Git program."""
    root = tmp_path / "n"
    write_tree(
        root,
        {
            "systemap.toml": CONFIG + '[render]\npage = "atlas"\n',
            "map/model.py": TOP,
            "map/gateway.py": NESTED,
            **SOURCE,
        },
    )
    for command in ("place", "extract"):
        assert main(["--root", str(root), command]) == 0
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    capsys.readouterr()
    assert main(["--root", str(root), "render"]) == 0
    err = capsys.readouterr().err
    notes = [line for line in err.splitlines() if "History" in line]
    assert len(notes) == 1
    assert notes[0].startswith("notice: The page has no History view, because Git cannot read")
    page = (root / "docs" / "map" / "index.html").read_text(encoding="utf-8")
    assert 'id="atlas-history"' not in page
    assert '<button type="button" data-mode="history"' not in page
    monkeypatch.setenv("PATH", str(tmp_path / "nothing"))
    data, lines = _of(root)
    assert data is None
    assert len(lines) == 1
    assert "git could not start" in lines[0]


def test_history_false_reads_no_git(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Acceptance 6."""
    (project / "systemap.toml").write_text(
        CONFIG + '[render]\npage = "atlas"\nhistory = false\n', encoding="utf-8"
    )

    def run(*_: Any, **__: Any) -> Any:
        raise AssertionError("no Git command")

    monkeypatch.setattr(git_command, "run", run)
    assert _of(project) == (None, [])


@pytest.mark.parametrize(
    ("setting", "error"),
    [
        ("history = 1\n", "render.history must be true or false"),
        ("history_days = 0\n", "render.history_days must be a positive integer"),
        ("history_days = -3\n", "render.history_days must be a positive integer"),
        ('history_days = "9"\n', "render.history_days must be a positive integer"),
        ("history_days = true\n", "render.history_days must be a positive integer"),
    ],
)
def test_a_wrong_history_setting_is_an_error(tmp_path: Path, setting: str, error: str) -> None:
    write_tree(tmp_path, {"systemap.toml": CONFIG + "[render]\n" + setting, **SOURCE})
    with pytest.raises(config.ConfigError, match=error):
        config.load(tmp_path)


def test_the_settings_have_defaults(tmp_path: Path) -> None:
    write_tree(tmp_path, {"systemap.toml": CONFIG, **SOURCE})
    cfg = config.load(tmp_path)
    assert (cfg.render_history, cfg.render_history_days) == (True, 0)
    write_tree(tmp_path, {"systemap.toml": CONFIG + "[render]\nhistory_days = 30\n"})
    assert config.load(tmp_path).render_history_days == 30


def test_the_check_does_not_read_git(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Acceptance 7."""
    assert main(["--root", str(project), "render"]) == 0
    page = (project / "docs" / "map" / "index.html").read_text(encoding="utf-8")
    assert '<script type="application/json" id="atlas-history">' in page
    assert '<button type="button" data-mode="history"' in page
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "page", at=T0 + 40 * DAY)
    _commit(project, {"README.md": "More words.\n"}, T0 + 41 * DAY)

    def no_log(_: Path) -> history_data.Log:
        raise AssertionError("the check must not read the Git log")

    monkeypatch.setattr(history_data, "read_log", no_log)
    assert main(["--root", str(project), "check"]) == 0
    assert main(["--root", str(project), "render", "--check"]) == 0
    stored = history_data.stored(config.load(project), nest.load(config.load(project)))
    assert stored is not None
    assert stored["commits"] == 4
    (project / "systemap.toml").write_text(
        CONFIG + '[render]\npage = "atlas"\nhistory = false\n', encoding="utf-8"
    )
    assert main(["--root", str(project), "render", "--check"]) != 0


def test_a_file_belongs_to_the_first_claim_in_the_facts(project: Path) -> None:
    """Acceptance 8."""
    cfg = config.load(project)
    tree = nest.load(cfg)
    own = history_data.owners(tree.top.model, facts_file.read_facts(cfg.facts_path, cfg.root))
    assert own["pkg/gateway/routes.py"] == ("Gateway", "routes")
    assert own["pkg/auth.py"] == ("Auth", "auth")
    assert "README.md" not in own


def test_the_parse_of_the_log() -> None:
    text = (
        "@aaa 10 bbb\n\0:000000 100644 0 1 A\0x.py\0:100644 100644 1 2 M\0y.py\0"
        "3\t1\tx.py\0-\t-\ty.py\0\0@bbb 5\n\0"
    )
    a, b = history_data.parse(text)
    assert a == history_data.Commit("aaa", 10, False, (("x.py", 4), ("y.py", 0)), ("x.py",))
    assert b == history_data.Commit("bbb", 5, True, (), ())
