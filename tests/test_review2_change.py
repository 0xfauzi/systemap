"""The second Codex review: the comment write, sequence generation, the test comparison,
the agent runner, the pull request metadata, and the plan comparison.

Each test gives its acceptance value in its docstring. The values were written before
the repairs. No test calls Jev or a coding agent: each agent test gives its own
`run_command`, and the runner tests start only a local file that is not an agent.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, TWO_CARD_MODEL, init_two_cards, write_tree
from test_change_git import commit, compare, git, make

from systemap import agent, change, nest, plan
from systemap.cli import main
from systemap.config import Config, load
from systemap.jev_cli import cmd_journeys
from systemap.model import Component, Container, Flow, Model, Region

URL = "https://example.org/pr-{number}/"
ANSWER = {
    "id": "read-and-write",
    "label": "A request is read and written",
    "steps": [
        {
            "edge": ["Reader", "Writer"],
            "acts": ["Reader"],
            "measures": [],
            "say": "The reader makes a request from the input and gives it to the writer.",
        }
    ],
}
READ_ROUTE = (
    'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/read")\n'
    "def read(source: str) -> str:\n    return source\n"
)
WRITE_ROUTE = (
    "from fastapi import FastAPI\n\nfrom pkg.reader import read\n\napp = FastAPI()\n\n\n"
    '@app.post("/write")\ndef write(request: str) -> str:\n    return read(request)\n'
)


# ---- change-1: the comment write and a link in the repository ---------------------------


@pytest.fixture
def delta_repo(tmp_path: Path) -> Path:
    """Two commits with a page URL: the second adds a module that no component claims."""
    root = tmp_path / "repo"
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(root, "--no-ci")
    settings = root / "systemap.toml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + f'\n[delta]\npage_url = "{URL}"\n',
        encoding="utf-8",
    )
    git(root, "init", "-q", "-b", "main")
    commit(root, "base")
    write_tree(root, {"pkg/extra.py": "def extra() -> int:\n    return 1\n"})
    commit(root, "head")
    return root


def delta(root: Path, *argv: str) -> int:
    return main(["--root", str(root), "delta", "--no-jev", "--base", "HEAD~1", *argv])


def test_the_comment_replaces_a_link_and_does_not_write_to_its_target(
    delta_repo: Path, tmp_path: Path
) -> None:
    """Acceptance (change-1): `comment.md` in the repository is a link to a file outside
    the repository. After `delta --comment comment.md --pr 42`, the outside file has its
    previous text, and `comment.md` is a regular file with the comment. The exit code is 1.
    """
    outside = tmp_path / "outside.txt"
    outside.write_text("keep this text\n", encoding="utf-8")
    link = delta_repo / "comment.md"
    link.symlink_to(outside)
    assert delta(delta_repo, "--pr", "42", "--comment", str(link)) == 1
    assert outside.read_text(encoding="utf-8") == "keep this text\n"
    assert not link.is_symlink()
    assert "pr-42/#changes" in link.read_text(encoding="utf-8")


def test_the_comment_is_not_written_through_a_folder_link_out_of_the_repository(
    delta_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (change-1): `out` in the repository is a link to a folder outside the
    repository. `delta --comment out/comment.md` writes no file in that folder. It gives
    the path and the cause on stderr, and the exit code 1.
    """
    folder = tmp_path / "elsewhere"
    folder.mkdir()
    (delta_repo / "out").symlink_to(folder, target_is_directory=True)
    assert delta(delta_repo, "--pr", "42", "--comment", str(delta_repo / "out/comment.md")) == 1
    assert list(folder.iterdir()) == []
    assert "the command does not use this file" in capsys.readouterr().err


def test_a_comment_path_outside_the_repository_is_still_written(
    delta_repo: Path, tmp_path: Path
) -> None:
    """Acceptance (change-1): a comment path that is not in the repository, such as a
    folder of the CI runner, gets the comment as before the repair.
    """
    out = tmp_path / "runner" / "comment.md"
    out.parent.mkdir()
    assert delta(delta_repo, "--pr", "42", "--comment", str(out)) == 1
    assert "pr-42/#changes" in out.read_text(encoding="utf-8")


