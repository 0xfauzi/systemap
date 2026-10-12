"""The model reader makes MODEL and MEANING from a model file. It runs no code from the file.

The reader parses the file into a syntax tree. It accepts only the statements and values
that this module lists, and it refuses all other syntax before it makes a value. A model
file can import a file in the same directory. The same reader reads that file.

The person who runs a command can set SYSTEMAP_TRUST_MODEL_CODE=1 in the environment.
Then systemap runs the model file as Python code, as systemap 2.0 did. The repository
cannot give this permission: systemap does not read it from a repository file.

Accepted statements: the module docstring, `from __future__ import annotations`, an
import of model names from `systemap` or `systemap.model`, `import NAME` for the file
NAME.py beside the model file, `NAME = value`, `NAME: annotation = value` (the reader
does not read the annotation), and `NAME = tuple[...]` and similar type aliases.

Accepted values: str, int, float, bool and None constants, a minus sign before a number,
tuples, lists, sets and dictionaries of values, calls of the model classes with
positional and keyword values, names that an earlier statement in the same file
defined, and `FILE.NAME` for a value in an imported file.
"""

from __future__ import annotations

import ast
import contextlib
import os
import sys
import types
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from systemap import model as schema

TRUST = "SYSTEMAP_TRUST_MODEL_CODE"
# The limits for one load. A file of MAX_BYTES with the most syntax nodes for its size
# takes about 260 MB to parse (bench/jev/README.md). The self-map files contain 72 KB.
# MAX_NODES limits the values that the check examines and that the reader makes.
MAX_BYTES = 512 * 1024
MAX_NODES = 100_000
MAX_FILES = 16
MAX_DEPTH = 32
# A name refers to a value without a copy. A value that names refer to many times can
# become very large when a later step writes it out in full. Each value has a limit
# for its full size: one unit for each value and one unit for each character.
MAX_EXPANDED = 8_000_000

MODEL_CLASSES: dict[str, type] = {
    cls.__name__: cls
    for cls in (
        schema.Component,
        schema.Container,
        schema.Flow,
        schema.Invariant,
        schema.Journey,
        schema.Layer,
        schema.Meaning,
        schema.Model,
        schema.Region,
        schema.Step,
    )
}
MODEL_CONSTANTS: dict[str, tuple[str, ...]] = {
    "AGENT_KINDS": schema.AGENT_KINDS,
    "KINDS": schema.KINDS,
    "STANDARD_KINDS": schema.STANDARD_KINDS,
}
# The order of systemap.__all__.
EXPORTS = ("AGENT_KINDS", "KINDS", "STANDARD_KINDS", *sorted(MODEL_CLASSES))
SCHEMA_MODULES = ("systemap", "systemap.model")
GENERIC_TYPES = frozenset({"dict", "frozenset", "list", "set", "tuple"})
TYPE_NAMES = frozenset({"bool", "bytes", "float", "int", "object", "str"})
CONSTANT_TYPES = (str, int, float, bool, type(None))

VALUE = "value"
CLASS = "class"
ALIAS = "type alias"

ADVICE = (
    "systemap does not run code from a model file. Write literal values: strings, numbers, "
    "True, False, None, tuples, lists, sets, dictionaries, and calls of the model classes. "
    f"If you know that the code in this repository is safe, set {TRUST}=1 in the "
    "environment of the command. Then systemap runs the model file as Python code."
)
IMPORT_ADVICE = "Import only model names from systemap, and files in the same directory. "
NESTING = f"Write the values with less nesting, or give a part of the value a name. {ADVICE}"


class ModelFileError(Exception):
    """The reader refuses a model file, or the file does not give its values."""


@dataclass
class Source:
    """One accepted model file: its syntax tree, its names, and the files it imports."""

    path: Path
    label: str
    tree: ast.Module
    names: dict[str, str] = field(default_factory=dict)
    sizes: dict[str, int] = field(default_factory=dict)
    imports: dict[str, Source] = field(default_factory=dict)


@dataclass
class _Budget:
    """What the files of one load can still use."""

    data: int = MAX_BYTES
    nodes: int = MAX_NODES
    files: int = MAX_FILES


