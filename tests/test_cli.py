from __future__ import annotations

import http.client
import threading
from pathlib import Path
from typing import Any

import pytest
from conftest import TINY_PACKAGE, TWO_CARD_MODEL, init_two_cards, write_tree

from systemap import __version__, cli
from systemap.cli import NO_COMPONENTS, main

STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def test_init_then_refresh_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(tmp_path), "init", "--name", "demo") == 0
    for rel in (
        "systemap.toml",
        "map/model.py",
        "docs/map/.gitkeep",
        ".github/workflows/systemap.yml",
        ".claude/skills/systemap/SKILL.md",
        ".claude/skills/systemap/references/schema.md",
    ):
        assert (tmp_path / rel).is_file(), rel
    assert 'name = "demo"' in (tmp_path / "systemap.toml").read_text()
    out = capsys.readouterr().out
    assert "wrote .claude/skills/systemap/ (SKILL.md and 7 references)" in out
    assert "SKILL.md\n" not in out.replace("(SKILL.md and 7 references)\n", "")
    assert out.rstrip().endswith("Map this repository with systemap. Follow the systemap skill.")

    # The starter model is empty: the check has one line to say, and says only that.
    assert run("--root", str(tmp_path), "check") == 1
    assert capsys.readouterr().out == NO_COMPONENTS + "\n"
    assert run("--root", str(tmp_path), "refresh") == 1
    assert capsys.readouterr().out == NO_COMPONENTS + "\n"
    assert run("--root", str(tmp_path), "judgement") == 0
    assert capsys.readouterr().out == NO_COMPONENTS + "\n"

    # The agent writes two cards; from here the loop runs.
    (tmp_path / "map/model.py").write_text(TWO_CARD_MODEL)
    # Nothing built yet: extract --check and render are stale, with the fix named.
    assert run("--root", str(tmp_path), "extract", "--check") == 1
    assert "run: systemap extract" in capsys.readouterr().out
    assert run("--root", str(tmp_path), "render") == 1
    assert "run: systemap extract" in capsys.readouterr().out

    assert run("--root", str(tmp_path), "extract") == 0
    assert (tmp_path / "docs/map/map.json").is_file()
    assert run("--root", str(tmp_path), "extract", "--check") == 0
    # Facts but no page yet: every rule is clean except stale, and the fix is refresh.
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "map layout: clean" in out
    assert "docs/map/index.html has not been rendered" in out
    assert "docs/map/figures/structure.svg has not been rendered" in out
    assert "docs/map/figures/system.svg has not been rendered" in out
    assert out.rstrip().endswith("run: systemap refresh")
    assert run("--root", str(tmp_path), "render") == 0
    page = (tmp_path / "docs/map/index.html").read_text()
    assert "<title>demo system map</title>" in page
    assert run("--root", str(tmp_path), "render", "--check") == 0

    # The first refresh draws the configured figures; the second has nothing to do.
    assert run("--root", str(tmp_path), "refresh") == 0
    assert (tmp_path / "docs/map/figures/structure.svg").is_file()
    assert (tmp_path / "docs/map/figures/system.svg").is_file()
    assert "map: updated" in capsys.readouterr().out
    assert run("--root", str(tmp_path), "check") == 0
    assert run("--root", str(tmp_path), "refresh") == 0
    assert "already current" in capsys.readouterr().out
    # Init never overwrites what exists.
    assert run("--root", str(tmp_path), "init") == 0
    assert "kept systemap.toml" in capsys.readouterr().out


def test_init_writes_an_empty_model_and_a_pinned_workflow(tmp_path: Path) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(tmp_path), "init") == 0
    model = (tmp_path / "map/model.py").read_text()
    assert model.startswith("# ruff: noqa: E501\n# The map is prose held in strings")
    assert "F401" not in model, "every import is used, so no pragma to trip RUF100"
    assert "COMPONENTS: tuple[Component, ...] = ()" in model
    assert "FLOWS: tuple[Flow, ...] = ()" in model
    assert "mypackage" not in model
    toml = (tmp_path / "systemap.toml").read_text()
    assert "\nignore = [" not in toml, "the starter carries no ignore"
    assert '[package_roots]\n"pkg" = "pkg"' in toml
    assert 'out = "figures/structure.svg"' in toml and 'layer = "structure"' in toml
    assert 'out = "figures/system.svg"' in toml
    assert "system.html" not in toml
    workflow = (tmp_path / ".github/workflows/systemap.yml").read_text()
    # Nothing is on PyPI yet: the pin is the release tag, and moves to PyPI at 1.0.
    pin = f'uvx --from "git+https://github.com/0xfauzi/systemap@v{__version__}" systemap'
    for command in ("extract --check", "check", "judgement --strict", "render --check"):
        assert f"{pin} {command}" in workflow, command
    assert workflow.index("systemap check") < workflow.index("judgement --strict")
    assert "uv sync" not in workflow and "uv run" not in workflow
    assert "needs no dependency on it" in workflow
    # A workflow linter's three complaints, answered: every action pinned to a
    # commit with the version beside it, least privilege, no persisted token.
    import re

    uses = re.findall(r"uses: (\S+)( # v[\d.]+)?", workflow)
    assert len(uses) == 2 and all(
        re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", u) for u, _v in uses
    ), uses
    assert all(v for _u, v in uses), "the version is beside the pin"
    assert "\npermissions:\n  contents: read\n" in workflow
    assert "persist-credentials: false" in workflow
    assert workflow.index("persist-credentials") < workflow.index("setup-uv")


