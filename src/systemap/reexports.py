"""The re-export resolver finds the module and the symbol that define each re-export.

It reads the module records of one extraction. The rules are the same for each language.
The adapter writes the language rules into the records:

- `star` marks a `*` re-export.
- `rebinds` on a `*` re-export marks the source-order rule: a later binding of a name
  replaces an earlier binding. Without `rebinds`, a local symbol or a named export hides
  a `*` name. Two `*` names from different defining symbols are ambiguous.
- `star_export` set to `false` marks a name that a `*` re-export does not give.
  `star_export` set to `null` marks a name that a `*` re-export can give or not give.
- On a `*` re-export record, `star_export_names` limits the names that a `*` re-export of
  the module gives from it, and `star_export` set to `null` makes them not known. The
  resolver writes the result as `star_export` on each name that the record gives.
- A `*` re-export from a module that the adapter could not read or parse gives names that
  are not known. The module then gets an unknown record with the cause `reexport`.

Each re-export gets `defined_in` and `defined_as`: the module and the symbol that define
it. `defined_as` is `*` when the name refers to a full module. The two values are `null`
when the defining module is not known.

A type-only re-export without a known kind has the kind `type`, because its statement
shows that the name is a type. Its `defined_in` and `defined_as` stay `null`.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Iterator, Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import Any, NamedTuple, TypeVar

from systemap import unknown_causes
from systemap.source_facts import WHOLE_MODULE, package_of

# The kind, the defining module, and the defining symbol of one public name.
Definition = tuple[str, str | None, str | None]
NOT_KNOWN: Definition = ("unknown", None, None)
# A module and a public name of it.
Key = tuple[str, str]
Value = TypeVar("Value")


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


def _typed(entry: dict[str, Any]) -> dict[str, Any]:
    """Give a type-only name of kind `unknown` the kind `type`."""
    if entry.get("type_only") and entry.get("kind") == "unknown":
        return {**entry, "kind": "type"}
    return entry


class _Star(NamedTuple):
    """The names that a `*` re-export of a module gives.

    `uncertain` is true when the adapter does not know if a name is in the `*` re-export.
    """

    names: list[str]
    known: frozenset[str]
    uncertain: bool


_NO_NAMES = _Star([], frozenset(), False)


class _Ref:
    """A request for the value of another pair of a module and a name."""

    __slots__ = ("key",)

    def __init__(self, key: Key) -> None:
        self.key = key


class _Resolver:
    """This class reads the adapter records before any change, so the order of the
    modules does not change a result.

    The resolver keeps each value that it calculates, so a diamond of `*` re-exports
    does not make the work exponential. It does not use recursive calls, so a long
    chain of re-exports does not stop it."""

    def __init__(self, components: dict[str, Any]) -> None:
        self.components = components
        self.raw = {m: [dict(e) for e in r.get("names", [])] for m, r in components.items()}
        self.problems: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.found: dict[Key, Definition] = {}
        self.only: dict[Key, bool] = {}
        self.star: dict[str, _Star] = {}
        self.group: dict[str, int] = {}
        self.members: list[list[str]] = []
        self.cut: dict[str, dict[str, _Star]] = {}
        self.graph = {
            m: [e["reexport_of"] for e in names if e.get("star") and e["reexport_of"] in self.raw]
            for m, names in self.raw.items()
        }
        self._star_groups()

    def names(self, module: str) -> list[dict[str, Any]]:
        """This function gives the public names of a module with the defining symbols."""
        out: list[dict[str, Any]] = []
        explicit = {e["name"] for e in self.raw[module] if not e.get("star")}
        rebinds = _rebinds(self.raw[module])
        for entry in self.raw[module]:
            if not entry.get("star"):
                _bind(module, out, _typed(self._resolved(module, entry)), rebinds)
                continue
            source = entry["reexport_of"]
            given = self.star_names(source, module)
            if given.uncertain:
                self._uncertain(module, source)
            for name in given.names:
                if not rebinds and name in explicit:
                    continue
                found = self._entry(name, source, name, bool(entry.get("type_only")))
                found.update(_star_policy(entry, name))
                _bind(module, out, _typed({**found, "via_star": True}), rebinds)
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
        kind, defined_in, defined_as = self.hop(source, symbol)
        found: dict[str, Any] = {
            "name": name,
            "kind": kind,
            "reexport_of": source,
            "defined_in": defined_in,
            "defined_as": defined_as,
        }
        if kind == "module" and defined_in == f"{source}.{symbol}":
            found["reexport_of"] = defined_in
        if type_only or self.type_only(source, symbol):
            found["type_only"] = True
        return found

    def hop(self, source: str, symbol: str) -> Definition:
        """This function follows one re-export to the symbol that defines `symbol` of
        `source`."""
        step = self._hop(source, symbol)
        if isinstance(step, _Ref):
            return _evaluate(step.key, self._lookup_steps, _one_definition, NOT_KNOWN, self.found)
        return step

    def _hop(self, source: str, symbol: str) -> Definition | _Ref:
        if self._submodule(source, symbol):
            return ("module", f"{source}.{symbol}", WHOLE_MODULE)
        return _Ref((source, symbol))

    def type_only(self, module: str, name: str) -> bool:
        """Tell if the binding of `name` in `module` is type-only at a link of its chain.

        The selected binding follows the rules of `_selected`. A type-only name has no
        value in the emitted code, so it is not an entry point.
        """
        return bool(_evaluate((module, name), self._type_only_steps, _all_true, False, self.only))

    def _selected(self, module: str, name: str) -> list[dict[str, Any]]:
        """Give the bindings of `name` in `module` that select its definition.

        With the source-order rule, the last binding replaces the other bindings. Without
        it, the first named binding hides the `*` bindings. If no named binding occurs,
        each `*` binding must give the same definition."""
        bindings = self._bindings(module, name)
        if _rebinds(self.raw[module]):
            return bindings[-1:]
        explicit = [e for e in bindings if not e.get("star")]
        return explicit[:1] if explicit else bindings

    def _lookup_steps(self, key: Key) -> list[Definition | _Ref]:
        """Give the definition, or the next link, of each selected binding."""
        module, name = key
        if module not in self.raw:
            return []
        return [self._definition(module, e, name) for e in self._selected(module, name)]

    def _type_only_steps(self, key: Key) -> list[bool | _Ref]:
        module, name = key
        if module not in self.raw:
            return []
        return [self._type_only_link(e, name) for e in self._selected(module, name)]

    def _type_only_link(self, entry: dict[str, Any], name: str) -> bool | _Ref:
        if entry.get("type_only"):
            return True
        source = entry.get("reexport_of")
        if entry.get("star"):
            return _Ref((str(source), name))
        if source and entry.get("kind") == "reexport":
            return _Ref((str(source), str(entry.get("defined_as", name))))
        return False

    def _bindings(self, module: str, name: str) -> list[dict[str, Any]]:
        """This function gives the records in `module` that can bind `name`, in source order."""
        out = []
        for entry in self.raw[module]:
            if entry.get("star"):
                if name in self.star_names(entry["reexport_of"], module).known:
                    out.append(entry)
            elif entry["name"] == name and not _refers_to_itself(module, entry):
                out.append(entry)
        return out

    def _definition(self, module: str, entry: dict[str, Any], name: str) -> Definition | _Ref:
        source = entry.get("reexport_of")
        if entry.get("star"):
            return self._hop(str(source), name)
        if not source:
            return (str(entry["kind"]), module, str(entry.get("defined_as", name)))
        if entry.get("kind") == "reexport":
            return self._hop(str(source), str(entry.get("defined_as", name)))
        if entry.get("kind") == "unknown":
            return NOT_KNOWN
        return (str(entry["kind"]), str(source), WHOLE_MODULE)

    def star_names(self, module: str, start: str) -> _Star:
        """This function gives the names that a `*` re-export of `module` in `start` gives.

        The names come from the modules that a chain of `*` re-exports from `module`
        reaches. The chain does not go through `start`."""
        if module not in self.raw or module == start:
            return _NO_NAMES
        if self.group[module] != self.group.get(start):
            return self.star[module]
        if start not in self.cut:
            self.cut[start] = self._without(start)
        return self.cut[start][module]

    def _without(self, start: str) -> dict[str, _Star]:
        """Give the `*` names of the modules that `start` re-exports from, in the same
        loop as `start`. A chain of `*` re-exports that goes through `start` gives no name."""
        inside = set(self.members[self.group[start]]) - {start}
        targets = [e["reexport_of"] for e in self.raw[start] if e.get("star")]
        return _Loop(self, inside, start).names([m for m in targets if m in inside])

    def _star_groups(self) -> None:
        """Calculate the groups of the `*` graph and the `*` names of each module.

        A loop of `*` re-exports connects the modules of a group. Each group comes after
        the groups that it reaches."""
        for members in _strong_groups(self.graph):
            for module in members:
                self.group[module] = len(self.members)
            self.members.append(members)
            if len(members) > 1 or members[0] in self.graph[members[0]]:
                self.star.update(_Loop(self, set(members), None).names(members))
            else:
                self.star[members[0]] = self._gather(members[0])

    def _gather(self, module: str) -> _Star:
        """Give the `*` names of a module that is not in a loop of `*` re-exports."""
        steps, uncertain = self._steps(module, set(), None)
        names = list(dict.fromkeys(step for step in steps if isinstance(step, str)))
        return _Star(names, frozenset(names), uncertain)

    def _steps(
        self, module: str, inside: AbstractSet[str], start: str | None
    ) -> tuple[list[str | _Go], bool]:
        """Give the `*` names of the records of `module` in source order.

        A `*` re-export from a module in `inside` gives a `_Go` in place of the names.
        The second value is true when the adapter does not know if a name is in the
        `*` re-export."""
        if _unread(self.components[module]):
            return [], True
        steps: list[str | _Go] = []
        uncertain = False
        for entry in self.raw[module]:
            policy = entry.get("star_export", True)
            if policy is None:
                uncertain = True
            elif not entry.get("star"):
                if policy is not False:
                    steps.append(entry["name"])
            elif entry["reexport_of"] in inside:
                steps.append(_Go(entry["reexport_of"], _allowed(entry)))
            else:
                given = self._given(entry["reexport_of"], start)
                steps.extend(_kept(entry, given.names))
                uncertain = uncertain or given.uncertain
        return steps, uncertain

    def _given(self, source: str, start: str | None) -> _Star:
        if source == start or source not in self.raw:
            return _NO_NAMES
        return self.star[source]

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
                "cause": unknown_causes.REEXPORT,
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
                    {
                        "line": 0,
                        "reason": f"ambiguous star export {name}",
                        "source": "",
                        "cause": unknown_causes.REEXPORT,
                    }
                )
        return kept


class _Go(NamedTuple):
    """A `*` re-export from a module of the same loop. `allowed` limits the names."""

    source: str
    allowed: frozenset[str] | None


class _Loop:
    """The `*` names of the modules of one loop of `*` re-exports.

    A chain of `*` re-exports goes only through the modules in `inside`. A module that is
    not in `inside` gives the names in `resolver.star`, and `start` gives no name.

    The names of a module come from one walk of the modules that it reaches, in the
    order of the records. Each module is examined one time, so the work does not
    increase with the length of the loop for each pass. The order of the names does
    not depend on the order of the calculation."""

    def __init__(self, resolver: _Resolver, inside: AbstractSet[str], start: str | None):
        self.resolver = resolver
        self.inside = inside
        self.start = start
        self.steps: dict[str, tuple[list[str | _Go], bool]] = {}

    def names(self, roots: list[str]) -> dict[str, _Star]:
        """Give the `*` names of each module in `roots`."""
        limits = self._limits()
        out: dict[str, _Star] = {}
        for root in roots:
            names, uncertain = self._walk(root)
            if limits is not None:
                names = [name for name in names if name in limits[root]]
            out[root] = _Star(names, frozenset(names), uncertain)
        return out

    def _of(self, module: str) -> tuple[list[str | _Go], bool]:
        if module not in self.steps:
            self.steps[module] = self.resolver._steps(module, self.inside, self.start)
        return self.steps[module]

    def _walk(self, root: str) -> tuple[list[str], bool]:
        """Give the names of the modules that `root` reaches, without the limits of the
        `*` records in the loop. Use a list of open modules, not recursive calls."""
        steps, uncertain = self._of(root)
        names: list[str] = []
        seen = {root}
        work = [iter(steps)]
        while work:
            step = next(work[-1], None)
            if step is None:
                work.pop()
            elif isinstance(step, str):
                names.append(step)
            elif step.source not in seen:
                seen.add(step.source)
                more, unsure = self._of(step.source)
                uncertain = uncertain or unsure
                work.append(iter(more))
        return list(dict.fromkeys(names)), uncertain

    def _limits(self) -> dict[str, set[str]] | None:
        """Give the set of names of each module of the loop when a `*` record in the loop
        limits its names. Otherwise give `None`.

        The calculation adds each name to each module one time. A module that gets new
        names sends only these names to the modules that re-export from it."""
        found = {module: self._of(module)[0] for module in self.inside}
        links = [(m, s) for m, steps in found.items() for s in steps if isinstance(s, _Go)]
        if all(go.allowed is None for _, go in links):
            return None
        sets = {m: {s for s in steps if isinstance(s, str)} for m, steps in found.items()}
        users: dict[str, list[tuple[str, frozenset[str] | None]]] = defaultdict(list)
        for module, go in links:
            users[go.source].append((module, go.allowed))
        work = deque((module, set(names)) for module, names in sets.items())
        while work:
            source, added = work.popleft()
            for module, allowed in users[source]:
                new = (added if allowed is None else added & allowed) - sets[module]
                if new:
                    sets[module] |= new
                    work.append((module, new))
        return sets


def _allowed(entry: dict[str, Any]) -> frozenset[str] | None:
    allowed = entry.get("star_export_names")
    return None if allowed is None else frozenset(allowed)


def _star_policy(entry: dict[str, Any], name: str) -> dict[str, Any]:
    """Give the `star_export` value of a name that the `*` re-export record gives: `{}`
    when a `*` re-export of the module gives the name."""
    if entry.get("star_export", True) is None:
        return {"star_export": None}
    allowed = entry.get("star_export_names")
    if allowed is not None and name not in allowed:
        return {"star_export": False}
    return {}


def _kept(entry: dict[str, Any], names: list[str]) -> list[str]:
    """Give the names for which `_star_policy` gives `{}`, in the same order."""
    if entry.get("star_export", True) is None:
        return []
    allowed = entry.get("star_export_names")
    if allowed is None:
        return names
    listed = set(allowed)
    return [name for name in names if name in listed]


def _unread(record: Mapping[str, Any]) -> bool:
    """Tell if the adapter could not read or parse all of the module. Its names are then
    not known."""
    state = record.get("completeness")
    return isinstance(state, Mapping) and state.get("parsed") is False


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
    itself is in the module under the same name. A name with `defined_as` and without
    `defined_in` is also in the module under the `defined_as` symbol, as the public name
    `default` of a local class. A defining module that is not known gives no result."""
    out = [(module, name)]
    for entry in record.get("names", []):
        if entry.get("name") != name:
            continue
        if "defined_in" not in entry:
            if entry.get("defined_as"):
                out.append((module, str(entry["defined_as"])))
            continue
        defined_in, defined_as = entry["defined_in"], entry["defined_as"]
        if defined_in is not None and defined_as is not None:
            out.append((str(defined_in), str(defined_as)))
    return list(dict.fromkeys(out))


