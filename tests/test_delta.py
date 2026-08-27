"""`systemap delta`: what a change did to the map, from the facts at two commits.

A synthetic repository with two commits exercises every line kind at
once: a module moved with the same content and one with the same public
names, modules added (claimed through a pattern, an empty marker, ignored,
and claimed by nobody), modules removed (named outright, named by a stale
ignore, claimed through a pattern), an entry and an interface name that
vanished, a new crossing import with no flow beside one the configuration
answers, and a flow whose import went away.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import delta
from systemap.cli import main

BASE_TREE = {
    "pkg/__init__.py": "",
    "pkg/reader.py": """
        from __future__ import annotations


        class Request:
            body: str = ""

            def send(self, body: str) -> None:
                self.body = body


        def read(source: str) -> Request:
            return Request()
    """,
    "pkg/parser.py": """
        from __future__ import annotations

        from pkg.reader import Request


        def parse(request: Request) -> list[str]:
            return [request.body]
    """,
    "pkg/writer.py": """
        from __future__ import annotations

        from pkg.ledger import Ledger


        def write(parts: list[str], ledger: Ledger) -> str:
            ledger.record(parts)
            return "".join(parts)
    """,
    "pkg/ledger.py": """
        from __future__ import annotations


        class Ledger:
            def record(self, parts: list[str]) -> None:
                pass
    """,
    "pkg/old_tool.py": "def tool() -> None:\n    return None\n",
    "pkg/helper.py": "def help_me() -> int:\n    return 1\n",
    "pkg/spare.py": "def spare() -> int:\n    return 0\n",
    "pkg/util.py": "UPPER = 1\n",
    "pkg/more/__init__.py": "",
    "pkg/more/gone.py": "def gone() -> None:\n    return None\n",
}

HEAD_EDITS = {
    # The interface name Reader points at is gone: send became post.
    "pkg/reader.py": """
        from __future__ import annotations


        class Request:
            body: str = ""

            def post(self, body: str) -> None:
                self.body = body


        def read(source: str) -> Request:
            return Request()
    """,
    # Parser's entry is gone, and so is the import that backed Reader -> Parser.
    "pkg/parser.py": """
        from __future__ import annotations


        def parse_all(parts: list[str]) -> list[str]:
            return parts
    """,
    # A new import across a boundary with no flow: Writer reaches Reader.
    "pkg/writer.py": """
        from __future__ import annotations

        from pkg.ledger import Ledger
        from pkg.reader import read


        def write(parts: list[str], ledger: Ledger) -> str:
            ledger.record(parts)
            read("")
            return "".join(parts)
    """,
    # A new crossing import the configuration answers: Ledger -> Parser.
    "pkg/ledger.py": """
        from __future__ import annotations

        from pkg.parser import parse_all


        class Ledger:
            def record(self, parts: list[str]) -> None:
                parse_all(parts)
    """,
    "pkg/tools/__init__.py": "",
    "pkg/tools/tool.py": "def tool() -> None:\n    return None\n",
    "pkg/helpers/__init__.py": "",
    "pkg/helpers/help.py": "def help_me() -> int:\n    return 2\n",
    "pkg/more/x.py": "def x() -> None:\n    return None\n",
    "pkg/fresh.py": "def fresh() -> None:\n    return None\n",
    "pkg/vendor/__init__.py": "",
    "pkg/vendor/lib.py": "def lib() -> None:\n    return None\n",
    "docs/map/figures/system.svg": "<svg xmlns='http://www.w3.org/2000/svg'></svg>\n",
}

HEAD_REMOVED = (
    "pkg/old_tool.py",
    "pkg/helper.py",
    "pkg/spare.py",
    "pkg/util.py",
    "pkg/more/gone.py",
)

CONFIG = """
[package_roots]
"pkg" = "pkg"

[coverage]
ignore = [
    { module = "pkg.vendor.*", reason = "vendored" },
    { module = "pkg.util", reason = "a helper" },
]

[judgement]
answered = [{ crossing = ["Ledger", "Parser"], reason = "a type import" }]

