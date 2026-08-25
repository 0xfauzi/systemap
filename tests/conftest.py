from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from systemap import config
from systemap.config import Config
from systemap.model import Meaning, Model

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "kstrl"


@pytest.fixture(scope="session")
def example_cfg() -> Config:
    return config.load(EXAMPLE)


@pytest.fixture(scope="session")
def example_model(example_cfg: Config) -> tuple[Model, Meaning]:
    return config.load_model(example_cfg.model_path)


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