def test_rendered_files_end_with_a_newline(tmp_path: Path) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert run("--root", str(tmp_path), "refresh") == 0
    for rel in (
        "docs/map/index.html",
        "docs/map/figures/structure.svg",
        "docs/map/figures/system.svg",
    ):
        assert (tmp_path / rel).read_text().endswith("\n"), rel
    out = tmp_path / "fig.html"
    assert run("--root", str(tmp_path), "figure", "--interactive", "--out", str(out)) == 0
    assert out.read_text().endswith("</figure>\n")
    (tmp_path / "docs/map/index.html").write_text(
        model_free := (tmp_path / "docs/map/index.html").read_text().rstrip("\n")
    )
    assert model_free and run("--root", str(tmp_path), "render", "--check") == 1


def test_init_no_ci_skips_the_workflow(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    assert not (tmp_path / ".github").exists()
    assert (tmp_path / "map/model.py").is_file()
    assert (tmp_path / ".claude/skills/systemap/SKILL.md").is_file()
    assert "systemap.yml" not in capsys.readouterr().out


def test_stale_after_code_change(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path)
    assert run("--root", str(tmp_path), "refresh") == 0
    (tmp_path / "pkg/reader.py").write_text("def read(source):\n    return 1\n")
    assert run("--root", str(tmp_path), "extract", "--check") == 1
    out = capsys.readouterr().out
    assert "code changed since the map was built: pkg.reader" in out
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "extract", "--check") == 0


def test_configuration_errors_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", "systemap.toml": 'nam = "typo"\n'})
    assert run("--root", str(tmp_path), "extract") == 2
    err = capsys.readouterr().err
    assert "unknown key: nam" in err
    assert "fix systemap.toml" in err

    write_tree(tmp_path, {"systemap.toml": 'name = "ok"\n'})
    assert run("--root", str(tmp_path), "extract") == 2
    assert "model module not found" in capsys.readouterr().err

    write_tree(tmp_path, {"map/model.py": "MODEL = 1\n"})
    assert run("--root", str(tmp_path), "check") == 2
    assert "map/model.py: MODEL must be a systemap.Model" in capsys.readouterr().err

    # A name the model does not import, or one systemap does not export, is one
    # line with the fix, never a traceback.
    write_tree(
        tmp_path, {"map/model.py": "from systemap import Model\nLAYERS = (Layer('a', 'A'),)\n"}
    )
    assert run("--root", str(tmp_path), "check") == 2
    err = capsys.readouterr().err
    assert (
        "map/model.py failed to import: name 'Layer' is not defined; add the missing name to the import from systemap"
        in err
    )
    assert "Traceback" not in err
    write_tree(tmp_path, {"map/model.py": "from systemap import Model, Layers\n"})
    assert run("--root", str(tmp_path), "check") == 2
    err = capsys.readouterr().err
    assert "map/model.py failed to import: cannot import name 'Layers' from 'systemap'" in err
    assert "add the missing name to the import from systemap" in err
    write_tree(tmp_path, {"map/model.py": "raise ValueError('boom')\n"})
    assert run("--root", str(tmp_path), "check") == 2
    assert "map/model.py failed to import: ValueError: boom" in capsys.readouterr().err

    write_tree(tmp_path, {"pyproject.toml": '[tool.systemap]\ntheme = "dark"\n'})
    (tmp_path / "systemap.toml").unlink()
    assert run("--root", str(tmp_path), "check") == 2
    assert "theme must be a table" in capsys.readouterr().err

    # The issue link template left with the field it served; an old key is refused.
    write_tree(tmp_path, {"pyproject.toml": '[tool.systemap]\nissue_url = "https://x/{n}"\n'})
    assert run("--root", str(tmp_path), "check") == 2
    assert "unknown key: issue_url" in capsys.readouterr().err


def test_check_fails_on_overlapping_fixture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path)
    model = tmp_path / "map/model.py"
    model.write_text(model.read_text().replace('x=COL["c2"]', 'x=COL["c1"]'))
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "placement: Reader overlaps Writer" in out
    assert "fix map/model.py" in out
    assert run("--root", str(tmp_path), "refresh") == 1


