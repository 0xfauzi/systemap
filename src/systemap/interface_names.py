"""The public names of a component, and the names in its interface.

`names_not_known` tells if the facts do not give all public names of a component.
`interface_problem` compares the name at the start of an interface with the public names
of the component modules. The check and the delta use these functions. They are in this
module, and not in `check`, because `check` imports the figure module, and the figure
module imports the delta through the change module. Thus a delta that imports `check`
makes an import cycle.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable, Mapping
from typing import Any

from systemap import identifier, reexports, source_facts, unknown_causes
from systemap import language as languages
from systemap.model import Component, claimed, public_names, symbol_claims


def names_not_known(c: Component, components: Mapping[str, Any]) -> bool:
    """Tell if the public names of the component are not known.

    A claimed module, or the module of a symbol claim, that the extractor could not read
    or parse has names that are not known. A module with an unknown record of the cause
    `reexport` also has names that are not known. Then a name that the facts do not give
    is not known: it is not a pass and not a failure. The `source inventory unresolved`
    group or the `unknown surface` group gives the module."""
    modules = [*claimed(c, components), *(m for m, _name in symbol_claims(c))]
    return any(m in components and names_unknown(components[m]) for m in modules)


def names_unknown(record: Mapping[str, Any]) -> bool:
    """Tell if the adapter could not read or parse all of the module, or if the names of a
    re-export of the module are not known.

    A record without a `completeness` record keeps the earlier check result."""
    state = record.get("completeness")
    if isinstance(state, Mapping) and state.get("parsed") is False:
        return True
    unknown = record.get("unknown") or []
    return any(unknown_causes.of(item) == unknown_causes.REEXPORT for item in unknown)


def interface_head(text: str) -> tuple[str, str] | None:
    """This function reads the initial interface identifier and the method name after a
    dot (`Class.method`), or gives `None`. An identifier can contain Unicode letters.
    """
    start = len(text) - len(text.lstrip())
    name = identifier.read(text, start)
    if not name:
        return None
    after = start + len(name)
    method = identifier.read(text, after + 1) if text[after : after + 1] == "." else ""
    return name, method


def method_names(record: Mapping[str, Any], class_name: str) -> set[str]:
    """This function gives public class methods from recorded signatures.

    The first language adapter that reads a name from the signature gives the name."""
    signatures = [
        sig
        for group in ("classes", "errors", "types")
        for cls in record.get(group, [])
        if cls.get("name") == class_name
        for sig in cls.get("methods", [])
    ]
    return {name for name in map(_method_name, signatures) if name}


def _method_name(signature: str) -> str:
    adapters = (languages.repository(name) for name in languages.names())
    return next((found for a in adapters if (found := a.method_name(signature))), "")


def _closest(name: str, candidates: Iterable[str]) -> str:
    matches = difflib.get_close_matches(name, sorted(set(candidates)), n=1, cutoff=0.0)
    return matches[0] if matches else ""


def interface_problem(c: Component, components: Mapping[str, Any]) -> str:
    """This function gives the interface diagnostic for one component, or an empty string
    if the interface is correct or not known.
    """
    if c.kind == "actor" or not c.interface.strip() or names_not_known(c, components):
        return ""
    modules = claimed(c, components)
    symbols = symbol_claims(c)
    names: set[str] = set()
    for m in modules:
        names |= public_names(components[m])
    names |= {name for _module, name in symbols}
    held = ", ".join(modules + [f"{m}:{n}" for m, n in symbols])
    head = interface_head(c.interface)
    if head is None:
        return (
            f"{c.id} interface '{c.interface}' does not start with a name. Start it with a "
            f"public name from its modules ({held})"
        )
    name, method = head
    if name not in names:
        hint = _name_hint(name, names, [components[m] for m in modules])
        return (
            f"{c.id} interface starts with {name}, but none of its modules defines this "
            f"name ({held}){hint}"
        )
    if not method:
        return ""
    holders = _holders(modules, symbols, components, name)
    methods = _interface_methods(holders, components, name)
    if method in methods or _methods_not_known(holders, components, name):
        return ""
    # The class's own methods first: a wrong method is usually a
    # misspelt one, not a module-level name.
    closest = _closest(method, methods) or _closest(method, names)
    hint = f". The nearest name is {closest}" if closest else ""
    return (
        f"{c.id} interface contains {name}.{method}, but {name} has no public method "
        f"{method} ({held}){hint}"
    )


def _name_hint(name: str, names: set[str], records: list[Mapping[str, Any]]) -> str:
    """Give the hint for an interface name that is not a public name.

    A public name with the defining symbol `name` (`defined_as`) comes first, for example
    the public name `default` of a module that exports the symbol `ky`. If there is no
    such name, the hint gives the nearest spelling."""
    given = sorted(
        {
            entry["name"]
            for record in records
            for entry in record.get("names") or []
            if entry.get("defined_as") == name and entry.get("name") != name
        }
    )
    if given:
        return f". The public name for the symbol {name} is {', '.join(given)}"
    closest = _closest(name, names)
    return f". The nearest name is {closest}" if closest else ""


def _holders(
    modules: list[str], symbols: list[tuple[str, str]], components: Mapping[str, Any], name: str
) -> list[str]:
    """Give the claimed modules and the modules of the symbol claims of the name."""
    return [*modules, *(m for m, n in symbols if n == name and m in components)]


def _methods_not_known(holders: list[str], components: Mapping[str, Any], name: str) -> bool:
    """Tell if the methods of the name are not known.

    They are not known if a module gives the name with an unknown definition. They are
    also not known if a module of a definition is missing from the facts or its names are not known.
    Then a method that the facts do not give is not known: it is not a pass and not a
    failure. The `source inventory unresolved` group or the `unknown surface` group gives
    the cause."""
    for holder in holders:
        record = components[holder]
        if _unknown_definition(record, name):
            return True
        for module, _symbol in reexports.definitions(record, holder, name):
            if module not in components or names_unknown(components[module]):
                return True
    return False


def _unknown_definition(record: Mapping[str, Any], name: str) -> bool:
    """Tell if the module gives the name with an unknown defining module or symbol."""
    return any(
        entry.get("defined_in") is None or entry.get("defined_as") is None
        for entry in record.get("names") or []
        if entry.get("name") == name and "defined_in" in entry
    )


def _interface_methods(holders: list[str], components: Mapping[str, Any], name: str) -> set[str]:
    """This function gives the public methods of each definition of the name.

    A re-export gives the module and the symbol of its definition. A name that refers to
    a full module gives the public names of that module."""
    methods: set[str] = set()
    for holder in holders:
        for module, symbol in reexports.definitions(components[holder], holder, name):
            if module not in components:
                continue
            if symbol == source_facts.WHOLE_MODULE:
                methods |= public_names(components[module])
            else:
                methods |= method_names(components[module], symbol)
    return methods