def _one_definition(found: list[Definition]) -> Definition:
    """Give the definition when all selected bindings give the same definition."""
    definitions = set(found)
    return definitions.pop() if len(definitions) == 1 else NOT_KNOWN


def _all_true(found: list[bool]) -> bool:
    return bool(found) and all(found)


def _evaluate(
    root: Key,
    steps: Callable[[Key], Sequence[Value | _Ref]],
    combine: Callable[[list[Value]], Value],
    loop: Value,
    cache: dict[Key, Value],
) -> Value:
    """Give the value of `root`. Use a list of open pairs, not recursive calls.

    `steps` gives the values and the `_Ref` links of a pair. `combine` makes one value
    from them. A link to an open pair is a loop and gives the value `loop`. This value
    makes the value of each pair in the loop `loop`, so each value goes into `cache`.
    A value is not `None`.
    """
    if root in cache:
        return cache[root]
    stack: list[tuple[Key, Iterator[Value | _Ref], list[Value]]] = [(root, iter(steps(root)), [])]
    open_keys = {root}
    while stack:
        key, links, values = stack[-1]
        link = next(links, None)
        if link is None:
            stack.pop()
            open_keys.discard(key)
            cache[key] = combine(values)
            if stack:
                stack[-1][2].append(cache[key])
        elif not isinstance(link, _Ref):
            values.append(link)
        elif link.key in cache:
            values.append(cache[link.key])
        elif link.key in open_keys:
            values.append(loop)
        else:
            open_keys.add(link.key)
            stack.append((link.key, iter(steps(link.key)), []))
    return cache[root]