def test_figure_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path)
    assert run("--root", str(tmp_path), "extract") == 0
    out = tmp_path / "fig.html"
    assert run("--root", str(tmp_path), "figure", "--static", "--out", str(out)) == 0
    text = out.read_text()
    assert text.startswith('<figure data-generated="systemap"')
    assert "<script>" not in text
    assert (
        run(
            "--root",
            str(tmp_path),
            "figure",
            "--interactive",
            "--components",
            "Reader,Writer",
            "--out",
            str(out),
        )
        == 0
    )
    assert "<script>" in out.read_text()
    # A relative --out lands in the output directory, like a [[figures]] out.
    capsys.readouterr()
    assert run("--root", str(tmp_path), "figure", "--static", "--out", "figures/one.svg") == 0
    assert (tmp_path / "docs/map/figures/one.svg").read_text().startswith("<svg ")
    assert capsys.readouterr().out.startswith("wrote docs/map/figures/one.svg (")
    assert not (Path.cwd() / "figures/one.svg").exists()
    assert run("--root", str(tmp_path), "figure", "--components", "Nope", "--out", str(out)) == 2
    assert "unknown component ids: Nope" in capsys.readouterr().err
    assert run("--root", str(tmp_path), "figure", "--mode", "change", "--out", str(out)) == 1


def test_skill_command_writes_the_skill(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "tmp"
    assert run("--root", str(tmp_path), "skill", "--dir", str(target)) == 0
    written = target / "SKILL.md"
    assert written.is_file()
    out = capsys.readouterr().out
    assert f"wrote {written}" in out
    assert "references/ (7 files)" in out
    text = written.read_text()
    assert text.startswith("---\nname: systemap\n")
    assert "systemap check" in text
    assert "systemap extract" in text
    # The directory comes with it: every reference SKILL.md names.
    for ref in (
        "schema",
        "example",
        "layout",
        "layers",
        "journeys-and-invariants",
        "second-pass",
        "pitfalls",
    ):
        assert (target / "references" / f"{ref}.md").is_file(), ref
    # The default location is under the root, and rerunning refreshes the text.
    assert run("--root", str(tmp_path), "skill") == 0
    default = tmp_path / ".claude/skills/systemap/SKILL.md"
    assert default.read_text() == text
    assert (tmp_path / ".claude/skills/systemap/references/schema.md").is_file()
    default.write_text("edited")
    assert run("--root", str(tmp_path), "skill") == 0
    assert default.read_text() == text
    # --print writes the same text to stdout and touches nothing.
    default.write_text("edited")
    capsys.readouterr()
    assert run("--root", str(tmp_path), "skill", "--print") == 0
    assert capsys.readouterr().out == text
    assert default.read_text() == "edited"


def test_extract_on_tiny_package_via_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    assert run("--root", str(tmp_path), "init") == 0
    assert run("--root", str(tmp_path), "extract") == 0
    out = capsys.readouterr().out
    # The numbers are labelled for what they are: the map carries no counts.
    assert (
        "facts for the change detector (these never appear on the map):\n  modules:          3\n"
        in out
    )
    assert "written to docs/map/map.json" in out


def test_serve_serves_the_output_directory(tmp_path: Path) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert run("--root", str(tmp_path), "refresh") == 0
    httpd = cli.make_server(tmp_path / "docs/map", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        port = httpd.server_address[1]
        for path in ("/", "/index.html", "/figures/structure.svg"):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", path)
            response = conn.getresponse()
            body = response.read().decode("utf-8")
            conn.close()
            assert response.status == 200, path
            assert (
                ("<title>" in body) if path != "/figures/structure.svg" else body.startswith("<svg")
            )
        # Nothing outside the output directory is served.
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/../map/model.py")
        assert conn.getresponse().status in (301, 404)
        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_serve_command_prints_the_url_and_stops_on_interrupt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    # No page yet: the command says what to run instead of serving nothing.
    assert run("--root", str(tmp_path), "serve") == 1
    assert "run: systemap refresh" in capsys.readouterr().out
    assert run("--root", str(tmp_path), "refresh") == 0
    made: dict[str, Any] = {}

    class Fake:
        server_address = ("127.0.0.1", 8765)

        def serve_forever(self) -> None:
            made["served"] = True
            raise KeyboardInterrupt

        def server_close(self) -> None:
            made["closed"] = True

    def fake_server(directory: Path, port: int) -> Fake:
        made["directory"], made["port"] = directory, port
        return Fake()

    monkeypatch.setattr(cli, "make_server", fake_server)
    capsys.readouterr()
    assert run("--root", str(tmp_path), "serve") == 0
    assert (
        capsys.readouterr().out == "serving docs/map at http://127.0.0.1:8765/ (Ctrl-C to stop)\n"
    )
    assert made == {
        "directory": tmp_path / "docs/map",
        "port": 8765,
        "served": True,
        "closed": True,
    }
    assert run("serve", "--root", str(tmp_path), "--port", "9000") == 0
    assert made["port"] == 9000
