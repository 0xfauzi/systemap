"`systemap suggest`: a first grouping from the facts alone, to revise.\n\nNothing said how many components a map should have; the skill now states\na target, and this command prints a starting point from the package\nstructure and the import graph, source review.\n"

from __future__ import annotations

from pathlib import Path
from typing import Any

import fixture_workspace
import pytest
from conftest import init_two_cards, write_tree

from systemap import skill, suggest
from systemap.cli import main


def run(*argv: str) -> int:
    return main(list(argv))


def test_camel_ids() -> None:
    assert suggest.camel("wharf_server.render.emit") == "RenderEmit"
    assert suggest.camel("wharf_server") == "WharfServer"
    assert suggest.camel("pkg.my-thing.x") == "MyThingX"


def test_proposals_on_the_workspace_fixture() -> None:
    facts = fixture_workspace.facts()
    groups, alone = suggest.proposals(facts)
    ids = [p.id for p in groups]
    assert ids == [
        "WharfContracts",
        "WharfServer",
        "Artifacts",
        "Config",
        "Content",
        "Gateway",
        "Layout",
        "Lineage",
        "Measure",
        "Orchestration",
        "Prompts",
        "Render",
        "RenderEmit",
        "Sandbox",
        "Style",
    ]
    by_id = {p.id: p for p in groups}
    assert by_id["RenderEmit"].package == "wharf_server.render.emit"
    assert len(by_id["RenderEmit"].modules) == 23
    assert by_id["WharfServer"].modules == (
        "wharf_server.edit",
        "wharf_server.hashing",
        "wharf_server.mirror",
        "wharf_server.quality",
    )
    assert alone == [
        "wharf_server.component_generator.library",
        "wharf_server.orchestration.agents.wharf.agent",
    ]
    # Every non-marker module is in exactly one proposal or alone.
    placed = [m for p in groups for m in p.modules] + alone
    assert len(placed) == len(set(placed)) == 144 - 18
    lines = suggest.lines(facts)
    assert lines[0] == "suggest: These groups must have a source review."
    assert "source review" in lines[0] and "three to ten modules" in lines[1]
    assert "N/10 to N/3" in lines[1]
    assert lines[2] == (
        "proposals: 15, from 144 modules (2 modules are alone in their package, 18 empty package markers are omitted)"
    )
    assert "    more than 10 modules: Divide the group by task." in lines
    assert lines.index("    more than 10 modules: Divide the group by task.") == (
        lines.index(next(line for line in lines if line.startswith("  WharfContracts"))) + 1
    )
    assert "crossing imports between proposals: 0 pairs" in lines


def test_two_packages_that_shorten_to_one_id_keep_their_path() -> None:
    facts = {
        "components": {
            "a.gateway": {
                "file": "a/gateway/__init__.py",
                "package": "a",
                "names": [{"name": "x", "kind": "object"}],
            },
            "a.gateway.app": {"file": "a/gateway/app.py", "package": "a.gateway"},
            "b.gateway": {
                "file": "b/gateway/__init__.py",
                "package": "b",
                "names": [{"name": "y", "kind": "object"}],
            },
            "b.gateway.app": {"file": "b/gateway/app.py", "package": "b.gateway"},
        }
    }
    groups, alone = suggest.proposals(facts)
    assert [p.id for p in groups] == ["AGateway", "BGateway"] and alone == []


def test_suggest_command_lists_crossings_between_proposals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
            "pkg/store/__init__.py": "",
            "pkg/store/ledger.py": "from pkg.reader import read\n\n\nclass Ledger:\n    pass\n",
            "pkg/store/rows.py": "from pkg.store.ledger import Ledger\n\n\ndef rows() -> None:\n    pass\n",
            "pkg/lone/__init__.py": "",
            "pkg/lone/only.py": "def only() -> None:\n    pass\n",
        },
    )
    init_two_cards(tmp_path, "--no-ci")
    capsys.readouterr()
    assert run("--root", str(tmp_path), "suggest") == 1
    assert (
        capsys.readouterr().out
        == "No facts are available at docs/map/map.json\nrun: systemap extract\n"
    )
    assert run("--root", str(tmp_path), "extract") == 0
    capsys.readouterr()
    assert run("--root", str(tmp_path), "suggest") == 0
    out = capsys.readouterr().out
    assert out.startswith("suggest: These groups must have a source review.\n")
    assert (
        "proposals: 2, from 8 modules (1 modules are alone in their package, 3 empty package markers are omitted)\n  Pkg (pkg): 2 modules: pkg.reader, pkg.writer\n  Store (pkg.store): 2 modules: pkg.store.ledger, pkg.store.rows\nThese modules are alone in their package. Put them in a related component: pkg.lone.only\ncrossing imports between proposals: 1 pairs\n  Store -> Pkg: 1 (pkg.store.ledger -> pkg.reader)\n"
    ) in out


def test_the_skill_states_the_target_and_runs_suggest_and_the_check_together() -> None:
    text = skill.text()
    assert "A component is a system part with one clear function" in text
    assert (
        "`systemap suggest`" in text and "Examine the proposed assignments against source." in text
    )
    assert "| `systemap suggest` |" in text
    # The check step runs the check and the strict judgement together, and says why.
    step = text[text.index("3. **check**") : text.index("4. **judgement**")]
    assert "`systemap check && systemap judgement --strict`" in step
    assert "If you remove a flow, crossing-import findings can open again" in step
    second = skill.files()["references/second-pass.md"]
    assert "`systemap check && systemap judgement --strict`" in second
    for form in (
        '{ crossing_into = "',
        '{ crossing_from = "',
        '{ crossing = ["Page", "Figures", "Describe"]',
    ):
        assert form in second, form


def _package_facts(packages: list[str]) -> dict[str, Any]:
    """Two modules in each package, and one import from each package to the next."""
    components: dict[str, Any] = {}
    for n, pkg in enumerate(packages):
        after = packages[(n + 1) % len(packages)]
        components[f"{pkg}.one"] = {"package": pkg, "uses": {f"{after}.one": ["x"]}}
        components[f"{pkg}.two"] = {"package": pkg}
    return {"components": components}


def test_no_two_proposals_get_one_id() -> None:
    """change-16: the acceptance value is 0 repeated proposal IDs and 3 crossings.

    `a.foo_bar` and `b.foo_bar` get their whole paths, `AFooBar` and `BFooBar`.
    The short name of `c.a_foo_bar` is also `AFooBar`. Each import between two
    packages must stay a crossing between two different IDs."""
    facts = _package_facts(["a.foo_bar", "b.foo_bar", "c.a_foo_bar"])
    groups, _alone = suggest.proposals(facts)
    ids = [p.id for p in groups]
    assert len(set(ids)) == len(ids) == 3, ids
    assert len(suggest.crossings(facts, groups)) == 3, "each import crosses two proposals"


@pytest.mark.parametrize(
    "packages",
    [
        ["a.foo_bar", "b.foo_bar", "c.a_foo_bar"],
        ["a_b.c", "a.b_c", "x.a_b_c"],
        ["p.x", "q.x", "r.p_x", "s.p_x1", "t.p_x2"],
        ["p.a.b", "q.a_b", "r.a.b", "a_b"],
    ],
)
def test_two_different_packages_cannot_get_one_id(packages: list[str]) -> None:
    """change-16: the acceptance value is one different ID for each package.

    The IDs must not change when the packages come in a different order."""
    ids = suggest.proposal_ids(packages)
    assert sorted(ids) == sorted(packages)
    assert len(set(ids.values())) == len(packages), ids
    assert suggest.proposal_ids(list(reversed(packages))) == ids
