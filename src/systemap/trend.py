"""The system over a year, read in today's cards.

A map says what the system is now. This says how it got here: the tree is
sampled back through history, the facts at each commit are read against the
map as it stands today, and each window is what moved between two samples.

    cards ........ how many modules each card claimed then and claims now
    crossings .... which pairs of cards imported each other with no flow
    ways in ...... how many places a run could start

Reading today's cards backwards is deliberate. A card is a claim about
purpose, and purpose outlives file names: a module that moved into a
package still belongs to the card whose job it does, so the trend is about
the system rather than about renames.

Nothing here judges. A card that grew is not a fault; a card that grew by
seventeen modules in a fortnight is something a maintainer should know they
did. Each window names the commits that wrote the modules which appeared, so
a number always leads back to the work behind it.

Measured before it was built, on a year of mealie sampled every fortnight:
25 samples took 29 seconds the first time and under a second with the facts
cached, against a bar of five minutes warm; and of the five largest windows,
five named a change a person can find in the commits of that window, against
a bar of three. `bench/jev/history_eval.py` is the run.
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
    """What the map would have said about the system at one commit."""

    sha: str
    cards: dict[str, int] = field(default_factory=dict)
    crossings: set[tuple[str, str]] = field(default_factory=set)
    ways_in: int = 0
    modules: int = 0
    files: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Window:
    """What moved between two samples, and the work that moved it."""

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
        """How much moved, for deciding what a reader should look at first."""
        return (
            abs(self.modules)
            + abs(self.ways_in)
            + 2 * len(self.new_crossings)
            + sum(abs(n) for n in self.grew.values())
        )


def sample_at(cfg: Config, model: Model, sha: str) -> Sample:
    """The facts at one commit, read in today's cards."""
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
    )


def _crossings(
    components: dict[str, Any], owner: dict[str, str], model: Model
) -> set[tuple[str, str]]:
    """The card pairs one imports the other, where the map draws no flow."""
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
    """What moved between two samples."""
    grew = {
        cid: now.cards.get(cid, 0) - before.cards.get(cid, 0)
        for cid in set(before.cards) | set(now.cards)
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
    """Every window between the sampled commits, oldest first."""
    out: list[Window] = []
    before: Sample | None = None
    for sha in shas:
        now = sample_at(cfg, model, sha)
        if before is not None:
            out.append(between(before, now))
        before = now
    return out


def with_causes(root: Path, window: Window, cap: int = 5) -> Window:
    """The same window, with the commits that wrote the modules which appeared."""
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
    """The trend as a person reads it: the largest windows first, with the work behind them."""
    moved = [w for w in windows if w.size]
    head = (
        f"history: {len(windows) + 1} samples since {since}, one every {every} days; "
        f"{len(moved)} of {len(windows)} windows moved the map"
    )
    if not moved:
        return [
            head,
            "  nothing the map can see changed in that time: no module came or went, "
            "no card grew, no new import crossed a card boundary",
        ]
    out = [head, f"  the {min(top, len(moved))} largest, most recent first where they tie:"]
    for window in sorted(moved, key=lambda w: w.size, reverse=True)[:top]:
        out += _window_lines(with_causes(root, window))
    out.append("  each window is read in today's cards, so a module that moved still counts")
    out.append("  as the card whose job it does")
    return out


def _window_lines(window: Window) -> list[str]:
    out = [f"  {window.base[:7]}..{window.head[:7]}"]
    if window.modules or window.ways_in:
        out.append(f"      modules {window.modules:+d}, ways in {window.ways_in:+d}")
    if window.grew:
        moved = ", ".join(f"{cid} {n:+d}" for cid, n in sorted(window.grew.items()))
        out.append(f"      cards: {moved}")
    if window.new_crossings:
        left = len(window.new_crossings) - 5
        pairs = ", ".join(f"{a} -> {b}" for a, b in window.new_crossings[:5])
        more = f", and {left} more" if left > 0 else ""
        out.append(f"      new crossing imports: {pairs}{more}")
    out += [f"      written by: {title[:100]}" for title in window.caused_by]
    return out
