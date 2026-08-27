"""What a change does to the map: `systemap delta --base REF [--head REF]`.

The loop in the skill is built for the first draft. After a pull request
moves a module, `extract --check` fails, says the map is stale, and the
only answer used to be the whole loop again, at first-draft cost. This
module reads the facts at two commits and says, in the map's terms, what
the change did:

    moved ................ a module at a new path, with the same content,
                           the same public names, or a file name that reads
                           the same and most of the same names; the card
                           that names the old path is told to rename it
    added ................ a new module, and the card that claims it; a new
                           module no card claims is coverage lost, and the
                           line says so
    removed .............. a module that is gone, and the card that still
                           names it
    entry vanished ....... a card's entry that its modules defined at the
                           base commit and no longer do
    interface vanished ... the same for the name an interface line starts
                           with, by the check's own interface rule
    new crossing import .. an import that crosses a card boundary at the
                           head commit, did not at the base, and has no
                           flow and no answer under [judgement]
    evidence lost ........ a flow an import backed at the base commit and
                           nothing backs now

Each line names its fix. A line needs a person, or it does not (a new
module claimed through a `pkg.*` pattern needs nobody), and the exit
code says which: 0 when nothing needs a person, 1 when something does.
`--format markdown` prints the same report as a pull-request comment.

The facts at each commit are read from the git tree (`git archive` into
a temporary directory, then the extractor as usual), so the working copy
is not touched and an extraction here cannot differ from what `systemap
extract` would read at that commit. The model is the one on disk, the map
as it is now, the file the person edits: a card that names a module's new
path is taken to have claimed the old one at the base commit, and a card
that still names the old path is judged as if renamed, so a pending rename
is one line, not four.

The comparison runs on every map of the tree (`compute_tree`): the top
map over every module, and the map inside a card over the modules that
card claims, so a moved module names its card on each map it is drawn
on, and the map's file. A sub-map's lines carry its id in front.
"""

from __future__ import annotations

import dataclasses
import io
import re
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path, PurePosixPath
from typing import Any

from systemap import evidence, extract, nest
from systemap.check import interface_head, interface_problem
from systemap.config import Config
from systemap.judgement import answers, crossing_line, crossing_pairs
from systemap.model import (
    Component,
    Meaning,
    Model,
    claimed,
    defines_entry,
    is_symbol,
    module_matches,
    public_names,
    symbol_claims,
)

MARKER = "<!-- systemap delta -->"
NEXT = "systemap refresh && systemap check && systemap judgement --strict"
# Past this share of the cards, the skill says to run the full loop instead
# of acting line by line.
FULL_LOOP_SHARE = 1 / 3
# What the last question asks of a module renamed and edited at once:
# how much of its public surface it kept, and how alike the two file
# names read. Measured over every python rename git reports in kstrl,
# rich, poetry, mealie and paperless-ngx. 0.8 of the surface is the
# loosest value that costs nothing: at 0.6, mealie gains two wrong
# pairings. 0.6 of the file name buys two more real renames for one
# wrong one, and is what recognises route.py -> routing.py, which
# reads 0.78 alike.
SURFACE_OVERLAP = 0.8
NAME_ALIKE = 0.6


class DeltaError(Exception):
    """The two commits cannot be compared; the message says why."""


# ---- git: the facts at a commit, without touching the working copy -----------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, timeout=300)


def resolve(repo: Path, ref: str) -> str:
    """The full commit sha a ref names, or a DeltaError naming the ref."""
    proc = _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if proc.returncode != 0 or not proc.stdout.strip():
        raise DeltaError(f"unknown ref {ref}; give a commit, a branch or a tag git can find")
    return proc.stdout.decode("utf-8").strip()


def merge_base(repo: Path, base: str, head: str) -> str:
    """The commit the two share, so a base branch that moved on is not a change;
    the base itself when git cannot say (no shared history)."""
    proc = _git(repo, "merge-base", base, head)
    out = proc.stdout.decode("utf-8").strip()
    return out if proc.returncode == 0 and out else base


def _extract_all(tar: tarfile.TarFile, into: Path) -> None:
    # The data filter refuses paths outside the target; it exists from
    # 3.11.4, and an older 3.11 extracts the archive git wrote as is.
    if hasattr(tarfile, "data_filter"):
        tar.extractall(into, filter="data")
    else:  # pragma: no cover - older interpreters only
        tar.extractall(into)


