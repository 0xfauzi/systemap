"""The TypeScript surface reader records declarations and public names."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from tree_sitter import Node

from systemap import unknown_causes
from systemap.typescript_imports import import_names
from systemap.typescript_reexports import export_specifiers, reexport_api, reexports
from systemap.typescript_scopes import pattern_names
from systemap.typescript_syntax import _one_line, _root, _text, docstring, first_named
from systemap.typescript_syntax import parse_problem as parse_problem
from systemap.typescript_tests import test_names as test_names

UPPER_NAME = re.compile(r"[A-Z][A-Z0-9_]{2,}")
FUNCTION_NODES = {
    "function_declaration",
    "generator_function_declaration",
    "function_signature",
}
EXPORTED_FUNCTION_NODES = FUNCTION_NODES | {
    "function_expression",
    "generator_function",
    "arrow_function",
}
CLASS_NODES = {"class_declaration", "abstract_class_declaration"}
# A type declaration that is not a class goes into `types`, with its category.
TYPE_CATEGORIES = {
    "interface_declaration": "interface",
    "type_alias_declaration": "type_alias",
    "enum_declaration": "enum",
}
TYPE_NODES = CLASS_NODES | set(TYPE_CATEGORIES)
# `namespace N {}` and `module N {}` declare the same kind of object.
NAMESPACE_NODES = {"internal_module", "module"}
# The deepest namespace nesting that the API reader reads. 1226 real files have 3 or less.
NAMESPACE_DEPTH = 16
DEEP_NAMESPACE = (
    f"The namespace nesting is deeper than {NAMESPACE_DEPTH} levels. "
    "The reader does not read the declarations in this namespace."
)


def _header(node: Node) -> str:
    body = node.child_by_field_name("body")
    if body is None:
        return _one_line(_text(node).rstrip(";"))
    length = body.start_byte - node.start_byte
    return _one_line((node.text or b"")[:length].decode("utf-8").strip())


def _public_methods(node: Node) -> list[str]:
    body = node.child_by_field_name("body")
    if body is None:
        body = next(
            (
                child
                for child in node.named_children
                if child.type in ("class_body", "interface_body")
            ),
            None,
        )
    if body is None:
        return []
    return [_header(method) for method in body.named_children if _is_public_method(method)]


def _is_public_method(method: Node) -> bool:
    if method.type not in ("method_definition", "method_signature"):
        return False
    name = method.child_by_field_name("name")
    if name is not None and _text(name).startswith("#"):
        return False
    modifiers = {
        _text(child) for child in method.named_children if child.type == "accessibility_modifier"
    }
    return not bool(modifiers & {"private", "protected"})


def _type_record(node: Node) -> tuple[dict[str, Any], bool]:
    name = node.child_by_field_name("name")
    if name is None:
        name = next(
            (
                child
                for child in node.named_children
                if child.type in ("identifier", "type_identifier")
            ),
            None,
        )
    public = _text(name) or "default"
    heritage = next(
        (child for child in node.named_children if child.type == "class_heritage"), None
    )
    is_error = node.type in CLASS_NODES and "Error" in _text(heritage)
    return {"name": public, "methods": _public_methods(node)}, is_error


def _type_kind(node: Node, is_error: bool) -> str:
    """Give the `names` kind of a type declaration: `error`, `class`, or `type`."""
    if is_error:
        return "error"
    return "class" if node.type in CLASS_NODES else "type"


def _type_entry(node: Node, name: str = "") -> tuple[str, dict[str, Any], str]:
    """Give the record group, the record, and the `names` kind of a type declaration.

    A direct export and a local export (`export { Shape }`) use this one classification.
    `name` replaces the declared name, as in `export { Shape as Form }`.
    """
    record, is_error = _type_record(node)
    if name:
        record = {**record, "name": name}
    kind = _type_kind(node, is_error)
    if kind == "type":
        return "types", {**record, "category": TYPE_CATEGORIES[node.type]}, kind
    return ("errors" if is_error else "classes"), record, kind


def _declaration(node: Node) -> Node | None:
    declaration = node.child_by_field_name("declaration")
    if declaration is not None and declaration.type == "ambient_declaration":
        return first_named(declaration) or declaration
    return declaration


def _declared_kinds(root: Node) -> dict[str, str]:
    out: dict[str, str] = {}
    for statement in root.named_children:
        declaration = _declaration(statement) if statement.type == "export_statement" else statement
        if declaration is not None:
            out.update(_declaration_kinds(declaration))
    return out


def _declaration_kinds(declaration: Node) -> dict[str, str]:
    if declaration.type in FUNCTION_NODES:
        name = _text(declaration.child_by_field_name("name"))
        return {name: "function"} if name else {}
    if declaration.type in TYPE_NODES:
        record, is_error = _type_record(declaration)
        return {record["name"]: _type_kind(declaration, is_error)}
    if declaration.type in NAMESPACE_NODES:
        return _namespace_kinds(declaration)
    if declaration.type == "lexical_declaration":
        return _variable_kinds(declaration)
    return {}


def _namespace_kinds(declaration: Node) -> dict[str, str]:
    name = next((child for child in declaration.named_children if child.type == "identifier"), None)
    return {_text(name): "object"} if name is not None else {}


def _is_callable(node: Node | None) -> bool:
    """This function tells if a value is a function. The names, the function records, and
    the export identities use this one test.
    """
    return node is not None and node.type in EXPORTED_FUNCTION_NODES


# The name kind of each record group of a variable.
RECORD_KINDS = {"functions": "function", "constants": "constant"}
# The record groups that `_add_local_records` can write.
RECORD_GROUPS = ("functions", "classes", "errors", "types", "constants")


def _variable_kinds(declaration: Node) -> dict[str, str]:
    """This function gives the `kind` value of each variable name, as an export of
    the declaration gives it.
    """
    out: dict[str, str] = {}
    for variable in (
        child for child in declaration.named_children if child.type == "variable_declarator"
    ):
        names = pattern_names(variable.child_by_field_name("name"))
        value = variable.child_by_field_name("value")
        found = _variable_record(value, names[0]) if len(names) == 1 else None
        kind = RECORD_KINDS[found[0]] if found is not None else "object"
        out.update((name, kind) for name in names)
    return out


def _declaration_nodes(root: Node) -> dict[str, list[Node]]:
    """This function gives the top-level declarations of each local name.

    A function with overload signatures has more than one declaration. A variable has
    its declarator, if the declarator declares only that name.
    """
    out: dict[str, list[Node]] = {}
    for statement in root.named_children:
        declaration = _declaration(statement) if statement.type == "export_statement" else statement
        for name, node in _declared_nodes(declaration):
            out.setdefault(name, []).append(node)
    return out


def _declared_nodes(declaration: Node | None) -> list[tuple[str, Node]]:
    if declaration is None:
        return []
    if declaration.type in FUNCTION_NODES:
        return [(_text(declaration.child_by_field_name("name")), declaration)]
    if declaration.type in TYPE_NODES:
        return [(_type_record(declaration)[0]["name"], declaration)]
    if declaration.type != "lexical_declaration":
        return []
    out: list[tuple[str, Node]] = []
    for variable in (
        child for child in declaration.named_children if child.type == "variable_declarator"
    ):
        names = pattern_names(variable.child_by_field_name("name"))
        if len(names) == 1:
            out.append((names[0], variable))
    return out


@dataclass(frozen=True)
class _Module:
    """The facts of one module that each export statement can use.

    `source` is the module text. The syntax tree does not contain all of the module text.
    """

    local_names: dict[str, dict[str, Any]]
    declarations: dict[str, list[Node]]
    source: bytes


def _local_exports(node: Node, module: _Module, surface: dict[str, Any]) -> bool:
    """This function records `export { name }` for a declared or an imported local name,
    and tells if the statement gives a public name.

    An imported name is a re-export of its source module. A declared name gets the
    declaration records, with the public name.
    """
    specifiers = export_specifiers(node)
    for local, public, type_only in specifiers:
        entry = _local_entry(public, module.local_names.get(local, {"kind": "unknown"}))
        if type_only:
            entry["type_only"] = True
        surface["names"].append(entry)
        _add_local_records(module.declarations.get(local, []), public, surface)
        if local not in module.local_names:
            surface["unknown"].append(
                _unknown(node, f"the local export {local!r} has an unknown declaration kind.")
            )
    return bool(specifiers)


def _local_entry(public: str, known: dict[str, Any]) -> dict[str, Any]:
    entry = {"name": public, **known}
    if entry.get("defined_as") == public:
        del entry["defined_as"]
    return entry


def _add_local_records(nodes: list[Node], public: str, surface: dict[str, Any]) -> None:
    """This function adds the records of local declarations, with the public name.

    `export { Store as Public }` gives the class record `Public`, with the methods of
    `Store`.
    """
    for node in nodes:
        if node.type in TYPE_NODES:
            group, record, _kind = _type_entry(node, public)
            surface[group].append(record)
        elif node.type in FUNCTION_NODES:
            surface["functions"].append({"name": public, "signature": _header(node)})
        elif node.type == "variable_declarator":
            found = _variable_record(node.child_by_field_name("value"), public)
            if found is not None:
                surface[found[0]].append(found[1])


def _unknown(node: Node, reason: str) -> dict[str, Any]:
    return {
        "line": node.start_point.row + 1,
        "reason": reason,
        "source": _one_line(_text(node))[:120],
        "cause": unknown_causes.DECLARATION,
    }


def _add_function(
    declaration: Node,
    functions: list[dict[str, str]],
    names: list[dict[str, str]],
    default: bool = False,
    name_override: str = "",
) -> None:
    name = (
        name_override
        or _text(declaration.child_by_field_name("name"))
        or ("default" if default else "")
    )
    if not name:
        return
    signature = _header(declaration)
    if declaration.type == "arrow_function":
        signature = _arrow_signature(name, declaration)
    functions.append({"name": name, "signature": signature})
    _add_name(names, {"name": name, "kind": "function"})


def _add_name(names: list[dict[str, str]], entry: dict[str, str]) -> None:
    """This function adds a public name one time. Overload signatures give one name."""
    if entry not in names:
        names.append(entry)


def _arrow_signature(name: str, node: Node) -> str:
    params = node.child_by_field_name("parameters") or node.child_by_field_name("parameter")
    result = node.child_by_field_name("return_type")
    return f"const {name} = {_text(params)}{_text(result)} =>"


def _add_declaration(
    declaration: Node,
    functions: list[dict[str, str]],
    classes: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    types: list[dict[str, Any]],
    constants: list[dict[str, str]],
    names: list[dict[str, str]],
    default: bool,
) -> bool:
    if declaration.type in EXPORTED_FUNCTION_NODES:
        _add_function(declaration, functions, names, default)
        return True
    if declaration.type in TYPE_NODES:
        group, record, kind = _type_entry(declaration)
        {"types": types, "errors": errors, "classes": classes}[group].append(record)
        names.append({"name": record["name"], "kind": kind})
        return True
    if declaration.type in NAMESPACE_NODES:
        if _add_namespace(declaration, names):
            return True
    if declaration.type == "lexical_declaration":
        _add_variables(declaration, functions, constants, names)
        return True
    if default:
        names.append({"name": "default", "kind": "unknown"})
        return False
    return False


def _add_namespace(declaration: Node, names: list[dict[str, str]]) -> bool:
    kinds = _namespace_kinds(declaration)
    if not kinds:
        return False
    names.extend({"name": name, "kind": kind} for name, kind in kinds.items())
    return True


def _add_variables(
    declaration: Node,
    functions: list[dict[str, str]],
    constants: list[dict[str, str]],
    names: list[dict[str, str]],
) -> None:
    for variable in (
        child for child in declaration.named_children if child.type == "variable_declarator"
    ):
        _add_variable(variable, functions, constants, names)


def _add_variable(
    variable: Node,
    functions: list[dict[str, str]],
    constants: list[dict[str, str]],
    names: list[dict[str, str]],
) -> None:
    bound_names = pattern_names(variable.child_by_field_name("name"))
    value = variable.child_by_field_name("value")
    if value is None or len(bound_names) != 1:
        names.extend({"name": name, "kind": "object"} for name in bound_names)
        return
    name = bound_names[0]
    if _is_callable(value):
        _add_function(value, functions, names, name_override=name)
    elif UPPER_NAME.fullmatch(name):
        constants.append({"name": name, "value": _one_line(_text(value))[:80]})
        names.append({"name": name, "kind": "constant"})
    else:
        names.append({"name": name, "kind": "object"})


def _variable_record(value: Node | None, name: str) -> tuple[str, dict[str, str]] | None:
    """This function gives the record group and the record of a variable with one name,
    as `_add_variable` records it. An object has no record.
    """
    if value is None:
        return None
    if _is_callable(value):
        signature = (
            _arrow_signature(name, value) if value.type == "arrow_function" else _header(value)
        )
        return "functions", {"name": name, "signature": signature}
    if UPPER_NAME.fullmatch(name):
        return "constants", {"name": name, "value": _one_line(_text(value))[:80]}
    return None


def _record_export(export: Node, surface: dict[str, Any], module: _Module) -> None:
    found = reexports(export, module.source)
    start = len(surface["names"])
    surface["names"].extend(found)
    if found and any(entry.get("star") for entry in found):
        return
    declaration = _declaration(export)
    default = any(child.type == "default" for child in export.children)
    if declaration is None:
        _record_export_without_declaration(export, surface, module, default, found)
        return
    _record_declared_export(export, declaration, surface, default, start)


def _record_export_without_declaration(
    export: Node,
    surface: dict[str, Any],
    module: _Module,
    default: bool,
    found: list[dict[str, Any]],
) -> None:
    value = export.child_by_field_name("value")
    if default and value is not None:
        _record_default_value(export, value, surface, module.local_names)
        _add_default_records(value, module, surface)
        return
    local = _local_exports(export, module, surface) if not found else False
    if not local and not found and not _empty_export(export):
        surface["unknown"].append(_unknown(export, "The export form has no recorded public name."))


def _empty_export(export: Node) -> bool:
    """This function tells if the statement is `export {}`, which only marks a module."""
    clause = next((child for child in export.named_children if child.type == "export_clause"), None)
    return clause is not None and not clause.named_children


def _record_default_value(
    export: Node, value: Node, surface: dict[str, Any], local_names: dict[str, dict[str, str]]
) -> None:
    if _is_callable(value):
        _add_function(value, surface["functions"], surface["names"], name_override="default")
        return
    entry = _default_name(value, local_names)
    surface["names"].append(entry)
    surface["unknown"].extend(_default_problems(export, entry))


def _add_default_records(value: Node, module: _Module, surface: dict[str, Any]) -> None:
    """This function adds the records of a local declaration for `export default name`.

    The records keep the local name, which `defined_as` gives, as for
    `export default class Store`. A record that the surface has already is not added.
    """
    if value.type != "identifier":
        return
    found: dict[str, Any] = {group: [] for group in RECORD_GROUPS}
    _add_local_records(module.declarations.get(_text(value), []), _text(value), found)
    for group, records in found.items():
        surface[group].extend(record for record in records if record not in surface[group])


def _default_problems(export: Node, entry: dict[str, str]) -> list[dict[str, Any]]:
    if entry["kind"] != "unknown":
        return []
    return [_unknown(export, "The default export expression has an unknown declaration kind.")]


def _default_name(value: Node, local_names: dict[str, dict[str, str]]) -> dict[str, str]:
    """This function gives the record of `export default name` for a local or imported
    name, or a record with kind unknown.
    """
    local = _text(value) if value.type == "identifier" else ""
    if local not in local_names:
        return {"name": "default", "kind": "unknown"}
    return {"name": "default", "defined_as": local, **local_names[local]}


def _record_declared_export(
    export: Node, declaration: Node, surface: dict[str, Any], default: bool, start: int
) -> None:
    recognized = _add_declaration(
        declaration,
        surface["functions"],
        surface["classes"],
        surface["errors"],
        surface["types"],
        surface["constants"],
        surface["names"],
        default,
    )
    if recognized:
        if default:
            _rename_default_names(surface["names"], start)
        return
    _record_unknown_declaration(export, declaration, surface, default, start)


def _rename_default_names(names: list[dict[str, Any]], start: int) -> None:
    for name in names[start:]:
        if name["name"] != "default":
            name["defined_as"] = name["name"]
            name["name"] = "default"


def _record_unknown_declaration(
    export: Node,
    declaration: Node,
    surface: dict[str, Any],
    default: bool,
    start: int,
) -> None:
    added = surface["names"][start:]
    if default and added and added[-1].get("name") == "default":
        surface["unknown"].append(
            _unknown(export, "The default expression is not a named declaration.")
        )
        return
    if added:
        return
    surface["unknown"].append(_unknown(export, "The parser cannot read this declaration form."))
    _record_unknown_name(declaration, surface["names"])


def _record_unknown_name(declaration: Node, names: list[dict[str, Any]]) -> None:
    candidate = next(
        (
            child
            for child in declaration.named_children
            if child.type in ("identifier", "type_identifier")
        ),
        None,
    )
    if candidate is not None:
        names.append({"name": _text(candidate), "kind": "unknown"})


def _syntax(node: Node, *, omit_body: bool = False) -> str:
    """This function calculates a token identity without layout or callable implementation
    bodies.
    """
    body = node.child_by_field_name("body") if omit_body else None
    tokens: list[str] = []
    stack = [node]  # A list is the stack, not recursion: a deep tree is permitted.
    while stack:
        part = stack.pop()
        if part == body or part.type == "comment":
            continue
        if not part.children:
            tokens.append(_text(part))
            continue
        callable_body = (
            part.child_by_field_name("body")
            if omit_body and part.type in EXPORTED_FUNCTION_NODES
            else None
        )
        stack.extend(child for child in reversed(part.children) if child != callable_body)
    return "\x1f".join(tokens)


def _type_definition(node: Node) -> str:
    if node.type not in CLASS_NODES:
        return _syntax(node)
    body = node.child_by_field_name("body")
    if body is None:
        return _syntax(node)
    members: list[str] = []
    for member in body.named_children:
        if member.type == "class_static_block":
            continue
        name = member.child_by_field_name("name")
        if name is not None and _text(name).startswith("#"):
            continue
        modifiers = {
            _text(child)
            for child in member.named_children
            if child.type == "accessibility_modifier"
        }
        if modifiers & {"private", "protected"}:
            continue
        members.append(_syntax(member, omit_body=True))
    return _syntax(node, omit_body=True) + "\n" + "\n".join(members)


@dataclass(frozen=True)
class _ApiContext:
    """The facts for the export identities of one module. `definitions` keeps the
    definition of each namespace node, thus the reader reads each namespace one time."""

    source: bytes
    definitions: dict[tuple[str, int, int], str] = field(default_factory=dict)
    unknown: list[dict[str, Any]] = field(default_factory=list)


def _namespace_definition(node: Node, context: _ApiContext) -> str:
    """This function gives the header and the body export identities of a namespace. If
    the nesting is too deep, it gives the body text and records an unknown declaration."""
    key = (node.type, node.start_byte, node.end_byte)
    if key in context.definitions:
        return context.definitions[key]
    body = node.child_by_field_name("body")
    if body is not None and _namespace_depth(node) >= NAMESPACE_DEPTH:
        context.unknown.append(_unknown(node, DEEP_NAMESPACE))
        exports = "unread:" + _text(body)
    else:
        exports = json.dumps(_exported_api(body, context) if body else [], sort_keys=True)
    context.definitions[key] = _syntax(node, omit_body=True) + "\n" + exports
    return context.definitions[key]


def _namespace_depth(node: Node) -> int:
    """This function gives the number of namespaces that contain the node."""
    depth, parent = 0, node.parent
    while parent is not None:
        depth, parent = depth + int(parent.type in NAMESPACE_NODES), parent.parent
    return depth


def _declaration_api(node: Node, context: _ApiContext) -> list[tuple[str, str, str]]:
    if node.type in FUNCTION_NODES:
        name = _text(node.child_by_field_name("name"))
        return [(name, "operations", _syntax(node, omit_body=True))] if name else []
    if node.type in TYPE_NODES:
        record, is_error = _type_record(node)
        return [(record["name"], "refusals" if is_error else "types", _type_definition(node))]
    if node.type in NAMESPACE_NODES:
        definition = _namespace_definition(node, context)
        return [(name, "constants", definition) for name in _namespace_kinds(node)]
    if node.type != "lexical_declaration":
        return []
    return _lexical_api(node)


def _lexical_api(node: Node) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for variable in (child for child in node.named_children if child.type == "variable_declarator"):
        names = pattern_names(variable.child_by_field_name("name"))
        is_function = _is_callable(variable.child_by_field_name("value"))
        definition = _syntax(variable, omit_body=is_function)
        out.extend(
            (name, "operations" if is_function else "constants", definition) for name in names
        )
    return out


# The export identities of each local name: (bucket, fingerprint) pairs.
LocalApi = dict[str, list[tuple[str, str]]]


def _local_api(root: Node, context: _ApiContext) -> LocalApi:
    local: LocalApi = {}
    for statement in root.named_children:
        declaration = _declaration(statement) if statement.type == "export_statement" else statement
        if declaration is None:
            continue
        for name, bucket, definition in _declaration_api(declaration, context):
            local.setdefault(name, []).append((bucket, definition))
    return local


def _exported_api(root: Node, context: _ApiContext) -> list[dict[str, str]]:
    local = _import_api(root) | _local_api(root, context)
    out: list[dict[str, str]] = []
    for statement in (node for node in root.named_children if node.type == "export_statement"):
        out.extend(_export_statement_api(statement, local, context))
    return out


def _import_api(root: Node) -> LocalApi:
    """This function gives the identity of each imported local name, for `export { name }`."""
    return {
        name: [
            (
                "constants",
                f"{'type-reexport' if entry.get('type_only') else 'reexport'}:"
                f"{entry['reexport_of']}:{entry.get('defined_as', '*')}",
            )
        ]
        for name, entry in import_names(root).items()
    }


def _export_statement_api(
    statement: Node, local: LocalApi, context: _ApiContext
) -> list[dict[str, str]]:
    found = reexports(statement, context.source)
    if found:
        return reexport_api(found)
    declared = _declared_export_api(statement, local, context)
    if declared is not None:
        return declared
    return _clause_export_api(statement, local)


def _declared_export_api(
    statement: Node, local: LocalApi, context: _ApiContext
) -> list[dict[str, str]] | None:
    declaration = _declaration(statement)
    default = any(child.type == "default" for child in statement.children)
    if declaration is not None:
        return [
            {"name": "default" if default else name, "bucket": bucket, "fingerprint": definition}
            for name, bucket, definition in _declaration_api(declaration, context)
        ]
    value = statement.child_by_field_name("value")
    if not default or value is None:
        return None
    if value.type == "identifier" and _text(value) in local:
        # `export default serve` has the identity of the declaration of `serve`.
        return [
            {"name": "default", "bucket": bucket, "fingerprint": definition}
            for bucket, definition in local[_text(value)]
        ]
    bucket = "operations" if _is_callable(value) else "constants"
    return [
        {
            "name": "default",
            "bucket": bucket,
            "fingerprint": _syntax(value, omit_body=bucket == "operations"),
        }
    ]


def _clause_export_api(statement: Node, local: LocalApi) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for original, public, type_only in export_specifiers(statement):
        prefix = "type-only:" if type_only else ""
        for bucket, definition in local.get(original, [("constants", f"unresolved:{original}")]):
            out.append({"name": public, "bucket": bucket, "fingerprint": prefix + definition})
    return out


def parse_surface(raw: str, path: str = "") -> dict[str, Any] | None:
    """This function gives the public surface of a TypeScript or TSX module, including
    unknown declarations.
    """
    root = _root(raw, path)
    if root is None:
        return None
    functions: list[dict[str, str]] = []
    classes: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    types: list[dict[str, Any]] = []
    constants: list[dict[str, str]] = []
    names: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    local_names: dict[str, dict[str, Any]] = dict(import_names(root))
    local_names.update((name, {"kind": kind}) for name, kind in _declared_kinds(root).items())
    source = raw.encode("utf-8")
    module = _Module(local_names, _declaration_nodes(root), source)
    surface = {
        "functions": functions,
        "classes": classes,
        "errors": errors,
        "types": types,
        "constants": constants,
        "names": names,
        "unknown": unknown,
    }
    for export in (node for node in root.named_children if node.type == "export_statement"):
        _record_export(export, surface, module)
    api = _exported_api(root, _ApiContext(source, unknown=unknown))
    return {
        "docstring": docstring(root),
        "functions": functions,
        "classes": classes,
        "errors": errors,
        "types": types,
        "constants": constants,
        "names": names,
        "unknown": unknown,
        "api": api,
    }
