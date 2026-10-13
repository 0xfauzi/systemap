"""Shared code reads a repository file only if the file is a regular file in the repository.

An external file is a file that is not in the repository. It has a secret marker.

Acceptance values:

1. The facts file gives an absolute path, a path with a `..` part, or a link to the
   external file. Then these readers do not read the external file: the `decision flow` audit
   questions (injected provider), the `judgement --order-by-drift` questions (injected
   provider and injected transport), the change detection, the evidence digests, and
   the sequence snapshot. No question state and no request body contains the marker.
   A Python fixture and a TypeScript fixture.
2. Extraction does not read a source file or a test file that is a link to the external
   file. The module record has `completeness.parsed` false with the reason "source could
   not be read: the file is not in the repository". The facts do not contain the marker.
   A Python fixture and a TypeScript fixture.
3. `repo_files` refuses an empty path, an absolute path, a Windows drive path, a UNC
   path, a path with a `..` part, a link to an external file, and a directory.
   It reads a normal file with the same text as `Path.read_text`.
4. A top model file or a nested model file that is not in the repository gives a
   configuration error.
5. A normal repository gives the same results as before: all earlier tests pass.

No test calls Jev. The providers and the transport are classes in this file.
"""

from __future__ import annotations

import copy
import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree
from test_drift_order import PY_CHANGE, TS_CHANGE, TS_MODEL, change, git, record_reviews

from systemap import (
    audit,
    config,
    drift_order,
    extract,
    facts_file,
    jev,
    journeys,
    judgement,
    judgement_evidence,
    nest,
    repo_files,
)
from systemap import change as change_mod
from systemap.cli import main
from systemap.config import ConfigError
from systemap.decision import Answer, PredicateAnswer, Question
from systemap.source_text import text_digest

MARKER = "zq7secretmarker"
OUTSIDE_REASON = "source could not be read: the file is not in the repository"

# The external files. Each one has lines that a reader copies into a question if it
# reads the file: `read` and `serve` are the names that the fixture modules import.
PY_SECRET = f'''"""{MARKER}"""
from pkg.reader import read

read = "{MARKER}"


def {MARKER}() -> None:
    return None


def test_{MARKER}() -> None:
    assert read
'''
TS_SECRET = f"""// {MARKER}
import {{ serve }} from "@/service";

export const used = serve;
export const label = "{MARKER}";

export function {MARKER}(): void {{}}

test("{MARKER}", () => serve("{MARKER}"));
"""

TS_FLOW_MODEL = TS_MODEL.replace(
    "Component, Container, Meaning", "Component, Container, Flow, Meaning"
).replace("flows=(),", 'flows=(Flow("Service", "Front", "user", "data"),),')

FORMS = ("absolute", "dotdot", "symlink")


class Recorder:
    """A decision provider that keeps each question and answers 0.5.

    The audit lines use the measured thresholds of a provider name, so it uses the Jev name.
    """

    name = "jev"

    def __init__(self) -> None:
        self.asked: list[Question] = []

    def decide(self, questions: Sequence[Question]) -> list[Answer]:
        self.asked += questions
        return [PredicateAnswer(0.5) for _ in questions]

    def states(self) -> str:
        return json.dumps([q.state for q in self.asked], default=str)


class Transport:
    """A Jev transport that keeps each request body and answers each question with 0.5."""

    def __init__(self) -> None:
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if path == "/models":
            return {"models": [{"name": "jev-latest", "release_date": "2026-10-01"}]}
        assert body is not None
        self.bodies.append(body)
        answers = {name: {"noul": 0.5} for name in body["questions"]}
        return {"model": "jev-latest", "answers": answers, "usage": {}}


def _secret(language: str) -> tuple[str, str]:
    return ("secret.py", PY_SECRET) if language == "python" else ("secret.ts", TS_SECRET)


def make_project(tmp_path: Path, language: str) -> tuple[Path, Path]:
    """A reviewed project in a Git commit with a source change, and an external file."""
    root, outside = tmp_path / "repo", tmp_path / "outside"
    outside.mkdir()
    name, text = _secret(language)
    (outside / name).write_text(text, encoding="utf-8")
    if language == "python":
        write_tree(root, {**STARTER_MODULES, "pkg/__init__.py": ""})
        init_two_cards(root, "--no-ci")
    else:
        shutil.copytree(Path(__file__).parent / "fixtures/typescript-app", root)
        (root / "map/model.py").write_text(TS_FLOW_MODEL, encoding="utf-8")
    assert main(["--root", str(root), "extract"]) == 0
    record_reviews(root)
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-qm", "reviewed")
    change(root, PY_CHANGE if language == "python" else TS_CHANGE)
    return root, outside / name


