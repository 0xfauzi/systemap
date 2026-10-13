"""Git arguments, output paths, the facts cache, and configuration loading.

Each test shows one Codex result (adapters-1, adapters-24, adapters-25, model-1, model-2,
model-12). Each acceptance value is in the docstring of its test. Before the repair, each
test failed on origin/main at d4b1514.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree
from test_nested import CONFIG, GATEWAY, STYLE, TOP, TREE

from systemap import change, config, delta, history
from systemap import language as languages
from systemap.cli import main

GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]


def _commit(root: Path, message: str) -> str:
    subprocess.run([*GIT, "-C", str(root), "add", "-A"], check=True)
    subprocess.run([*GIT, "-C", str(root), "commit", "-qm", message], check=True)
    return delta.resolve(root, "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A two-card map in a Git repository with one commit, below tmp_path/repo."""
    root = tmp_path / "repo"
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(root, "--no-ci")
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    _commit(root, "the first map")
    return root


# ---- adapters-1: a revision that Git can read as an option -------------------------


def test_history_refuses_a_ref_that_git_reads_as_an_option(repo: Path) -> None:
    """Acceptance: `history.sample` with the ref `--all` raises DeltaError.

    Before the repair, Git read `--all` as an option and gave the commits of all refs."""
    with pytest.raises(delta.DeltaError, match="unknown ref --all"):
        history.sample(repo, "30 years ago", 1, "--all")


def test_history_ref_cannot_make_git_write_a_file(repo: Path, tmp_path: Path) -> None:
    """Acceptance: `history --ref=--output=FILE` writes no file and does not exit 0."""
    target = tmp_path / "written-by-git.txt"
    code = main(["--root", str(repo), "history", f"--ref=--output={target}"])
    assert code != 0
    assert not target.exists()


def test_merge_base_refuses_a_ref_that_git_reads_as_an_option(repo: Path) -> None:
    """Acceptance: `delta.merge_base` with the base `--octopus` raises DeltaError.

    `systemap plan --check ID --base REF` gives the base to this function. Before the
    repair, Git read `--octopus` as an option and gave the HEAD commit as the merge base."""
    with pytest.raises(delta.DeltaError, match="unknown ref --octopus"):
        delta.merge_base(repo, "--octopus", "HEAD")


def test_the_facts_cache_takes_only_a_full_commit_sha(repo: Path) -> None:
    """Acceptance: `history.facts_at(cfg, "HEAD")` raises DeltaError and writes no cache.

    A cache file under the name `HEAD` stays after HEAD moves, so its facts become stale.
    A value from a caller also becomes a part of a cache path."""
    cfg = config.load(repo)
    with pytest.raises(delta.DeltaError, match="full commit SHA"):
        history.facts_at(cfg, "HEAD")
    assert not list(history.cache_dir(cfg).glob("HEAD-*"))


