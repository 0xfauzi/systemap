"""When systemap asks Jev without being told to, and what it says when it cannot.

delta asks Jev on its own when a key is set; judgement and delta say, on
stderr, what Jev would add when none is. `[jev] enabled = false` turns off
both, and check and judgement never ask.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import jev, jev_cli
from systemap.cli import main
from systemap.config import ConfigError
from systemap.config import load as load_config


@pytest.fixture
def project(tmp_path: Path) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return tmp_path


def disable(root: Path) -> None:
    toml = root / "systemap.toml"
    toml.write_text(toml.read_text() + "\n[jev]\nenabled = false\n")


def test_delta_asks_jev_when_a_key_is_set_unless_told_not_to(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = load_config(project)
    assert not jev_cli.uses_jev(cfg, None)
    monkeypatch.setenv(jev.KEY_ENV, "a key")
    assert jev_cli.uses_jev(cfg, None)
    assert not jev_cli.uses_jev(cfg, False)
    disable(project)
    assert not jev_cli.uses_jev(load_config(project), None)
    # an explicit --jev still asks, and says so when it cannot
    assert jev_cli.uses_jev(load_config(project), True)


def test_judgement_says_what_jev_would_add_on_stderr_only(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["--root", str(project), "judgement"])
    out, err = capsys.readouterr()
    assert "systemap audit" in err and "95%" in err
    assert "hint:" not in out


def test_the_hint_is_silent_with_a_key_or_when_jev_is_disabled(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(jev.KEY_ENV, "a key")
    main(["--root", str(project), "judgement"])
    assert "hint:" not in capsys.readouterr().err
    monkeypatch.delenv(jev.KEY_ENV)
    disable(project)
    main(["--root", str(project), "judgement"])
    assert "hint:" not in capsys.readouterr().err


def test_jev_enabled_must_be_a_boolean(project: Path) -> None:
    toml = project / "systemap.toml"
    toml.write_text(toml.read_text() + '\n[jev]\nenabled = "no"\n')
    with pytest.raises(ConfigError, match="jev.enabled must be true or false"):
        load_config(project)
