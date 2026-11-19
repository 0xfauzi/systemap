"""The history data of the atlas page: where the source files of each component changed, and when.

The History view of the atlas page (docs/design/atlas.md, `atlas_history`) shows one row for
each component with a change and one column for each of PARTS equal parts of the time. This
module reads the commits with Git and gives the data of the view.

The log. `read_log` reads each commit that is not a merge, with `git log --no-merges
--no-renames --numstat --raw`. For each commit it keeps the time of the commit, the changed
files with their changed lines (the added and the removed lines), and the new files. A binary
file has 0 changed lines. A moved file is a removed file and a new file, because the log has
no rename detection. A commit with no parent is not used: this is the root commit, or a
boundary commit of a shallow clone. Git gives the full tree of such a commit as new lines, so
it is not a change. The data says when the clone is shallow (`shallow`): then the commits
before the boundary are not there.

The cache. The log goes into `.systemap/history.json` with the commit of HEAD, the digest of
the list of the boundary commits of a shallow clone, and `history_days`. A render with the
same HEAD, the same boundary and the same days uses the cache and does not read the log
again. When the commit of the cache is an earlier commit of HEAD, the module reads only the
new commits (`git log OLD..HEAD`) and adds them. A different boundary (for example after
`git fetch --deepen`), a different value of the days, or a HEAD that does not contain the
commit of the cache makes a full read. A problem with the cache file is not an error: the
module then reads the log.

The window. With `[render] history_days = N`, a full read first reads only the commit times
(`git log --no-merges --min-parents=1 --format=%ct`). The last of these times is the end. The
read of the changes then uses `--since-as-filter`, and it gives only the commits of the N days
before the end. Thus Git does not give the changes of the older commits, and the cache keeps
only the commits of the window. `first` keeps the time of the first used commit of HEAD, so
that the parts are the same as with the full log. `--since-as-filter` needs Git 2.37 or
later. An earlier Git gives the notice line of `NOTICE`.

The components. A file belongs to a component when the module claims of the component
(`implemented_by`, with `model.claimed`) cover the module of the file in the facts
(`facts["components"]`, the `file` of each module record). The first component of the model
in model order owns a module, as in `change`. A symbol claim covers no module. Only the
files of the modules of the current facts count: a file that the facts do not have (a test,
a document, a removed module) has no component. The rows are the components of the top map.

The time. The parts go from the time of the first used commit to the time of the last used
commit. With `[render] history_days = N`, the first part starts N days before the last used
commit, and the older commits are not used. The end is the time of a commit, not the time
of the clock. Thus the data of the same commits is the same on each day.

The data. `commits` is the count of used commits, `days` is the value of `history_days`,
`from` and `to` are the dates of the first and the last part, `parts` gives the dates of
each part, and `cells` gives for each component with a change one list of PARTS cells:
[file changes, changed lines, new modules]. The new modules are the short names of the new
files. The dates are UTC dates, with the year when the parts are not all in one year.

When Git cannot start, or the root is not in a Git work tree with a commit, `of_tree` gives
no data and one notice line (`NOTICE`) with the cause of Git. When Git reads the commits and
no commit is used, `of_tree` gives no data and one notice line: `SHALLOW` for a shallow clone
that has only boundary commits (a clone with `--depth 1`, the default clone of many CI
systems), and `ROOT_ONLY` for a HEAD with only a root commit. When commits are used and no
commit changed a file of a component, the notice line is `NO_CHANGE`. The exit code does not
change. Then the page has no History view.

A merge commit is not used. `--no-merges` leaves it out of `commits` and out of the cells.
The changes of a merge are in the commits that it joins.

The output check (`check`, `render --check`) does not read Git. It uses the history data of
the page file (`stored`). Thus a new commit, also the commit of the page itself, does not
make the page stale. A refresh writes the history of the commits at that time. The data has
`days`, the value of `history_days` of the render (0 for all commits). When the page file has
a different value, `stored` gives no data, and the output check finds that the page is stale.
A change from one shallow depth to a different depth does not make the page stale, because
the check does not read Git.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from systemap import file_write, git_command, nest
from systemap.config import Config
from systemap.model import Model, claimed

PARTS = 12
CACHE = ".systemap/history.json"
VERSION = 2
DAY = 86_400
NOTICE = "notice: The page has no History view, because Git cannot read the commits: {cause}"
# The notice lines when Git reads the commits and no history data is possible.
SHALLOW = (
    "notice: The page has no History view, because the clone is shallow and has only boundary"
    " commits. Git cannot give the changes of a boundary commit. Get more commits, for example"
    " with git fetch --deepen=100."
)
ROOT_ONLY = "notice: The page has no History view, because HEAD has only a root commit."
NO_CHANGE = (
    "notice: The page has no History view, because no commit changed a source file of a"
    " component of the top map."
)
# The history element of the atlas page (`atlas_page`). The page escapes "<" in the data.
_STORED = re.compile(r'<script type="application/json" id="atlas-history">(.*?)</script>', re.S)
_NUMSTAT = re.compile(r"(\d+|-)\t(\d+|-)\t(.*)", re.S)


class Unavailable(Exception):
    """Git did not start, or the root has no commit to read."""


@dataclass(frozen=True)
class Commit:
    """One commit of the log: its time, its changed files with their lines, its new files."""

    sha: str
    time: int
    root: bool  # true for a commit with no parent: a root commit or a shallow boundary
    files: tuple[tuple[str, int], ...]
    added: tuple[str, ...]


@dataclass(frozen=True)
class Log:
    """The commits of HEAD, newest first, and the shallow state of the clone."""

    head: str
    shallow: bool
    commits: tuple[Commit, ...]
    # With `history_days`: the time of the first used commit of HEAD. The log can then
    # leave out the commits before the window. None: the log has all commits.
    first: int | None = None


def _git(root: Path, *args: str) -> str:
    proc = git_command.run(root, *args, error=Unavailable)
    if proc.returncode != 0:
        raise Unavailable(git_command.cause(proc.stderr, proc.returncode))
    return proc.stdout.decode("utf-8", "replace")


def _state(root: Path) -> tuple[str, bool, str]:
    """Give the commit of HEAD, the shallow state and the digest of the boundary list."""
    out = _git(root, "rev-parse", "--is-shallow-repository", "--git-path", "shallow", "HEAD")
    lines = out.split("\n")
    if len(lines) < 3:
        raise Unavailable("git rev-parse gave no commit")
    shallow = lines[0].strip() == "true"
    boundary = b""
    if shallow:
        path = Path(lines[1].strip())
        path = path if path.is_absolute() else root / path
        try:
            boundary = path.read_bytes()
        except OSError:
            boundary = b""
    return lines[2].strip(), shallow, hashlib.sha256(boundary).hexdigest()


def parse(text: str) -> list[Commit]:
    """Read the output of `git log -z --raw --numstat --format=@%H %ct %P`."""
    out: list[Commit] = []
    head: list[str] | None = None
    files: list[tuple[str, int]] = []
    added: list[str] = []
    tokens = iter(text.split("\0"))

    def done() -> None:
        if head is not None:
            out.append(Commit(head[0], int(head[1]), len(head) < 3, tuple(files), tuple(added)))

    for raw in tokens:
        token = raw.lstrip("\n")
        if token.startswith("@"):
            done()
            head, files, added = token[1:].split(), [], []
        elif token.startswith(":"):
            path = next(tokens, "")
            if token.split()[-1] == "A":
                added.append(path)
        elif match := _NUMSTAT.fullmatch(token):
            a, d, path = match.groups()
            files.append((path, (int(a) if a != "-" else 0) + (int(d) if d != "-" else 0)))
    done()
    return out


def _cache_load(root: Path, path: Path, key: dict[str, Any]) -> Log | None:
    """Give the log of the cache file when its key is `key`. The shallow state is false."""
    try:
        raw = json.loads(file_write.read_text(root, path) or "")
        if {k: raw.get(k) for k in key} != key:
            return None
        commits = tuple(
            Commit(c[0], int(c[1]), bool(c[2]), tuple((p, int(n)) for p, n in c[3]), tuple(c[4]))
            for c in raw["commits"]
        )
        first = raw["first"]
        return Log(str(raw["head"]), False, commits, None if first is None else int(first))
    except (OSError, ValueError, KeyError, TypeError, IndexError, file_write.RefusedFile):
        return None


def _cache_save(root: Path, path: Path, key: dict[str, Any], log: Log) -> None:
    rows = [[c.sha, c.time, c.root, [list(f) for f in c.files], list(c.added)] for c in log.commits]
    value = {**key, "head": log.head, "first": log.first, "commits": rows}
    try:
        file_write.ignore_caches(root, path)
        file_write.write_atomic(root, path, json.dumps(value))
    except (OSError, file_write.RefusedFile):
        return


def _read(root: Path, revisions: str, since: int | None = None) -> tuple[Commit, ...]:
    """Read the commits of `revisions` with their changes. With `since`, only the commits
    of that time or later."""
    window = () if since is None else (f"--since-as-filter=@{since}",)
    return tuple(
        parse(
            _git(
                root,
                "log",
                "--no-merges",
                "--no-renames",
                "--relative",
                "--raw",
                "--numstat",
                "-z",
                "--format=@%H %ct %P",
                *window,
                revisions,
                "--",
            )
        )
    )


def _span(root: Path, head: str, days: int) -> tuple[int | None, int | None]:
    """Give the time of the first used commit and the start of the window of `days`. This
    read gives only the times, not the changes. With no days, give (None, None)."""
    if days <= 0:
        return None, None
    out = _git(root, "log", "--no-merges", "--min-parents=1", "--format=%ct", head, "--")
    times = [int(t) for t in out.split()]
    if not times:
        return None, None
    return min(times), max(times) - days * DAY


def _window(commits: tuple[Commit, ...], days: int) -> tuple[Commit, ...]:
    """Remove the commits before the window of `days`. The window ends at the last used
    commit."""
    times = [c.time for c in commits if not c.root]
    if days <= 0 or not times:
        return commits
    start = max(times) - days * DAY
    return tuple(c for c in commits if c.time >= start)


def _ancestor(root: Path, old: str, head: str) -> bool:
    proc = git_command.run(root, "merge-base", "--is-ancestor", old, head, error=Unavailable)
    return proc.returncode == 0


def read_log(root: Path, days: int = 0) -> Log:
    """Give the log of HEAD from the cache, or read it with Git and keep it in the cache.

    When the commit of the cache is an earlier commit of HEAD, read only the new commits.
    With `days`, keep only the commits of the window (`_span`)."""
    head, shallow, boundary = _state(root)
    key = {"version": VERSION, "boundary": boundary, "days": days}
    path = root / CACHE
    cached = _cache_load(root, path, key)
    if cached is not None and cached.head == head:
        return Log(head, shallow, cached.commits, cached.first)
    if cached is not None and _ancestor(root, cached.head, head):
        new = _read(root, f"{cached.head}..{head}")
        first = cached.first
        if days > 0:
            first = min(
                [c.time for c in new if not c.root] + ([] if first is None else [first]),
                default=None,
            )
        log = Log(head, shallow, _window(new + cached.commits, days), first)
    else:
        first, since = _span(root, head, days)
        log = Log(head, shallow, _read(root, head, since), first)
    _cache_save(root, path, key, log)
    return log


def owners(model: Model, facts: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    """Give each file of a module of the facts with its component and the short name of its
    module. The first component in model order owns a module."""
    records = facts.get("components", {})
    out: dict[str, tuple[str, str]] = {}
    for c in reversed(model.components):
        for module in claimed(c, records):
            record = records.get(module)
            path = record.get("file") if isinstance(record, Mapping) else None
            if isinstance(path, str) and path:
                out[path] = (c.id, module.rsplit(".", 1)[-1])
    return out


def _dates(times: list[int]) -> list[str]:
    days = [datetime.fromtimestamp(t, UTC) for t in times]
    year = len({d.year for d in days}) > 1
    return [f"{d.day} {d:%b}" + (f" {d.year}" if year else "") for d in days]


def _count(
    cells: dict[str, list[list[Any]]],
    commit: Commit,
    part: int,
    own: Mapping[str, tuple[str, str]],
) -> None:
    """Add the file changes and the new modules of a commit to the cells of the part."""

    def cell(path: str) -> list[Any]:
        return cells.setdefault(own[path][0], [[0, 0, []] for _ in range(PARTS)])[part]

    for path, lines in commit.files:
        if path in own:
            x = cell(path)
            x[0] += 1
            x[1] += lines
    for path in commit.added:
        if path in own:
            cell(path)[2].append(own[path][1])


def build(log: Log, own: Mapping[str, tuple[str, str]], days: int = 0) -> dict[str, Any] | None:
    """Give the history data of the log, with the files of `own`. Give None when no used
    commit changed a file of a component."""
    used = [c for c in log.commits if not c.root]
    if not used:
        return None
    t1 = max(c.time for c in used)
    t0 = min([c.time for c in used] + ([] if log.first is None else [log.first]))
    if days > 0:
        t0 = max(t0, t1 - days * DAY)
        used = [c for c in used if c.time >= t0]
    span = (t1 - t0) / PARTS or 1
    cells: dict[str, list[list[Any]]] = {}
    for c in sorted(used, key=lambda c: (c.time, c.sha)):
        _count(cells, c, min(PARTS - 1, int((c.time - t0) / span)), own)
    if not cells:
        return None
    edges = _dates([round(t0 + span * i) for i in range(PARTS + 1)])
    return {
        "commits": len(used),
        "days": days,
        "from": edges[0],
        "to": edges[-1],
        "shallow": log.shallow,
        "parts": [[edges[i], edges[i + 1]] for i in range(PARTS)],
        "cells": cells,
    }


def of_tree(
    cfg: Config, tree: nest.Tree, facts: Mapping[str, Any]
) -> tuple[dict[str, Any] | None, list[str]]:
    """Give the history data of the top map of the tree and the notice lines.

    Only the atlas page with `[render] history = true` reads the log."""
    if cfg.render_page != "atlas" or not cfg.render_history:
        return None, []
    try:
        log = read_log(cfg.root, cfg.render_history_days)
    except Unavailable as exc:
        return None, [NOTICE.format(cause=exc)]
    data = build(log, owners(tree.top.model, facts), cfg.render_history_days)
    if data is not None:
        return data, []
    if any(not c.root for c in log.commits):
        return None, [NO_CHANGE]
    return None, [SHALLOW if log.shallow else ROOT_ONLY]


def stored(cfg: Config, tree: nest.Tree) -> dict[str, Any] | None:
    """Give the history data of the page file of the top map, for the output check. A
    missing file, a page with no history and a history that is not valid give None."""
    if cfg.render_page != "atlas" or not cfg.render_history:
        return None
    try:
        text = file_write.read_text(cfg.root, tree.top.page_path(cfg))
    except (OSError, UnicodeError, file_write.RefusedFile):
        return None
    match = _STORED.search(text or "")
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
    except ValueError:
        return None
    # A history of a different `history_days` is not the history of the settings.
    if not isinstance(value, dict) or value.get("days", 0) != cfg.render_history_days:
        return None
    return value
