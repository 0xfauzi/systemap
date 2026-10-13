"""The TypeScript import reader gives the local names that import statements make.

`export { name }` can export such a name. The export is then a re-export of the
imported module, as `export { name } from "./module"` is.
"""

from __future__ import annotations

from typing import Any

from systemap.typescript_syntax import specifier_name, string_value

# One local name: the record that an export of the name gives, without the public name.
LocalNames = dict[str, dict[str, Any]]


def import_names(root: Any) -> LocalNames:
    """This function gives each local name of the top-level import statements.

    A named or default import is a re-export with `defined_as`. A namespace import or
    `import name = require(...)` is an object with `reexport_of`. A type-only import
    has `type_only` set to `true`.
    """
    out: LocalNames = {}
    for statement in root.named_children:
        if statement.type == "import_statement":
            out.update(_statement_names(statement))
    return out


def _statement_names(statement: Any) -> LocalNames:
    source = _source(statement)
    out: LocalNames = {}
    for clause in statement.named_children:
        if clause.type == "import_require_clause":
            out.update(_namespace(clause, _source(clause)))
        elif clause.type == "import_clause" and source:
            out.update(_clause_names(clause, source))
    if any(child.type == "type" for child in statement.children):
        for entry in out.values():
            entry["type_only"] = True
    return out


def _clause_names(clause: Any, source: str) -> LocalNames:
    out: LocalNames = {}
    for child in clause.named_children:
        if child.type == "identifier":
            out[_text(child)] = _reexport(source, "default")
        elif child.type == "namespace_import":
            out.update(_namespace(child, source))
        elif child.type == "named_imports":
            out.update(_named(child, source))
    return out


def _named(named: Any, source: str) -> LocalNames:
    out: LocalNames = {}
    for specifier in (child for child in named.named_children if child.type == "import_specifier"):
        name = specifier_name(specifier.child_by_field_name("name"))
        alias = specifier_name(specifier.child_by_field_name("alias"))
        if name:
            out[alias or name] = _reexport(source, name)
            if any(child.type == "type" for child in specifier.children):
                out[alias or name]["type_only"] = True
    return out


def _namespace(node: Any, source: str) -> LocalNames:
    name = next((child for child in node.named_children if child.type == "identifier"), None)
    if name is None or not source:
        return {}
    return {_text(name): {"kind": "object", "reexport_of": source}}


def _reexport(source: str, name: str) -> dict[str, Any]:
    return {"kind": "reexport", "reexport_of": source, "defined_as": name}


def _source(node: Any) -> str:
    return string_value(node.child_by_field_name("source"))


def _text(node: Any | None) -> str:
    return (node.text or b"").decode("utf-8") if node is not None else ""