# ---- change-2, change-3, change-7: sequence generation -----------------------------------


@pytest.fixture
def two_cards(tmp_path: Path) -> Config:
    """The two-card map with an agent command and a route into the reader."""
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES, "pkg/reader.py": READ_ROUTE})
    init_two_cards(tmp_path, "--no-ci")
    settings = tmp_path / "systemap.toml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + '\n[agent]\ncommand = "agent -p"\n',
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return load(tmp_path)


def args_for(cfg: Config) -> argparse.Namespace:
    return argparse.Namespace(root_path=cfg.root, limit=3, dry_run=False)


def answering(*answers: dict[str, Any]) -> Any:
    """A transport that gives the answers in sequence, then the last answer again."""
    asked: list[str] = []

    def run(command: str, question: str, cwd: Path, timeout: float) -> str:
        asked.append(question)
        return json.dumps(answers[min(len(asked), len(answers)) - 1])

    return run


NO_SEQUENCE_NAMES = (
    TWO_CARD_MODEL.replace("    Journey,\n", "").replace("    Step,\n", "").split("JOURNEYS = (")[0]
    + "JOURNEYS = ()\n\nMEANING = Meaning(\n    plain=PLAIN,\n    layers=LAYERS,\n"
    "    layer_of_kind=LAYER_OF_KIND,\n    relations=RELATIONS,\n    journeys=JOURNEYS,\n"
    "    verbs=VERBS,\n)\n"
)