[[figures]]
out = "figures/system.svg"
mode = "system"
interactive = false
"""

MODEL = """
from systemap import Component, Container, Flow, Meaning, Model, Region

CONTAINERS = (Container(id="system", label="SYSTEM", box=(16, 16, 700, 400)),)
REGIONS = (Region(id="core", label="CORE", box=(40, 60, 640, 320), container="system"),)
COMPONENTS = (
    Component(id="Reader", does="Reads.", interface="Request.send(body) -> None",
              implemented_by=("pkg.reader",), entry="read", region="core", x=60, y=90),
    Component(id="Parser", does="Parses.", implemented_by=("pkg.parser",), entry="parse",
              region="core", x=250, y=90),
    Component(id="Writer", does="Writes.", implemented_by=("pkg.writer", "pkg.old_tool", "pkg.more.*"),
              entry="write", region="core", x=440, y=90),
    Component(id="Ledger", does="Keeps.", implemented_by=("pkg.ledger",), entry="Ledger",
              kind="store", region="core", x=60, y=200),
    Component(id="Spare", does="Spare.", implemented_by=("pkg.spare",), entry="spare",
              region="core", x=250, y=200),
    Component(id="Idle", does="Idle.", implemented_by=("pkg.nothing.*",), region="core",
              kind="store", x=440, y=200),
)
FLOWS = (
    Flow("Reader", "Parser", "request", "data"),
    Flow("Writer", "Ledger", "parts", "data"),
)
MODEL = Model(canvas=(740, 440), containers=CONTAINERS, regions=REGIONS,
              components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={c.id: c.id.lower() for c in COMPONENTS},
    relations={("Reader", "Parser"): "The request goes to the parser.",
               ("Writer", "Ledger"): "The parts are recorded."},
)
"""


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Two commits: the base tree, then every edit above; the model and the
    configuration are the working copy's."""
    write_tree(tmp_path, {**BASE_TREE, "systemap.toml": CONFIG, "map/model.py": MODEL})
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    for rel in HEAD_REMOVED:
        (tmp_path / rel).unlink()
    write_tree(tmp_path, HEAD_EDITS)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "head")
    return tmp_path