def facts_at(cfg: Config, sha: str) -> dict[str, Any]:
    """The facts for the tree at `sha`, extracted from git, never from the working copy."""
    proc = _git(cfg.root, "archive", "--format=tar", sha)
    if proc.returncode != 0:
        raise DeltaError(
            f"git archive {sha[:7]} failed: {proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    with tempfile.TemporaryDirectory(prefix="systemap-delta-") as tmp:
        into = Path(tmp).resolve()
        with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tar:
            _extract_all(tar, into)
        facts = extract.build(dataclasses.replace(cfg, root=into))
    facts["built_at_commit"] = sha
    return facts


def remote_repository(repo: Path) -> str:
    """`owner/name` of the origin remote when it is on GitHub, else empty."""
    proc = _git(repo, "remote", "get-url", "origin")
    if proc.returncode != 0:
        return ""
    url = proc.stdout.decode("utf-8", "replace").strip()
    found = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return f"{found.group(1)}/{found.group(2)}" if found else ""


def figure_url(cfg: Config, sha: str) -> str:
    """The committed whole-map figure at `sha`, as the URL a comment renders, or empty.

    A comment cannot show a relative path, and GitHub's own writing guide
    gives the form for an image in the repository from an issue or a pull
    request: the blob URL with `?raw=true`. The figure is the first
    configured `.svg` that draws every reading (no `layer`), else the first
    `.svg`; nothing when the file is not in the tree at that commit.
    """
    owner = remote_repository(cfg.root)
    if not owner:
        return ""
    svgs = [f for f in cfg.figures if f.out.endswith(".svg")]
    whole = [f for f in svgs if not f.layer]
    for fig in whole + svgs:
        path = f"{cfg.out_dir}/{fig.out}"
        if _git(cfg.root, "cat-file", "-e", f"{sha}:{path}").returncode == 0:
            return f"https://github.com/{owner}/blob/{sha}/{path}?raw=true"
    return ""


# ---- the comparison --------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    """One thing the change did to the map, with its fix when a person is needed."""

    kind: str
    text: str
    cards: tuple[str, ...] = ()
    person: bool = False


@dataclass(frozen=True)
class Delta:
    """Everything `systemap delta` reports about two commits."""

    base: str
    head: str
    base_ref: str
    head_ref: str
    changed: int
    added: int
    removed: int
    moved: int
    cards: int
    lines: tuple[Line, ...]

    @property
    def open(self) -> list[Line]:
        return [line for line in self.lines if line.person]

    @property
    def quiet(self) -> list[Line]:
        return [line for line in self.lines if not line.person]

    @property
    def named(self) -> list[str]:
        return sorted({card for line in self.lines for card in line.cards})

    @property
    def has_change(self) -> bool:
        return bool(self.changed or self.added or self.removed or self.moved or self.lines)

    @property
    def past_a_third(self) -> bool:
        return self.cards > 0 and len(self.named) > self.cards * FULL_LOOP_SHARE


def _path(record: dict[str, Any]) -> PurePosixPath:
    """Where a module's file sits, as the facts recorded it."""
    return PurePosixPath(str(record.get("file", "")))


def _affinity(old: dict[str, Any], cand: dict[str, Any]) -> tuple[int, int, int]:
    """How alike two modules' files are: the tail of the path first, then
    how alike the two file names read, then the head of the path.

    The middle term is the one that earns its place. A package that
    renumbers its migrations offers a file per number with the same one
    class in each, so every other signal ties, and only `0003_widget.py`
    reading like `0004_widget.py` says which became which.
    """
    a, b = _path(old).parts, _path(cand).parts
    tail = 0
    for x, y in zip(reversed(a), reversed(b), strict=False):
        if x != y:
            break
        tail += 1
    head = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        head += 1
    return (tail, int(_alike(a[-1] if a else "", b[-1] if b else "") * 1000), head)


def _first(score: tuple[int, int, int]) -> tuple[int, int, int]:
    """The sort key that puts the likeliest pairing first."""
    return (-score[0], -score[1], -score[2])


def _alike(a: str, b: str) -> float:
    """How alike two file names read, between 0 and 1."""
    return SequenceMatcher(None, a, b).ratio()


def _overlap(a: set[str], b: set[str]) -> float:
    """The share of the two surfaces' names that both of them have."""
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _moves(
    base: dict[str, Any], head: dict[str, Any], gone: list[str], new: list[str]
) -> dict[str, tuple[str, str]]:
    """old module -> (new module, how it was recognised), for every move.

    Three questions, the strongest first: the same source (the extractor's
    sha), then the same public names, then a file name that reads the same
    and most of the same names. Each new module is matched once.

    Every pairing a question admits is scored by `_affinity` and the best
    is taken, because a question can admit a great many at once. When a
    package moves to a src layout, every empty `__init__.py` in it has the
    same source as every other, and pairing each old module with the first
    free candidate walks the whole set one place along, so each card is
    told to rename its claim to its neighbour's module. Measured on the
    renames git reports in five repositories, taking the best pairing
    rather than the first turned 27 such wrong lines into 12.
    """
    surface = {m: public_names(r) for m, r in list(base.items()) + list(head.items())}
    out: dict[str, tuple[str, str]] = {}
    taken: set[str] = set()

    def assign(pairs: list[tuple[tuple[int, int, int], str, str]], how: str) -> None:
        for _score, old, cand in sorted(pairs, key=lambda p: (_first(p[0]), p[1], p[2])):
            if old in out or cand in taken:
                continue
            out[old] = (cand, how)
            taken.add(cand)

    def left() -> list[str]:
        return [m for m in gone if m not in out]

    def right() -> list[str]:
        return [m for m in new if m not in taken]

    # The same source is strong evidence, except where there is no source
    # to speak of: two empty modules are alike for a reason that says
    # nothing about which is which, so their file names must agree.
    assign(
        [
            (_affinity(base[o], head[c]), o, c)
            for o in left()
            for c in right()
            if base[o]["sha"] == head[c]["sha"]
            and (surface[o] or _path(base[o]).name == _path(head[c]).name)
        ],
        "same content",
    )
    assign(
        [
            (_affinity(base[o], head[c]), o, c)
            for o in left()
            if surface[o]
            for c in right()
            if surface[c] == surface[o]
        ],
        "same public names",
    )
    # A module renamed and edited in the same commit answers neither
    # question above: its source changed and so did its surface. What is
    # left is how much of the surface survived and how alike the two file
    # names read.
    assign(
        [
            (_affinity(base[o], head[c]), o, c)
            for o in left()
            if surface[o]
            for c in right()
            if surface[c]
            and _alike(_path(base[o]).name, _path(head[c]).name) >= NAME_ALIKE
            and _overlap(surface[o], surface[c]) >= SURFACE_OVERLAP
        ],
        "a file name that reads the same and most of the same names",
    )
    return out


def _mapped(pattern: str, mapping: dict[str, str]) -> str:
    """One `implemented_by` entry with a moved module renamed; patterns stay."""
    if is_symbol(pattern):
        module, _, name = pattern.partition(":")
        return f"{mapping.get(module, module)}:{name}"
    return mapping.get(pattern, pattern)


def with_claims(model: Model, mapping: dict[str, str]) -> Model:
    """The model with every claim renamed through `mapping`, positions and all."""
    return dataclasses.replace(
        model,
        components=tuple(
            dataclasses.replace(
                c, implemented_by=tuple(_mapped(p, mapping) for p in c.implemented_by)
            )
            for c in model.components
        ),
    )


def _names_it(c: Component, module: str) -> bool:
    """Does a card name `module` outright, by name or as a symbol's module?"""
    return module in c.implemented_by or any(m == module for m, _n in symbol_claims(c))


def compute(
    cfg: Config,
    model: Model,
    meaning: Meaning,
    base: dict[str, Any],
    head: dict[str, Any],
    base_ref: str = "",
    head_ref: str = "",
    *,
    model_file: str = "",
    within: str = "",
    prefix: str = "",
) -> Delta:
    """What the change from `base` to `head` does to the map the model draws.

    `model_file` is the file the fixes name (the configured model when
    empty); `within` names the card a sub-map is inside, whose claims
    bound what a new module may be ignored from; `prefix` is what the
    sub-map's judgement lines carry, so an answered crossing import is
    matched as printed.
    """
    b: dict[str, Any] = base.get("components", {})
    h: dict[str, Any] = head.get("components", {})
    gone = sorted(set(b) - set(h))
    new = sorted(set(h) - set(b))
    moves = _moves(b, h, gone, new)
    renamed = {old: new_name for old, (new_name, _how) in moves.items()}
    inverse = {new_name: old for old, new_name in renamed.items()}
    model_file = model_file or cfg.model
    base_short = base.get("built_at_commit", "")[:7]
    at_base = f" at {base_short}" if base_short else " at the base commit"

    # The map as written names what the person can edit; the two views are
    # the same claims carried to each commit's names.
    head_model = with_claims(model, renamed)
    base_model = with_claims(model, inverse)
    owner_written = evidence.owners(model, head)
    owner_head = evidence.owners(head_model, head)
    owner_base = evidence.owners(base_model, base)
    ignores = [i.module for i in cfg.coverage_ignore]

    def ignored(module: str) -> bool:
        return any(module_matches(i, module) for i in ignores)

    lines: list[Line] = []

    # ---- moved, added, removed ------------------------------------------------
    for old, (new_name, how) in moves.items():
        explicit = [c.id for c in model.components if _names_it(c, old)]
        claimed_by = owner_written.get(new_name)
        if explicit:
            who = ", ".join(explicit)
            lines.append(
                Line(
                    "moved",
                    f"moved: {old} -> {new_name} ({how}); {who} names {old} in implemented_by: "
                    f"rename it to {new_name} in {model_file}",
                    tuple(explicit),
                    person=True,
                )
            )
        elif (
            claimed_by is None
            and not ignored(new_name)
            and not extract.is_empty_marker(h[new_name])
        ):
            was = owner_base.get(old)
            lines.append(
                Line(
                    "moved",
                    f"moved: {old} -> {new_name} ({how}); no card claims {new_name}: name it in "
                    f"a card's implemented_by in {model_file}",
                    (was,) if was else (),
                    person=True,
                )
            )
        else:
            where = f", claimed by {claimed_by}" if claimed_by else ", ignored under [coverage]"
            lines.append(
                Line(
                    "moved",
                    f"moved: {old} -> {new_name} ({how}){where}",
                    (claimed_by,) if claimed_by else (),
                )
            )
    for module in new:
        if module in inverse:
            continue
        claimed_by = owner_written.get(module)
        if claimed_by:
            lines.append(Line("added", f"added: {module}, claimed by {claimed_by}", (claimed_by,)))
        elif extract.is_empty_marker(h[module]):
            lines.append(Line("added", f"added: {module}, an empty package marker"))
        elif ignored(module) and not within:
            lines.append(Line("added", f"added: {module}, ignored under [coverage]"))
        else:
            # Inside a card there is no ignoring: the sub-map claims
            # exactly what the card claims.
            way_out = (
                f"the map inside {within} claims exactly what {within} claims"
                if within
                else "or ignore it with a reason under [coverage]"
            )
            lines.append(
                Line(
                    "added",
                    f"added: {module}, claimed by no card; name it in a card's implemented_by "
                    f"in {model_file}, {way_out}",
                    person=True,
                )
            )
    for module in gone:
        if module in renamed:
            continue
        explicit = [c.id for c in model.components if module in c.implemented_by]
        symbols = [
            (c.id, name) for c in model.components for m, name in symbol_claims(c) if m == module
        ]
        if explicit:
            who = ", ".join(explicit)
            lines.append(
                Line(
                    "removed",
                    f"removed: {module}; {who} names it in implemented_by: drop it in {model_file}",
                    tuple(explicit),
                    person=True,
                )
            )
        elif symbols:
            who = ", ".join(f"{cid} claims symbol {module}:{name}" for cid, name in symbols)
            lines.append(
                Line(
                    "removed",
                    f"removed: {module}; {who}: drop it in {model_file}",
                    tuple(cid for cid, _n in symbols),
                    person=True,
                )
            )
        elif module in ignores and not within:
            lines.append(
                Line(
                    "removed",
                    f"removed: {module}; the [coverage] ignore that names it is stale: remove it",
                    person=True,
                )
            )
        else:
            was = owner_base.get(module)
            tail = f", was claimed by {was} through a pattern" if was else ""
            lines.append(Line("removed", f"removed: {module}{tail}", (was,) if was else ()))

    # ---- entry and interface names that vanished ---------------------------------
    # A card told to rename or drop a module is not asked about its names
    # too: the rename or the drop comes first, and delta is run again.
    touched = {card for line in lines if line.person for card in line.cards}
    for c_base, c_head in zip(base_model.components, head_model.components, strict=True):
        if c_head.kind == "actor" or c_head.id in touched:
            continue
        if c_head.entry and defines_entry(c_base, base) and not defines_entry(c_head, head):
            lines.append(
                Line(
                    "entry vanished",
                    f"entry vanished: {c_head.id} names entry {c_head.entry}, which its modules "
                    f"defined{at_base} and no longer do; set entry to a public name they define "
                    f"in {model_file}",
                    (c_head.id,),
                    person=True,
                )
            )
        if not c_head.interface.strip() or interface_problem(c_base, b):
            continue
        if interface_problem(c_head, h):
            found = interface_head(c_head.interface)
            name = ".".join(part for part in (found or ("", "")) if part)
            lines.append(
                Line(
                    "interface vanished",
                    f"interface vanished: {c_head.id}'s interface starts with {name}, which its "
                    f"modules defined{at_base} and no longer do; start it with a public name "
                    f"they define in {model_file}, or leave it empty",
                    (c_head.id,),
                    person=True,
                )
            )

    # ---- new crossing imports ------------------------------------------------------
    joined = {frozenset(f.edge) for f in model.flows}
    before = {(renamed.get(m, m), renamed.get(t, t)) for m in b for t in b[m].get("uses", {})}
    # The judgement's line for the pair at the head commit, so an answer
    # that covers the pair there (by pair, into, from, kind or the exact
    # line) covers the new import here.
    pairs = crossing_pairs(h, owner_head)
    for module in sorted(h):
        p = owner_head.get(module)
        if not p:
            continue
        for target in sorted(h[module].get("uses", {})):
            q = owner_head.get(target)
            if not q or q == p or frozenset((p, q)) in joined or (module, target) in before:
                continue
            asked = prefix + crossing_line(p, q, pairs.get((p, q), [(module, target)]))
            if any(answers(a, asked) for a in cfg.judgement_answered):
                continue
            lines.append(
                Line(
                    "new crossing import",
                    f"new crossing import: {module} (card {p}) imports {target} (card {q}) and "
                    f"no flow joins {p} and {q}; add the flow with its sentence in {model_file}, "
                    "or answer it under [judgement] answered",
                    (p, q),
                    person=True,
                )
            )

    # ---- evidence lost ------------------------------------------------------------------
    ev_base = evidence.of_model(base_model, meaning, base, cfg.observed_by)
    ev_head = evidence.of_model(head_model, meaning, head, cfg.observed_by)
    for f in model.flows:
        was_observed = ev_base[f.edge].state == evidence.OBSERVED
        if was_observed and ev_head[f.edge].state == evidence.DECLARED:
            lines.append(
                Line(
                    "evidence lost",
                    f"evidence lost: {f.src} -> {f.dst} ({f.artifact}) was observed{at_base} and "
                    "no import joins them now; find the evidence, name the mechanism in the "
                    f"sentence, or remove the flow in {model_file}",
                    (f.src, f.dst),
                    person=True,
                )
            )

    changed = sum(1 for m in set(b) & set(h) if b[m].get("sha") != h[m].get("sha"))
    return Delta(
        base=base.get("built_at_commit", ""),
        head=head.get("built_at_commit", ""),
        base_ref=base_ref,
        head_ref=head_ref,
        changed=changed,
        added=len(new) - len(moves),
        removed=len(gone) - len(moves),
        moved=len(moves),
        cards=sum(1 for c in model.components if c.kind != "actor"),
        lines=tuple(lines),
    )


def _view(facts: dict[str, Any], modules: set[str]) -> dict[str, Any]:
    """The facts restricted to `modules`: what a map inside a card compares."""
    components: dict[str, Any] = facts.get("components", {})
    return {**facts, "components": {m: r for m, r in components.items() if m in modules}}


def compute_tree(
    cfg: Config,
    tree: nest.Tree,
    base: dict[str, Any],
    head: dict[str, Any],
    base_ref: str = "",
    head_ref: str = "",
) -> Delta:
    """The change on every map of the tree, as one report.

    The top map is compared over every module. The map inside a card is
    compared over the modules the card claims, at each commit (a moved
    module counts on both sides, through the card's renamed claims), so
    a module the card lost or gained names the sub-map's card and file
    too, and nothing outside the card is the sub-map's business. The
    counts are the top map's; the cards named are every map's, a
    sub-map's under `<map>/<card>`.
    """
    top = compute(cfg, tree.top.model, tree.top.meaning, base, head, base_ref, head_ref)
    b: dict[str, Any] = base.get("components", {})
    h: dict[str, Any] = head.get("components", {})
    gone = sorted(set(b) - set(h))
    new = sorted(set(h) - set(b))
    renamed = {old: new_name for old, (new_name, _how) in _moves(b, h, gone, new).items()}
    inverse = {new_name: old for old, new_name in renamed.items()}
    lines = list(top.lines)
    cards = top.cards
    for m in tree.maps[1:]:
        card = tree.opening_card(m)
        if card is None:
            continue
        at_head = set(claimed(card, h))
        at_base = set(claimed(with_claims_of(card, inverse), b))
        sub = compute(
            cfg,
            m.model,
            m.meaning,
            _view(base, at_base),
            _view(head, at_head),
            base_ref,
            head_ref,
            model_file=m.rel,
            within=card.id,
            prefix=m.prefix,
        )
        cards += sub.cards
        lines += [
            dataclasses.replace(
                line,
                text=m.prefix + line.text,
                cards=tuple(f"{m.id}/{c}" for c in line.cards),
            )
            for line in sub.lines
        ]
    return dataclasses.replace(top, cards=cards, lines=tuple(lines))


def with_claims_of(card: Component, mapping: dict[str, str]) -> Component:
    """One card with its claims renamed through `mapping`."""
    return dataclasses.replace(
        card, implemented_by=tuple(_mapped(p, mapping) for p in card.implemented_by)
    )


# ---- the two reports -------------------------------------------------------------------


def _label(ref: str, sha: str) -> str:
    short = sha[:7]
    if ref and short and not ref.startswith(short) and ref != sha:
        return f"{ref} ({short})"
    return ref or short


def _counts(d: Delta) -> str:
    return (
        f"{d.changed} modules changed, {d.added} added, {d.removed} removed, {d.moved} moved; "
        f"{len(d.named)} of {d.cards} cards named"
    )


FULL_LOOP = (
    "more than a third of the cards are named: the skill says to run the full loop "
    "instead of acting line by line"
)


def report(d: Delta) -> list[str]:
    """The lines the CLI prints: the header, each group, and what to run."""
    span = f"{_label(d.base_ref, d.base)} -> {_label(d.head_ref, d.head)}"
    if not d.has_change:
        pair = f"{_label(d.base_ref, d.base)} and {_label(d.head_ref, d.head)}"
        return [f"delta: no module changed between {pair}; the map is unaffected"]
    out = [f"delta: {span}: {_counts(d)}"]
    if d.open:
        out.append(f"needs a person ({len(d.open)}):")
        out += [f"  {line.text}" for line in d.open]
    if d.quiet:
        out.append(f"changed, nothing to do ({len(d.quiet)}):")
        out += [f"  {line.text}" for line in d.quiet]
    if d.past_a_third:
        out.append(FULL_LOOP)
    if d.open:
        out.append(f"act on each line above, then run: {NEXT}")
    else:
        out.append("nothing needs a person; run: systemap refresh")
    return out


def markdown(d: Delta, figure: str = "") -> str:
    """The same report as a pull-request comment; `figure` is the committed map's URL."""
    span = f"`{_label(d.base_ref, d.base)}` to `{_label(d.head_ref, d.head)}`"
    out = [MARKER, "## What this change does to the map", ""]
    if not d.has_change:
        out += [
            f"No module changed between {span.replace(' to ', ' and ')}; the map is unaffected.",
            "",
        ]
        return "\n".join(out)
    out += [f"{span}: {_counts(d)}.", ""]
    if d.open:
        out += [f"**Needs a person ({len(d.open)})**", ""]
        out += [f"- `{line.text}`" for line in d.open]
        out.append("")
    if d.quiet:
        out += [f"**Changed, nothing to do ({len(d.quiet)})**", ""]
        out += [f"- `{line.text}`" for line in d.quiet]
        out.append("")
    if d.past_a_third:
        out += [f"> {FULL_LOOP[0].upper()}{FULL_LOOP[1:]}.", ""]
    head_short = d.head[:7] or d.head_ref
    base_short = d.base[:7] or d.base_ref
    if figure:
        out += [f"![the map at {head_short}]({figure})", ""]
        out.append(
            f"The committed map at `{head_short}`; the change map itself is "
            f"`systemap figure --mode change --base {base_short} --out change.svg`."
        )
    else:
        out.append(
            f"No committed figure to show at `{head_short}`; the change map is "
            f"`systemap figure --mode change --base {base_short} --out change.svg`."
        )
    if d.open:
        out.append(f"Act on each line, then run `{NEXT}`.")
    else:
        out.append("Nothing needs a person; `systemap refresh` brings the facts up to date.")
    out.append("")
    return "\n".join(out)
