"""The writing profile: the language rules for the map text that a person reads.

`[writing] profile` selects "plain" (the default) or "asd-ste100". The
configuration reader validates the table, `systemap init` writes it with a
comment for each value, and the coding-agent request carries the policy of
the selected profile. The source-language key `language` stays a string, so
the profile is in its own table: a TOML file cannot have `language = "..."`
and a `[language]` table.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import agent, config, scaffold
from systemap.cli import main
from systemap.config import ConfigError

ROOT = Path(__file__).resolve().parent.parent
STARTER = {"pkg/__init__.py": "", "pkg/reader.py": "def read() -> None:\n    return None\n"}


def configured(tmp_path: Path, text: str) -> config.Config:
    (tmp_path / "systemap.toml").write_text(text, encoding="utf-8")
    return config.load(tmp_path)


def test_without_the_table_the_profile_is_plain(tmp_path: Path) -> None:
    assert configured(tmp_path, 'name = "x"\n').writing_profile == "plain"
    assert configured(tmp_path, 'name = "x"\n[writing]\n').writing_profile == "plain"


@pytest.mark.parametrize("profile", ["plain", "asd-ste100"])
def test_each_profile_is_accepted(tmp_path: Path, profile: str) -> None:
    text = f'name = "x"\n[writing]\nprofile = "{profile}"\n'
    assert configured(tmp_path, text).writing_profile == profile


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ('[writing]\nprofile = "ste"\n', 'writing.profile must be "plain" or "asd-ste100"'),
        ('[writing]\nprofile = "ASD-STE100"\n', 'writing.profile must be "plain" or "asd-ste100"'),
        ("[writing]\nprofile = 1\n", 'writing.profile must be "plain" or "asd-ste100"'),
        ('[writing]\nprofil = "plain"\n', "writing has an unknown key: profil"),
        ('writing = "plain"\n', "writing must be a table"),
    ],
)
def test_a_wrong_writing_table_is_a_configuration_error(
    tmp_path: Path, text: str, error: str
) -> None:
    with pytest.raises(ConfigError, match=error):
        configured(tmp_path, text)


def test_a_wrong_profile_stops_a_command_with_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {**STARTER, "systemap.toml": '[writing]\nprofile = "strict"\n'})
    assert main(["--root", str(tmp_path), "extract"]) == 2
    err = capsys.readouterr().err
    assert 'systemap.toml: writing.profile must be "plain" or "asd-ste100"' in err
    assert "Traceback" not in err


def test_the_profile_is_read_from_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.systemap]\nname = "x"\n[tool.systemap.writing]\nprofile = "asd-ste100"\n',
        encoding="utf-8",
    )
    assert config.load(tmp_path).writing_profile == "asd-ste100"


def test_a_typescript_configuration_can_set_the_profile(tmp_path: Path) -> None:
    text = 'language = "typescript"\n[package_roots]\n"src" = "web"\n[writing]\nprofile = "plain"\n'
    (tmp_path / "src").mkdir()
    cfg = configured(tmp_path, text)
    assert (cfg.language, cfg.writing_profile) == ("typescript", "plain")


def test_this_repository_uses_the_asd_ste100_profile() -> None:
    assert config.load(ROOT).writing_profile == "asd-ste100"


# ---- the init template ------------------------------------------------------------


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_the_template_writes_the_plain_profile_with_both_values_explained(language: str) -> None:
    text = scaffold.files("demo", "pkg", [("pkg", "pkg")], ci=False, language=language)[
        "systemap.toml"
    ]
    assert tomllib.loads(text)["writing"] == {"profile": "plain"}
    head = text[: text.index("[writing]")]
    comment = head[head.rindex("\n\n") :]
    assert '"plain"' in comment and '"asd-ste100"' in comment
    assert "dictionary" in comment


def test_init_writes_a_configuration_that_gives_the_plain_profile(tmp_path: Path) -> None:
    write_tree(tmp_path, STARTER)
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    assert config.load(tmp_path).writing_profile == "plain"
    toml = tmp_path / "systemap.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace('profile = "plain"', 'profile = "asd-ste100"'),
        encoding="utf-8",
    )
    assert config.load(tmp_path).writing_profile == "asd-ste100"


def test_the_template_model_names_the_profile_not_one_standard() -> None:
    model = scaffold.files("demo", "pkg", [("pkg", "pkg")], ci=False)["map/model.py"]
    assert "ASD-STE100 Issue 9" not in model
    assert "[writing] profile" in model


# ---- the coding-agent request -----------------------------------------------------


def recorder() -> tuple[agent.Run, list[str]]:
    asked: list[str] = []

    def run(command: str, question: str, cwd: Path, timeout: float) -> str:
        asked.append(question)
        return "The reader gives records to the store."

    return run, asked


def asked_with(tmp_path: Path, profile: str) -> str:
    text = f'name = "x"\n[agent]\ncommand = "agent -p"\n[writing]\nprofile = "{profile}"\n'
    run, asked = recorder()
    configured_agent = agent.from_cfg(configured(tmp_path, text), run)
    configured_agent.cache = agent.Cache(None)
    configured_agent.ask("Write a sequence.")
    return asked[0]


def test_a_plain_request_has_the_common_rules_and_the_glossary_only(tmp_path: Path) -> None:
    question = asked_with(tmp_path, "plain")
    for part in ("## Common rules", "## Project glossary", "## Acceptance procedure"):
        assert part in question, part
    assert "Descriptive sentences must not exceed 25 words" in question
    assert agent.STRICT_SECTION not in question
    assert "asd-ste100.org" not in question
    assert "Use the `plain` writing profile for this request." in question
    assert question.endswith("Write a sequence.")


def test_an_asd_ste100_request_has_the_whole_policy(tmp_path: Path) -> None:
    question = asked_with(tmp_path, "asd-ste100")
    assert question.startswith(agent.LANGUAGE_POLICY)
    assert agent.STRICT_SECTION in question and "asd-ste100.org" in question
    assert "Use the `asd-ste100` writing profile for this request." in question


def test_a_profile_change_requires_a_new_answer(tmp_path: Path) -> None:
    run, asked = recorder()
    cache = agent.Cache(tmp_path / "agent.json")
    plain = agent.Agent("agent -p", tmp_path, cache, run_command=run, profile="plain")
    strict = agent.Agent("agent -p", tmp_path, cache, run_command=run, profile="asd-ste100")
    plain.ask("Write a sequence.")
    plain.ask("Write a sequence.")
    strict.ask("Write a sequence.")
    assert len(asked) == 2
    assert asked[0] != asked[1]


def test_the_policy_sections_are_in_order() -> None:
    policy = agent.LANGUAGE_POLICY
    order = [
        "## Writing profiles",
        "## Common rules",
        "## Technical identities",
        agent.STRICT_SECTION,
        "## Project glossary",
        "## Acceptance procedure",
    ]
    places = [policy.index(heading) for heading in order]
    assert places == sorted(places)
    assert policy.count(agent.STRICT_SECTION) == 1
