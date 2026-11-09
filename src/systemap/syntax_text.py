"""The syntax text is the fixed text form that systemap stores for a Python syntax tree.

The source-review digest, the `api` fingerprints, and the base and decorator values of a
fingerprint come from this text. CPython does not keep `ast.dump` the same between
versions. Thus systemap writes the text itself, from the class name and the field names
of each node. The text is the same on each supported Python version.

The rules of the text:

- A node is its class name and its fields in the sequence of `FIELDS`, for example
  `Name(id='x', ctx=Load())`. A list is `[a, b]`. A literal value is its `repr`, but an
  integer with more than `INT_BITS` bits is its hexadecimal text.
- The text does not include a field whose value is `None` or an empty list. A `None`
  item in a list stays, because the position of each item is a part of the list.
- The parts of an f-string or a template string do not include an empty string
  constant. CPython 3.12.3 adds `Constant('')` at the end of a format spec that ends with
  a replacement field (issue 126). Other versions do not add it.
- `FIELDS` gives each node class that a supported version can make. `SINCE` gives each
  class and each field that only some supported versions have, with the first version.
  A version without the field gives the same text as a version with an empty field.

A node class or a field that the tables do not include gives `UnknownSyntax`. The
extraction then stops, because a text without the field can hide a change of the source.
The tree does not change.
"""

from __future__ import annotations

import ast
import sys

# The fields of each node class, in the sequence of the text.
FIELDS: dict[str, tuple[str, ...]] = {
    "Module": ("body", "type_ignores"),
    "Interactive": ("body",),
    "Expression": ("body",),
    "FunctionType": ("argtypes", "returns"),
    "TypeIgnore": ("lineno", "tag"),
    "FunctionDef": (
        "name",
        "args",
        "body",
        "decorator_list",
        "returns",
        "type_comment",
        "type_params",
    ),
    "AsyncFunctionDef": (
        "name",
        "args",
        "body",
        "decorator_list",
        "returns",
        "type_comment",
        "type_params",
    ),
    "ClassDef": ("name", "bases", "keywords", "body", "decorator_list", "type_params"),
    "Return": ("value",),
    "Delete": ("targets",),
    "Assign": ("targets", "value", "type_comment"),
    "TypeAlias": ("name", "type_params", "value"),
    "AugAssign": ("target", "op", "value"),
    "AnnAssign": ("target", "annotation", "value", "simple"),
    "For": ("target", "iter", "body", "orelse", "type_comment"),
    "AsyncFor": ("target", "iter", "body", "orelse", "type_comment"),
    "While": ("test", "body", "orelse"),
    "If": ("test", "body", "orelse"),
    "With": ("items", "body", "type_comment"),
    "AsyncWith": ("items", "body", "type_comment"),
    "Match": ("subject", "cases"),
    "Raise": ("exc", "cause"),
    "Try": ("body", "handlers", "orelse", "finalbody"),
    "TryStar": ("body", "handlers", "orelse", "finalbody"),
    "Assert": ("test", "msg"),
    "Import": ("names",),
    "ImportFrom": ("module", "names", "level"),
    "Global": ("names",),
    "Nonlocal": ("names",),
    "Expr": ("value",),
    "Pass": (),
    "Break": (),
    "Continue": (),
    "BoolOp": ("op", "values"),
    "NamedExpr": ("target", "value"),
    "BinOp": ("left", "op", "right"),
    "UnaryOp": ("op", "operand"),
    "Lambda": ("args", "body"),
    "IfExp": ("test", "body", "orelse"),
    "Dict": ("keys", "values"),
    "Set": ("elts",),
    "ListComp": ("elt", "generators"),
    "SetComp": ("elt", "generators"),
    "DictComp": ("key", "value", "generators"),
    "GeneratorExp": ("elt", "generators"),
    "Await": ("value",),
    "Yield": ("value",),
    "YieldFrom": ("value",),
    "Compare": ("left", "ops", "comparators"),
    "Call": ("func", "args", "keywords"),
    "FormattedValue": ("value", "conversion", "format_spec"),
    "Interpolation": ("value", "str", "conversion", "format_spec"),
    "JoinedStr": ("values",),
    "TemplateStr": ("values",),
    "Constant": ("value", "kind"),
    "Attribute": ("value", "attr", "ctx"),
    "Subscript": ("value", "slice", "ctx"),
    "Starred": ("value", "ctx"),
    "Name": ("id", "ctx"),
    "List": ("elts", "ctx"),
    "Tuple": ("elts", "ctx"),
    "Slice": ("lower", "upper", "step"),
    "Load": (),
    "Store": (),
    "Del": (),
    "And": (),
    "Or": (),
    "Add": (),
    "Sub": (),
    "Mult": (),
    "MatMult": (),
    "Div": (),
    "Mod": (),
    "Pow": (),
    "LShift": (),
    "RShift": (),
    "BitOr": (),
    "BitXor": (),
    "BitAnd": (),
    "FloorDiv": (),
    "Invert": (),
    "Not": (),
    "UAdd": (),
    "USub": (),
    "Eq": (),
    "NotEq": (),
    "Lt": (),
    "LtE": (),
    "Gt": (),
    "GtE": (),
    "Is": (),
    "IsNot": (),
    "In": (),
    "NotIn": (),
    "comprehension": ("target", "iter", "ifs", "is_async"),
    "ExceptHandler": ("type", "name", "body"),
    "arguments": (
        "posonlyargs",
        "args",
        "vararg",
        "kwonlyargs",
        "kw_defaults",
        "kwarg",
        "defaults",
    ),
    "arg": ("arg", "annotation", "type_comment"),
    "keyword": ("arg", "value"),
    "alias": ("name", "asname"),
    "withitem": ("context_expr", "optional_vars"),
    "match_case": ("pattern", "guard", "body"),
    "MatchValue": ("value",),
    "MatchSingleton": ("value",),
    "MatchSequence": ("patterns",),
    "MatchMapping": ("keys", "patterns", "rest"),
    "MatchClass": ("cls", "patterns", "kwd_attrs", "kwd_patterns"),
    "MatchStar": ("name",),
    "MatchAs": ("pattern", "name"),
    "MatchOr": ("patterns",),
    "TypeVar": ("name", "bound", "default_value"),
    "ParamSpec": ("name", "default_value"),
    "TypeVarTuple": ("name", "default_value"),
}