@dataclass
class _Reader:
    """The files of one load: the directory, the limits, and the files on the import path."""

    folder: Path
    labels: PurePosixPath
    budget: _Budget = field(default_factory=_Budget)
    done: dict[Path, Source] = field(default_factory=dict)
    stack: list[Path] = field(default_factory=list)

    def source(self, path: Path, label: str) -> Source:
        key = path.resolve()
        if key in self.done:
            return self.done[key]
        text, tree = _parse(path, label, self.budget)
        found = Source(key, label, tree)
        self.stack.append(key)
        _File(found, text, self).check()
        self.stack.pop()
        self.done[key] = found
        return found

    def sibling(self, name: str, node: ast.stmt, file: _File) -> Source:
        path = self.folder / f"{name}.py"
        if not path.is_file():
            raise file.refuse(
                node, f"an import of {name}, which is not a file beside the model file"
            )
        resolved = path.resolve()
        if resolved.parent != self.folder:
            raise file.refuse(
                node,
                f"an import of {name}, which is a link to a file outside the directory of "
                "the model file",
            )
        if resolved in self.stack:
            raise file.refuse(node, f"an import cycle: {name}.py imports this file")
        return self.source(resolved, str(self.labels / f"{name}.py"))


def _parse(path: Path, label: str, budget: _Budget) -> tuple[str, ast.Module]:
    """This function reads at most the remaining bytes, then parses and counts the nodes."""
    budget.files -= 1
    if budget.files < 0:
        raise ModelFileError(f"{label}: The model imports more than {MAX_FILES} files.")
    with path.open("rb") as handle:
        data = handle.read(budget.data + 1)
    if len(data) > budget.data:
        raise ModelFileError(
            f"{label}: The model files contain more than {MAX_BYTES} bytes. "
            "Move a part of the map into a nested map."
        )
    budget.data -= len(data)
    try:
        text = data.decode("utf-8-sig")
        tree = ast.parse(text, filename=label)
    except UnicodeDecodeError as exc:
        raise ModelFileError(f"{label}: The file is not UTF-8 text: {exc.reason}.") from exc
    except SyntaxError as exc:
        raise ModelFileError(f"{label}:{exc.lineno or 0}: Python syntax error: {exc.msg}.") from exc
    except (MemoryError, RecursionError, ValueError) as exc:
        raise ModelFileError(
            f"{label}: The parser cannot read values that are nested this deeply. {NESTING}"
        ) from exc
    return text, tree


def _dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


Segment = Callable[[ast.AST], str]


def _construct(node: ast.AST, segment: Segment) -> str:
    """This function names a refused construct for the reader of the message."""
    namer = _NAMERS.get(type(node))
    if namer is not None:
        return namer(node, segment)
    return _PHRASES.get(type(node)) or f"the Python syntax {type(node).__name__}"


def _definition(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, _: Segment) -> str:
    if node.decorator_list:
        return "a decorator"
    return "a class definition" if isinstance(node, ast.ClassDef) else "a function definition"


def _statement_value(node: ast.Expr, segment: Segment) -> str:
    if isinstance(node.value, ast.Call):
        return _construct(node.value, segment)
    return "a value that has no name"


def _call_construct(node: ast.Call, segment: Segment) -> str:
    if isinstance(node.func, ast.Lambda):
        return "a lambda expression"
    return f"a call of {segment(node.func)}"


_NAMERS: dict[type[ast.AST], Callable[[Any, Segment], str]] = {
    ast.FunctionDef: _definition,
    ast.AsyncFunctionDef: _definition,
    ast.ClassDef: _definition,
    ast.Expr: _statement_value,
    ast.Call: _call_construct,
    ast.Attribute: lambda node, segment: f"the attribute {segment(node)}",
    ast.Name: lambda node, _: f"the name {node.id}",
}
_PHRASES: dict[type[ast.AST], str] = {
    ast.Lambda: "a lambda expression",
    ast.ListComp: "a comprehension",
    ast.SetComp: "a comprehension",
    ast.DictComp: "a comprehension",
    ast.GeneratorExp: "a comprehension",
    ast.JoinedStr: "an f-string",
    ast.Starred: "an unpacked value (*)",
    ast.BinOp: "an operator expression",
    ast.BoolOp: "an operator expression",
    ast.UnaryOp: "an operator expression",
    ast.Compare: "a comparison",
    ast.IfExp: "a conditional expression",
    ast.NamedExpr: "an assignment expression (:=)",
    ast.Subscript: "an index or a slice",
}


