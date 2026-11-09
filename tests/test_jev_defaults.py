"""When delta sends questions to Jev, and the hints that tell what Jev can add.

delta sends questions to Jev only with --decide. A key
or `[jev] enabled = true` sends nothing. judgement and delta print hints on stderr.
`[jev] enabled = false` stops the hints. check and judgement never send a question.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import jev, providers
from systemap.cli import main
from systemap.config import ConfigError
from systemap.config import load as load_config
from systemap.decision import DecisionError


@pytest.fixture
def project(tmp_path: Path) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return tmp_path


def disable(root: Path) -> None:
    toml = root / "systemap.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8") + "\n[jev]\nenabled = false\n", encoding="utf-8"
    )


def test_the_provider_gate_needs_an_option_on_the_command_line(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A key and `[jev] enabled = true` do not permit a request. Only `permitted` does."""
    monkeypatch.setenv(jev.KEY_ENV, "a key")
    toml = project / "systemap.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + "\n[jev]\nenabled = true\n", "utf-8")
    cfg = load_config(project)
    assert cfg.jev_enabled is True
    with pytest.raises(DecisionError, match="no data was sent"):
        providers.select(cfg, permitted=False)
    assert providers.select(cfg, permitted=True).name == "jev"


def test_judgement_says_what_jev_would_add_on_stderr_only(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["--root", str(project), "judgement"])
    out, err = capsys.readouterr()
    assert "systemap audit" in err and "TYPESAFE_API_KEY" in err
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
    toml.write_text(
        toml.read_text(encoding="utf-8") + '\n[jev]\nenabled = "no"\n', encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="jev.enabled must be true or false"):
        load_config(project)
