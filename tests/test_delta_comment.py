"""The pull request comment of `systemap delta --format markdown`.

The comment gives the decision first, then the components, flows, sequences, and
invariants that the change added, removed, or changed, then a picture of the changed
flows. The model at the base commit comes from the committed tree. The comparison does
not change the delta lines or the exit code.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import config, delta, delta_model, delta_picture, nest
from systemap.cli import main
from systemap.delta_model import Drawn, Item, MapChange

CONFIG = """
[package_roots]
"pkg" = "pkg"
"""

BASE_SOURCE = {
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read() -> str:\n    return 'text'\n",
    "pkg/writer.py": """
        from pkg.reader import read


        def write() -> str:
            return read()
    """,
    "pkg/store.py": "def keep(text: str) -> None:\n    return None\n",
    "pkg/spare.py": "def spare() -> int:\n    return 0\n",
}

HEAD_SOURCE = {
    # The writer now keeps the text in the store and asks the audit.
    "pkg/writer.py": """
        from pkg.audit import check
        from pkg.reader import read
        from pkg.store import keep


        def write() -> str:
            text = read()
            check(text)
            keep(text)
            return text
    """,
    "pkg/audit.py": "def check(text: str) -> bool:\n    return bool(text)\n",
}

MODEL = """
from systemap import Component, Container, Flow, Invariant, Journey, Meaning, Model, Region, Step

CONTAINERS = (Container(id="system", label="SYSTEM", box=(16, 16, 700, 400)),)
REGIONS = (Region(id="core", label="CORE", box=(40, 60, 640, 320), container="system"),)
COMPONENTS = (
    Component(id="Reader", does="{reader_does}", implemented_by=("pkg.reader",), entry="read",
              region="core", x=60, y=90),
    Component(id="Writer", does="Writes the text.", implemented_by=("pkg.writer",),
              entry="write", region="core", x=250, y=90),
    Component(id="Store", does="Keeps the text.", implemented_by=("pkg.store",), kind="store",
              region="core", x=440, y=90),
    {last_component}
)
FLOWS = (
    Flow("Reader", "Writer", "text", "data"),
    Flow("Writer", "Store", "records", "data"),
    {last_flow}
)
INVARIANTS = (
    Invariant(1, "The writer keeps each text.", ("Writer",)),
    {last_invariant}
)
MODEL = Model(canvas=(740, 440), containers=CONTAINERS, regions=REGIONS,
              components=COMPONENTS, flows=FLOWS, flow_kinds=(), invariants=INVARIANTS)
MEANING = Meaning(
    plain={{c.id: c.id.lower() for c in COMPONENTS}},
    relations={{("Reader", "Writer"): "{relation}",
               ("Writer", "Store"): "The writer keeps the records.",
               {last_relation}}},
    journeys=(
        Journey(id="write-text", label="Write the text", starts="Reader", steps=(
            Step(("Reader",), (), ("Reader", "Writer"), "The reader gives the text."),
            Step(("Writer",), (), ("Writer", "Store"), "The writer keeps the text."),
        )),
    ),
)
"""

BASE_MODEL = MODEL.format(
    reader_does="Reads.",
    last_component=(
        'Component(id="Spare", does="Spare.", implemented_by=("pkg.spare",), entry="spare", '
        'region="core", x=60, y=200),'
    ),
    last_flow='Flow("Spare", "Writer", "extra", "data"),',
    last_invariant='Invariant(2, "The spare gives nothing.", ("Spare",)),',
    relation="The reader gives the text.",
    last_relation='("Spare", "Writer"): "The spare gives more.",',
)

HEAD_MODEL = MODEL.format(
    reader_does="Reads the text.",
    last_component=(
        'Component(id="Audit", does="Examines the text.", implemented_by=("pkg.audit",), '
        'entry="check", region="core", x=60, y=200),'
    ),
    last_flow='Flow("Writer", "Audit", "text | \\"quoted\\"", "control"),',
    last_invariant="",
    relation="The reader gives the text to the writer.",
    last_relation='("Writer", "Audit"): "The writer asks the audit.",',
)


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


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Two commits: the change adds, removes, and changes components and flows."""
    git(tmp_path, "init", "-q")
    commit(
        tmp_path,
        {**BASE_SOURCE, "systemap.toml": CONFIG, "map/model.py": BASE_MODEL},
        "base",
    )
    (tmp_path / "pkg/spare.py").unlink()
    commit(tmp_path, {**HEAD_SOURCE, "map/model.py": HEAD_MODEL}, "head")
    return tmp_path