@dataclass
class _File:
    """The check of one file. A name has a kind: a value, a model class, a type alias, or
    an imported file."""

    source: Source
    text: str
    reader: _Reader
    scope: dict[str, str | Source] = field(default_factory=dict)

    def segment(self, node: ast.AST) -> str:
        text = ast.get_source_segment(self.text, node) or type(node).__name__
        first = text.splitlines()[0] if text else text
        return first if len(first) <= 60 else first[:57] + "..."

    def refuse(self, node: ast.AST, construct: str, advice: str = "") -> ModelFileError:
        line = getattr(node, "lineno", 0)
        return ModelFileError(
            f"{self.source.label}:{line}: The model file contains {construct}. {advice}{ADVICE}"
        )

    def check(self) -> None:
        for index, stmt in enumerate(self.source.tree.body):
            if index == 0 and _docstring(stmt):
                continue
            check = _STATEMENTS.get(type(stmt))
            if check is None:
                decorators = getattr(stmt, "decorator_list", None)
                raise self.refuse(
                    decorators[0] if decorators else stmt, _construct(stmt, self.segment)
                )
            check(self, stmt)
        self.source.names = {
            name: kind if isinstance(kind, str) else "file" for name, kind in self.scope.items()
        }

    def bind(self, node: ast.AST, name: str, kind: str | Source, size: int = 0) -> None:
        if _dunder(name):
            raise self.refuse(node, f"the special name {name}")
        self.scope[name] = kind
        self.source.sizes[name] = size

    def count(self, node: ast.expr, depth: int) -> None:
        """This method counts one value against the limits of the load."""
        if depth > MAX_DEPTH:
            raise self.refuse(node, f"values that are nested more than {MAX_DEPTH} levels", NESTING)
        self.reader.budget.nodes -= 1
        if self.reader.budget.nodes < 0:
            raise ModelFileError(
                f"{self.source.label}: The model files contain more than {MAX_NODES} values. "
                "Move a part of the map into a nested map."
            )

    def value(self, node: ast.expr, depth: int = 1) -> int:
        """This method accepts a value or refuses it. It gives the full size of the value."""
        self.count(node, depth)
        check = _VALUES.get(type(node))
        if check is None:
            raise self.refuse(node, _construct(node, self.segment))
        return check(self, node, depth)

    def type_alias(self, node: ast.expr, depth: int = 1) -> None:
        self.count(node, depth)
        if isinstance(node, ast.Tuple):
            for item in node.elts:
                self.type_alias(item, depth + 1)
        elif _generic(node, self.scope):
            assert isinstance(node, ast.Subscript)
            self.type_alias(node.slice, depth + 1)
        elif not _type_name(node, self.scope):
            raise self.refuse(node, f"{_construct(node, self.segment)} in a type alias")


def _docstring(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _generic(node: ast.expr, scope: dict[str, str | Source]) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id in GENERIC_TYPES
        and node.value.id not in scope
    )


def _type_name(node: ast.expr, scope: dict[str, str | Source]) -> bool:
    if isinstance(node, ast.Constant):
        return node.value is None or node.value is Ellipsis
    if not isinstance(node, ast.Name):
        return False
    kind = scope.get(node.id)
    return kind in (CLASS, ALIAS) or (kind is None and node.id in TYPE_NAMES)


# ---- statements ---------------------------------------------------------------------------


