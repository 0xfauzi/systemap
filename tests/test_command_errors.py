"""Each command error names the input that the person must correct.

A command option, systemap.toml, the model module, and a tsconfig file are different
inputs. The correction line names the input that gives the error.
"""

from __future__ import annotations

import argparse
import dataclasses
import socket
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import cli, extract, skill
from systemap.cli import main

CONFIG_FIX = "Correct systemap.toml or the model module. Then run the command again."
OPTION_FIX = "Correct the command option. Then run the command again."


def run(*argv: str) -> int:
    return main(list(argv))


@pytest.fixture
def two_cards(tmp_path: Path) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert run("--root", str(tmp_path), "extract") == 0
    return tmp_path


def test_skill_help_gives_the_directory_that_the_command_uses(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        run("skill", "--help")
    out = " ".join(capsys.readouterr().out.split())
    assert f"The default is {skill.DEFAULT_DIR} under the project root." in out
    assert ".agents" not in out


@pytest.mark.parametrize(
    ("option", "message"),
    [
        (("--layer", "nope"), "unknown layer id: nope"),
        (("--components", "Reader,Nope"), "unknown component ids: Nope"),
        (("--map", "Nope"), "unknown map id: Nope"),
    ],
)
def test_an_unknown_option_value_names_the_option(
    two_cards: Path, capsys: pytest.CaptureFixture[str], option: tuple[str, str], message: str
) -> None:
    out = two_cards / "fig.svg"
    assert run("--root", str(two_cards), "figure", *option, "--out", str(out)) == 2
    err = capsys.readouterr().err
    assert message in err
    assert err.rstrip().endswith(OPTION_FIX)
    assert "systemap.toml" not in err
    assert not out.exists()


def test_an_unknown_layer_in_systemap_toml_names_the_configuration(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    toml = two_cards / "systemap.toml"
    text = toml.read_text(encoding="utf-8").replace('layer = "structure"', 'layer = "nope"')
    toml.write_text(text, encoding="utf-8")
    assert run("--root", str(two_cards), "refresh") == 2
    err = capsys.readouterr().err
    assert "unknown layer id: nope" in err
    assert err.rstrip().endswith(CONFIG_FIX)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows lets a server use a port in use")
def test_serve_on_a_port_in_use_gives_the_option_fix(
    two_cards: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run("--root", str(two_cards), "refresh") == 0

    def stop(_server: ThreadingHTTPServer, poll_interval: float = 0.5) -> None:
        raise KeyboardInterrupt

    # If the server starts, it stops at once: the test does not wait for requests.
    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", stop)
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        port = holder.getsockname()[1]
        capsys.readouterr()
        assert run("--root", str(two_cards), "serve", "--port", str(port)) == 2
    finally:
        holder.close()
    captured = capsys.readouterr()
    assert f"The server cannot use port {port}" in captured.err
    assert "--port 0" in captured.err
    assert captured.err.rstrip().endswith(OPTION_FIX)
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_a_tsconfig_error_names_the_tsconfig_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("tree_sitter_typescript")
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "tsconfig.json": "[1, 2]\n",
            "src/index.ts": "export function start(): void {}\n",
        },
    )
    # init keeps the configuration and writes the initial model.
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    capsys.readouterr()
    assert run("--root", str(tmp_path), "extract") == 2
    err = capsys.readouterr().err
    assert "tsconfig.json" in err
    assert err.rstrip().endswith(
        "Correct the tsconfig file in the message. Then run the command again."
    )
    assert "systemap.toml" not in err


def test_refresh_has_a_short_quiet_option_with_help(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        run("refresh", "--help")
    assert "-q, --quiet" in capsys.readouterr().out
    assert run("--root", str(two_cards), "refresh", "-q") == 0
    assert run("--root", str(two_cards), "refresh", "-q") == 0
    assert capsys.readouterr().out == ""


def test_extract_check_gives_a_model_claim_as_a_model_correction(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    model = two_cards / "map/model.py"
    text = model.read_text(encoding="utf-8")
    model.write_text(
        text.replace('implemented_by=("pkg.writer",)', 'implemented_by=("pkg.writer", "pkg.old")'),
        encoding="utf-8",
    )
    capsys.readouterr()
    assert run("--root", str(two_cards), "extract", "--check") == 1
    out = capsys.readouterr().out
    assert out.splitlines() == [
        "map: The model does not agree with the source tree (1 problem):",
        "  Writer has a module claim for pkg.old, which is missing from the facts.",
        "Correct map/model.py. Then use systemap check.",
    ]
    # Stale facts and a model claim give two groups, each with its own correction.
    (two_cards / "pkg/extra.py").write_text("def more() -> None:\n    pass\n", encoding="utf-8")
    assert run("--root", str(two_cards), "extract", "--check") == 1
    out = capsys.readouterr().out
    assert out.startswith("map: The map is stale (")
    assert "run: systemap extract\nmap: The model does not agree" in out
    assert out.rstrip().endswith("Correct map/model.py. Then use systemap check.")


def test_facts_without_modules_give_the_package_roots_correction(two_cards: Path) -> None:
    # The check gives this entry line when the facts have no module and the model
    # has source components. The model is then not the input to correct.
    project = cli._project(argparse.Namespace(root=str(two_cards)))
    results = cli._check_tree(project, extract.read_facts(project.cfg.facts_path))
    assert cli._fix_line(project, results) == "run: systemap refresh"
    top = results[project.tree.top.id]
    results[project.tree.top.id] = dataclasses.replace(
        top,
        coverage=dataclasses.replace(top.coverage, total=0, mapped=0),
        entry=["The facts contain no source modules."],
    )
    assert cli._fix_line(project, results) == (
        "Set [package_roots] in systemap.toml to the directories that contain the source "
        "files. Then use systemap check."
    )
