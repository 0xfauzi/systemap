"""The re-export resolver gives each re-exported public name the kind of its definition.

It reads the module records of one extraction. The rules are the same for each language.
The adapter writes the language rules into the records: `star` marks a `*` re-export, and
`star_export` set to `false` marks a name that a `*` re-export does not give.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from systemap.source_facts import package_of


def resolve_reexports(components: dict[str, Any]) -> None:
    """Give each re-export the kind recorded by its defining module.

    `from . import mod` has kind `module`, with the module itself in `reexport_of`.
    A name absent from the source module keeps `reexport_of` and has kind `object`.
    The source can import that name from elsewhere, including an unextracted module.
    A name that the source module defines has the kind of that definition, also when
    a module with the dotted name `source.name` exists.
    """
    _expand_star_exports(components)
    _resolve_named_reexports(components)


def _expand_star_exports(components: dict[str, Any]) -> None:
    for module, record in components.items():
        expanded = _expanded_names(module, record, components)
        record["names"] = expanded
        ambiguous = _ambiguous_exports(expanded)
        if ambiguous:
            record.setdefault("unknown", []).extend(ambiguous)


def _expanded_names(
    module: str, record: dict[str, Any], components: dict[str, Any]
) -> list[dict[str, Any]]:
    """This function replaces each `*` re-export with the names of its source module.

    A local definition or a named export hides a `*` name with the same public name.
    """
    explicit = _explicit_names(record)
    expanded: list[dict[str, Any]] = []
    for entry in record.get("names", []):
        if not entry.get("star"):
            expanded.append(entry)
            continue
        source = entry["reexport_of"]
        expanded.extend(
            {
                "name": item["name"],
                "kind": "reexport",
                "reexport_of": source,
                "defined_as": item["name"],
            }
            for item in _star_names(source, components, {module})
            if item["name"] not in explicit
        )
    return expanded


def _explicit_names(record: dict[str, Any]) -> set[str]:
    return {entry["name"] for entry in record.get("names", []) if not entry.get("star")}


def _ambiguous_exports(expanded: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: dict[str, set[str]] = defaultdict(set)
    for entry in expanded:
        if entry.get("reexport_of"):
            sources[entry["name"]].add(entry["reexport_of"])
    return [
        {"line": 0, "reason": f"ambiguous star export {name}", "source": ""}
        for name, origins in sources.items()
        if len(origins) > 1
    ]


def _resolve_named_reexports(components: dict[str, Any]) -> None:
    for record in components.values():
        for entry in record.get("names", []):
            if entry.get("kind") == "reexport":
                _resolve_named_reexport(entry, components)


def _resolve_named_reexport(entry: dict[str, Any], components: dict[str, Any]) -> None:
    source = entry["reexport_of"]
    original = entry.pop("defined_as", entry["name"])
    if _submodule(source, original, components):
        entry["reexport_of"] = f"{source}.{original}"
        entry["kind"] = "module"
    else:
        entry["kind"] = _defined_kind(source, original, components, set())


def _submodule(source: str, name: str, components: dict[str, Any]) -> bool:
    """This function tells if `source.name` is a module that the name refers to.

    The module must be in the package `source`, as its `package` fact gives. A file
    name with a dot gives a module id that looks like a child of another module, but
    its package is its folder. A name that the source module defines is not that module.
    """
    child = f"{source}.{name}"
    in_package = child in components and package_of(child, components) == source
    return in_package and _definition(source, name, components) is None


def _definition(source: str, name: str, components: dict[str, Any]) -> dict[str, Any] | None:
    """This function finds the record of a name in its source module.

    The record of `from . import name` in a package refers to the package itself, so it
    is not a definition.
    """
    for item in components.get(source, {}).get("names", []):
        if item["name"] == name and item.get("reexport_of") not in (source, f"{source}.{name}"):
            return dict(item)
    return None


def _defined_kind(
    source: str, name: str, components: dict[str, Any], visited: set[tuple[str, str]]
) -> str:
    if (source, name) in visited:
        return "unknown"
    item = _definition(source, name, components)
    if item is None:
        return "module" if _submodule(source, name, components) else "unknown"
    if item["kind"] == "reexport":
        return _defined_kind(
            item["reexport_of"],
            item.get("defined_as", item["name"]),
            components,
            visited | {(source, name)},
        )
    return str(item["kind"])


def _star_names(module: str, components: dict[str, Any], visited: set[str]) -> list[dict[str, Any]]:
    """The public names reached through local `*` re-exports.

    A name with `star_export` set to `false` is not in a `*` re-export. A name without the
    field is in it."""
    if module not in components or module in visited:
        return []
    out: list[dict[str, Any]] = []
    for entry in components[module].get("names", []):
        if entry.get("star"):
            out.extend(_star_names(entry["reexport_of"], components, visited | {module}))
        elif entry.get("star_export", True) is not False:
            out.append(entry)
    return out
