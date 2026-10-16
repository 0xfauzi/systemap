"""Regression tests for module descriptions in issue #91."""

from __future__ import annotations

import pytest

from systemap.typescript import parse_surface


@pytest.mark.parametrize("declaration", ["const LIMIT = 3", "let value = 1", "var value = 1"])
@pytest.mark.parametrize("export", ["", "export "])
@pytest.mark.parametrize("comment", ["/** The maximum value. */", "// The maximum value."])
def test_variable_comment_is_not_a_module_description(
    declaration: str, export: str, comment: str
) -> None:
    """Acceptance: a comment attached to a variable does not describe the module."""
    surface = parse_surface(f"{comment}\n{export}{declaration};\n")
    assert surface is not None and surface["docstring"] == ""


@pytest.mark.parametrize("tag", ["@module", "@module Limits", "@packageDocumentation"])
def test_module_tag_identifies_a_file_comment(tag: str) -> None:
    """Acceptance: a tagged comment describes the file, without the tag or module name."""
    surface = parse_surface(f"/**\n * Reads limits.\n * {tag}\n */\nexport const LIMIT = 3;\n")
    assert surface is not None and surface["docstring"] == "Reads limits."


@pytest.mark.parametrize(
    "source",
    [
        "/** Reads limits. */\n\nexport const LIMIT = 3;\n",
        "// Reads limits.\n\nconst LIMIT = 3;\n",
        '/** Reads limits. */\nimport { limit } from "./limit";\nexport const LIMIT = limit;\n',
        "/** Reads limits. */\n\n// The maximum value.\nexport const LIMIT = 3;\n",
    ],
)
def test_untagged_file_headers_keep_their_descriptions(source: str) -> None:
    """Acceptance: separate headers and headers before imports keep their descriptions."""
    surface = parse_surface(source)
    assert surface is not None and surface["docstring"] == "Reads limits."


def test_contiguous_line_comments_on_a_constant_are_not_a_file_header() -> None:
    """Acceptance: all contiguous comment lines belong to the constant."""
    surface = parse_surface("// The maximum value.\n// In seconds.\nexport const LIMIT = 3;\n")
    assert surface is not None and surface["docstring"] == ""


def test_tag_without_description_does_not_become_prose() -> None:
    """Acceptance: a module tag without prose gives an empty description."""
    surface = parse_surface("/** @module Limits */\nexport const LIMIT = 3;\n")
    assert surface is not None and surface["docstring"] == ""
