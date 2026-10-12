"""A model file is data: loading it runs no code from the repository.

Each adversarial model below runs code under a loader that executes the file: it writes
a marker file. The safe loader must refuse it before it builds a value, with the file,
the line and the construct, and the marker file must not exist after the load. Only the
person who runs the command can permit code, with SYSTEMAP_TRUST_MODEL_CODE=1. The
conftest removes that variable before each test.
"""

from __future__ import annotations

import dataclasses
import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import config, delta_git
from systemap.cli import main
from systemap.config import ConfigError
from systemap.journeys import as_source
from systemap.model import Journey, Step

TRUST = "SYSTEMAP_TRUST_MODEL_CODE"
ROOT = Path(__file__).resolve().parent.parent

VALID = """
from systemap import Container, Meaning, Model, Region

MODEL = Model(
    canvas=(600, 300),
    containers=(Container(id="s", label="S", box=(0, 0, 600, 300)),),
    regions=(Region(id="r", label="R", box=(10, 10, 580, 280), container="s"),),
    components=(),
    flows=(),
    flow_kinds=(),
)
MEANING = Meaning(plain={})
"""


def shell_marker(marker: Path) -> str:
    """A shell command that makes the marker file, the same in sh and in cmd.exe."""
    return repr(f'echo ran > "{marker}"')


def load_refused(tmp_path: Path, body: str, name: str = "model.py") -> str:
    """Write the model, load it, and give the refusal. No marker file may exist."""
    folder = tmp_path / "map"
    folder.mkdir(exist_ok=True)
    marker = tmp_path / "ran"
    (folder / name).write_text(body.replace("MARKER", repr(str(marker))), encoding="utf-8")
    message = ""
    try:
        config.load_model(folder / name, f"map/{name}")
    except ConfigError as exc:
        message = str(exc)
    assert not marker.exists(), "the model file ran code"
    assert message, "the loader did not refuse the model file"
    return message


def m_str(marker: Path) -> str:
    # Forward slashes: Python 3.11 refuses a backslash of a Windows path in an f-string
    # expression, and open() reads a path with forward slashes on Windows also.
    return repr(marker.as_posix())