def comment(root: Path, capsys: pytest.CaptureFixture[str], base: str = "HEAD~1") -> str:
    code = main(["--root", str(root), "delta", "--base", base, "--format", "markdown"])
    text = capsys.readouterr().out
    assert main(["--root", str(root), "delta", "--base", base, "--brief"]) == code
    capsys.readouterr()
    return text


def row(text: str, title: str) -> str:
    return next(line for line in text.splitlines() if line.startswith(f"- **{title}**: "))


def test_the_comment_gives_the_decision_then_the_map_changes_then_the_picture(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = comment(repo, capsys)
    lines = text.splitlines()
    assert lines[:3] == [delta.MARKER, "## What this change does to the map", ""]
    assert lines[3].startswith("**A decision is necessary (2).** Do the action in each line.")
    order = [
        lines[3],
        row(text, "Components"),
        row(text, "Flows"),
        row(text, "Sequences"),
        row(text, "Invariants"),
        "```mermaid",
        "<details><summary>No action is necessary for these changes (2)</summary>",
    ]
    assert [lines.index(line) for line in order] == sorted(lines.index(line) for line in order)
    assert row(text, "Components") == (
        "- **Components**: Added: Audit. Removed: Spare. Changed claims: Reader (does). "
        "Changed source: Writer."
    )
    assert row(text, "Flows") == (
        '- **Flows**: Added: `Writer -> Audit (text | "quoted")`. '
        "Removed: `Spare -> Writer (extra)`. "
        "Changed: `Reader -> Writer (text)` (relation) and "
        "`Writer -> Store (records)` (evidence declared to structural)."
    )
    assert (
        row(text, "Sequences")
        == "- **Sequences**: With a changed step: Write the text (2 of 2 steps)."
    )
    assert row(text, "Invariants") == "- **Invariants**: Removed: 2. For a changed component: 1."
    assert "- 2: The spare gives nothing." in lines
    assert "- 1: The writer keeps each text." in lines
    # The component connections and the full map image are not in the comment.
    assert "Components connected to the change" not in text
    assert "![" not in text


def test_the_comment_keeps_each_delta_line_and_the_exit_code(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = config.load(repo)
    base = delta.facts_at(cfg, delta.resolve(repo, "HEAD~1"))
    head = delta.facts_at(cfg, delta.resolve(repo, "HEAD"))
    d = delta.compute_tree(cfg, nest.load(cfg), base, head, "HEAD~1", "HEAD")
    lines = [line.text for line in d.lines]
    assert "removed: pkg.spare" in lines
    assert "added: pkg.audit, with a claim in Audit" in lines
    assert len(d.open) == 2
    text = comment(repo, capsys)
    for line in lines:
        assert f"- `{line}`" in text, line
    assert main(["--root", str(repo), "delta", "--base", "HEAD~1", "--format", "markdown"]) == 1


def test_the_picture_draws_only_the_changed_flows(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = comment(repo, capsys)
    start = text.index("```mermaid\n")
    picture = text[start : text.index("```\n", start + 3) + 3].splitlines()
    assert picture == [
        "```mermaid",
        "flowchart LR",
        '  n0["Reader (changed claims)"]',
        '  n1["Writer (changed source)"]',
        '  n2["Store"]',
        '  n3["Audit (added)"]',
        '  n4["Spare (removed)"]',
        '  n0 -->|"text (changed)"| n1',
        '  n1 -->|"records (changed)"| n2',
        '  n1 ==>|"text #124; #quot;quoted#quot; (added)"| n3',
        '  n4 -.->|"extra (removed)"| n1',
        "```",
    ]


def test_a_change_to_the_model_only_is_in_the_comment(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    commit(repo, {"map/model.py": HEAD_MODEL.replace("Reads the text.", "Reads text.")}, "words")
    text = comment(repo, capsys)
    assert "No module changed" not in text
    assert "**No decision is necessary.** The map includes this change." in text
    assert row(text, "Components") == "- **Components**: Changed claims: Reader (does)."
    assert row(text, "Flows") == "- **Flows**: No change."
    assert "```mermaid" not in text, "a change without a changed flow has no picture"
    commit(repo, {"README.md": "words\n"}, "no map change")
    text = comment(repo, capsys)
    assert "No module changed between `HEAD~1 (" in text
    assert text.rstrip().endswith("The map has no change.")


def test_a_base_model_that_does_not_load_gives_only_changed_source(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    commit(repo, {"map/model.py": "MODEL = (\n"}, "broken model")
    commit(
        repo,
        {"map/model.py": HEAD_MODEL, "pkg/reader.py": "def read() -> str:\n    return ''\n"},
        "fixed",
    )
    text = comment(repo, capsys)
    short = git(repo, "rev-parse", "--short=7", "HEAD~1")
    assert (
        f"The comparison shows only changed source, because the model at {short} does not "
        "load: map/model.py could not import: SyntaxError:"
    ) in text
    assert row(text, "Components") == "- **Components**: Changed source: Reader."
    assert row(text, "Flows") == "- **Flows**: No change."


def test_a_model_path_that_is_not_in_the_base_commit_is_the_reason(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(repo, "rm", "-q", "map/model.py")
    git(repo, "commit", "-q", "-m", "no model")
    commit(
        repo,
        {"map/model.py": HEAD_MODEL, "pkg/reader.py": "def read() -> str:\n    return ''\n"},
        "model again",
    )
    short = git(repo, "rev-parse", "--short=7", "HEAD~1")
    text = comment(repo, capsys)
    assert f"because map/model.py is not in the commit {short}." in text


def test_a_new_digest_for_the_same_source_record_is_not_a_change() -> None:
    from systemap.model import Flow

    old = Flow("A", "B", "x", "data", source_refs=("pkg.a:run@" + "1" * 64,))
    new = Flow("A", "B", "x", "data", source_refs=("pkg.a:run@" + "2" * 64,))
    other = Flow("A", "B", "x", "data", source_refs=("pkg.a:stop@" + "2" * 64,))
    assert delta_model._cited(old) == delta_model._cited(new)
    assert delta_model._cited(old) != delta_model._cited(other)


def test_long_groups_name_ten_items_and_count_the_rest() -> None:
    d = delta.Delta(
        base="a" * 40, head="b" * 40, base_ref="main", head_ref="HEAD",
        changed=1, added=0, removed=0, moved=0, cards=20, lines=(),
    )  # fmt: skip
    change = MapChange(
        components=tuple(Item(delta_model.SOURCE, f"C{n}") for n in range(12)),
        sequences=tuple(Item("", f"S{n}", ("1 of 2 steps",)) for n in range(3)),
        sequence_count=3,
        invariants=tuple(Item("", str(n), (f"Rule {n}.",)) for n in range(1, 3)),
        invariant_count=4,
    )
    text = delta.markdown(d, change)
    assert row(text, "Components") == (
        "- **Components**: Changed source: C0, C1, C2, C3, C4, C5, C6, C7, C8, C9 and 2 more."
    )
    assert row(text, "Sequences") == "- **Sequences**: All 3 sequences have a changed step."
    assert row(text, "Invariants") == "- **Invariants**: For a changed component: 1 and 2."


def test_a_large_change_draws_the_added_and_removed_flows_only() -> None:
    many = [Drawn(f"A{n}", f"B{n}", "x", delta_model.CHANGED) for n in range(31)]
    change = MapChange(drawn=(*many, Drawn("A", "B", "new", delta_model.ADDED)))
    out = delta_picture.mermaid(change)
    assert out[0] == (
        "The picture shows only the added and removed flows, because 32 flows changed."
    )
    assert out[-5:] == ['  n0["A"]', '  n1["B"]', '  n0 ==>|"new (added)"| n1', "```", ""]
    change = MapChange(drawn=tuple(many))
    assert delta_picture.mermaid(change) == [
        "The picture is not shown, because 31 flows changed. A picture shows 30 flows or fewer.",
        "",
    ]
    assert delta_picture.mermaid(MapChange()) == []


def test_a_label_cannot_end_the_picture() -> None:
    change = MapChange(drawn=(Drawn("A", "B", 'a "b" | `c` <d> #e', delta_model.REMOVED),))
    out = delta_picture.mermaid(change)
    assert '  n0 -.->|"a #quot;b#quot; #124; #96;c#96; #lt;d#gt; #35;e (removed)"| n1' in out
    assert sum(line.startswith("```") for line in out) == 2
