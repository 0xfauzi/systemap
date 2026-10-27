"""Each read of a cache file that `file_write.write_atomic` replaces holds the cache lock.

On Windows, a process cannot open a file while a different process replaces it with
`os.replace`. Also, `os.replace` gives an error while a different process has the file
open. Thus each reader and each writer of the same cache file must hold the same lock.

Each test holds the lock in one thread, and starts the reader in a second thread.
The two threads open the lock file independently. Thus the operating system lock applies
between them, as between two processes.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from conftest import TINY_PACKAGE, write_tree

from systemap import config, file_write, history, jev
from systemap import language as languages

# The time that the reader must wait while the lock is held. A reader without the lock
# finishes in less time, because it reads one small file.
HELD_SECONDS = 0.5


def waits_for_the_lock(lock_of: Path, read: Callable[[], Any]) -> tuple[bool, Any]:
    """Hold the lock of `lock_of`, then start `read`.

    Give `True` if `read` did not finish while the lock was held, and the result of `read`
    after the release."""
    held, release, done = threading.Event(), threading.Event(), threading.Event()
    result: list[Any] = []

    def hold() -> None:
        with file_write.locked(lock_of.parent, lock_of):
            held.set()
            release.wait(30)

    def reader() -> None:
        result.append(read())
        done.set()

    holder = threading.Thread(target=hold)
    holder.start()
    assert held.wait(30)
    worker = threading.Thread(target=reader)
    worker.start()
    waited = not done.wait(HELD_SECONDS)
    release.set()
    holder.join(30)
    worker.join(30)
    assert done.is_set(), "the reader did not finish after the release"
    return waited, result[0]


def test_a_jev_cache_reader_waits_for_the_lock(tmp_path: Path) -> None:
    """win-2: the acceptance value is a wait while the lock is held, then the full file.

    Before the repair, `jev.Cache` read the file without the lock."""
    path = tmp_path / "jev.json"
    path.write_text(
        json.dumps({"version": 1, "entries": {"k": {"n": 1}}, "releases": {}}),
        encoding="utf-8",
        newline="\n",
    )
    waited, cache = waits_for_the_lock(path, lambda: jev.Cache(path, root=path.parent))
    assert waited
    assert cache.entries == {"k": {"n": 1}}


def test_a_jev_cache_without_a_file_makes_no_lock_file(tmp_path: Path) -> None:
    """win-2: the acceptance value is an empty cache and no new file or folder."""
    cache = jev.Cache(tmp_path / "missing" / "jev.json", root=tmp_path)
    assert cache.entries == {}
    assert list(tmp_path.iterdir()) == []


def test_a_facts_cache_reader_waits_for_the_lock(tmp_path: Path) -> None:
    """win-2: the acceptance value is a wait while the lock is held, then the cached facts.

    Before the repair, `history.facts_at` read the cache file without a lock."""
    write_tree(tmp_path, TINY_PACKAGE)
    (tmp_path / "systemap.toml").write_text(
        'language = "python"\n[package_roots]\n"pkg" = "pkg"\n', encoding="utf-8", newline="\n"
    )
    cfg = config.load(tmp_path)
    sha = "a" * 40
    scope = history.cache_scope(cfg, languages.repository(cfg.language).parser_version())
    path = history.cache_dir(cfg) / f"{sha}-{scope}.json"
    path.parent.mkdir(parents=True)
    # The record has the keys that the shape check of the stored facts requires.
    record = {"file": "pkg/a.py", "functions": [], "classes": [], "errors": [], "sha": "0" * 12}
    cached = {"components": {"pkg.a": {**record, "tests_total": 0, "tests_primary": 0}}}
    path.write_text(json.dumps(cached), encoding="utf-8", newline="\n")
    waited, facts = waits_for_the_lock(history.lock_of(cfg), lambda: history.facts_at(cfg, sha))
    assert waited
    assert facts == cached
