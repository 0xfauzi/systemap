"""The re-export resolver finds the module and the symbol that define each re-export.

It reads the module records of one extraction. The rules are the same for each language.
The adapter writes the language rules into the records:

- `star` marks a `*` re-export.
- `rebinds` on a `*` re-export marks the source-order rule: a later binding of a name
  replaces an earlier binding. Without `rebinds`, a local symbol or a named export hides
  a `*` name. Two `*` names from different defining symbols are ambiguous.
- `star_export` set to `false` marks a name that a `*` re-export does not give.
  `star_export` set to `null` marks a name that a `*` re-export can give or not give.

Each re-export gets `defined_in` and `defined_as`: the module and the symbol that define
it. `defined_as` is `*` when the name refers to a full module. The two values are `null`
when the defining module is not known.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from systemap.source_facts import WHOLE_MODULE, package_of

# The kind, the defining module, and the defining symbol of one public name.
Definition = tuple[str, str | None, str | None]
NOT_KNOWN: Definition = ("unknown", None, None)


def resolve_reexports(components: dict[str, Any]) -> None:
    """Give each re-export the kind, the module, and the symbol that define it.

    `from . import mod` has kind `module`, with the module itself in `reexport_of`.
    A name absent from the source module keeps `reexport_of` and has kind `unknown`.
    The source can import that name from elsewhere, including an unextracted module.
    A name that the source module defines has the kind of that symbol, also when
    a module with the dotted name `source.name` exists.
    """
    resolver = _Resolver(components)
    names = {module: resolver.names(module) for module in components}
    for module, record in components.items():
        record["names"] = names[module]
        problems = resolver.problems.get(module)
        if problems:
            record.setdefault("unknown", []).extend(problems)


class _Resolver:
    """This class reads the adapter records before any change, so the order of the
    modules does not change a result."""

    def __init__(self, components: dict[str, Any]) -> None:
        self.components = components
        self.raw = {m: [dict(e) for e in r.get("names", [])] for m, r in components.items()}
        self.problems: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.given: dict[tuple[str, frozenset[str]], tuple[list[str], bool]] = {}

    def names(self, module: str) -> list[dict[str, Any]]:
        """This function gives the public names of a module with the defining symbols."""
        out: list[dict[str, Any]] = []
        explicit = {e["name"] for e in self.raw[module] if not e.get("star")}
        rebinds = _rebinds(self.raw[module])
        for entry in self.raw[module]:
            if not entry.get("star"):
                _bind(module, out, self._resolved(module, entry), rebinds)
                continue
            source = entry["reexport_of"]
            given, uncertain = self.star_names(source, frozenset({module}))
            if uncertain:
                self._uncertain(module, source)
            for name in given:
                if not rebinds and name in explicit:
                    continue
                found = self._entry(name, source, name, bool(entry.get("type_only")))
                _bind(module, out, {**found, "via_star": True}, rebinds)
        return self._without_duplicates(module, out)

    def _resolved(self, module: str, entry: dict[str, Any]) -> dict[str, Any]:
        source = entry.get("reexport_of")
        if not source:
            if "defined_as" in entry:
                return {**entry, "defined_in": module}
            return entry
        kept = {k: v for k, v in entry.items() if k not in ("star", "rebinds", "defined_as")}
        if entry.get("kind") != "reexport":
            # A namespace re-export refers to the full module. The defining module of
            # an unresolved package re-export is not known.
            whole = entry.get("kind") != "unknown"
            identity = (source, WHOLE_MODULE) if whole else (None, None)
            return {**kept, "defined_in": identity[0], "defined_as": identity[1]}
        return {
            **kept,
            **self._entry(entry["name"], source, entry.get("defined_as", entry["name"])),
        }

    def _entry(
        self, name: str, source: str, symbol: str, type_only: bool = False
    ) -> dict[str, Any]:
        """Give the resolved record. A type-only link in the chain makes it type-only."""
        kind, defined_in, defined_as = self.hop(source, symbol, frozenset())
        found = {
            "name": name,
            "kind": kind,
            "reexport_of": source,
            "defined_in": defined_in,
            "defined_as": defined_as,
        }
        if kind == "module" and defined_in == f"{source}.{symbol}":
            found["reexport_of"] = defined_in
        if type_only or self.type_only(source, symbol, frozenset()):
            found["type_only"] = True
        return found

    def hop(self, source: str, symbol: str, visited: frozenset[tuple[str, str]]) -> Definition:
        """This function follows one re-export to the symbol that defines `symbol` of
        `source`."""
        if self._submodule(source, symbol):
            return ("module", f"{source}.{symbol}", WHOLE_MODULE)
        return self.lookup(source, symbol, visited)

    def lookup(self, module: str, name: str, visited: frozenset[tuple[str, str]]) -> Definition:
        """This function gives the defining symbol of the public name `name` of `module`."""
        if (module, name) in visited or module not in self.raw:
            return NOT_KNOWN
        visited = visited | {(module, name)}
        found = [self._definition(module, e, name, visited) for e in self._bindings(module, name)]
        if not found:
            return NOT_KNOWN
        if _rebinds(self.raw[module]):
            return found[-1][1]
        explicit = [d for star, d in found if not star]
        if explicit:
            return explicit[0]
        definitions = {d for _star, d in found}
        return definitions.pop() if len(definitions) == 1 else NOT_KNOWN

    def type_only(self, module: str, name: str, visited: frozenset[tuple[str, str]]) -> bool:
        """Tell if the binding of `name` in `module` is type-only at a link of its chain.

        The selected binding follows the rules of `lookup`. A type-only name has no value
        in the emitted code, so it is not an entry point.
        """
        if (module, name) in visited or module not in self.raw:
            return False
        visited = visited | {(module, name)}
        found = [
            (bool(e.get("star")), self._type_only_link(e, name, visited))
            for e in self._bindings(module, name)
        ]
        if not found:
            return False
        if _rebinds(self.raw[module]):
            return found[-1][1]
        explicit = [only for star, only in found if not star]
        return explicit[0] if explicit else all(only for _star, only in found)

    def _type_only_link(
        self, entry: dict[str, Any], name: str, visited: frozenset[tuple[str, str]]
    ) -> bool:
        if entry.get("type_only"):
            return True
        source = entry.get("reexport_of")
        if entry.get("star"):
            return self.type_only(str(source), name, visited)
        if source and entry.get("kind") == "reexport":
            return self.type_only(str(source), str(entry.get("defined_as", name)), visited)
        return False

    def _bindings(self, module: str, name: str) -> list[dict[str, Any]]:
        """This function gives the records in `module` that can bind `name`, in source order."""
        out = []
        for entry in self.raw[module]:
            if entry.get("star"):
                if name in self.star_names(entry["reexport_of"], frozenset({module}))[0]:
                    out.append(entry)
            elif entry["name"] == name and not _refers_to_itself(module, entry):
                out.append(entry)
        return out

    def _definition(
        self, module: str, entry: dict[str, Any], name: str, visited: frozenset[tuple[str, str]]
    ) -> tuple[bool, Definition]:
        source = entry.get("reexport_of")
        if entry.get("star"):
            return True, self.hop(str(source), name, visited)
        if not source:
            return False, (str(entry["kind"]), module, str(entry.get("defined_as", name)))
        if entry.get("kind") == "reexport":
            return False, self.hop(str(source), str(entry.get("defined_as", name)), visited)
        if entry.get("kind") == "unknown":
            return False, NOT_KNOWN
        return False, (str(entry["kind"]), str(source), WHOLE_MODULE)

    def star_names(self, module: str, visited: frozenset[str]) -> tuple[list[str], bool]:
        """This function gives the names that a `*` re-export of `module` gives.

        The second value is true when the adapter does not know if a name is in the
        `*` re-export."""
        if module not in self.raw or module in visited:
            return [], False
        if (module, visited) not in self.given:
            self.given[module, visited] = self._star_names(module, visited)
        return self.given[module, visited]

    def _star_names(self, module: str, visited: frozenset[str]) -> tuple[list[str], bool]:
        names: list[str] = []
        uncertain = False
        for entry in self.raw[module]:
            if entry.get("star"):
                given, unsure = self.star_names(entry["reexport_of"], visited | {module})
                names.extend(given)
                uncertain = uncertain or unsure
            elif entry.get("star_export", True) is None:
                uncertain = True
            elif entry.get("star_export", True) is not False:
                names.append(entry["name"])
        return list(dict.fromkeys(names)), uncertain

    def _submodule(self, source: str, name: str) -> bool:
        """This function tells if `source.name` is a module that the name refers to.

        The module must be in the package `source`, as its `package` fact gives. A file
        name with a dot gives a module id that looks like a child of another module, but
        its package is its folder. A name that the source module defines is not that module.
        """
        child = f"{source}.{name}"
        in_package = child in self.components and package_of(child, self.components) == source
        return in_package and (source not in self.raw or not self._bindings(source, name))

    def _uncertain(self, module: str, source: str) -> None:
        self.problems[module].append(
            {
                "line": 0,
                "reason": f"the `*` re-export from {source} gives names that are not known",
                "source": "",
            }
        )

    def _without_duplicates(self, module: str, out: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """This function keeps one record for each defining symbol that a `*` re-export
        gives.

        Two `*` names from different defining symbols are ambiguous. Two `*` names are
        also ambiguous when their defining symbols are not known."""
        identities: dict[str, set[tuple[Any, Any]]] = defaultdict(set)
        count: dict[str, int] = defaultdict(int)
        for entry in out:
            if entry.get("via_star"):
                identities[entry["name"]].add((entry["defined_in"], entry["defined_as"]))
                count[entry["name"]] += 1
        seen: set[str] = set()
        kept: list[dict[str, Any]] = []
        for entry in out:
            star = entry.pop("via_star", False)
            name = entry["name"]
            if star and len(identities[name]) == 1 and None not in next(iter(identities[name])):
                if name in seen:
                    continue
                seen.add(name)
            kept.append(entry)
        for name, found in identities.items():
            if len(found) > 1 or ((None, None) in found and count[name] > 1):
                self.problems[module].append(
                    {"line": 0, "reason": f"ambiguous star export {name}", "source": ""}
                )
        return kept


def _rebinds(names: list[dict[str, Any]]) -> bool:
    return any(entry.get("star") and entry.get("rebinds") for entry in names)


def _bind(module: str, out: list[dict[str, Any]], entry: dict[str, Any], rebinds: bool) -> None:
    """This function adds a binding to the public names of `module`.

    With the source-order rule, a binding replaces an earlier binding of the same name
    when one of the two comes from a `*` re-export. A `*` binding of the same known
    defining symbol keeps the earlier record and its position."""
    if rebinds:
        star = bool(entry.get("via_star"))
        same = [e for e in out if e["name"] == entry["name"] and (star or e.get("via_star"))]
        identity = _identity(module, entry)
        if star and identity[0] is not None and any(_identity(module, e) == identity for e in same):
            return
        out[:] = [e for e in out if all(e is not s for s in same)]
    out.append(entry)


def _identity(module: str, entry: dict[str, Any]) -> tuple[Any, Any]:
    if "defined_in" in entry:
        return entry["defined_in"], entry["defined_as"]
    return module, entry["name"]


def _refers_to_itself(module: str, entry: dict[str, Any]) -> bool:
    """The record of `from . import name` in a package refers to the package itself, so
    it does not define the name."""
    return entry.get("reexport_of") in (module, f"{module}.{entry['name']}")


def definitions(record: Mapping[str, Any], module: str, name: str) -> list[tuple[str, str]]:
    """This function gives each module and symbol that can define a public name.

    It reads only the `defined_in` and `defined_as` facts. A name that the module defines
    itself is in the module under the same name. A defining module that is not known
    gives no result."""
    out = [(module, name)]
    for entry in record.get("names", []):
        if entry.get("name") != name or "defined_in" not in entry:
            continue
        defined_in, defined_as = entry["defined_in"], entry["defined_as"]
        if defined_in is not None and defined_as is not None:
            out.append((str(defined_in), str(defined_as)))
    return list(dict.fromkeys(out))