def test_a_model_without_the_sequence_names_gets_the_imports_and_loads(
    two_cards: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (change-2): the model imports neither `Journey` nor `Step`. After
    `systemap journeys`, the exit code is 0, the model loads, and it has the sequence.
    """
    two_cards.model_path.write_text(NO_SEQUENCE_NAMES, encoding="utf-8")
    assert cmd_journeys(args_for(two_cards), run_command=answering(ANSWER)) == 0
    assert "wrote read-and-write" in capsys.readouterr().out
    meaning = nest.load(two_cards).top.meaning
    assert [j.id for j in meaning.journeys] == ["read-and-write"]


def test_a_proposed_model_without_the_sequence_is_not_written(
    two_cards: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (change-2): `JOURNEYS` is not the list that MEANING uses. The command
    inserts the sequence into `JOURNEYS`, but the loaded MEANING does not contain it. The
    command writes no file, gives the cause, and the exit code 1.
    """
    text = NO_SEQUENCE_NAMES.replace("    journeys=JOURNEYS,\n", "    journeys=(),\n")
    two_cards.model_path.write_text(text, encoding="utf-8")
    assert cmd_journeys(args_for(two_cards), run_command=answering(ANSWER)) == 1
    out = capsys.readouterr().out
    assert "does not contain the sequence read-and-write" in out
    assert two_cards.model_path.read_text(encoding="utf-8") == text


def test_a_rejected_second_draft_gives_exit_1_and_keeps_the_first(
    two_cards: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (change-3): two entry points get answers with the same sequence id. The
    first sequence is written. The second draft is rejected with its cause. The exit
    code is 1, and the last line gives 1 of 2 requests that did not complete.
    """
    (two_cards.root / "pkg/writer.py").write_text(WRITE_ROUTE, encoding="utf-8")
    assert main(["--root", str(two_cards.root), "extract"]) == 0
    capsys.readouterr()
    assert cmd_journeys(args_for(two_cards), run_command=answering(ANSWER)) == 1
    out = capsys.readouterr().out
    assert "wrote read-and-write" in out
    assert "the map has a sequence with the id read-and-write" in out
    assert "1 of 2 requests did not complete" in out
    ids = [j.id for j in nest.load(two_cards).top.meaning.journeys]
    assert ids.count("read-and-write") == 1


def test_a_source_file_removed_after_extraction_gives_exit_1_and_the_file(
    two_cards: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (change-7): the facts name `pkg/writer.py`, which is then removed. The
    command gives no traceback. It names the file, and the exit code is 1.
    """
    (two_cards.root / "pkg/writer.py").unlink()
    assert cmd_journeys(args_for(two_cards), run_command=answering(ANSWER)) == 1
    assert "pkg/writer.py" in capsys.readouterr().out


# ---- change-8: the agent runner -----------------------------------------------------------


def test_a_command_with_an_unmatched_quote_is_an_agent_error(
    two_cards: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (change-8): `[agent] command = "agent -p 'x"` gives exit 1 from
    `systemap journeys`, with no traceback, and a line that names the quotation.
    """
    settings = two_cards.root / "systemap.toml"
    text = settings.read_text(encoding="utf-8").replace(
        'command = "agent -p"', 'command = "agent -p \'x"'
    )
    settings.write_text(text, encoding="utf-8")
    assert main(["--root", str(two_cards.root), "journeys"]) == 1
    assert "quotation" in capsys.readouterr().out


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no execute permission bit")
def test_a_command_without_execute_permission_is_an_agent_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance (change-8): a configured file without execute permission gives
    AgentError, not PermissionError.
    """
    monkeypatch.setenv(agent.TRUST, "1")
    script = tmp_path / "agent.sh"
    script.write_text("#!/bin/sh\necho answer\n", encoding="utf-8")
    os.chmod(script, 0o644)
    with pytest.raises(agent.AgentError, match="could not start"):
        agent.shell_run(str(script), "question", tmp_path, 5.0)


# ---- change-9: the pull request metadata ------------------------------------------------


def test_render_without_gh_gives_the_page_and_a_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (change-9): without `gh` on the search path, `render --base HEAD~1 --pr 42`
    gives exit 0 and one note on stderr that the pull request data is not available.
    """
    root = make(tmp_path / "repo", "python")
    write_tree(root, {"pkg/extra.py": "def extra() -> int:\n    return 1\n"})
    commit(root, "head")
    assert main(["--root", str(root), "extract"]) == 0
    empty = tmp_path / "no-programs"
    empty.mkdir()
    git_dir = Path(shutil.which("git") or "git").parent
    monkeypatch.setenv("PATH", f"{empty}{os.pathsep}{git_dir}")
    capsys.readouterr()
    assert main(["--root", str(root), "render", "--base", "HEAD~1", "--pr", "42"]) == 0
    err = capsys.readouterr().err
    assert err.count("pull request 42") == 1


def test_pr_meta_without_gh_gives_no_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Acceptance (change-9): `pr_meta` without `gh` gives an empty record, not an
    exception.
    """
    monkeypatch.setenv("PATH", str(tmp_path))
    assert change.pr_meta(tmp_path, "42") == {}


# ---- change-4, change-5, change-6: the test comparison ------------------------------------

# A test file that imports a different module at each revision.
MOVED = {
    "python": (
        "tests/test_value.py",
        "from pkg.reader import read\n\n\ndef test_a() -> None:\n    assert read('x')\n",
        "from pkg.writer import write\n\n\ndef test_b() -> None:\n    assert write('x')\n",
        ("Reader", "Writer"),
        ("tests/test_value.py::test_a", "tests/test_value.py::test_b"),
    ),
    "typescript": (
        "tests/value.spec.ts",
        'import { main } from "@/cli";\n\ntest("a", () => main());\n',
        'import { serve } from "@/service";\n\ntest("b", () => serve("1"));\n',
        ("Front", "Service"),
        ("tests/value.spec.ts::a", "tests/value.spec.ts::b"),
    ),
}


def card_tests(found: dict[str, Any], card: str) -> tuple[list[str], list[str]]:
    surface = found["per_component"].get(card, {}).get("surface", {})
    return surface.get("tests_added", []), surface.get("tests_removed", [])


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_each_revision_assigns_its_own_tests_to_its_own_imports(
    tmp_path: Path, language: str
) -> None:
    """Acceptance (change-4): at the base, the test file imports module A and defines test
    a. At the head, it imports module B and defines test b. The comparison gives test a
    as removed from the component of A, test b as added to the component of B, and no
    other test change.
    """
    rel, before, after, (first, second), (old, new) = MOVED[language]
    root = make(tmp_path / "repo", language)
    write_tree(root, {rel: before})
    base = commit(root, "a test of A")
    write_tree(root, {rel: after})
    commit(root, "a test of B")
    found = compare(root, base, "HEAD")
    assert card_tests(found, first) == ([], [old])
    assert card_tests(found, second) == ([new], [])


def test_each_commit_resolves_its_tests_with_its_own_typescript_configuration(
    tmp_path: Path,
) -> None:
    """Acceptance (change-5): the alias `#target` selects `src/cli.ts` at the base and
    `src/service.ts` at the head. The working tree has a third alias value. The
    comparison gives test a as removed from Front and test b as added to Service.
    """
    root = make(tmp_path / "repo", "typescript")
    rel = "tests/value.spec.ts"

    def aliased(target: str) -> str:
        return json.dumps(
            {"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"], "#target": [target]}}}
        )

    write_tree(
        root,
        {
            "tsconfig.json": aliased("src/cli.ts"),
            rel: 'import { main } from "#target";\n\ntest("a", () => main());\n',
        },
    )
    base = commit(root, "the alias selects the CLI")
    write_tree(
        root,
        {
            "tsconfig.json": aliased("src/service.ts"),
            rel: 'import { serve } from "#target";\n\ntest("b", () => serve("1"));\n',
        },
    )
    head = commit(root, "the alias selects the service")
    write_tree(root, {"tsconfig.json": aliased("src/client.ts")})
    found = compare(root, base, head)
    assert card_tests(found, "Front") == ([], ["tests/value.spec.ts::a"])
    assert card_tests(found, "Service") == (["tests/value.spec.ts::b"], [])


