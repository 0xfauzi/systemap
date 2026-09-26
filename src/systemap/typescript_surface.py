"""Read TypeScript declarations into the public names systemap can explain."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

TS = Language(tree_sitter_typescript.language_typescript())
TSX = Language(tree_sitter_typescript.language_tsx())
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
TYPE_NODES = {
    "class_declaration",
    "abstract_class_declaration",
    "interface_declaration",
    "type_alias_declaration",
    "enum_declaration",
}


def _tree(raw: str, path: str = "") -> Node:
    language = TSX if path.endswith(".tsx") else TS
    return Parser(language).parse(raw.encode("utf-8")).root_node


def _root(raw: str, path: str = "") -> Node | None:
    root = _tree(raw, path)
    return None if root.has_error else root


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(node: Node | None) -> str:
    return (node.text or b"").decode("utf-8") if node is not None else ""


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _string(node: Node | None) -> str:
    if node is None or node.type != "string":
        return ""
    fragment = next(
        (child for child in node.named_children if child.type == "string_fragment"), None
    )
    return _text(fragment)


def _source(node: Node) -> str:
    return _string(node.child_by_field_name("source"))


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
    out: list[str] = []
    for method in body.named_children:
        if method.type not in ("method_definition", "method_signature"):
            continue
        modifiers = {
            _text(child)
            for child in method.named_children
            if child.type == "accessibility_modifier"
        }
        if not modifiers & {"private", "protected"}:
            out.append(_header(method))
    return out


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
    is_error = node.type in (
        "class_declaration",
        "abstract_class_declaration",
    ) and "Error" in _text(heritage)
    return {"name": public, "methods": _public_methods(node)}, is_error


def _binding_names(node: Node | None) -> list[str]:
    if node is None:
        return []
    if node.type in ("identifier", "shorthand_property_identifier_pattern"):
        return [_text(node)]
    if node.type == "pair_pattern":
        return _binding_names(node.child_by_field_name("value"))
    if node.type in ("rest_pattern", "assignment_pattern"):
        return _binding_names(node.named_children[0] if node.named_children else None)
    return [name for child in node.named_children for name in _binding_names(child)]


def _declaration(node: Node) -> Node | None:
    declaration = node.child_by_field_name("declaration")
    if declaration is not None and declaration.type == "ambient_declaration":
        return next(iter(declaration.named_children), declaration)
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
        return {record["name"]: "error" if is_error else "class"}
    if declaration.type == "internal_module":
        return _namespace_kinds(declaration)
    if declaration.type == "lexical_declaration":
        return _variable_kinds(declaration)
    return {}


def _namespace_kinds(declaration: Node) -> dict[str, str]:
    name = next((child for child in declaration.named_children if child.type == "identifier"), None)
    return {_text(name): "object"} if name is not None else {}


def _variable_kinds(declaration: Node) -> dict[str, str]:
    out: dict[str, str] = {}
    for variable in (
        child for child in declaration.named_children if child.type == "variable_declarator"
    ):
        value = variable.child_by_field_name("value")
        kind = (
            "function" if value is not None and value.type in EXPORTED_FUNCTION_NODES else "object"
        )
        out.update((name, kind) for name in _binding_names(variable.child_by_field_name("name")))
    return out


def _reexports(node: Node) -> list[dict[str, Any]]:
    source = _source(node)
    if not source:
        return []
    namespace = next(
        (child for child in node.named_children if child.type == "namespace_export"), None
    )
    if namespace is not None:
        return [_namespace_reexport(namespace, source)]
    clause = next((child for child in node.named_children if child.type == "export_clause"), None)
    if clause is None:
        return [_star_reexport(source)] if any(child.type == "*" for child in node.children) else []
    return _named_reexports(clause, source)


def _namespace_reexport(namespace: Node, source: str) -> dict[str, Any]:
    alias = next((child for child in namespace.named_children if child.type == "identifier"), None)
    return {"name": _text(alias) or "unknown", "kind": "object", "reexport_of": source}


def _star_reexport(source: str) -> dict[str, Any]:
    return {"name": "*", "kind": "reexport", "reexport_of": source, "star": True}


def _named_reexports(clause: Node, source: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for specifier in (child for child in clause.named_children if child.type == "export_specifier"):
        identifiers = [
            child
            for child in specifier.named_children
            if child.type in ("identifier", "type_identifier")
        ]
        if identifiers:
            original, public = _text(identifiers[0]), _text(identifiers[-1])
            entry: dict[str, Any] = {"name": public, "kind": "reexport", "reexport_of": source}
            if public != original:
                entry["defined_as"] = original
            out.append(entry)
    return out


def _local_exports(
    node: Node, kinds: dict[str, str]
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    clause = next((child for child in node.named_children if child.type == "export_clause"), None)
    if clause is None:
        return [], []
    names: list[dict[str, str]] = []
    unknown: list[dict[str, Any]] = []
    for specifier in (child for child in clause.named_children if child.type == "export_specifier"):
        identifiers = [
            child
            for child in specifier.named_children
            if child.type in ("identifier", "type_identifier")
        ]
        if not identifiers:
            continue
        local, public = _text(identifiers[0]), _text(identifiers[-1])
        kind = kinds.get(local, "unknown")
        names.append({"name": public, "kind": kind})
        if kind == "unknown":
            unknown.append(_unknown(node, f"the local export {local!r} could not be classified"))
    return names, unknown


def _unknown(node: Node, reason: str) -> dict[str, Any]:
    return {
        "line": node.start_point.row + 1,
        "reason": reason,
        "source": _one_line(_text(node))[:120],
    }


def parse_problem(raw: str, path: str = "") -> dict[str, Any]:
    """The first parser error, for an otherwise retained module record."""
    root = _tree(raw, path)
    node = next((child for child in _walk(root) if child.type == "ERROR" or child.is_missing), root)
    source = _one_line(_text(node))[:120]
    reason = "TypeScript syntax could not be parsed"
    if source:
        reason += f" near {source!r}"
    return {"line": node.start_point.row + 1, "reason": reason, "source": source}


def _add_function(
    declaration: Node,
    functions: list[dict[str, str]],
    names: list[dict[str, str]],
    default: bool = False,
    name_override: str = "",
) -> None:
    name = (
        _text(declaration.child_by_field_name("name"))
        or name_override
        or ("default" if default else "")
    )
    if not name:
        return
    signature = _header(declaration)
    if declaration.type == "arrow_function":
        signature = _arrow_signature(name, declaration)
    functions.append({"name": name, "signature": signature})
    names.append({"name": name, "kind": "function"})


def _arrow_signature(name: str, node: Node) -> str:
    params = node.child_by_field_name("parameters") or node.child_by_field_name("parameter")
    result = node.child_by_field_name("return_type")
    return f"const {name} = {_text(params)}{_text(result)} =>"


def _add_declaration(
    declaration: Node,
    functions: list[dict[str, str]],
    classes: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    constants: list[dict[str, str]],
    names: list[dict[str, str]],
    default: bool,
) -> bool:
    if declaration.type in EXPORTED_FUNCTION_NODES:
        _add_function(declaration, functions, names, default)
        return True
    if declaration.type in TYPE_NODES:
        record, is_error = _type_record(declaration)
        (errors if is_error else classes).append(record)
        names.append({"name": record["name"], "kind": "error" if is_error else "class"})
        return True
    if declaration.type == "internal_module":
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
    bound_names = _binding_names(variable.child_by_field_name("name"))
    value = variable.child_by_field_name("value")
    if value is None or len(bound_names) != 1:
        names.extend({"name": name, "kind": "object"} for name in bound_names)
        return
    name = bound_names[0]
    if value.type in ("arrow_function", "function_expression"):
        _add_function(value, functions, names, name_override=name)
    elif UPPER_NAME.fullmatch(name):
        constants.append({"name": name, "value": _one_line(_text(value))[:80]})
        names.append({"name": name, "kind": "constant"})
    else:
        names.append({"name": name, "kind": "object"})


def _record_export(export: Node, surface: dict[str, Any], local_kinds: dict[str, str]) -> None:
    reexports = _reexports(export)
    start = len(surface["names"])
    surface["names"].extend(reexports)
    if reexports and any(entry.get("star") for entry in reexports):
        return
    declaration = _declaration(export)
    default = any(child.type == "default" for child in export.children)
    if declaration is None:
        _record_export_without_declaration(export, surface, local_kinds, default, reexports)
        return
    _record_declared_export(export, declaration, surface, default, start)


def _record_export_without_declaration(
    export: Node,
    surface: dict[str, Any],
    local_kinds: dict[str, str],
    default: bool,
    reexports: list[dict[str, Any]],
) -> None:
    value = export.child_by_field_name("value")
    if default and value is not None:
        _record_default_value(export, value, surface)
        return
    local, local_unknown = _local_exports(export, local_kinds) if not reexports else ([], [])
    surface["names"].extend(local)
    surface["unknown"].extend(local_unknown)
    if not local and not reexports:
        surface["unknown"].append(_unknown(export, "the export form has no recorded public name"))


def _record_default_value(export: Node, value: Node, surface: dict[str, Any]) -> None:
    if value.type in ("arrow_function", "function_expression", "generator_function"):
        _add_function(value, surface["functions"], surface["names"], default=True)
        return
    surface["names"].append({"name": "default", "kind": "unknown"})
    surface["unknown"].append(
        _unknown(export, "the default export expression could not be classified")
    )


def _record_declared_export(
    export: Node, declaration: Node, surface: dict[str, Any], default: bool, start: int
) -> None:
    recognized = _add_declaration(
        declaration,
        surface["functions"],
        surface["classes"],
        surface["errors"],
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
            _unknown(export, "the default expression is not a named declaration")
        )
        return
    if added:
        return
    surface["unknown"].append(_unknown(export, "the declaration form is not supported"))
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


def parse_surface(raw: str, path: str = "") -> dict[str, Any] | None:
    """The exported surface of one TypeScript or TSX module, with unknowns explicit."""
    root = _root(raw, path)
    if root is None:
        return None
    functions: list[dict[str, str]] = []
    classes: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    constants: list[dict[str, str]] = []
    names: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    local_kinds = _declared_kinds(root)
    surface = {
        "functions": functions,
        "classes": classes,
        "errors": errors,
        "constants": constants,
        "names": names,
        "unknown": unknown,
    }
    for export in (node for node in root.named_children if node.type == "export_statement"):
        _record_export(export, surface, local_kinds)

    leading = next((node for node in root.named_children if node.type == "comment"), None)
    docstring = _text(leading).removeprefix("/**").removesuffix("*/").strip(" *\n")
    return {
        "docstring": _one_line(docstring),
        "functions": functions,
        "classes": classes,
        "errors": errors,
        "constants": constants,
        "names": names,
        "unknown": unknown,
    }


def test_names(raw: str, path: str = "") -> list[str]:
    """The literal names passed to `test` and `it`, including nested suites."""
    root = _root(raw, path)
    if root is None:
        return []
    out: list[str] = []
    for call in (node for node in _walk(root) if node.type == "call_expression"):
        function = call.child_by_field_name("function")
        if _text(function).rsplit(".", 1)[-1] not in ("test", "it"):
            continue
        arguments = call.child_by_field_name("arguments")
        first = arguments.named_children[0] if arguments and arguments.named_children else None
        if name := _string(first):
            out.append(name)
    return out