def test_every_line_kind_with_its_fix(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = git(repo, "rev-parse", "HEAD~1")[:7]
    assert main(["--root", str(repo), "delta", "--base", "HEAD~1"]) == 1
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == (
        f"delta: HEAD~1 ({base}) -> HEAD ({git(repo, 'rev-parse', 'HEAD')[:7]}): "
        "4 modules changed, 6 added, 3 removed, 2 moved; 4 of 6 cards named"
    )
    expected_open = [
        "moved: pkg.old_tool -> pkg.tools.tool (same content); Writer names pkg.old_tool in "
        "implemented_by: rename it to pkg.tools.tool in map/model.py",
        "moved: pkg.helper -> pkg.helpers.help (same public names); no card claims "
        "pkg.helpers.help: name it in a card's implemented_by in map/model.py",
        "added: pkg.fresh, claimed by no card; name it in a card's implemented_by in "
        "map/model.py, or ignore it with a reason under [coverage]",
        "removed: pkg.spare; Spare names it in implemented_by: drop it in map/model.py",
        "removed: pkg.util; the [coverage] ignore that names it is stale: remove it",
        f"interface vanished: Reader's interface starts with Request.send, which its modules "
        f"defined at {base} and no longer do; start it with a public name they define in "
        "map/model.py, or leave it empty",
        f"entry vanished: Parser names entry parse, which its modules defined at {base} and "
        "no longer do; set entry to a public name they define in map/model.py",
        "new crossing import: pkg.writer (card Writer) imports pkg.reader (card Reader) and "
        "no flow joins Writer and Reader; add the flow with its sentence in map/model.py, or "
        "answer it under [judgement] answered",
        f"evidence lost: Reader -> Parser (request) was observed at {base} and no import joins "
        "them now; find the evidence, name the mechanism in the sentence, or remove the flow "
        "in map/model.py",
    ]
    expected_quiet = [
        "added: pkg.helpers, an empty package marker",
        "added: pkg.more.x, claimed by Writer",
        "added: pkg.tools, an empty package marker",
        "added: pkg.vendor, an empty package marker",
        "added: pkg.vendor.lib, ignored under [coverage]",
        "removed: pkg.more.gone, was claimed by Writer through a pattern",
    ]
    start = lines.index(f"needs a person ({len(expected_open)}):")
    assert lines[start + 1 : start + 1 + len(expected_open)] == [f"  {t}" for t in expected_open]
    start = lines.index(f"changed, nothing to do ({len(expected_quiet)}):")
    assert lines[start + 1 : start + 1 + len(expected_quiet)] == [f"  {t}" for t in expected_quiet]
    # The answered crossing import (Ledger -> Parser) is not asked again.
    assert "pkg.ledger" not in out
    # Spare is told to drop its module, not also that its entry vanished.
    assert "entry vanished: Spare" not in out
    assert delta.FULL_LOOP in lines
    assert lines[-1] == (
        "act on each line above, then run: systemap refresh && systemap check && "
        "systemap judgement --strict"
    )


def test_markdown_is_the_comment_with_the_committed_figure(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(repo, "remote", "add", "origin", "https://github.com/acme/demo.git")
    head = git(repo, "rev-parse", "HEAD")
    assert main(["--root", str(repo), "delta", "--base", "HEAD~1", "--format", "markdown"]) == 1
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == delta.MARKER
    assert lines[1] == "## What this change does to the map"
    assert "**Needs a person (9)**" in lines
    assert "**Changed, nothing to do (6)**" in lines
    assert "- `added: pkg.fresh, claimed by no card; " in out
    assert f"> {delta.FULL_LOOP[0].upper()}{delta.FULL_LOOP[1:]}." in lines
    url = f"https://github.com/acme/demo/blob/{head}/docs/map/figures/system.svg?raw=true"
    assert f"![the map at {head[:7]}]({url})" in lines
    assert "systemap figure --mode change --base" in out
    assert out.endswith("`systemap refresh && systemap check && systemap judgement --strict`.\n")
    # Without a remote there is no URL to give, and the comment says so.
    git(repo, "remote", "remove", "origin")
    assert main(["--root", str(repo), "delta", "--base", "HEAD~1", "--format", "markdown"]) == 1
    out = capsys.readouterr().out
    assert "![" not in out
    assert f"No committed figure to show at `{head[:7]}`" in out


def test_nothing_to_do_and_no_change_exit_zero(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A third commit that edits a body: the facts change, the map does not.
    (repo / "pkg/writer.py").write_text(
        (repo / "pkg/writer.py").read_text().replace('read("")', 'read("x")')
    )
    git(repo, "commit", "-q", "-am", "body")
    assert main(["--root", str(repo), "delta", "--base", "HEAD~1"]) == 0
    out = capsys.readouterr().out
    assert "1 modules changed, 0 added, 0 removed, 0 moved; 0 of 6 cards named" in out
    assert out.rstrip().endswith("nothing needs a person; run: systemap refresh")
    assert main(["--root", str(repo), "delta", "--base", "HEAD"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("delta: no module changed between HEAD (")
    assert "the map is unaffected" in out
    assert main(["--root", str(repo), "delta", "--base", "HEAD", "--format", "markdown"]) == 0
    assert "No module changed" in capsys.readouterr().out


def test_the_base_is_the_merge_base_and_the_working_copy_is_not_read(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The base branch moves on after the branch point: only the branch's own
    # change is reported, since the comparison starts at the merge base.
    git(repo, "branch", "feature", "HEAD")
    git(repo, "checkout", "-q", "-b", "main-moved", "HEAD~1")
    (repo / "pkg/util.py").write_text("UPPER = 2\n")
    git(repo, "commit", "-q", "-am", "main moved")
    main_moved = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "feature")
    # An uncommitted edit in the working copy is not what delta reads.
    (repo / "pkg/uncommitted.py").write_text("def nope() -> None:\n    return None\n")
    assert main(["--root", str(repo), "delta", "--base", main_moved]) == 1
    out = capsys.readouterr().out
    assert f"delta: {main_moved} ({git(repo, 'rev-parse', 'HEAD~1')[:7]}) ->" in out
    assert "pkg.uncommitted" not in out


def test_unknown_ref_is_refused(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(repo), "delta", "--base", "no-such-ref"]) == 2
    err = capsys.readouterr().err
    assert "unknown ref no-such-ref" in err
    assert "give delta a ref git can resolve" in err


def test_with_claims_renames_modules_and_symbols_and_keeps_patterns() -> None:
    from systemap.model import Component, Model

    model = Model(
        canvas=(10, 10),
        containers=(),
        regions=(),
        components=(
            Component(id="A", does="a", implemented_by=("pkg.old", "pkg.old:name", "pkg.sub.*")),
        ),
        flows=(),
        flow_kinds=(),
    )
    renamed = delta.with_claims(model, {"pkg.old": "pkg.new"})
    assert renamed.components[0].implemented_by == ("pkg.new", "pkg.new:name", "pkg.sub.*")
    assert delta.with_claims(model, {}) == model


def record(file: str, sha: str, *names: str) -> dict[str, object]:
    """One module's facts, as much of them as the matcher reads."""
    return {"file": file, "sha": sha, "names": [{"name": n, "kind": "function"} for n in names]}


def test_the_best_pairing_wins_over_the_first_free_one() -> None:
    # Every migration holds one class of the same name, so each old module
    # is eligible for every new one. Taking the first free candidate walks
    # the whole set one place along and tells each card to claim its
    # neighbour's module; the file names are what say which became which.
    base = {
        f"pkg.migrations.{n:04d}_{word}": record(f"pkg/migrations/{n:04d}_{word}.py", "aa", "Migration")
        for n, word in ((3, "order"), (4, "storage"), (5, "checksum"))
    }
    head = {
        f"pkg.migrations.{n:04d}_{word}": record(f"pkg/migrations/{n:04d}_{word}.py", "bb", "Migration")
        for n, word in ((4, "order"), (5, "storage"), (6, "checksum"))
    }
    moves = delta._moves(base, head, sorted(base), sorted(head))
    assert {old: new for old, (new, _how) in moves.items()} == {
        "pkg.migrations.0003_order": "pkg.migrations.0004_order",
        "pkg.migrations.0004_storage": "pkg.migrations.0005_storage",
        "pkg.migrations.0005_checksum": "pkg.migrations.0006_checksum",
    }


def test_a_module_renamed_and_edited_at_once_is_still_one_move() -> None:
    # Neither the source nor the whole surface survives, so the two
    # stronger questions cannot answer; the file name and the names that
    # did survive can. One name in ten changing leaves 0.82 of the surface,
    # over SURFACE_OVERLAP, and route.py reads 0.78 like routing.py, over
    # NAME_ALIKE.
    kept = tuple(f"name{i}" for i in range(9))
    base = {"pkg.route": record("pkg/route.py", "aa", "route_all", *kept)}
    head = {"pkg.routing": record("pkg/routing.py", "bb", "compute_routes", *kept)}
    moves = delta._moves(base, head, ["pkg.route"], ["pkg.routing"])
    new, how = moves["pkg.route"]
    assert new == "pkg.routing"
    assert "file name" in how


def test_two_empty_modules_with_different_names_are_not_joined() -> None:
    # Identical source is no evidence when there is no source: an empty
    # module is like every other empty module, so the file names must agree.
    base = {"pkg.a.ui": record("pkg/a/ui.py", "e3b0")}
    head = {"pkg.b": record("pkg/b/__init__.py", "e3b0")}
    assert delta._moves(base, head, ["pkg.a.ui"], ["pkg.b"]) == {}
    same = {"pkg.b.thing": record("pkg/b/thing/__init__.py", "e3b0")}
    moves = delta._moves({"pkg.a.thing": record("pkg/a/thing/__init__.py", "e3b0")},
                         same, ["pkg.a.thing"], ["pkg.b.thing"])
    assert moves["pkg.a.thing"][0] == "pkg.b.thing"
