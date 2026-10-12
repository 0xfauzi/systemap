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


def test_delta_asks_jev_only_when_jev_is_selected(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = load_config(project)
    assert cfg.jev_enabled is None
    assert not jev_cli.uses_jev(cfg, None)
    monkeypatch.setenv(jev.KEY_ENV, "a key")
    # A key alone does not select Jev.
    assert not jev_cli.uses_jev(cfg, None)
    assert not jev_cli.uses_jev(cfg, False)
    assert jev_cli.uses_jev(cfg, True)
    toml = project / "systemap.toml"
    before = toml.read_text(encoding="utf-8")
    toml.write_text(before + "\n[jev]\nenabled = true\n", encoding="utf-8")
    assert jev_cli.uses_jev(load_config(project), None)
    assert not jev_cli.uses_jev(load_config(project), False)
    monkeypatch.delenv(jev.KEY_ENV)
    assert not jev_cli.uses_jev(load_config(project), None)
    toml.write_text(before, encoding="utf-8")
    disable(project)
    assert not jev_cli.uses_jev(load_config(project), None)
    # an explicit --jev still asks, and says so when it cannot
    assert jev_cli.uses_jev(load_config(project), True)


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
