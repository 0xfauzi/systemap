"""Measure the flow reviews that a source change outside the examined code made stale.

A flow source record has the form `module[:symbol]@digest`. The digest is the SHA-256 of
the full module text (`flow_review`). Thus each change to a cited module makes the flow
review stale, also a change to a comment. A component review uses the syntax digest
(`syntax_sha`), which a comment or a format change does not change.

The script reads the Git history of this repository. It reads each `Flow(...)` call in
`map/*.py` at each commit. An event is one flow at one step of the history whose source
records are different from the records at the parent. The script counts the events in
two units:

- `merge`: each commit on the first-parent line of HEAD against its first parent. This is
  the unit of a pull request, where CI examines the reviews.
- `commit`: each commit with one parent against that parent.

Each event gets one class:

- `set`: a record location was added or removed. The examined code changed.
- `unknown`: no commit of the history has a module text with a recorded digest.
- `format`: each changed module has the same normalized syntax (`syntax_text.text`)
  before and after. A syntax digest in the record prevents this event.
- `partner`: not `format`, and each changed module has the same partner code before and
  after. A symbol digest can prevent this event.
- `start`: not `partner`, and each changed module has the same start statements before
  and after. A symbol digest of only the start statements prevents this event.
- `no start`: not `format`, and a changed module has no start statement (see below).
  The estimate cannot make the examined code smaller than the module.
- `code`: all other events. The partner code of a changed module changed.

The partner code is an estimate, because no record at HEAD names a symbol. For a module
`m` of a flow, the partners are the other cited modules of that flow. The start
statements are the top-level statements of `m` that use a name from a partner, and the
top-level statements whose names a partner uses. The partner code is the start
statements, each top-level statement that they use by name (found again and again until
no statement is new), and each top-level statement that is not an import, a function, a
class, or an assignment. A module without a start statement has no partner code, and its
event is `no start`. The estimate does not follow attribute access on objects or dynamic
calls. Thus the `partner` count is an upper estimate.

Acceptance values, written on 2026-11-24 before the first run. Each value uses the
`merge` unit:

(a) The measurement is valid only if the `unknown` events are at most 0.05 of all events.
(b) If the `format` events are 0.10 or more of all events, a syntax digest in the flow
    source records is worth its migration.
(c) If the `partner` events are 0.30 or more of all events, a symbol digest is worth a
    design. Below 0.30, it is not.
(d) No acceptance value. The script gives the events for each cited module.

Added on 2026-11-24 after run R1, with no acceptance value: the `no start` class, which
R1 counted as `code`, and the part of the top-level statements that the partner code
keeps. These values show if the estimate can make the examined code smaller.

Added on 2026-11-24 after run R2, with no acceptance value: the `start` class. R2 showed
that the partner code keeps a median of 0.95 of the top-level statements. In
`systemap.cli`, `build_parser` uses each command function, so the partner code of each
flow of the CLI contains most of the module. Thus `partner` is a lower estimate for a
symbol digest, not an upper estimate. The `start` class does not include the statements
that the start statements use, so `partner` plus `start` is the upper estimate.
Acceptance value (c) uses the two estimates as a range.

Added on 2026-11-24 before run R4: the symbol measure. After R3, the records of
`systemap.cli` in 16 flows at HEAD name a symbol. For an event that is not `set` and
not `unknown`, the script finds the symbols that the records at HEAD name for the same
flow and each changed module. The event has the symbol state `same` if each changed
module has such a symbol, and the definition of each symbol has the same normalized
syntax before and after. A digest of the named definitions prevents a `same` event. The
definition does not include the statements that it uses, so this value is an upper
estimate for these flows. A flow whose key changed in the history has no symbol.

(e) If the `same` events are 0.30 or more of all `merge` events, a symbol digest is
    worth a design. Below 0.30, it is not worth a design for the records at HEAD.

Run from the repository root, with the full history (`git fetch --unshallow`):

    uv run python bench/jev/flow_stale_replay.py
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from functools import cache

from systemap import python_tree, syntax_text

Key = tuple[str, str, str, str]
Refs = dict[str, str]
SET, UNKNOWN, FORMAT, PARTNER, CODE = "set", "unknown", "format", "partner", "code"
START, NO_START = "start", "no start"
CLASSES = (SET, UNKNOWN, FORMAT, PARTNER, START, NO_START, CODE)
# The part of the top-level statements that each partner code keeps.
KEPT: list[float] = []


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def shallow() -> bool:
    return git("rev-parse", "--is-shallow-repository").strip() == "true"


def source_texts() -> dict[str, str]:
    """Give each Python text below `src` in the history of HEAD, by its SHA-256 digest."""
    ids = set()
    for line in git("rev-list", "--objects", "HEAD", "--", "src").splitlines():
        blob, _, path = line.partition(" ")
        if path.endswith(".py"):
            ids.add(blob)
    out = subprocess.run(
        ["git", "cat-file", "--batch"],
        input="\n".join(sorted(ids)).encode(),
        check=True,
        capture_output=True,
    ).stdout
    texts: dict[str, str] = {}
    at = 0
    while at < len(out):
        end = out.index(b"\n", at)
        size = int(out[at:end].split()[2])
        raw = out[end + 1 : end + 1 + size]
        texts[hashlib.sha256(raw).hexdigest()] = raw.decode("utf-8", "replace")
        at = end + 2 + size
    return texts


def _text_arg(call: ast.Call, at: int, name: str) -> str:
    node: ast.expr | None = call.args[at] if at < len(call.args) else None
    for keyword in call.keywords:
        if keyword.arg == name:
            node = keyword.value
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else ""


def _refs(call: ast.Call) -> Refs:
    for keyword in call.keywords:
        if keyword.arg == "source_refs" and isinstance(keyword.value, ast.Tuple | ast.List):
            items = [e.value for e in keyword.value.elts if isinstance(e, ast.Constant)]
            pairs = [str(item).rpartition("@") for item in items]
            return {location: digest for location, mark, digest in pairs if mark}
    return {}


def _is_flow(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
    return name == "Flow"


_FLOWS: dict[str, dict[Key, Refs]] = {}


def _calls(commit: str) -> list[tuple[Key, Refs]]:
    """Give the key and the source records of each `Flow(...)` call in `map/*.py`."""
    out = []
    paths = git("ls-tree", "-r", "--name-only", commit, "map/").splitlines()
    for path in (p for p in paths if p.endswith(".py")):
        for node in ast.walk(ast.parse(git("show", f"{commit}:{path}"))):
            if _is_flow(node):
                assert isinstance(node, ast.Call)
                key = (
                    _text_arg(node, 0, "src"),
                    _text_arg(node, 1, "dst"),
                    _text_arg(node, 2, "artifact"),
                    _text_arg(node, 99, "id"),
                )
                out.append((key, _refs(node)))
    return out


def flows(commit: str) -> dict[Key, Refs]:
    """Give the source records of each flow in `map/*.py` at a commit.

    A flow key that two calls have is not in the result."""
    try:
        tree = git("rev-parse", f"{commit}:map").strip()
    except subprocess.CalledProcessError:
        return {}
    if tree not in _FLOWS:
        calls = _calls(commit)
        count = Counter(key for key, _ in calls)
        _FLOWS[tree] = {key: refs for key, refs in calls if count[key] == 1}
    return _FLOWS[tree]


@cache
def _normal(text: str) -> str:
    try:
        return syntax_text.text(python_tree.parse(text))
    except (SyntaxError, ValueError):
        return text


def _module_of(node: ast.ImportFrom, package: str) -> str:
    if not node.level:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def _bound(tree: ast.AST, package: str, targets: set[str]) -> tuple[set[str], set[str]]:
    """Give the local names that an import of a target module binds.

    The first set has the names of the target modules. The second set has the names that
    come from a target module."""
    modules: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.asname for a in node.names if a.asname and a.name in targets}
        elif isinstance(node, ast.ImportFrom):
            _bound_from(node, _module_of(node, package), targets, modules, names)
    return modules, names


def _bound_from(
    node: ast.ImportFrom, origin: str, targets: set[str], modules: set[str], names: set[str]
) -> None:
    for alias in node.names:
        local = alias.asname or alias.name
        if f"{origin}.{alias.name}" in targets:
            modules.add(local)
        elif origin in targets:
            names.add(local)


def _defined(statement: ast.stmt) -> set[str]:
    if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return {statement.name}
    if isinstance(statement, ast.Import | ast.ImportFrom):
        return {(a.asname or a.name).partition(".")[0] for a in statement.names}
    targets: list[ast.expr] = []
    if isinstance(statement, ast.Assign):
        targets = statement.targets
    elif isinstance(statement, ast.AnnAssign | ast.AugAssign):
        targets = [statement.target]
    return {n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)}


def _used(statement: ast.stmt) -> set[str]:
    return {n.id for n in ast.walk(statement) if isinstance(n, ast.Name)}


@cache
def _partner_uses(partner: str, module: str, package: str) -> frozenset[str]:
    """Give the names of `module` that the text of a partner uses."""
    try:
        tree = ast.parse(partner)
    except (SyntaxError, ValueError):
        return frozenset()
    modules, names = _bound(tree, package, {module})
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and _module_of(node, package) == module:
            out |= {alias.name for alias in node.names}
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in modules
        ):
            out.add(node.attr)
    return frozenset(out | names)


def partner_code(module: str, text: str, partners: dict[str, str]) -> tuple[str, str] | None:
    return _partner_code(module, text, tuple(sorted(partners.items())))


@cache
def _partner_code(
    module: str, text: str, pairs: tuple[tuple[str, str], ...]
) -> tuple[str, str] | None:
    """Give the normalized partner code and the normalized start statements of a module
    text, or None without a start statement."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    package = module.rpartition(".")[0]
    modules, names = _bound(tree, package, {name for name, _ in pairs})
    theirs: set[str] = set()
    for _, partner in pairs:
        theirs |= _partner_uses(partner, module, package)
    body = [s for s in tree.body if not isinstance(s, ast.Import | ast.ImportFrom)]
    start = [s for s in body if (_used(s) & (modules | names)) or (_defined(s) & theirs)]
    if not start:
        return None
    keep = _with_used(tree, start)
    KEPT.append(len(keep) / len(tree.body))
    return _joined(keep), _joined(start)


