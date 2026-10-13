"""The TypeScript re-export reader records the statements `export ... from "module"`.

A type-only re-export gives names for types only. The emitted JavaScript has no value
for these names. Each record of such a name has `type_only` set to `true`.
"""

from __future__ import annotations

from typing import Any

from tree_sitter import Node

from systemap.typescript_syntax import _text, specifier_name, string_value

# The tokens that can follow `export type` in `export type * from` and
# `export type * as name from`.
STAR_TOKENS = ("*", "namespace_export")


def reexports(node: Node, source: bytes) -> list[dict[str, Any]]:
    """This function gives the public-name records of one export statement with a source
    module. The result is empty for a statement without a source module.

    `source` is the module text. If the first parse has an error, the syntax reader removes
    the keyword `type` from `export type *`. Then the tree does not contain that keyword.
    """
    specifier = string_value(node.child_by_field_name("source"))
    if not specifier:
        return []
    entries = _entries(node, specifier)
    if _type_only_statement(node, source):
        for entry in entries:
            entry["type_only"] = True
    return entries


def _entries(node: Node, specifier: str) -> list[dict[str, Any]]:
    namespace = next(
        (child for child in node.named_children if child.type == "namespace_export"), None
    )
    if namespace is not None:
        return [_namespace_reexport(namespace, specifier)]
    clause = next((child for child in node.named_children if child.type == "export_clause"), None)
    if clause is None:
        return (
            [_star_reexport(specifier)] if any(child.type == "*" for child in node.children) else []
        )
    return _named_reexports(node, specifier)


def _type_only_statement(node: Node, source: bytes) -> bool:
    """This function tells if the statement is `export type ... from`."""
    if _has_type_keyword(node):
        return True
    keyword = next((child for child in node.children if child.type == "export"), None)
    star = next((child for child in node.children if child.type in STAR_TOKENS), None)
    if keyword is None or star is None:
        return False
    return source[keyword.end_byte : star.start_byte].strip() == b"type"


def _namespace_reexport(namespace: Node, specifier: str) -> dict[str, Any]:
    alias = next((child for child in namespace.named_children if child.type == "identifier"), None)
    return {"name": _text(alias) or "unknown", "kind": "object", "reexport_of": specifier}


def _star_reexport(specifier: str) -> dict[str, Any]:
    return {"name": "*", "kind": "reexport", "reexport_of": specifier, "star": True}


def _named_reexports(node: Node, specifier: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for original, public, type_only in export_specifiers(node):
        entry: dict[str, Any] = {"name": public, "kind": "reexport", "reexport_of": specifier}
        if public != original:
            entry["defined_as"] = original
        if type_only:
            entry["type_only"] = True
        out.append(entry)
    return out


def export_specifiers(node: Node) -> list[tuple[str, str, bool]]:
    """This function gives the local name, the public name, and the type-only condition of
    each name in the export clause of a statement.

    `export type { A }` and `export { type A }` give a type-only name. A name can be a
    string: `export { a as 'module.exports' }` gives the public name `module.exports`.
    """
    clause = next((child for child in node.named_children if child.type == "export_clause"), None)
    if clause is None:
        return []
    statement_type_only = _has_type_keyword(node)
    out: list[tuple[str, str, bool]] = []
    for item in (child for child in clause.named_children if child.type == "export_specifier"):
        local = specifier_name(item.child_by_field_name("name"))
        alias = item.child_by_field_name("alias")
        if local:
            type_only = statement_type_only or _has_type_keyword(item)
            out.append((local, specifier_name(alias) if alias else local, type_only))
    return out


def _has_type_keyword(node: Node) -> bool:
    return any(child.type == "type" for child in node.children)


def reexport_api(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """This function gives the export identities of re-export records.

    A `*` re-export gives the name `*`. The names that it gives come from a different
    module. One module text cannot supply them. A type-only re-export has a different identity
    from a re-export of the value.
    """
    out: list[dict[str, str]] = []
    for entry in entries:
        original = "*" if entry.get("star") else entry.get("defined_as", entry["name"])
        prefix = "type-reexport" if entry.get("type_only") else "reexport"
        out.append(
            {
                "name": entry["name"],
                "bucket": "constants",
                "fingerprint": f"{prefix}:{entry['reexport_of']}:{original}",
            }
        )
    return out