def test_a_pull_request_value_is_not_a_gh_option(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance: `change.pr_meta` with `--web` does not give `--web` to gh as an option.

    A recorded gh program writes its arguments to a file. The test does not call GitHub."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    record = tmp_path / "gh-arguments.txt"
    gh = bin_dir / "gh"
    gh.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{record}"\necho "{{}}"\n', encoding="utf-8")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    assert change.pr_meta(repo, "--web") == {}
    if record.exists():
        arguments = record.read_text(encoding="utf-8").splitlines()
        assert arguments.index("--web") > arguments.index("--"), arguments


# ---- adapters-24: a package root outside the repository ----------------------------


@pytest.mark.parametrize("form", ["absolute", "relative", "symbolic link"])
def test_a_package_root_outside_the_repository_is_a_configuration_error(
    tmp_path: Path, form: str
) -> None:
    """Acceptance: `config.load` raises ConfigError for a package root outside the root.

    Before the repair, the root passed validation, and extraction raised ValueError."""
    outside = tmp_path / "outside" / "pkg"
    write_tree(outside, {"__init__.py": "", "reader.py": "def read() -> None:\n    pass\n"})
    root = tmp_path / "repo"
    root.mkdir()
    rel = {"absolute": str(outside), "relative": "../outside/pkg", "symbolic link": "pkg"}[form]
    if form == "symbolic link":
        (root / "pkg").symlink_to(outside, target_is_directory=True)
    # A literal TOML key, because a Windows path has backslashes. In a basic TOML string,
    # "\U" starts an escape, and the file is not TOML.
    (root / "systemap.toml").write_text(
        f'language = "python"\n[package_roots]\n\'{rel}\' = "pkg"\n', encoding="utf-8"
    )
    with pytest.raises(config.ConfigError, match="not in the repository"):
        config.load(root)


# ---- adapters-25: a temporary file name that two writers share ---------------------


def test_the_facts_cache_does_not_use_a_shared_temporary_name(repo: Path) -> None:
    """Acceptance: `history.facts_at` writes the cache when the name `<cache>.tmp` is in use.

    A directory at that name stands for a second writer that holds the name. Before the
    repair, each writer used `<cache>.tmp`, and this call raised IsADirectoryError."""
    cfg = config.load(repo)
    sha = delta.resolve(repo, "HEAD")
    scope = history.cache_scope(cfg, languages.repository(cfg.language).parser_version())
    path = history.cache_dir(cfg) / f"{sha}-{scope}.json"
    path.with_suffix(".tmp").mkdir(parents=True)
    facts = history.facts_at(cfg, sha)
    assert path.is_file()
    assert facts["built_at_commit"] == sha
    left = {p.name for p in path.parent.iterdir()}
    # The lock file of the facts cache stays. It is not a temporary file.
    expected = {path.name, path.with_suffix(".tmp").name, history.lock_of(cfg).name + ".lock"}
    assert left == expected, "no temporary file stays"


# ---- model-1: a nested map ID that becomes an output path --------------------------


def _nested_with_card_id(root: Path, card: str) -> None:
    models = {
        "map/model.py": TOP.replace('"Gateway"', repr(card)),
        "map/gateway.py": GATEWAY,
        "map/style.py": STYLE.replace('"Gateway"', repr(card)),
    }
    write_tree(root, {**TREE, "systemap.toml": CONFIG, **models})


@pytest.mark.parametrize("form", ["parent", "absolute", "empty part"])
def test_a_nested_map_id_must_be_one_path_segment(tmp_path: Path, form: str) -> None:
    """Acceptance: a card ID that opens a map and is not one safe path segment gives exit 2.

    The render command also writes no file outside the output directory. Before the
    repair, the ID `../../../escape` made `render` write `index.html` outside it."""
    root = tmp_path / "repo"
    card = {
        "parent": "../../../escape",
        "absolute": str(tmp_path / "escape"),
        "empty part": "a//b",
    }[form]
    _nested_with_card_id(root, card)
    main(["--root", str(root), "place"])
    main(["--root", str(root), "extract"])
    assert main(["--root", str(root), "render"]) == 2
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize("key", ["facts_file", "figure out"])
def test_a_configured_output_file_stays_in_the_output_directory(repo: Path, key: str) -> None:
    """Acceptance: a configured output file outside `out_dir` gives exit 2 and no write."""
    escape = repo.parent / "escape.out"
    text = (repo / "systemap.toml").read_text(encoding="utf-8")
    if key == "facts_file":
        text = 'facts_file = "../../../escape.out"\n' + text
    else:
        text = text + '\n[[figures]]\nout = "../../../escape.out"\n'
    (repo / "systemap.toml").write_text(text, encoding="utf-8")
    assert main(["--root", str(repo), "refresh"]) == 2
    assert not escape.exists()


# ---- model-2: model fields that are not validated ----------------------------------


BAD_COMPONENTS = """
from systemap import Meaning, Model

MODEL = Model(canvas=(0, 0), containers=(), regions=(), components=("incorrect",), flows=(), flow_kinds=())
MEANING = Meaning(plain={})
"""


def test_a_model_field_with_an_incorrect_type_is_a_configuration_error(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: `systemap check` gives exit 2 and a message that names the field.

    Before the repair, `nest._theme` raised AttributeError, and the CLI showed a traceback."""
    (repo / "map/model.py").write_text(BAD_COMPONENTS, encoding="utf-8")
    assert main(["--root", str(repo), "check"]) == 2
    err = capsys.readouterr().err
    assert "MODEL.components[0]" in err
    assert "Traceback" not in err


def test_a_meaning_field_with_an_incorrect_type_is_a_configuration_error(repo: Path) -> None:
    """Acceptance: a relation key that is a number gives ConfigError, not an other error."""
    text = BAD_COMPONENTS.replace('("incorrect",)', "()").replace(
        "Meaning(plain={})", 'Meaning(plain={}, relations={3: "A sentence."})'
    )
    (repo / "map/model.py").write_text(text, encoding="utf-8")
    with pytest.raises(config.ConfigError, match=r"MEANING\.relations"):
        config.load_model(repo / "map/model.py", "map/model.py")


# ---- model-12: root discovery that searches for one literal TOML header ------------


def test_root_discovery_reads_the_tool_systemap_table(tmp_path: Path) -> None:
    """Acceptance: `find_root` finds a pyproject.toml with only `[tool.systemap.X]` tables."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.systemap.package_roots]\n"pkg" = "pkg"\n\n[tool.systemap.writing]\n'
        'profile = "plain"\n',
        encoding="utf-8",
    )
    child = tmp_path / "pkg" / "inner"
    child.mkdir(parents=True)
    assert config.find_root(child) == tmp_path


def test_root_discovery_ignores_the_header_text_in_a_string(tmp_path: Path) -> None:
    """Acceptance: a pyproject.toml without a tool.systemap table is not a root."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndescription = "Use [tool.systemap] to configure."\n',
        encoding="utf-8",
    )
    child = tmp_path / "inner"
    child.mkdir()
    found = config.find_root(child)
    assert found != tmp_path