def _from_import(file: _File, stmt: ast.ImportFrom) -> None:
    if stmt.level:
        raise file.refuse(stmt, "a relative import", IMPORT_ADVICE)
    names = [alias.name for alias in stmt.names]
    if stmt.module == "__future__":
        if names != ["annotations"] or stmt.names[0].asname:
            raise file.refuse(stmt, f"an import of {', '.join(names)} from __future__")
        return
    if stmt.module not in SCHEMA_MODULES:
        raise file.refuse(stmt, f"an import from {stmt.module}", IMPORT_ADVICE)
    for alias in stmt.names:
        if alias.name not in EXPORTS:
            raise file.refuse(
                stmt,
                f"an import of {alias.name} from {stmt.module}",
                f"Use a name that systemap exports for a model: {', '.join(EXPORTS)}. ",
            )
        kind = CLASS if alias.name in MODEL_CLASSES else VALUE
        file.bind(stmt, alias.asname or alias.name, kind, 1)


def _import(file: _File, stmt: ast.Import) -> None:
    for alias in stmt.names:
        if "." in alias.name or _dunder(alias.name):
            raise file.refuse(stmt, f"an import of {alias.name}", IMPORT_ADVICE)
        imported = file.reader.sibling(alias.name, stmt, file)
        file.source.imports[alias.name] = imported
        file.bind(stmt, alias.asname or alias.name, imported)


def _assign(file: _File, stmt: ast.Assign) -> None:
    target = stmt.targets[0]
    if len(stmt.targets) != 1 or not isinstance(target, ast.Name):
        raise file.refuse(stmt, "an assignment that is not NAME = value")
    _bind_value(file, stmt, target.id, stmt.value)


def _annotated(file: _File, stmt: ast.AnnAssign) -> None:
    if not isinstance(stmt.target, ast.Name) or stmt.value is None:
        raise file.refuse(stmt, "an annotation that is not NAME: annotation = value")
    _bind_value(file, stmt, stmt.target.id, stmt.value)


def _bind_value(file: _File, stmt: ast.stmt, name: str, value: ast.expr) -> None:
    if _generic(value, file.scope):
        file.type_alias(value)
        file.bind(stmt, name, ALIAS)
        return
    size = file.value(value)
    if size > MAX_EXPANDED:
        raise file.refuse(
            stmt,
            f"the value of {name}, which has more than {MAX_EXPANDED} parts and characters "
            "when each name in it is written out",
        )
    file.bind(stmt, name, VALUE, size)


_STATEMENTS: dict[type[ast.AST], Callable[[_File, Any], None]] = {
    ast.ImportFrom: _from_import,
    ast.Import: _import,
    ast.Assign: _assign,
    ast.AnnAssign: _annotated,
}


# ---- values -------------------------------------------------------------------------------


def _constant(file: _File, node: ast.Constant, depth: int) -> int:
    if type(node.value) not in CONSTANT_TYPES:
        raise file.refuse(node, f"the constant {file.segment(node)}")
    return 1 + len(node.value) if isinstance(node.value, str) else 1


def _items(file: _File, node: ast.Tuple | ast.List | ast.Set, depth: int) -> int:
    size = 1
    for item in node.elts:
        size += file.value(item, depth + 1)
    return size


def _dict(file: _File, node: ast.Dict, depth: int) -> int:
    size = 1
    for key, item in zip(node.keys, node.values, strict=True):
        if key is None:
            raise file.refuse(item, "an unpacked dictionary (**)")
        size += file.value(key, depth + 1) + file.value(item, depth + 1)
    return size


def _negative(file: _File, node: ast.UnaryOp, depth: int) -> int:
    operand = node.operand
    number = isinstance(operand, ast.Constant) and type(operand.value) in (int, float)
    if not isinstance(node.op, ast.USub) or not number:
        raise file.refuse(node, "an operator expression")
    return 1


def _name(file: _File, node: ast.Name, depth: int) -> int:
    kind = file.scope.get(node.id)
    if kind == VALUE:
        return file.source.sizes[node.id]
    advice = ""
    if _dunder(node.id):
        construct = f"the special name {node.id}"
    elif kind is None:
        construct = f"the name {node.id}, which the file does not define before this line"
        if node.id in EXPORTS:
            advice = f"Add {node.id} to the import from systemap. "
    elif kind == CLASS:
        construct = f"the model class {node.id} as a value"
    elif kind == ALIAS:
        construct = f"the type alias {node.id} as a value"
        advice = "Use a type alias only in an annotation. "
    else:
        construct = f"the imported file {node.id} as a value"
    raise file.refuse(node, construct, advice)