_SIMPLE = (
    ast.Import,
    ast.ImportFrom,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Assign,
    ast.AnnAssign,
)


def _with_used(tree: ast.Module, start: list[ast.stmt]) -> list[ast.stmt]:
    """Give the start statements, each top-level statement that they use by name, and
    each top-level statement that is not simple."""
    keep = {id(s): s for s in start}
    keep.update({id(s): s for s in tree.body if not isinstance(s, _SIMPLE)})
    wanted = set().union(*(_used(s) for s in keep.values()))
    changed = True
    while changed:
        changed = False
        for statement in tree.body:
            if id(statement) not in keep and _defined(statement) & wanted:
                keep[id(statement)] = statement
                wanted |= _used(statement)
                changed = True
    return list(keep.values())


def _joined(statements: list[ast.stmt]) -> str:
    return "\n".join(sorted(syntax_text.text(s) for s in statements))


@dataclass(frozen=True)
class Event:
    commit: str
    key: Key
    kind: str
    modules: tuple[str, ...]
    symbol: str = ""


SAME, CHANGED = "same", "changed"


@cache
def _definition(text: str, name: str) -> str | None:
    """Give the normalized syntax of the top-level definition of a name, or None."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    found = [
        s
        for s in tree.body
        if name in _defined(s) and not isinstance(s, ast.Import | ast.ImportFrom)
    ]
    return _joined(found) if found else None


def symbol_state(before: Refs, after: Refs, texts: dict[str, str], named: Refs) -> str:
    """Give the symbol state of an event: `same`, `changed`, or an empty string when a
    changed module has no symbol in the records at HEAD (`named`)."""
    for loc in before.keys() & after.keys():
        if before[loc] == after[loc]:
            continue
        symbols = [n.partition(":")[2] for n in named if _module(n) == _module(loc) and ":" in n]
        if not symbols:
            return ""
        for name in symbols:
            was = _definition(texts[before[loc]], name)
            if was is None or was != _definition(texts[after[loc]], name):
                return CHANGED
    return SAME


def _module(location: str) -> str:
    return location.partition(":")[0]


def classify(before: Refs, after: Refs, texts: dict[str, str]) -> tuple[str, tuple[str, ...]]:
    changed = sorted(loc for loc in before.keys() & after.keys() if before[loc] != after[loc])
    modules = tuple(sorted({_module(loc) for loc in changed}))
    if before.keys() != after.keys():
        return SET, modules
    digests = [d for loc in changed for d in (before[loc], after[loc])]
    if any(d not in texts for d in digests):
        return UNKNOWN, modules
    if all(_normal(texts[before[loc]]) == _normal(texts[after[loc]]) for loc in changed):
        return FORMAT, modules
    kind = PARTNER
    for loc in changed:
        one = _one(loc, before, after, texts)
        if one in (NO_START, CODE):
            return one, modules
        if one == START:
            kind = START
    return kind, modules


def _one(loc: str, before: Refs, after: Refs, texts: dict[str, str]) -> str:
    """Give the class of one changed record location of a flow."""
    module = _module(loc)
    old = {_module(o): texts[d] for o, d in before.items() if o != loc and d in texts}
    new = {_module(o): texts[d] for o, d in after.items() if o != loc and d in texts}
    was = partner_code(module, texts[before[loc]], old)
    now = partner_code(module, texts[after[loc]], new)
    if was is None or now is None:
        return NO_START
    if was[1] != now[1]:
        return CODE
    return START if was[0] != now[0] else PARTNER


def events(steps: list[tuple[str, str]], texts: dict[str, str]) -> list[Event]:
    out = []
    head = flows("HEAD")
    for commit, parent in steps:
        before, after = flows(parent), flows(commit)
        for key in sorted(before.keys() & after.keys()):
            if before[key] != after[key]:
                kind, modules = classify(before[key], after[key], texts)
                state = ""
                if kind not in (SET, UNKNOWN):
                    state = symbol_state(before[key], after[key], texts, head.get(key, {}))
                out.append(Event(commit, key, kind, modules, state))
    return out


def steps(unit: str) -> list[tuple[str, str]]:
    if unit == "merge":
        lines = git("rev-list", "--first-parent", "--parents", "HEAD").splitlines()
    else:
        lines = git("rev-list", "--no-merges", "--parents", "HEAD").splitlines()
    pairs = [line.split() for line in lines]
    return [(p[0], p[1]) for p in pairs if len(p) > 1]


def report(unit: str, found: list[Event], step_count: int) -> None:
    total = len(found)
    kinds = Counter(e.kind for e in found)
    with_event = Counter(e.commit for e in found)
    print(f"unit {unit}: {step_count} steps, {len(with_event)} steps with an event, {total} events")
    for kind in CLASSES:
        share = kinds[kind] / total if total else 0.0
        print(f"  {kind:8} {kinds[kind]:5}  {share:.3f}")
    sizes = sorted(with_event.values())
    if sizes:
        print(f"  events in one step: median {sizes[len(sizes) // 2]}, largest {sizes[-1]}")
    by_module: Counter[str] = Counter()
    for event in found:
        by_module.update(event.modules)
    print("  events for each cited module (a flow event with two changed modules counts for each):")
    for module, count in by_module.most_common(8):
        print(f"    {module:32} {count:5}  {count / total:.3f}")
    states = Counter(e.symbol for e in found)
    with_symbol = states[SAME] + states[CHANGED]
    print(
        f"  symbol measure: {with_symbol} events have a symbol at HEAD for each changed module. "
        f"same {states[SAME]} ({states[SAME] / total:.3f} of all events), changed {states[CHANGED]}"
    )
    kinds_same = Counter(e.kind for e in found if e.symbol == SAME)
    print(f"  the classes of the same events: {dict(sorted(kinds_same.items()))}")
    one = sum(1 for e in found if e.kind != SET and len(e.modules) == 1)
    print(f"  events with one changed module and no set change: {one}")


def main() -> int:
    if shallow():
        print("The history is not complete. Do `git fetch --unshallow` first.", file=sys.stderr)
        return 1
    texts = source_texts()
    head = flows("HEAD")
    locations = [loc for refs in head.values() for loc in refs]
    print(f"HEAD {git('rev-parse', '--short', 'HEAD').strip()}: {len(texts)} source texts")
    print(
        f"flows at HEAD: {len(head)}, with source records: {sum(1 for r in head.values() if r)}, "
        f"records: {len(locations)}, records with a symbol: {sum(':' in x for x in locations)}"
    )
    for unit in ("merge", "commit"):
        pairs = steps(unit)
        report(unit, events(pairs, texts), len(pairs))
    kept = sorted(KEPT)
    print(
        f"partner code of {len(kept)} module texts: the kept part of the top-level statements "
        f"has median {kept[len(kept) // 2]:.2f}, lowest {kept[0]:.2f}, highest {kept[-1]:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
