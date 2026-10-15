"""The answer writer adds exact answers to `[judgement] answered` in the configuration file.

The writer keeps all other text of the file: comments, line breaks, and spaces. If the
list has an exact answer for only the same line, the new inline table replaces it. If
not, the writer adds one inline table for each answer:

- in the `answered = [...]` list of the judgement table, before the closing bracket,
- or in a new `answered` list below the header of the judgement table,
- or in a new judgement table at the end of the file.

The writer writes the file only if the TOML parser gives the previous data with only these
changes. If not, it writes nothing and tells the person to add the answers.
"""

from __future__ import annotations

import copy
import json
import re
import tomllib
from pathlib import Path
from typing import Any

from systemap.config import CONFIG_FILE, ConfigError


class AnswerWriteError(ConfigError):
    """The writer cannot add the answers. The message gives the answers to add."""


def inline(entry: dict[str, Any]) -> str:
    """Give one TOML inline table. A JSON string or integer is also a TOML value."""
    parts = []
    for key, value in entry.items():
        if isinstance(value, list):
            text = "[" + ", ".join(inline(item) for item in value) + "]"
        else:
            text = json.dumps(value, ensure_ascii=False)
        parts.append(f"{key} = {text}")
    return "{ " + ", ".join(parts) + " }"


def _location(source: str) -> tuple[str, tuple[str, ...]]:
    """Give the judgement table header and the key path of the answers list."""
    if source == CONFIG_FILE:
        return "judgement", ("judgement", "answered")
    return "tool.systemap.judgement", ("tool", "systemap", "judgement", "answered")


def _close(text: str, start: int) -> tuple[int, int]:
    """Give the index of the bracket that closes the list at `start`, and the index of the
    last character before it that is not a space, a line break, or a comment."""
    depth, at, last = 0, start, start
    while at < len(text):
        skipped = _skip(text, at)
        if skipped is not None:
            last = skipped - 1 if text[at] != "#" else last
            at = skipped
            continue
        char = text[at]
        depth = _depth(depth, char)
        if depth == 0:
            return at, last
        last = at if not char.isspace() else last
        at += 1
    raise ValueError("The list has no closing bracket.")


def _skip(text: str, at: int) -> int | None:
    """Give the index after a string or a comment that starts at `at`, or None."""
    char = text[at]
    if char == "#":
        newline = text.find("\n", at)
        return len(text) if newline < 0 else newline
    if char in "\"'":
        quote = char * 3 if text.startswith(char * 3, at) else char
        return _string_end(text, at, quote)
    return None


def _string_end(text: str, at: int, quote: str) -> int:
    """Give the index after the end of the TOML string that starts at `at`."""
    at += len(quote)
    while at < len(text):
        if quote[0] == '"' and text[at] == "\\":
            at += 2
            continue
        if text.startswith(quote, at):
            return at + len(quote)
        at += 1
    raise ValueError("A string has no end.")


def _list_start(text: str, header: str) -> tuple[re.Match[str] | None, int, int]:
    """Give the header match, the index after the header line, and the index of the `[`
    of the `answered` list, or -1 if the table has no `answered` key."""
    head = re.search(rf"^[ \t]*\[{re.escape(header)}\][ \t]*(#[^\r\n]*)?\r?$", text, re.MULTILINE)
    if head is None:
        return None, -1, -1
    after = text.find("\n", head.end())
    after = len(text) if after < 0 else after + 1
    nxt = re.compile(r"^[ \t]*\[", re.MULTILINE).search(text, after)
    end = nxt.start() if nxt else len(text)
    key = re.compile(r"^[ \t]*answered[ \t]*=[ \t]*\[", re.MULTILINE).search(text, after, end)
    return head, after, (key.end() - 1 if key else -1)


def _tables(text: str, start: int) -> list[tuple[int, int]]:
    """Give the start and the end of each inline table in the list that starts at `start`."""
    spans: list[tuple[int, int]] = []
    depth, at, begin = 0, start, -1
    while at < len(text):
        skipped = _skip(text, at)
        if skipped is not None:
            at = skipped
            continue
        before, depth = depth, _depth(depth, text[at])
        if (before, depth, text[at]) == (1, 2, "{"):
            begin = at
        if (before, depth, text[at]) == (2, 1, "}"):
            spans.append((begin, at + 1))
        if depth == 0:
            return spans
        at += 1
    raise ValueError("The list has no closing bracket.")


def _depth(depth: int, char: str) -> int:
    """Give the bracket depth after one character that is not in a string or a comment."""
    return depth + 1 if char in "[{" else depth - 1 if char in "]}" else depth


def _added(text: str, header: str, rows: list[str]) -> str:
    """Give the text with the rows added. The result is examined with the TOML parser."""
    newline = "\r\n" if "\r\n" in text else "\n"
    body = "".join(f"    {row},{newline}" for row in rows)
    head, after, start = _list_start(text, header)
    if head is None:
        tail = "" if text.endswith(("\n", "\r\n")) or not text else newline
        return f"{text}{tail}{newline}[{header}]{newline}answered = [{newline}{body}]{newline}"
    if start < 0:
        return f"{text[:after]}answered = [{newline}{body}]{newline}{text[after:]}"
    close, last = _close(text, start)
    comma = "" if text[last] in ",[" else ","
    line_start = text.rfind("\n", 0, close) + 1
    if line_start > last and not text[line_start:close].strip():
        # The closing bracket is on its own line: put the rows above that line.
        at, rows_text = line_start, body
    else:
        at, rows_text = close, newline + body
    return text[: last + 1] + comma + text[last + 1 : at] + rows_text + text[at:]