def _attribute(file: _File, node: ast.Attribute, depth: int) -> int:
    owner = node.value
    imported = file.scope.get(owner.id) if isinstance(owner, ast.Name) else None
    if not isinstance(imported, Source) or imported.names.get(node.attr) != VALUE:
        raise file.refuse(
            node,
            _construct(node, file.segment),
            "Use FILE.NAME only for a value that an imported file beside the model defines. ",
        )
    return imported.sizes[node.attr]


def _call(file: _File, node: ast.Call, depth: int) -> int:
    func = node.func
    if not isinstance(func, ast.Name) or file.scope.get(func.id) != CLASS:
        if isinstance(func, ast.Name) and func.id in EXPORTS:
            _name(file, func, depth)
        raise file.refuse(node, _construct(node, file.segment))
    size = 1
    for arg in node.args:
        if isinstance(arg, ast.Starred):
            raise file.refuse(arg, "an unpacked value (*) in a call")
        size += file.value(arg, depth + 1)
    given: set[str] = set()
    for keyword in node.keywords:
        if keyword.arg is None:
            raise file.refuse(keyword, "an unpacked keyword value (**) in a call")
        if keyword.arg in given:
            raise file.refuse(keyword, f"the keyword {keyword.arg} two times in one call")
        given.add(keyword.arg)
        size += file.value(keyword.value, depth + 1)
    return size


_VALUES: dict[type[ast.AST], Callable[[_File, Any, int], int]] = {
    ast.Constant: _constant,
    ast.Tuple: _items,
    ast.List: _items,
    ast.Set: _items,
    ast.Dict: _dict,
    ast.UnaryOp: _negative,
    ast.Name: _name,
    ast.Attribute: _attribute,
    ast.Call: _call,
}


# ---- building the values of accepted files ------------------------------------------------


@dataclass(frozen=True)
class _Imported:
    """The values of an imported file, for FILE.NAME."""

    values: dict[str, Any]


def _build(source: Source, built: dict[Path, dict[str, Any]]) -> dict[str, Any]:
    """This function makes the values of an accepted file, after the check of all files."""
    if source.path in built:
        return built[source.path]
    space: dict[str, Any] = {}
    for stmt in source.tree.body:
        if isinstance(stmt, ast.Import | ast.ImportFrom):
            space.update(_imported(source, stmt, built))
        elif isinstance(stmt, ast.Assign | ast.AnnAssign):
            _assign_value(source, stmt, space)
    built[source.path] = space
    return space


def _imported(
    source: Source, stmt: ast.Import | ast.ImportFrom, built: dict[Path, dict[str, Any]]
) -> dict[str, Any]:
    """This function gives the names of one accepted import statement."""
    if isinstance(stmt, ast.Import):
        return {
            alias.asname or alias.name: _Imported(_build(source.imports[alias.name], built))
            for alias in stmt.names
        }
    if stmt.module not in SCHEMA_MODULES:
        return {}  # from __future__ import annotations
    return {alias.asname or alias.name: _exported(alias.name) for alias in stmt.names}


def _exported(name: str) -> Any:
    return MODEL_CLASSES.get(name) or MODEL_CONSTANTS[name]


def _assign_value(source: Source, stmt: ast.Assign | ast.AnnAssign, space: dict[str, Any]) -> None:
    """This function makes one value. A type alias has no value: the check accepted a
    subscript only as a type alias."""
    target = stmt.targets[0] if isinstance(stmt, ast.Assign) else stmt.target
    assert isinstance(target, ast.Name) and stmt.value is not None
    if isinstance(stmt.value, ast.Subscript):
        space.pop(target.id, None)
        return
    try:
        space[target.id] = _make(stmt.value, space)
    except (TypeError, ValueError) as exc:
        raise ModelFileError(
            f"{source.label}:{stmt.lineno}: The value of {target.id} is not correct: {exc}."
        ) from exc