UNPARSED = {
    "python": (
        "tests/test_value.py",
        "def test_value(:\n    pass\n",
        "from pkg.reader import read\n\n\ndef test_value() -> None:\n    assert read('x')\n",
    ),
    "typescript": (
        "tests/value.spec.ts",
        'import { serve } from "@/service";\n\ntest("value", () => {\n',
        'import { serve } from "@/service";\n\ntest("value", () => serve("1"));\n',
    ),
}


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_a_test_file_that_does_not_parse_has_unknown_test_changes(
    tmp_path: Path, language: str
) -> None:
    """Acceptance (change-6): the base text of a test file does not parse. The head text
    has one test. The comparison gives the file in `unread_tests` with a parse problem,
    and it gives no added test.
    """
    rel, before, after = UNPARSED[language]
    root = make(tmp_path / "repo", language)
    write_tree(root, {rel: before})
    base = commit(root, "a test that does not parse")
    write_tree(root, {rel: after})
    commit(root, "a test that parses")
    found = compare(root, base, "HEAD")
    assert [line.split(": ")[0] for line in found["unread_tests"]] == [rel]
    assert "parse" in found["unread_tests"][0]
    assert not any(part["surface"]["tests_added"] for part in found["per_component"].values())


# ---- change-10: the plan comparison and symbol claims ---------------------------------


def test_a_change_to_a_claimed_symbol_changes_each_component_that_claims_its_module() -> None:
    """Acceptance (change-10): Agent claims `pkg.agent`, and Tool claims `pkg.agent:search`.
    A change of `pkg.agent` gives the changed components Agent and Tool. A plan that
    names only Agent gives Tool as a change outside the plan.
    """
    model = Model(
        canvas=(600, 300),
        containers=(Container("system", "PKG", (0, 0, 600, 300)),),
        regions=(Region("core", "CORE", (10, 10, 580, 280), container="system"),),
        components=(
            Component("Agent", "Asks.", implemented_by=("pkg.agent",), region="core"),
            Component("Tool", "Finds.", implemented_by=("pkg.agent:search",), region="core"),
        ),
        flows=(Flow("Agent", "Tool", "query", "data"),),
        flow_kinds=(),
    )
    base = {"components": {"pkg.agent": {"sha": "1"}}}
    head = {"components": {"pkg.agent": {"sha": "2"}}}
    owner = plan.owners(model, model, base, head)
    changed = plan.touched(base, head, owner)
    assert changed == {"Agent", "Tool"}
    assert plan.check(["Agent"], changed) == (["Tool"], [])