# Each case: the model text (MARKER is the marker path), the refused line, and words of
# the construct that the refusal must name.
CASES: dict[str, tuple[Callable[[Path], str], int, str]] = {
    "import os and os.system": (
        lambda m: f"import os\nos.system({shell_marker(m)})\n",
        1,
        "an import of os",
    ),
    "__import__": (
        lambda m: f'X = __import__("os").system({shell_marker(m)})\n',
        1,
        '__import__("os").system',
    ),
    "exec": (
        lambda m: f"exec(\"open({m_str(m)}, 'w').close()\")\n",
        1,
        "a call of exec",
    ),
    "eval": (
        lambda m: f"X = eval(\"open({m_str(m)}, 'w').close()\")\n",
        1,
        "a call of eval",
    ),
    "getattr": (
        lambda m: f'X = getattr(open({m_str(m)}, "w"), "close")()\n',
        1,
        "getattr(open(",
    ),
    "a dunder name": (
        lambda m: f'__builtins__["open"]({m_str(m)}, "w").close()\n',
        1,
        "__builtins__",
    ),
    "a lambda": (
        lambda m: f'X = (lambda: open({m_str(m)}, "w").close())()\n',
        1,
        "a lambda expression",
    ),
    "a function definition": (
        lambda m: f'"""Doc."""\n\ndef f(x=open({m_str(m)}, "w")):\n    pass\n',
        3,
        "a function definition",
    ),
    "a class definition": (
        lambda m: f'class C:\n    open({m_str(m)}, "w").close()\n',
        1,
        "a class definition",
    ),
    "a decorator": (
        lambda m: f'@(lambda f: open({m_str(m)}, "w"))\ndef g():\n    pass\n',
        1,
        "a decorator",
    ),
    "a comprehension": (
        lambda m: f'X = [open({m_str(m)}, "w") for _ in (1,)]\n',
        1,
        "a comprehension",
    ),
    "an f-string with a call": (
        lambda m: f"X = f\"{{open({m_str(m)}, 'w')}}\"\n",
        1,
        "an f-string",
    ),
    "an import of systemap.config": (
        lambda m: f"from systemap.config import os\nos.system({shell_marker(m)})\n",
        1,
        "an import from systemap.config",
    ),
    "an import of another systemap module": (
        lambda m: f"from systemap import config\nconfig.os.system({shell_marker(m)})\n",
        1,
        "an import of config from systemap",
    ),
    "a dotted import of a systemap module": (
        lambda m: f"import systemap.config\nsystemap.config.os.system({shell_marker(m)})\n",
        1,
        "an import of systemap.config",
    ),
    "a call of a built-in function after an annotation": (
        lambda m: f'from __future__ import annotations\nX: int = 1\nopen({m_str(m)}, "w")\n',
        3,
        "a call of open",
    ),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_model_with_code_is_refused_and_runs_nothing(tmp_path: Path, case: str) -> None:
    body, line, construct = CASES[case]
    message = load_refused(tmp_path, body(tmp_path / "ran"))
    assert message.startswith(f"map/model.py:{line}: "), message
    assert construct in message, message
    assert "Write literal values" in message, message
    assert f"{TRUST}=1" in message, message


def test_a_relative_import_is_refused(tmp_path: Path) -> None:
    write_tree(tmp_path, {"map/evil.py": "open(MARKER, 'w').close()\n"})
    evil = tmp_path / "map/evil.py"
    evil.write_text(evil.read_text().replace("MARKER", repr(str(tmp_path / "ran"))))
    message = load_refused(tmp_path, "from .evil import X\n" + VALID)
    assert message.startswith("map/model.py:1: "), message
    assert "a relative import" in message, message


def _link_or_skip(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("this system cannot make a symbolic link")


def test_a_sibling_import_through_a_link_to_outside_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "evil.py").write_text(f'open({m_str(tmp_path / "ran")}, "w").close()\n')
    (tmp_path / "map").mkdir()
    _link_or_skip(tmp_path / "map/evil.py", outside / "evil.py")
    message = load_refused(tmp_path, "import evil\n" + VALID)
    assert message.startswith("map/model.py:1: "), message
    assert "outside the directory of the model file" in message, message


def test_a_literal_sibling_through_a_link_to_outside_is_refused(tmp_path: Path) -> None:
    """The guard is about the path, not the contents: data outside the directory is
    not read either."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "data.py").write_text("X = 1\n")
    (tmp_path / "map").mkdir()
    _link_or_skip(tmp_path / "map/data.py", outside / "data.py")
    message = load_refused(tmp_path, "import data\n" + VALID)
    assert "outside the directory of the model file" in message, message


def test_a_link_inside_the_directory_is_accepted(tmp_path: Path) -> None:
    folder = tmp_path / "map"
    folder.mkdir()
    (folder / "real.py").write_text(
        'from systemap import Meaning\n\nMEANING = Meaning(plain={"A": "a"})\n'
    )
    _link_or_skip(folder / "alias.py", folder / "real.py")
    (folder / "model.py").write_text(
        VALID.replace("MEANING = Meaning(plain={})", "import alias\nMEANING = alias.MEANING")
    )
    _model, meaning = config.load_model(folder / "model.py")
    assert dict(meaning.plain) == {"A": "a"}


def test_an_import_cycle_is_refused(tmp_path: Path) -> None:
    write_tree(tmp_path, {"map/a.py": "import b\nX = 1\n", "map/b.py": "import a\nY = 2\n"})
    message = load_refused(tmp_path, "import a\n" + VALID)
    assert message.startswith("map/b.py:1: "), message
    assert "an import cycle" in message, message


@pytest.mark.parametrize("unpack", ["**KW", "*ARGS"])
def test_a_model_class_call_with_unpacked_values_from_a_name_is_refused(
    tmp_path: Path, unpack: str
) -> None:
    body = (
        "from systemap import Component\n"
        'KW = {"id": "A", "does": "a job."}\n'
        'ARGS = ("A", "a job.")\n'
        f"C = Component({unpack})\n" + VALID
    )
    message = load_refused(tmp_path, body)
    assert message.startswith("map/model.py:4: "), message
    assert "an unpacked" in message, message


def test_a_very_deep_nesting_is_refused(tmp_path: Path) -> None:
    deep = "X = " + "[" * 150 + "1" + "]" * 150 + "\n"
    message = load_refused(tmp_path, deep + VALID)
    assert message.startswith("map/model.py:1: "), message
    assert "nested" in message, message


def test_a_nesting_that_the_parser_cannot_read_is_refused(tmp_path: Path) -> None:
    message = load_refused(tmp_path, "X = " + "-" * 200_000 + "1\n" + VALID)
    assert message.startswith("map/model.py: "), message
    assert "nested" in message, message


def test_a_very_long_file_is_refused_before_it_is_parsed(tmp_path: Path) -> None:
    lines = "".join(f"X{k} = {k}\n" for k in range(80_000))
    message = load_refused(tmp_path, VALID + lines)
    assert message.startswith("map/model.py: "), message
    assert "bytes" in message, message


def test_an_annotation_is_not_evaluated(tmp_path: Path) -> None:
    folder = tmp_path / "map"
    folder.mkdir()
    marker = tmp_path / "ran"
    (folder / "model.py").write_text(
        f'X: open({m_str(marker)}, "w") = 1\n' + VALID, encoding="utf-8"
    )
    model, _meaning = config.load_model(folder / "model.py")
    assert model.canvas == (600, 300)
    assert not marker.exists()


def test_the_refusal_comes_before_any_value_is_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from systemap import model_load

    built: list[Path] = []
    real = model_load._build

    def spy(source: model_load.Source, *args: object) -> dict[str, object]:
        built.append(source.path)
        return real(source, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(model_load, "_build", spy)
    write_tree(tmp_path, {"map/walks.py": "X = (1, 2)\n"})
    load_refused(tmp_path, "import walks\n" + VALID + "Y = [k for k in walks.X]\n")
    assert built == []


def test_the_person_who_runs_the_command_can_permit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "map"
    folder.mkdir()
    (folder / "model.py").write_text(
        VALID.replace("plain={}", 'plain={k: k.lower() for k in ("A", "B")}'), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="a comprehension"):
        config.load_model(folder / "model.py")
    monkeypatch.setenv(TRUST, "1")
    _model, meaning = config.load_model(folder / "model.py")
    assert dict(meaning.plain) == {"A": "a", "B": "b"}


def test_the_configuration_cannot_permit_code(tmp_path: Path) -> None:
    """The repository controls systemap.toml, so it has no key for this permission."""
    write_tree(tmp_path, {"pkg/__init__.py": "", "systemap.toml": "trust_model_code = true\n"})
    with pytest.raises(ConfigError, match="unknown key: trust_model_code"):
        config.load(tmp_path)


def test_a_type_alias_is_accepted_and_is_not_a_value(tmp_path: Path) -> None:
    folder = tmp_path / "map"
    folder.mkdir()
    head = "from systemap import Step\n\nSteps = tuple[Step, ...]\nPairs = dict[str, tuple[str, str]]\n"
    (folder / "model.py").write_text(head + VALID, encoding="utf-8")
    model, _meaning = config.load_model(folder / "model.py")
    assert model.flows == ()
    message = load_refused(tmp_path, head + "X = Steps\n" + VALID)
    assert message.startswith("map/model.py:5: "), message
    assert "type alias" in message, message


def test_a_model_class_that_the_file_did_not_import_gives_the_fix(tmp_path: Path) -> None:
    message = load_refused(tmp_path, "from systemap import Model\nLAYERS = (Layer('a', 'A'),)\n")
    assert message.startswith("map/model.py:2: "), message
    assert "Add Layer to the import from systemap" in message, message


def test_a_name_that_systemap_does_not_export_gives_the_names(tmp_path: Path) -> None:
    message = load_refused(tmp_path, "from systemap import Model, Layers\n")
    assert message.startswith("map/model.py:1: "), message
    assert "Use a name that systemap exports for a model: AGENT_KINDS, KINDS," in message


def test_the_init_template_loads_with_the_safe_loader(tmp_path: Path) -> None:
    write_tree(
        tmp_path, {"pkg/__init__.py": "", "pkg/reader.py": "def read() -> None:\n    return None\n"}
    )
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    model, meaning = config.load_model(tmp_path / "map/model.py")
    assert [r.id for r in model.regions] == ["a", "b", "c", "d"]
    assert meaning.journeys == ()


def test_the_self_map_loads_with_the_safe_loader() -> None:
    model, meaning = config.load_model(ROOT / "map/model.py", "map/model.py")
    assert len(model.flows) > 0 and len(meaning.journeys) > 0
    assert any(f.source_refs for f in model.flows)


def test_a_committed_model_with_code_is_not_run_by_the_comparison(tmp_path: Path) -> None:
    marker = tmp_path.parent / f"{tmp_path.name}-ran"
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
            "map/model.py": f'open({m_str(marker)}, "w").close()\n' + VALID,
        },
    )
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "base"]):
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@t",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
    found = delta_git.model_at(config.load(tmp_path), "HEAD")
    assert not marker.exists(), "the committed model file ran code"
    assert isinstance(found, str) and "does not load" in found, found
    assert "a call of open" in found, found


def test_a_value_that_names_make_very_large_is_refused(tmp_path: Path) -> None:
    """Each name refers to the earlier value without a copy, so 30 lines can describe
    2**30 strings. A later step that writes the value out in full would not stop."""
    lines = 'A0 = ("x",)\n' + "".join(f"A{k} = (A{k - 1}, A{k - 1})\n" for k in range(1, 31))
    message = load_refused(tmp_path, lines + VALID)
    assert re.match(r"map/model\.py:2[0-9]: ", message), message
    assert "when each name in it is written out" in message, message


def test_a_keyword_that_a_call_gives_two_times_is_refused(tmp_path: Path) -> None:
    body = 'from systemap import Layer\nL = Layer(id="a", label="A", label="B")\n' + VALID
    message = load_refused(tmp_path, body)
    assert message.startswith("map/model.py:2: "), message
    assert "the keyword label two times" in message, message


@pytest.mark.parametrize("value", ["true", "yes", "0", ""])
def test_only_the_value_1_permits_model_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(TRUST, value)
    message = load_refused(tmp_path, f'open({m_str(tmp_path / "ran")}, "w").close()\n' + VALID)
    assert "a call of open" in message, message


def test_a_sequence_that_systemap_journeys_writes_loads_with_the_safe_loader(
    tmp_path: Path,
) -> None:
    sentence = 'A sends the "value" \\ path.\nNext line: café.'
    walk = Journey(
        id="quoted",
        label=sentence,
        starts="GET /read",
        covers=('["route","pkg.app","GET","/read"]',),
        steps=(Step(acts=("A",), measures=("B",), edge=("A", "B"), say=sentence),),
    )
    folder = tmp_path / "map"
    folder.mkdir()
    source = "from systemap import Journey, Step\nJOURNEYS = (\n" + "\n".join(as_source(walk))
    (folder / "walks.py").write_text(source + "\n)\n", encoding="utf-8")
    meaning_line = "import walks\nMEANING = Meaning(plain={}, journeys=walks.JOURNEYS)"
    (folder / "model.py").write_text(
        VALID.replace("MEANING = Meaning(plain={})", meaning_line), encoding="utf-8"
    )
    _model, meaning = config.load_model(folder / "model.py")
    assert meaning.journeys == (dataclasses.replace(walk, drafted=True),)
