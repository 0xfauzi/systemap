"""The pull request comment: the summary, and a link to the Changes view if the repository sets it up.

`[delta] page_url` gives the URL of the map page that the repository publishes for each
pull request, with `{number}` for the pull request number. The configuration reader
refuses a value that cannot give that link, with one line that names the key.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import config, delta_link
from systemap.cli import main

URL = "https://example.org/pr-{number}/"


@pytest.fixture
def two_cards(tmp_path: Path) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    return tmp_path


def add_config(root: Path, text: str) -> None:
    """Put configuration text at the end of the file."""
    path = root / "systemap.toml"
    path.write_text(path.read_text(encoding="utf-8") + "\n" + text, encoding="utf-8")


# ---- the configuration value ------------------------------------------------------


def test_the_page_url_is_empty_without_the_table(two_cards: Path) -> None:
    assert config.load(two_cards).delta_page_url == ""


def test_the_page_url_loads_with_its_number_placeholder(two_cards: Path) -> None:
    add_config(two_cards, f'[delta]\npage_url = "{URL}"\n')
    assert config.load(two_cards).delta_page_url == URL


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ('delta = "x"', "delta must be a table"),
        ('[delta]\nurl = "x"', "delta has an unknown key: url"),
        ("[delta]\npage_url = 4", "delta.page_url must be a string"),
        ('[delta]\npage_url = "example.org/pr-{number}/"', "must start with https:// or http://"),
        ('[delta]\npage_url = "https://example.org/pr/"', "must contain {number}"),
        ('[delta]\npage_url = "https://example.org/{pr}/{number}/"', "only the {number}"),
        ('[delta]\npage_url = "https://example.org/{number}/#map"', "must not contain #"),
        ('[delta]\npage_url = "https://example.org/{number}/ x"', "must not contain #"),
    ],
)
def test_a_page_url_that_cannot_give_the_link_is_a_configuration_error(
    two_cards: Path, capsys: pytest.CaptureFixture[str], text: str, said: str
) -> None:
    path = two_cards / "systemap.toml"
    body = path.read_text(encoding="utf-8")
    # A top-level key must come before the first table of the file.
    top = text.startswith("delta =")
    path.write_text(f"{text}\n{body}" if top else f"{body}\n{text}\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="systemap.toml: delta"):
        config.load(two_cards)
    assert main(["--root", str(two_cards), "check"]) == 2
    err = capsys.readouterr().err
    assert said in err
    assert "Correct systemap.toml or the model module." in err


# ---- the comment --------------------------------------------------------------------


def test_the_comment_is_the_marker_the_summary_and_one_link_to_the_changes_view() -> None:
    assert delta_link.comment("SUMMARY", URL, 42) == (
        "<!-- systemap delta -->\n"
        "SUMMARY\n"
        "\n"
        "[Open the Changes view of the map](https://example.org/pr-42/#changes)\n"
    )


def test_without_a_page_url_the_comment_is_the_marker_and_the_summary() -> None:
    assert delta_link.comment("SUMMARY") == "<!-- systemap delta -->\nSUMMARY\n"


# ---- `systemap delta --comment FILE --pr N` --------------------------------------------


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


@pytest.fixture
def repo(two_cards: Path) -> Path:
    """Two commits: the second adds a module that no component claims."""
    git(two_cards, "init", "-q")
    git(two_cards, "add", "-A")
    git(two_cards, "commit", "-q", "-m", "base")
    write_tree(two_cards, {"pkg/extra.py": "def extra() -> int:\n    return 1\n"})
    git(two_cards, "add", "-A")
    git(two_cards, "commit", "-q", "-m", "head")
    return two_cards


def delta(root: Path, *argv: str) -> int:
    return main(["--root", str(root), "delta", "--no-jev", *argv])


UPDATE = (
    "- **Map update:** necessary for 1 line. "
    "The log of the delta job gives the action for each line."
)


def test_without_a_page_url_delta_writes_the_summary_without_a_link(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: the second commit adds a module without a component. The comment gives
    the marker, no contract change, no map change, and one row for the map update. It has
    no link and does not use a pull request number."""
    out = repo / "comment.md"
    assert delta(repo, "--base", "HEAD~1", "--comment", str(out)) == 1
    text = out.read_text(encoding="utf-8")
    assert text.startswith(delta_link.MARKER + "\n**Architecture**\n")
    assert "- **Contract:** no change\n- **Map:** no change\n" in text
    assert UPDATE in text
    assert "#changes" not in text
    said = capsys.readouterr().out
    assert "The map needs an update (1):" in said
    assert "<!--" not in said
    # With no source change, the summary is one line.
    assert delta(repo, "--base", "HEAD", "--comment", str(out)) == 0
    assert out.read_text(encoding="utf-8") == (
        f"{delta_link.MARKER}\n**Architecture:** no change to the contract or the map. "
        "Rules: none.\n"
    )


def test_with_a_page_url_delta_writes_the_summary_and_the_link(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add_config(repo, f'[delta]\npage_url = "{URL}"\n')
    out = repo / "comment.md"
    assert delta(repo, "--base", "HEAD~1", "--pr", "5", "--comment", str(out)) == 1
    text = out.read_text(encoding="utf-8")
    assert UPDATE in text
    assert text.endswith(
        "\n\n[Open the Changes view of the map](https://example.org/pr-5/#changes)\n"
    )
    assert "The map needs an update (1):" in capsys.readouterr().out


def test_a_comment_without_a_pull_request_number_is_an_option_error(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add_config(repo, f'[delta]\npage_url = "{URL}"\n')
    assert delta(repo, "--base", "HEAD~1", "--comment", str(repo / "comment.md")) == 2
    err = capsys.readouterr().err
    assert "delta --comment must have --pr with the pull request number." in err
    assert "Correct the command option." in err
    for bad in ("abc", "0", "-3"):
        with pytest.raises(SystemExit) as stop:
            delta(repo, "--base", "HEAD~1", "--pr", bad, "--comment", "comment.md")
        assert stop.value.code == 2
    assert "give a pull request number, such as 42" in capsys.readouterr().err


def test_delta_has_no_markdown_format(repo: Path) -> None:
    with pytest.raises(SystemExit) as stop:
        delta(repo, "--base", "HEAD~1", "--format", "markdown")
    assert stop.value.code == 2


def test_this_repository_workflow_writes_the_summary_comment() -> None:
    """This repository writes the architecture summary, with the same comment job as the
    workflow from `systemap init`. Only the comment job can write to the pull request."""
    text = (Path(__file__).resolve().parent.parent / ".github/workflows/systemap.yml").read_text(
        encoding="utf-8"
    )
    job = text.split("\n  delta:\n", 1)[1].split("\n\n  # This job writes", 1)[0]
    comment = text.split("\n  comment:\n", 1)[1].split("\n  test:\n", 1)[0]
    assert (
        'uv run systemap delta --base "$BASE" --head "$HEAD" --comment comment.md || code=$?' in job
    )
    assert 'cat comment.md >> "$GITHUB_STEP_SUMMARY"' in job
    assert "::error title=Map delta::The map needs an update." in job
    assert job.rstrip().endswith('exit "$code"')
    assert text.count("pull-requests: write") == 1 and "pull-requests: write" in comment
    assert "github.event.pull_request.head.repo.full_name == github.repository" in comment
    # The job changes only a comment from the Actions bot. A comment from a different person can
    # also start with the marker.
    assert '.user.login == "github-actions[bot]" and' in comment
    assert "pull_request_target" not in text
    assert "--format markdown" not in text