def link_name(language: str) -> str:
    return "pkg/link.py" if language == "python" else "src/link.ts"


def bad_path(form: str, root: Path, secret: Path, language: str) -> str:
    if form == "absolute":
        return str(secret)
    if form == "dotdot":
        return f"../outside/{secret.name}"
    link = root / link_name(language)
    if not link.is_symlink():
        link.symlink_to(secret)
    return link_name(language)


def tampered(facts: dict[str, Any], path: str) -> dict[str, Any]:
    """The facts with the same bad file path in each module record."""
    out = copy.deepcopy(facts)
    for record in out["components"].values():
        record["file"] = path
    return out


@pytest.fixture(params=["python", "typescript"])
def project(
    request: pytest.FixtureRequest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[Path, Path, str]:
    root, secret = make_project(tmp_path, request.param)
    capsys.readouterr()
    return root, secret, request.param


def loaded(root: Path) -> tuple[config.Config, nest.Tree, dict[str, Any]]:
    cfg = config.load(root)
    return cfg, nest.load(cfg), facts_file.read_facts(cfg.facts_path)


# ---- acceptance 1 -----------------------------------------------------------------


@pytest.mark.parametrize("form", FORMS)
def test_the_flow_audit_does_not_read_an_outside_file(
    project: tuple[Path, Path, str], form: str
) -> None:
    """Acceptance 1 for `systemap audit --kind "decision flow"`, with an injected provider."""
    root, secret, language = project
    cfg, tree, facts = loaded(root)
    control = Recorder()
    audit.run(tree, facts, cfg, control, ["decision flow"])
    assert any(q.key.split("|")[1] == "flow" for q in control.asked)
    provider = Recorder()
    audit.run(
        tree,
        tampered(facts, bad_path(form, root, secret, language)),
        cfg,
        provider,
        ["decision flow"],
    )
    assert MARKER not in provider.states()


@pytest.mark.parametrize("form", FORMS)
def test_the_drift_questions_do_not_read_an_outside_file(
    project: tuple[Path, Path, str], form: str
) -> None:
    """Acceptance 1 for `judgement --order-by-drift`, with an injected provider."""
    root, secret, language = project
    cfg, tree, facts = loaded(root)
    lines = judgement.run_tree(tree, facts)
    provider = Recorder()
    bad = tampered(facts, bad_path(form, root, secret, language))
    drift_order.order(cfg, tree, bad, lines, lambda: provider)
    assert provider.asked
    assert MARKER not in provider.states()


@pytest.mark.parametrize("form", FORMS)
def test_the_drift_request_bodies_do_not_hold_an_outside_file(
    project: tuple[Path, Path, str],
    form: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Acceptance 1 for the command `judgement --order-by-drift`, with a stored facts file
    that has the bad paths, and an injected transport."""
    root, secret, language = project
    cfg, _tree, facts = loaded(root)
    bad = tampered(facts, bad_path(form, root, secret, language))
    cfg.facts_path.write_text(facts_file.dumps(bad), encoding="utf-8")
    sent = Transport()
    monkeypatch.setenv(jev.KEY_ENV, "a test key")
    monkeypatch.setattr(jev, "http_send", lambda key, base=jev.API: sent)
    main(["--root", str(root), "judgement", "--json", "--order-by-drift"])
    out = capsys.readouterr()
    assert MARKER not in json.dumps(sent.bodies)
    assert MARKER not in out.out + out.err


@pytest.mark.parametrize("form", FORMS)
def test_the_change_detection_does_not_read_an_outside_file(
    project: tuple[Path, Path, str], form: str
) -> None:
    """Acceptance 1 for the change detection of the working tree. A source file and a
    test file are links to the external file, and the facts have the bad path."""
    root, secret, language = project
    cfg, tree, facts = loaded(root)
    test_link = root / ("tests/test_link.py" if language == "python" else "tests/link.spec.ts")
    test_link.parent.mkdir(exist_ok=True)
    test_link.symlink_to(secret)
    bad = tampered(facts, bad_path(form, root, secret, language))
    if form != "symlink":
        bad_path("symlink", root, secret, language)
    for given in (facts, bad):
        found = change_mod.compute(cfg, tree.top.model, "HEAD", given, head=change_mod.WORKING_TREE)
        assert found["has_change"]
        assert MARKER not in repr(found)


@pytest.mark.parametrize("form", FORMS)
def test_the_digests_and_the_snapshot_do_not_read_an_outside_file(
    project: tuple[Path, Path, str], form: str
) -> None:
    """Acceptance 1 for the evidence digests and the sequence snapshot."""
    root, secret, language = project
    _cfg, _tree, facts = loaded(root)
    bad = tampered(facts, bad_path(form, root, secret, language))
    state = judgement_evidence.answer_state(bad["components"], root, "", None)
    assert text_digest(secret.read_bytes()) not in json.dumps(state)
    assert "missing source" in json.dumps(state)
    with pytest.raises(ValueError, match="is not available"):
        journeys._source_snapshot(root, bad)


# ---- acceptance 2 -----------------------------------------------------------------


def test_extraction_does_not_read_a_link_to_an_outside_file(
    project: tuple[Path, Path, str],
) -> None:
    """Acceptance 2 for a Python fixture and a TypeScript fixture."""
    root, secret, language = project
    bad_path("symlink", root, secret, language)
    test_link = root / ("tests/test_link.py" if language == "python" else "tests/link.spec.ts")
    test_link.parent.mkdir(exist_ok=True)
    test_link.symlink_to(secret)
    facts = extract.build(config.load(root))
    module = "pkg.link" if language == "python" else "acme.web.link"
    record = facts["components"][module]
    assert record["completeness"] == {
        "parsed": False,
        "line": 0,
        "reason": OUTSIDE_REASON,
        "cause": "read",
        "unresolved_imports": None,
    }
    assert MARKER not in facts_file.dumps(facts)


# ---- acceptance 3 -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("rel", "problem"),
    [
        ("", "the path is empty"),
        ("/etc/hosts", "the path is not relative to the repository"),
        ("C:\\Windows\\win.ini", "the path is not relative to the repository"),
        ("C:secret.txt", "the path is not relative to the repository"),
        ("\\\\host\\share\\secret.txt", "the path is not relative to the repository"),
        ("../outside/secret.txt", "the path contains a .. part"),
        ("pkg/../../outside/secret.txt", "the path contains a .. part"),
        ("pkg\\..\\..\\secret.txt", "the path contains a .. part"),
        ("pkg/link.txt", "the file is not in the repository"),
        ("pkg/folder", "the path is not a regular file"),
    ],
)
def test_repo_files_refuses_each_unsafe_path(tmp_path: Path, rel: str, problem: str) -> None:
    """Acceptance 3: each refusal is a RepoPathError with a specific text."""
    root, outside = tmp_path / "repo", tmp_path / "outside"
    (root / "pkg/folder").mkdir(parents=True)
    outside.mkdir()
    (outside / "secret.txt").write_text(MARKER, encoding="utf-8")
    (root / "pkg/link.txt").symlink_to(outside / "secret.txt")
    for read in (repo_files.read_text, repo_files.read_bytes):
        with pytest.raises(repo_files.RepoPathError) as caught:
            read(root, rel)
        assert str(caught.value) == problem
        assert isinstance(caught.value, OSError)


def test_repo_files_reads_a_normal_file_as_path_read_text(tmp_path: Path) -> None:
    """Acceptance 3: a file, and a link to a file in the root, give the same text."""
    (tmp_path / "pkg").mkdir()
    path = tmp_path / "pkg/a.py"
    path.write_bytes(b"\xef\xbb\xbfone\r\ntwo\rthree\n")
    (tmp_path / "pkg/b.py").symlink_to(path)
    for rel in ("pkg/a.py", "pkg/b.py", "./pkg/a.py"):
        assert repo_files.read_text(tmp_path, rel, encoding="utf-8-sig") == path.read_text(
            encoding="utf-8-sig"
        )
        assert repo_files.read_bytes(tmp_path, rel) == path.read_bytes()
    with pytest.raises(FileNotFoundError):
        repo_files.read_text(tmp_path, "pkg/missing.py")


# ---- acceptance 4 -----------------------------------------------------------------


def test_a_nested_map_outside_the_repository_is_refused(tmp_path: Path) -> None:
    """Acceptance 4: the command does not read a model file that is not in the repository."""
    root, outside = tmp_path / "repo", tmp_path / "outside"
    write_tree(root, {**STARTER_MODULES, "pkg/__init__.py": ""})
    init_two_cards(root, "--no-ci")
    outside.mkdir()
    shutil.copy(root / "map/model.py", outside / "model.py")
    model = root / "map/model.py"
    text = model.read_text(encoding="utf-8")
    model.write_text(
        text.replace('entry="write",', 'entry="write", map="../../outside/model.py",'),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="not in the repository"):
        nest.load(config.load(root))
    model.write_text(text, encoding="utf-8")
    nest.load(config.load(root))
    (root / "systemap.toml").write_text(
        (root / "systemap.toml")
        .read_text(encoding="utf-8")
        .replace('model = "map/model.py"', 'model = "../outside/model.py"'),
        encoding="utf-8",
    )
    assert config.load(root).model == "../outside/model.py"
    with pytest.raises(ConfigError, match="not in the repository"):
        nest.load(config.load(root))