def _make(node: ast.expr, space: dict[str, Any]) -> Any:
    maker = _MAKERS[type(node)]
    return maker(node, space)


def _call_value(node: ast.Call, space: dict[str, Any]) -> Any:
    assert isinstance(node.func, ast.Name)
    args = [_make(arg, space) for arg in node.args]
    keywords = {str(k.arg): _make(k.value, space) for k in node.keywords}
    return space[node.func.id](*args, **keywords)


def _dict_value(node: ast.Dict, space: dict[str, Any]) -> dict[Any, Any]:
    return {
        _make(key, space): _make(item, space)
        for key, item in zip(node.keys, node.values, strict=True)
        if key is not None
    }


_MAKERS: dict[type[ast.AST], Callable[[Any, dict[str, Any]], Any]] = {
    ast.Constant: lambda node, space: node.value,
    ast.Tuple: lambda node, space: tuple(_make(item, space) for item in node.elts),
    ast.List: lambda node, space: [_make(item, space) for item in node.elts],
    ast.Set: lambda node, space: {_make(item, space) for item in node.elts},
    ast.Dict: _dict_value,
    ast.UnaryOp: lambda node, space: -node.operand.value,
    ast.Name: lambda node, space: space[node.id],
    ast.Attribute: lambda node, space: space[node.value.id].values[node.attr],
    ast.Call: _call_value,
}


def read(path: Path, label: str) -> dict[str, Any]:
    """This function gives the values of a model file without running its code.

    It checks the file and every imported file first. A refusal gives the file, the line,
    the construct, and the necessary action.
    """
    labels = PurePosixPath(label.replace("\\", "/")).parent
    reader = _Reader(path.parent.resolve(), labels)
    source = reader.source(path, label)
    return _build(source, {})


# ---- the permitted alternative: run the model file as Python code ------------------------


@contextlib.contextmanager
def _beside(folder: Path) -> Iterator[None]:
    """This context puts the model directory on the import path during model execution. It
    restores the path afterward.
    """
    sys.path.insert(0, str(folder))
    held = set(sys.modules)
    try:
        yield
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(folder))
        for name in set(sys.modules) - held:
            found = getattr(sys.modules[name], "__file__", None) or ""
            if found and Path(found).resolve().parent == folder:
                del sys.modules[name]


def _import_problem(label: str, exc: ImportError | NameError) -> str:
    """Give the model import error. Only a systemap name gets the systemap import fix."""
    from systemap import __all__ as exported

    name = getattr(exc, "name", None)
    if isinstance(exc, NameError) and name in exported:
        return f"{label} could not import: {exc}. Add the missing name to the import from systemap."
    if isinstance(exc, ImportError) and name == "systemap":
        names = ", ".join(n for n in exported if not n.startswith("_"))
        return f"{label} could not import: {exc}. Use a name that systemap exports: {names}."
    return f"{label} could not import: {type(exc).__name__}: {exc}"


def run_code(path: Path, label: str) -> dict[str, Any]:
    """This function runs the model file as Python code, only with the permission of the
    person who runs the command. An import error gives a diagnostic."""
    name = f"systemap_model_{abs(hash(str(path)))}"
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    beside = path.parent.resolve()
    try:
        source = path.read_text(encoding="utf-8-sig")
        with _beside(beside):
            exec(compile(source, str(path), "exec"), module.__dict__)  # noqa: S102 - permitted
    except (ImportError, NameError) as exc:
        raise ModelFileError(_import_problem(label, exc)) from exc
    except Exception as exc:  # noqa: BLE001 - the consumer's module may fail any way
        raise ModelFileError(f"{label} could not import: {type(exc).__name__}: {exc}") from exc
    finally:
        sys.modules.pop(name, None)
    return module.__dict__


def load(path: Path, label: str) -> dict[str, Any]:
    """This function gives the names of a model file. It runs the file as code only if the
    environment of the command sets SYSTEMAP_TRUST_MODEL_CODE=1."""
    if os.environ.get(TRUST) == "1":
        return run_code(path, label)
    return read(path, label)
