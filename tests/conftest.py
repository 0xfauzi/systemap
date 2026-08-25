from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from systemap import extract
from systemap import theme as theme_mod
from systemap.config import Config, Ignore
from systemap.model import (
    Component,
    Container,
    Flow,
    Invariant,
    Journey,
    Layer,
    Meaning,
    Model,
    Region,
    Step,
    all_layers,
)


def write_tree(root: Path, files: dict[str, str]) -> None:
    """Write a dict of relative path -> content under root."""
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


TINY_PACKAGE: dict[str, str] = {
    "pkg/__init__.py": '"""A tiny package."""\n',
    "pkg/reader.py": '''
        """Read things.

        Second paragraph, not shown.
        """

        from __future__ import annotations

        LIMIT: int = 10
        _PRIVATE = 1


        class Request:
            """One request."""

            def send(self, body: str) -> None:
                """Send it."""


        class ReadError(Exception):
            """Reading failed."""


        def read(source: str) -> Request:
            """Read a source."""
            return Request()


        def _helper() -> None:
            pass
    ''',
    "pkg/writer.py": """
        from __future__ import annotations

        from pkg import reader
        from pkg.reader import Request


        def write(request: Request) -> str:
            return reader.LIMIT * "x"
    """,
    "tests/test_reader.py": """
        from pkg.reader import read


        def test_read_returns_request() -> None:
            assert read("x")


        class TestNested:
            def test_nested(self) -> None:
                assert True
    """,
    "tests/test_other.py": """
        from pkg import writer


        def test_write() -> None:
            assert writer
    """,
}


# ---- the sample system: a small pipeline with a store and an actor ------------
# Rich enough to exercise every drawing rule: two containers, two regions,
# a store, an actor outside the system, both standard kinds and one custom
# kind, two layers of its own, a layer override, a verb override, two
# invariants and a journey.

SAMPLE_TREE: dict[str, str] = {
    "pkg/__init__.py": '"""The sample system."""\n',
    "pkg/reader.py": """
        from __future__ import annotations


        class Request:
            body: str = ""


        def read(source: str) -> Request:
            return Request()
    """,
    "pkg/parser.py": """
        from __future__ import annotations

        from pkg.reader import Request


        def parse(request: Request) -> list[str]:
            return [request.body]
    """,
    "pkg/writer.py": """
        from __future__ import annotations

        from pkg.ledger import Ledger


        def write(parts: list[str], ledger: Ledger) -> str:
            ledger.record(parts)
            return "".join(parts)
    """,
    "pkg/ledger.py": """
        from __future__ import annotations


        class Ledger:
            def record(self, parts: list[str]) -> None:
                pass

            def history(self) -> list[list[str]]:
                return []
    """,
    "tests/test_reader.py": """
        from pkg.reader import read


        def test_read() -> None:
            assert read("x")
    """,
    "tests/test_writer.py": """
        from pkg.ledger import Ledger
        from pkg.writer import write


        def test_write() -> None:
            assert write(["a"], Ledger()) == "a"
    """,
}

COL = {"c1": 270, "c2": 460, "c3": 650}
ROW = {"r1": 90, "r2": 250}


def sample_model() -> tuple[Model, Meaning]:
    model = Model(
        canvas=(900, 400),
        containers=(
            Container("outside", "OUTSIDE", (16, 16, 186, 368), tone="host"),
            Container("system", "SYSTEM", (222, 16, 662, 368), sub="one process", tone="server"),
        ),
        regions=(
            Region("work", "WORK", (240, 50, 626, 130), container="system"),
            Region("keep", "KEEP", (240, 210, 626, 130), container="system"),
        ),
        components=(
            Component("User", "Types the input.", kind="actor", container="outside", x=34, y=96),
            Component(
                "Reader",
                "Reads the input and turns it into a request.",
                interface="read(source) -> Request",
                implemented_by=("pkg.reader",),
                entry="read",
                region="work",
                x=COL["c1"],
                y=ROW["r1"],
            ),
            Component(
                "Parser",
                "Splits a request into the parts the writer needs.",
                interface="parse(request) -> list[str]",
                implemented_by=("pkg.parser",),
                entry="parse",
                region="work",
                x=COL["c2"],
                y=ROW["r1"],
            ),
            Component(
                "Ledger",
                "Keeps every record ever written.",
                interface="Ledger.record / Ledger.history",
                implemented_by=("pkg.ledger",),
                entry="Ledger",
                kind="store",
                region="keep",
                x=COL["c2"],
                y=ROW["r2"],
            ),
            Component(
                "Writer",
                "Joins the parts and records the result.",
                interface="write(parts, ledger) -> str",
                implemented_by=("pkg.writer",),
                entry="write",
                region="keep",
                x=COL["c3"],
                y=ROW["r2"],
            ),
        ),
        flows=(
            Flow("User", "Reader", "input", "data"),
            Flow("Reader", "Parser", "parse", "control"),
            Flow("Parser", "Writer", "parts", "data"),
            Flow("Writer", "Ledger", "record", "record"),
            Flow("Ledger", "Parser", "history", "record"),
        ),
        flow_kinds=("record",),
        invariants=(
            Invariant(1, "The writer never reads the input itself.", governs=("Writer",)),
            Invariant(2, "Every record is written once.", governs=("Writer", "Ledger")),
        ),
    )
    meaning = Meaning(
        plain={
            "User": "the person typing",
            "Reader": "the part that reads",
            "Parser": "the part that splits",
            "Ledger": "the record book",
            "Writer": "the part that writes",
        },
        layers=(
            Layer("record", "Record", question="What is written down?"),
            Layer("memory", "Memory", question="What does the system remember?"),
        ),
        layer_of_kind={"record": "record"},
        layer_overrides={("Ledger", "Parser"): "memory"},
        relations={
            ("User", "Reader"): "The user types one input at a time.",
            ("Reader", "Parser"): "The reader calls the parser on each request.",
            ("Parser", "Writer"): "The parser gives the writer the parts in order.",
            ("Writer", "Ledger"): "The writer records every result it produces.",
            ("Ledger", "Parser"): "The ledger tells the parser what was written before.",
        },
        verbs={
            "data": ("hands to", "receives from"),
            "record": ("records in", "is written by"),
            "memory": ("reminds", "remembers through"),
        },
        verb_overrides={("User", "Reader"): ("types into", "is typed by")},
        journeys=(
            Journey(
                "input-to-record",
                "An input becomes a record",
                steps=(
                    Step(("User",), (), ("User", "Reader"), "The user types an input."),
                    Step(("Reader",), (), ("Reader", "Parser"), "The reader calls the parser."),
                    Step(("Parser",), ("Ledger",), ("Parser", "Writer"), "The parser splits it."),
                    Step(("Writer",), ("Ledger",), ("Writer", "Ledger"), "The writer records it."),
                ),
            ),
        ),
    )
    return model, meaning


@dataclass(frozen=True)
class Sample:
    cfg: Config
    model: Model
    meaning: Meaning
    theme: dict[str, Any]
    facts: dict[str, Any]


@pytest.fixture
def sample(tmp_path: Path) -> Sample:
    """The sample system on disk, with facts read out of it by the real extractor."""
    write_tree(tmp_path, SAMPLE_TREE)
    cfg = Config(
        root=tmp_path,
        name="sample",
        package_roots=(("pkg", "pkg"),),
        coverage_ignore=(Ignore("pkg", "the package root only marks the directory"),),
    )
    model, meaning = sample_model()
    facts = extract.build(cfg)
    return Sample(cfg, model, meaning, theme_mod.resolve({}, all_layers(model, meaning)), facts)
