"""The placement writer writes calculated positions, boxes, and the canvas into the model file.

It changes only the values of x, y, box, and canvas arguments. It keeps all other text.
It writes LF line ends and no byte order mark, on each operating system.
After the write, it loads the file again. It compares all positions, boxes, and the canvas
with the calculated values. If it cannot load the file or a value is different, it
restores the previous file bytes and gives an error.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass, fields
from pathlib import Path

from systemap.model import Component, Container, Model, Region
from systemap.place import PlaceError, Placement


def _index(cls: type, name: str) -> int:
    """This function gives the positional index of a field of a model class."""
    return next(k for k, f in enumerate(fields(cls)) if f.name == name)


# The positional index of each written argument, for a call without a keyword.
X_AT, Y_AT = _index(Component, "x"), _index(Component, "y")
BOX_AT = {"Region": _index(Region, "box"), "Container": _index(Container, "box")}
CANVAS_AT = _index(Model, "canvas")
LAYOUT_CALLS = ("Region", "Container", "Model")


def _name_of(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _const_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _kw(call: ast.Call, name: str) -> ast.keyword | None:
    return next((k for k in call.keywords if k.arg == name), None)


def _argument(call: ast.Call, name: str, at: int) -> ast.expr | None:
    """This function gives the value of a keyword argument, or of the positional argument."""
    kw = _kw(call, name)
    if kw is not None:
        return kw.value
    return call.args[at] if len(call.args) > at else None


def _id_of(call: ast.Call) -> str | None:
    return _const_str(_argument(call, "id", 0))


# What the source positions are read from: an expression or a keyword.
_Located = ast.expr | ast.keyword


@dataclass(frozen=True)
class _Edit:
    start: int
    end: int
    text: bytes


def _offsets(source: bytes) -> list[int]:
    """This function calculates byte offsets for source lines to convert AST positions."""
    out = [0]
    for k, b in enumerate(source):
        if b == 0x0A:
            out.append(k + 1)
    return out


@dataclass(frozen=True)
class _Text:
    """The model source bytes and the byte offset of each line."""

    raw: bytes
    starts: list[int]

    def span(self, node: _Located) -> tuple[int, int]:
        assert node.end_lineno is not None and node.end_col_offset is not None
        return (
            self.starts[node.lineno - 1] + node.col_offset,
            self.starts[node.end_lineno - 1] + node.end_col_offset,
        )

    def value(self, node: ast.expr, text: str) -> _Edit:
        a, b = self.span(node)
        return _Edit(a, b, text.encode())


def _component(text: _Text, call: ast.Call, xy: tuple[int, int]) -> list[_Edit]:
    """This function replaces the x and y values of a Component call, or inserts them."""
    out: list[_Edit] = []
    missing: list[tuple[str, int]] = []
    for key, at, number in (("x", X_AT, xy[0]), ("y", Y_AT, xy[1])):
        found = _argument(call, key, at)
        if found is None:
            missing.append((key, number))
        else:
            out.append(text.value(found, str(number)))
    if missing:
        out.append(_insertion(text.raw, call, missing, text.span))
    return out


def _layout(text: _Text, call: ast.Call, name: str, placement: Placement) -> list[_Edit]:
    """This function replaces the box of a Region or Container call, or the Model canvas."""
    if name == "Model":
        canvas = _argument(call, "canvas", CANVAS_AT)
        return [] if canvas is None else [text.value(canvas, repr(tuple(placement.canvas)))]
    table = placement.regions if name == "Region" else placement.containers
    rid = _id_of(call)
    box = _argument(call, "box", BOX_AT[name])
    if rid is None or rid not in table or box is None:
        return []
    return [text.value(box, repr(tuple(table[rid])))]


def edits(source: str, placement: Placement) -> list[_Edit]:
    """This function prepares source-byte edits for component positions and layout boxes.

    It replaces existing x and y arguments, as keywords or as positional values. It inserts
    missing arguments in explicit Component calls. A fresh layout also replaces the boxes
    and the canvas.
    """
    raw = source.encode("utf-8")
    text = _Text(raw, _offsets(raw))
    out: list[_Edit] = []
    seen: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = _name_of(node.func)
        cid = _id_of(node) if name == "Component" else None
        if cid is not None and cid in placement.positions and cid not in seen:
            seen.add(cid)
            out += _component(text, node, placement.positions[cid])
        elif placement.fresh and name in LAYOUT_CALLS:
            out += _layout(text, node, name, placement)
    return out


def _insertion(
    raw: bytes,
    call: ast.Call,
    missing: list[tuple[str, int]],
    span: Callable[[_Located], tuple[int, int]],
) -> _Edit:
    """This function formats missing x and y arguments in the existing call style."""
    last = max(
        (*call.args, *(k.value for k in call.keywords)),
        key=lambda n: span(n)[1],
    )
    _a, end = span(last)
    _call_start, call_end = span(call)
    between = raw[end : call_end - 1]
    if b"\n" in between:
        line_start = raw.rfind(b"\n", 0, span(last)[0]) + 1
        indent = raw[line_start : span(last)[0]]
        indent = indent[: len(indent) - len(indent.lstrip())]
        # The last argument may be a keyword: its line's indent is the one.
        kw = next((k for k in call.keywords if k.value is last), None)
        if kw is not None:
            line_start = raw.rfind(b"\n", 0, span(kw)[0]) + 1
            indent = raw[line_start : span(kw)[0]]
        text = b"".join(b",\n" + indent + f"{k}={v}".encode() for k, v in missing)
        return _Edit(end, end, text)
    text = b"".join(f", {k}={v}".encode() for k, v in missing)
    return _Edit(end, end, text)


def written(source: str, placement: Placement) -> str:
    """This function gives the model source with placement edits."""
    raw = bytearray(source.encode("utf-8"))
    for edit in sorted(edits(source, placement), key=lambda e: (e.start, e.end), reverse=True):
        raw[edit.start : edit.end] = edit.text
    return raw.decode("utf-8")


def unwritten(reloaded: Model, expected: Model) -> list[str]:
    """This function names each position, box, or canvas value that is not the expected one."""
    out: list[str] = []
    positions = {c.id: (c.x, c.y) for c in reloaded.components}
    out += [c.id for c in expected.components if positions.get(c.id) != (c.x, c.y)]
    regions = {r.id: tuple(r.box) for r in reloaded.regions}
    out += [f"region {r.id}" for r in expected.regions if regions.get(r.id) != tuple(r.box)]
    containers = {b.id: tuple(b.box) for b in reloaded.containers}
    out += [
        f"container {b.id}" for b in expected.containers if containers.get(b.id) != tuple(b.box)
    ]
    if tuple(reloaded.canvas) != tuple(expected.canvas):
        out.append("canvas")
    return out


def write(
    path: Path,
    label: str,
    placement: Placement,
    expected: Model,
    load: Callable[[Path, str], Model],
) -> None:
    """Write the placement into the model file. Then load the file and compare its geometry.

    `expected` is the model with the placement applied. `load` reads a model file and
    raises an error for a file that it cannot read. If `load` raises an error, or a value
    is not the expected value, the function restores the previous bytes and raises
    PlaceError.
    """
    raw = path.read_bytes()
    # The text gets LF line ends, as with universal newlines. Thus the command writes a
    # CRLF file from a Windows checkout with LF line ends.
    source = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    path.write_text(written(source, placement), encoding="utf-8", newline="\n")
    try:
        wrong = unwritten(load(path, label), expected)
    except Exception as exc:
        path.write_bytes(raw)
        raise PlaceError(
            f"The command could not load {label} after the change: {exc} "
            "The command restored the previous file contents."
        ) from exc
    except BaseException:
        path.write_bytes(raw)
        raise
    if wrong:
        path.write_bytes(raw)
        raise PlaceError(
            f"The command could not write {', '.join(wrong)} in {label}. Each value must be "
            "in this file, as an argument of Component, Region, Container, or Model. "
            "The command restored the previous file contents. Use systemap place --print to "
            "show the values. Then write them manually."
        )
