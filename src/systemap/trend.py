"""The trend analysis compares historical snapshots with the component claims from the
model.

Each sample contains source facts at one commit. Each window compares two samples. The
report gives module counts, entry point counts, component sizes, and new imports across
component boundaries. It also gives commits that added modules. Rename detection pairs
the same content only. Other pairs must have a source examination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap import history
from systemap.config import Config
from systemap.evidence import owners
from systemap.model import Model

# How many modules of the window's new files are named to git at once: a
# command line has a limit, and sixty files is already more than a reader
# will follow.
FILES_ASKED = 60


@dataclass(frozen=True)
class Sample:
    """This record contains the map counts at one historical commit."""

    sha: str
    cards: dict[str, int] = field(default_factory=dict)
    crossings: set[tuple[str, str]] = field(default_factory=set)
    ways_in: int = 0
    modules: int = 0
    files: dict[str, str] = field(default_factory=dict)
    owners: dict[str, str] = field(default_factory=dict)
    shas: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Window:
    """This record contains changes between two samples and the commits that added modules."""

    base: str
    head: str
    modules: int = 0
    ways_in: int = 0
    grew: dict[str, int] = field(default_factory=dict)
    new_crossings: tuple[tuple[str, str], ...] = ()
    gone_crossings: tuple[tuple[str, str], ...] = ()
    new_files: tuple[str, ...] = ()
    caused_by: tuple[str, ...] = ()

    @property
    def size(self) -> int:
        """This property gives the total change count for window ranking."""
        return (
            abs(self.modules)
            + abs(self.ways_in)
            + 2 * len(self.new_crossings)
            + sum(abs(n) for n in self.grew.values())
        )


def sample_at(cfg: Config, model: Model, sha: str) -> Sample:
    """This function reads facts at one commit against the component claims from the model."""
    facts = history.facts_at(cfg, sha)
    components: dict[str, Any] = facts.get("components", {})
    owner = owners(model, facts)
    cards: dict[str, int] = {}
    for module in components:
        cid = owner.get(module)
        if cid:
            cards[cid] = cards.get(cid, 0) + 1
    return Sample(
        sha=sha,
        cards=cards,
        crossings=_crossings(components, owner, model),
        ways_in=len(facts.get("entry_points", [])),
        modules=len(components),
        files={m: r["file"] for m, r in components.items() if r.get("file")},
        owners=owner,
        shas={m: r["sha"] for m, r in components.items() if r.get("sha")},
    )


def _crossings(
    components: dict[str, Any], owner: dict[str, str], model: Model
) -> set[tuple[str, str]]:
    """This function finds import connections across components without a flow."""
    drawn = {f.edge for f in model.flows} | {(f.dst, f.src) for f in model.flows}
    out: set[tuple[str, str]] = set()
    for module, record in components.items():
        here = owner.get(module)
        for used in record.get("uses", {}):
            there = owner.get(used)
            if here and there and here != there and (here, there) not in drawn:
                out.add((here, there))
    return out


def between(before: Sample, now: Sample) -> Window:
    """This function compares two samples."""
    before_cards = dict(before.cards)
    vanished = set(before.files) - set(now.files)
    appeared = set(now.files) - set(before.files)
    for fresh in appeared:
        card = now.owners.get(fresh)
        digest = now.shas.get(fresh)
        if not card or not digest:
            continue
        matching = [old for old in vanished if before.shas.get(old) == digest]
        if len(matching) == 1 and fresh not in before.files:
            old = matching[0]
            if old not in before.owners:
                before_cards[card] = before_cards.get(card, 0) + 1
                vanished.remove(old)
    grew = {
        cid: now.cards.get(cid, 0) - before_cards.get(cid, 0)
        for cid in set(before_cards) | set(now.cards)
    }
    return Window(
        base=before.sha,
        head=now.sha,
        modules=now.modules - before.modules,
        ways_in=now.ways_in - before.ways_in,
        grew={cid: n for cid, n in grew.items() if n},
        new_crossings=tuple(sorted(now.crossings - before.crossings)),
        gone_crossings=tuple(sorted(before.crossings - now.crossings)),
        new_files=tuple(sorted(now.files[m] for m in set(now.files) - set(before.files))),
    )


def walk(cfg: Config, model: Model, shas: list[str]) -> list[Window]:
    """This function gives windows between sampled commits, in chronological order."""
    out: list[Window] = []
    before: Sample | None = None
    for sha in shas:
        now = sample_at(cfg, model, sha)
        if before is not None:
            out.append(between(before, now))
        before = now
    return out


def with_causes(root: Path, window: Window, cap: int = 5) -> Window:
    """This function adds the commits that introduced modules to the window."""
    if not window.new_files:
        return window
    try:
        out = history.git(
            root,
            "log",
            "--format=%s",
            f"{window.base}..{window.head}",
            "--",
            *window.new_files[:FILES_ASKED],
        )
    except Exception:  # noqa: BLE001 - a window whose commits cannot be read is still a window
        return window
    found = tuple(line for line in out.splitlines() if line)[:cap]
    return Window(
        base=window.base,
        head=window.head,
        modules=window.modules,
        ways_in=window.ways_in,
        grew=window.grew,
        new_crossings=window.new_crossings,
        gone_crossings=window.gone_crossings,
        new_files=window.new_files,
        caused_by=found,
    )


def report(windows: list[Window], root: Path, since: str, every: int, top: int) -> list[str]:
    """This function formats the largest change windows and their source commits."""
    moved = [w for w in windows if w.size]
    head = (
        f"history: {len(windows) + 1} samples since {since}, one every {every} days. "
        f"{len(moved)} of {len(windows)} windows changed the map."
    )
    if not moved:
        return [
            head,
            (
                "  No map change occurs in this period. Module counts, component sizes, and "
                "imports across component boundaries stayed the same."
            ),
        ]
    out = [
        head,
        (
            f"  The {min(top, len(moved))} largest windows follow. Equal sizes use the "
            f"last window in chronological order first:"
        ),
    ]
    for window in sorted(moved, key=lambda w: w.size, reverse=True)[:top]:
        out += _window_lines(with_causes(root, window))
    out.append("  Component counts use the module claims from the model for each historical tree.")
    out.append(
        "  Renames with the same content form pairs. Renames with changed content must "
        "have a source review."
    )
    return out


def _window_lines(window: Window) -> list[str]:
    out = [f"  {window.base[:7]}..{window.head[:7]}"]
    if window.modules or window.ways_in:
        out.append(f"      modules {window.modules:+d}, entry points {window.ways_in:+d}")
    if window.grew:
        moved = ", ".join(f"{cid} {n:+d}" for cid, n in sorted(window.grew.items()))
        out.append(f"      components: {moved}")
    if window.new_crossings:
        left = len(window.new_crossings) - 5
        pairs = ", ".join(f"{a} -> {b}" for a, b in window.new_crossings[:5])
        more = f", and {left} more" if left > 0 else ""
        out.append(f"      new crossing imports: {pairs}{more}")
    out += [f"      added by commit: {title[:100]}" for title in window.caused_by]
    return out