class _Groups:
    """The strongly connected groups of a graph, with the Tarjan method and no recursion."""

    def __init__(self, graph: Mapping[str, list[str]]) -> None:
        self.graph = graph
        self.index: dict[str, int] = {}
        self.low: dict[str, int] = {}
        self.stack: list[str] = []
        self.on_stack: set[str] = set()
        self.out: list[list[str]] = []

    def visit(self, root: str) -> None:
        self._open(root)
        work = [(root, iter(self.graph[root]))]
        while work:
            node, children = work[-1]
            child = next(children, None)
            if child is None:
                work.pop()
                self._close(node, work[-1][0] if work else None)
            elif child not in self.index:
                self._open(child)
                work.append((child, iter(self.graph[child])))
            elif child in self.on_stack:
                self.low[node] = min(self.low[node], self.index[child])

    def _open(self, node: str) -> None:
        self.index[node] = self.low[node] = len(self.index)
        self.stack.append(node)
        self.on_stack.add(node)

    def _close(self, node: str, parent: str | None) -> None:
        if parent is not None:
            self.low[parent] = min(self.low[parent], self.low[node])
        if self.low[node] != self.index[node]:
            return
        members: list[str] = []
        while not members or members[-1] != node:
            members.append(self.stack.pop())
            self.on_stack.discard(members[-1])
        self.out.append(members)


def _strong_groups(graph: Mapping[str, list[str]]) -> list[list[str]]:
    """Give the groups of modules that loops connect. A group comes after the groups
    that it reaches."""
    groups = _Groups(graph)
    for node in graph:
        if node not in groups.index:
            groups.visit(node)
    return groups.out
