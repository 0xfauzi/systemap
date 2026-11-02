"""When delta sends questions to Jev, and the hints that tell what Jev can add.

delta sends questions to Jev only with --jev, or with `[jev] enabled = true` and a
key. A key alone sends nothing. judgement and delta print hints on stderr.
`[jev] enabled = false` stops the hints. check and judgement never send a question.
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
    toml.write_text(
        toml.read_text(encoding="utf-8") + "\n[jev]\nenabled = false\n", encoding="utf-8"
    )


def test_delta_asks_jev_only_when_the_command_line_selects_it(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only --decide selects the provider. A key or `[jev] enabled = true` does not."""
    cfg = load_config(project)
    assert cfg.jev_enabled is None
    assert not jev_cli.uses_jev(None)
    monkeypatch.setenv(jev.KEY_ENV, "a key")
    assert not jev_cli.uses_jev(None)
    assert not jev_cli.uses_jev(False)
    assert jev_cli.uses_jev(True)
    toml = project / "systemap.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + "\n[jev]\nenabled = true\n", "utf-8")
    assert load_config(project).jev_enabled is True
    assert not jev_cli.uses_jev(None)


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
