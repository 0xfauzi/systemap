"""Tests for hostile input to the TypeScript surface reader.

Each test name gives the audit finding ID. Each test failed at d90d08e.
"""

from __future__ import annotations

from typing import Any

import pytest

from systemap import typescript_surface, unknown_causes
from systemap.typescript_strings import decode_quoted, escape
from systemap.typescript_surface import NAMESPACE_DEPTH, parse_surface


def nested(depth: int) -> str:
    """This function gives `depth` exported namespaces, one in the other."""
    opening = "".join(f"export namespace N{level} {{\n" for level in range(depth))
    return opening + "export const x = 1;\n" + "}\n" * depth


def surface(source: str) -> dict[str, Any]:
    found = parse_surface(source, "src/m.ts")
    assert found is not None
    return found


def test_g1ts_1_each_namespace_is_read_one_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Acceptance: 20 nested namespaces (510 bytes) cause at most 2 calls for each
    namespace. At d90d08e, the reader made 2097150 calls and took 70 s to 112 s.
    """
    original = typescript_surface._namespace_definition
    calls = 0

    def counted(*args: Any) -> str:
        nonlocal calls
        calls += 1
        if calls > 1000:
            raise AssertionError("The reader reads the namespaces again and again.")
        return original(*args)

    monkeypatch.setattr(typescript_surface, "_namespace_definition", counted)
    source = nested(20)
    assert len(source) == 510
    surface(source)
    assert calls <= 2 * 20


def test_g1ts_1_namespace_at_the_depth_limit_is_read() -> None:
    """Acceptance: at NAMESPACE_DEPTH levels, the surface has no unknown record, and the
    API identity contains the innermost declaration.
    """
    found = surface(nested(NAMESPACE_DEPTH))
    assert found["unknown"] == []
    fingerprint = found["api"][0]["fingerprint"]
    assert f"N{NAMESPACE_DEPTH - 1}" in fingerprint
    assert "const" in fingerprint
    assert "unread:" not in fingerprint


def test_g1ts_1_namespace_deeper_than_the_depth_limit_gives_an_unknown_record() -> None:
    """Acceptance: one more level gives one unknown record with the cause declaration,
    on the line of the namespace that the reader does not read.
    """
    found = surface(nested(NAMESPACE_DEPTH + 1))
    (record,) = found["unknown"]
    assert record["cause"] == unknown_causes.DECLARATION
    assert record["line"] == NAMESPACE_DEPTH + 1
    assert record["reason"].startswith("The namespace nesting is deeper than")
    assert [entry["name"] for entry in found["names"]] == ["N0"]


def test_g1ts_1_very_deep_namespaces_complete() -> None:
    """Acceptance: 1000 nested namespaces give a surface with one unknown record."""
    assert len(surface(nested(1000))["unknown"]) == 1


def test_g1ts_2_very_large_code_point_is_not_valid() -> None:
    """Acceptance: a code point that is too large for chr gives the escape text, as
    a code point above U+10FFFF gives. At d90d08e, it raised OverflowError.
    """
    large = "u{" + "F" * 20 + "}"
    assert escape("\\" + large) == large
    assert escape("\\u{110000}") == "u{110000}"
    assert decode_quoted('"\\' + large + '"') == large
    found = surface("export { a } from './\\" + large + "';\n")
    assert found["names"][0]["reexport_of"] == "./" + large