# The node classes (field "") and the fields that only some supported versions have, with
# the first version that has them. The supported versions are 3.11 to 3.14.
SINCE: dict[tuple[str, str], tuple[int, int]] = {
    ("FunctionDef", "type_params"): (3, 12),
    ("AsyncFunctionDef", "type_params"): (3, 12),
    ("ClassDef", "type_params"): (3, 12),
    ("TypeAlias", ""): (3, 12),
    ("TypeVar", ""): (3, 12),
    ("ParamSpec", ""): (3, 12),
    ("TypeVarTuple", ""): (3, 12),
    ("TypeVar", "default_value"): (3, 13),
    ("ParamSpec", "default_value"): (3, 13),
    ("TypeVarTuple", "default_value"): (3, 13),
    ("TemplateStr", ""): (3, 14),
    ("Interpolation", ""): (3, 14),
}

# The node classes whose `values` are the parts of a string.
STRING_PARTS = frozenset({"JoinedStr", "TemplateStr"})

# The written fields of each node class that this process found, after the field check.
_plans: dict[type, tuple[str, ...]] = {}


class UnknownSyntax(Exception):  # noqa: N818 - the name tells what the error is about
    """A node class, a field, or a literal value that the tables of this module do not include."""

    def __init__(self, item: str) -> None:
        version = sys.version.split()[0]
        super().__init__(
            f"The syntax text of systemap does not include {item} of Python {version}. "
            "The extraction stopped, because a text without this item can hide a source change."
        )
        self.item = item
        self.version = version


def text(node: ast.AST) -> str:
    """Give the syntax text of a node and of all the nodes below it."""
    out: list[str] = []
    _write(node, out)
    return "".join(out)


def _plan(node: ast.AST) -> tuple[str, ...]:
    """Give the fields to write for the class of the node. Do a check of its fields first."""
    name = type(node).__name__
    fields = FIELDS.get(name)
    if fields is None:
        raise UnknownSyntax(f"the node class {name}")
    present = {field for field, _value in ast.iter_fields(node)}
    extra = sorted(present - set(fields))
    if extra:
        raise UnknownSyntax(f"the field {name}.{extra[0]}")
    for field in fields:
        since = SINCE.get((name, field))
        if field not in present and (since is None or sys.version_info[:2] >= since):
            raise UnknownSyntax(f"a node {name} without the field {field}")
    _plans[type(node)] = fields
    return fields


def _write(node: ast.AST, out: list[str]) -> None:
    kind = type(node)
    fields = _plans.get(kind)
    if fields is None:
        fields = _plan(node)
    out.append(kind.__name__ + "(")
    first = True
    for field in fields:
        value = _value(node, kind.__name__, field)
        if value is None:
            continue
        out.append(f"{field}=" if first else f", {field}=")
        first = False
        if isinstance(value, ast.AST):
            _write(value, out)
        else:
            _write_value(value, out)
    out.append(")")


def _value(node: ast.AST, name: str, field: str) -> object:
    """Give the value of a field, or None for a field that the text does not include."""
    value: object = getattr(node, field, None)
    if not isinstance(value, list):
        return value
    if name in STRING_PARTS:
        value = [part for part in value if not _empty_string(part)]
    return value or None


def _write_value(value: object, out: list[str]) -> None:
    """Write a list or a literal value. `_write` writes a node field directly, so that a
    node below a node uses one stack frame, as in `ast.dump`."""
    if isinstance(value, list):
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(", ")
            if isinstance(item, ast.AST):
                _write(item, out)
            else:
                out.append(_literal(item))
        out.append("]")
    else:
        out.append(_literal(value))


def _empty_string(node: object) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and not node.value


# An integer with more bits than this has more than 600 decimal digits. The lowest
# conversion limit that Python accepts is 640 digits, thus `repr` of a smaller integer
# always operates.
INT_BITS = 2000

_LITERALS = (str, bytes, bool, int, float, complex, type(None), type(...))


def _literal(value: object) -> str:
    if not isinstance(value, _LITERALS):
        raise UnknownSyntax(f"a literal value of the type {type(value).__name__}")
    if isinstance(value, int) and value.bit_length() > INT_BITS:
        # The decimal text of a large integer depends on the conversion limit of the
        # process (PYTHONINTMAXSTRDIGITS). The hexadecimal text does not.
        return hex(value)
    return repr(value)
