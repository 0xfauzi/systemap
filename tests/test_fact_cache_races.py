"""The fact cache does not keep the facts of a text under the digest of a different text.

Acceptance (SEC-2): a file changes from text A to text B between the digest read and the
parse, and then goes back to A. Before the repair, the next extraction gave the facts of
B for text A. Now it gives the facts of A.

Acceptance (SEC-7): a write that keeps the size and the modification time changes the
change time. Before the repair, the racy test used only the modification time, and the
cache gave the old digest. Now the cache reads the text again.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest

from systemap import extract, extraction, fact_cache

A = "import os\ndef alpha():\n    pass\n"
B = "def beta():\n    pass\n"


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path.resolve()
    (repo / "p").mkdir()
    (repo / "p/__init__.py").write_text("", encoding="utf-8")
    path = repo / "p/m.py"
    path.write_text(A, encoding="utf-8")
    old = time.time() - 100
    os.utime(path, (old, old))
    return repo, path


def _names(found: Any) -> list[str]:
    return [item["name"] for item in found[0]["functions"]]


def test_a_change_during_the_parse_does_not_keep_the_facts_of_the_new_text(
    tmp_path: Path,
) -> None:
    repo, path = _repo(tmp_path)
    cache = fact_cache.FactCache()
    cache.renew("g")

    def collect() -> Any:
        return (extract.collect_module(path, repo, "p.m", frozenset({"p"})), "", set())

    def changed_first() -> Any:
        path.write_text(B, encoding="utf-8")
        return collect()

    assert _names(extraction._kept_module(cache, repo, "p.m", path, changed_first)) == ["beta"]
    path.write_text(A, encoding="utf-8")
    old = time.time() - 100
    os.utime(path, (old, old))
    assert _names(extraction._kept_module(cache, repo, "p.m", path, collect)) == ["alpha"]


def test_a_file_value_is_kept_if_the_text_does_not_change(tmp_path: Path) -> None:
    repo, path = _repo(tmp_path)
    cache = fact_cache.FactCache()
    cache.renew("g")
    made: list[int] = []

    def make() -> str:
        made.append(1)
        return path.read_text(encoding="utf-8")

    assert cache.remember_file("tests", "m", repo, path, make) == A
    assert cache.remember_file("tests", "m", repo, path, make) == A
    assert made == [1]


@pytest.mark.skipif(not fact_cache.STATUS_SHOWS_WRITES, reason="the cache reads each text")
def test_a_recent_change_time_makes_the_cache_read_the_text_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, path = _repo(tmp_path)
    found = os.stat(path)
    # A file system with a coarse change time: two writes in one tick give one status.
    status = (found.st_dev, found.st_ino, found.st_size, found.st_mtime_ns, time.time_ns())
    monkeypatch.setattr(fact_cache, "_status", lambda _path: status)
    cache = fact_cache.FactCache()
    assert cache.digest(repo, path) == fact_cache.text_digest(A)
    other = A.replace("alpha", "gamma")
    path.write_text(other, encoding="utf-8")
    assert cache.digest(repo, path) == fact_cache.text_digest(other)