def _same_line(old: list[Any], line: str) -> int:
    """Give the index of the exact answer for only this line, or -1."""
    for k, entry in enumerate(old):
        if isinstance(entry, dict) and (entry.get("item") == line or entry.get("items") == [line]):
            return k
    return -1


def _edited(
    text: str, header: str, old: list[Any], entries: list[dict[str, Any]]
) -> tuple[str, list[Any]]:
    """Give the new text and the expected list. An entry replaces the exact answer for its
    line. The other entries go at the end of the list."""
    _head, _after, start = _list_start(text, header)
    spans = _tables(text, start) if start >= 0 else []
    usable = len(spans) == len(old)
    replace: dict[int, dict[str, Any]] = {}
    rest: list[dict[str, Any]] = []
    for entry in entries:
        k = _same_line(old, entry["item"]) if usable else -1
        if k < 0 or k in replace:
            rest.append(entry)
        else:
            replace[k] = entry
    for k in sorted(replace, reverse=True):
        begin, end = spans[k]
        text = text[:begin] + inline(replace[k]) + text[end:]
    if rest:
        text = _added(text, header, [inline(entry) for entry in rest])
    return text, [replace.get(k, entry) for k, entry in enumerate(old)] + rest


def _expected(data: dict[str, Any], keys: tuple[str, ...], answers: list[Any]) -> Any:
    out = copy.deepcopy(data)
    table = out
    for key in keys[:-1]:
        table = table.setdefault(key, {})
    table[keys[-1]] = copy.deepcopy(answers)
    return out


def _old(data: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
    table: Any = data
    for key in keys:
        table = table.get(key, {}) if isinstance(table, dict) else {}
    return list(table) if isinstance(table, list) else []


def path(root: Path, source: str) -> Path:
    """Give the configuration file: systemap.toml, or pyproject.toml for [tool.systemap]."""
    return root / (CONFIG_FILE if source == CONFIG_FILE else "pyproject.toml")


def add(root: Path, source: str, entries: list[dict[str, Any]]) -> Path:
    """Add or renew the answers in the configuration file. Give the path of the file.

    An answer replaces the exact answer for only the same line. The other answers go at the
    end of the list.
    """
    if not source:
        raise AnswerWriteError(
            f"The project has no {CONFIG_FILE}. Use systemap init. Then submit the results again."
        )
    target = path(root, source)
    raw = target.read_bytes()
    text = raw.decode("utf-8-sig")
    header, keys = _location(source)
    manual = "\n".join(f"    {inline(entry)}," for entry in entries)
    try:
        data = tomllib.loads(text)
        new, answers = _edited(text, header, _old(data, keys), entries)
        same = tomllib.loads(new) == _expected(data, keys, answers)
    except (ValueError, tomllib.TOMLDecodeError):
        same = False
    if not same:
        raise AnswerWriteError(
            f"{target.name}: the command cannot add the answers and keep the other values. "
            f"It wrote no file. Add these rows to [{header}] answered:\n{manual}"
        )
    _write(target, raw, new)
    return target


def _write(target: Path, raw: bytes, new: str) -> None:
    """Write the new text. Keep the byte order mark of the file."""
    bom = "﻿" if raw.startswith(b"\xef\xbb\xbf") else ""
    target.write_bytes((bom + new).encode("utf-8"))


def renew_evidence(root: Path, source: str, digests: dict[str, str]) -> Path:
    """Replace each `evidence` value that is a key of `digests` with its new value. Give
    the path of the file.

    The writer changes only the text of these values in the inline tables of the answers
    list. It writes the file only if the TOML parser gives the previous data with only
    these changes."""
    target = path(root, source)
    raw = target.read_bytes()
    text = raw.decode("utf-8-sig")
    header, keys = _location(source)
    try:
        data = tomllib.loads(text)
        new, answers = _renewed(text, header, _old(data, keys), digests)
        same = tomllib.loads(new) == _expected(data, keys, answers)
    except (ValueError, tomllib.TOMLDecodeError):
        same = False
    if not same:
        raise AnswerWriteError(
            f"{target.name}: the command cannot write the new evidence digests and keep the "
            "other values. It wrote no file."
        )
    _write(target, raw, new)
    return target


def _renewed(
    text: str, header: str, old: list[Any], digests: dict[str, str]
) -> tuple[str, list[Any]]:
    """Give the new text and the expected list, with the new evidence values."""
    _head, _after, start = _list_start(text, header)
    spans = _tables(text, start) if start >= 0 else []
    if len(spans) != len(old):
        raise ValueError("The writer cannot find each answer in the list.")
    answers = copy.deepcopy(old)
    for k in reversed(range(len(old))):
        value = old[k].get("evidence") if isinstance(old[k], dict) else None
        if not isinstance(value, str) or value not in digests:
            continue
        begin, end = spans[k]
        part = text[begin:end]
        if part.count(value) != 1:
            raise ValueError("The evidence value occurs more than one time in an answer.")
        text = text[:begin] + part.replace(value, digests[value]) + text[end:]
        answers[k]["evidence"] = digests[value]
    return text, answers
