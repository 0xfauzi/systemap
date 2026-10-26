"""The cost and the failures of one scan of the live watcher (findings g1live-1 to g1live-3).

Before this change, each scan read `cfg.test_dirs` again for each source file. Without
a configured test directory, each read walked the repository. At 20202 files, one scan
took 314 s. The scan also parsed each tsconfig file again, and a NUL character in a
tsconfig reference, or a tsconfig file with too many nested levels, stopped the watcher
thread for all time.

Acceptance, written before the change:

- One scan walks the repository for test directories one time (before: one time for each
  source file, plus one).
- The scan finds an edit, a new file, and a removed file, as before.
- A NUL character in `extends` or `references`, and a deeply nested tsconfig file, do not
  stop the scan.
- If a scan fails, the live map gets the error one time, and the watcher continues.
- After a slow scan, the watcher waits two times the time of that scan.
- The scan removes the JSONC comments of a tsconfig file one time while the file stays
  the same, also when the repository has more than 32 tsconfig files.
- A render does not clear a scan error. A scan with a result clears it.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import config, live_watch, serve, typescript_config

SOURCES = 200
DEFAULT_TREE = {
    "systemap.toml": (
        'name = "t"\nlanguage = "python"\nmodel = "map/model.py"\n[package_roots]\n"pkg" = "pkg"\n'
    ),
    "map/model.py": "",
    "pkg/__init__.py": "",
    "tests/test_one.py": "def test_one() -> None:\n    pass\n",
    **{f"pkg/m{n}.py": "" for n in range(SOURCES)},
}
TYPESCRIPT = {
    "systemap.toml": 'language = "typescript"\nname = "t"\n',
    "package.json": '{"name": "t"}\n',
    "src/index.ts": "export const one = 1;\n",
}


class Requests:
    def __init__(self) -> None:
        self.count = 0
        self.errors: list[str] = []

    def request(self) -> None:
        self.count += 1

    def scan_failed(self, text: str) -> None:
        self.errors.append(text)


class Ticks:
    """The stop event of the scan, without a clock. Each wait() does the next action."""

    def __init__(self, *actions: Callable[[], None]) -> None:
        self.actions = list(actions)
        self.waits: list[float] = []

    def wait(self, seconds: float) -> bool:
        self.waits.append(seconds)
        if not self.actions:
            return True
        self.actions.pop(0)()
        return False


def _names(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in live_watch.watched(root) if p.exists()}


def test_one_scan_walks_for_test_directories_one_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_tree(tmp_path, DEFAULT_TREE)
    calls: list[Path] = []
    discover = config.discover_tests

    def counted(root: Path, package_dir: config.PackageDir) -> list[str]:
        calls.append(root)
        return discover(root, package_dir)

    monkeypatch.setattr(config, "discover_tests", counted)
    names = _names(tmp_path)
    # Before the change: 204 walks for this tree (one for each walked .py file, plus one).
    assert len(calls) == 1
    assert "tests/test_one.py" in names and f"pkg/m{SOURCES - 1}.py" in names


def _requests(root: Path, act: Callable[[], None]) -> int:
    requests = Requests()
    live_watch.watch(requests, lambda: live_watch.watched(root), Ticks(act, lambda: None), 0)
    assert requests.errors == []
    return requests.count


def test_the_scan_finds_an_edit_a_new_file_and_a_removed_file(tmp_path: Path) -> None:
    write_tree(tmp_path, DEFAULT_TREE)

    def edit() -> None:
        path = tmp_path / "pkg/m3.py"
        path.write_text("X = 1\n", encoding="utf-8")
        os.utime(path, ns=(10**9, 10**9))

    def add_source() -> None:
        (tmp_path / "pkg/new.py").write_text("", encoding="utf-8")

    def add_test() -> None:
        (tmp_path / "tests/test_two.py").write_text("", encoding="utf-8")

    def remove() -> None:
        (tmp_path / "pkg/m4.py").unlink()

    def add_outside() -> None:
        (tmp_path / "other.py").write_text("", encoding="utf-8")

    assert [_requests(tmp_path, act) for act in (edit, add_source, add_test, remove)] == [1] * 4
    # A file that extraction does not read does not cause a render, as before.
    assert _requests(tmp_path, add_outside) == 0


@pytest.mark.parametrize(
    "tsconfig",
    [
        '{"extends": "./a\\u0000b"}',
        '{"references": [{"path": "x\\u0000y"}]}',
        "[" * 5000 + "]" * 5000,
    ],
    ids=["nul-extends", "nul-references", "deep"],
)
def test_a_bad_tsconfig_does_not_stop_the_scan(tmp_path: Path, tsconfig: str) -> None:
    write_tree(tmp_path, {**TYPESCRIPT, "tsconfig.json": tsconfig})
    # Before the change: ValueError (embedded null byte) or RecursionError.
    assert {"tsconfig.json", "src/index.ts"} <= _names(tmp_path)


def test_a_deeply_nested_tsconfig_gives_a_value_error(tmp_path: Path) -> None:
    # Python 3.13 parses 5000 levels. 200000 levels give RecursionError on 3.11 and 3.13.
    depth = 200_000
    write_tree(tmp_path, {"tsconfig.json": '{"a": ' + "[" * depth + "]" * depth + "}"})
    with pytest.raises(ValueError, match="could not read"):
        typescript_config._read_config(tmp_path / "tsconfig.json", tmp_path)


def test_a_failed_scan_gives_one_error_and_the_watcher_continues(tmp_path: Path) -> None:
    write_tree(tmp_path, DEFAULT_TREE)
    state = {"broken": True}

    def files() -> list[Path]:
        if state["broken"]:
            raise ValueError("embedded null byte")
        return live_watch.watched(tmp_path)

    def repair() -> None:
        state["broken"] = False

    requests = Requests()
    # Two failed scans, then the repair, then two scans without a change.
    live_watch.watch(requests, files, Ticks(lambda: None, repair, lambda: None), 0)
    assert requests.errors == [
        "The watcher could not scan the files. ValueError: embedded null byte",
        "",
    ]
    assert requests.count == 1


def test_after_a_slow_scan_the_watcher_waits_two_times_its_time(tmp_path: Path) -> None:
    write_tree(tmp_path, DEFAULT_TREE)
    now = [0.0]

    def files() -> list[Path]:
        now[0] += 5.0
        return live_watch.watched(tmp_path)

    ticks = Ticks(lambda: None)
    live_watch.watch(Requests(), files, ticks, 1.0, clock=lambda: now[0])
    assert ticks.waits == [10.0, 10.0]
    fast = Ticks(lambda: None)
    live_watch.watch(Requests(), lambda: live_watch.watched(tmp_path), fast, 1.0, clock=lambda: 0)
    assert fast.waits == [1.0, 1.0]


class _CountedStrip:
    """The JSONC strip function. It counts the strips."""

    def __init__(self, strip: Callable[[str], str]) -> None:
        self.strip = strip
        self.calls = 0

    def __call__(self, text: str) -> str:
        self.calls += 1
        return self.strip(text)


def test_a_tsconfig_file_is_stripped_one_time_while_it_stays_the_same(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects = 40
    references = ", ".join(f'{{"path": "./packages/p{n}"}}' for n in range(projects))
    tree = {**TYPESCRIPT, "tsconfig.json": f'{{"files": [], "references": [{references}]}}\n'}
    for n in range(projects):
        tree[f"packages/p{n}/tsconfig.json"] = f'{{"include": ["src"]}} // {n}\n'
        tree[f"packages/p{n}/src/index.ts"] = f"export const v{n} = {n};\n"
    write_tree(tmp_path, tree)
    pattern = _CountedStrip(typescript_config.strip_jsonc)
    monkeypatch.setattr(typescript_config, "strip_jsonc", pattern)
    first = live_watch.watched(tmp_path)
    assert pattern.calls == projects + 1
    pattern.calls = 0
    assert live_watch.watched(tmp_path) == first
    # Before the change, a cache of 32 texts lost each text before the next read. Then
    # each scan stripped each file again (84 strips), and a hostile 20 KB tsconfig file
    # made each scan take about 6 s.
    assert pattern.calls == 0
    (tmp_path / "packages/p3/tsconfig.json").write_text('{"include": ["lib"]}\n')
    live_watch.watched(tmp_path)
    assert pattern.calls == 1


def test_a_render_does_not_clear_a_scan_error(tmp_path: Path) -> None:
    events: list[dict[str, Any]] = []
    page = {"index.html": "<html><body></body></html>"}
    live = serve.LiveMap(tmp_path / "out", lambda: serve.Rendered(files=page), events.append)
    reader = live.listen()
    text = "The watcher could not scan the files. ValueError: x"
    live.scan_failed(text)
    assert events[-1] == {"event": "error", "version": 0, "text": text}
    assert "event: error" in reader.get(timeout=5)
    live.request()
    live.wait(30)
    # Before the change, the render set the state to ready and removed the error.
    assert live.status()["state"] == "error" and live.status()["error"] == text
    later = live.listen()
    assert "event: rendered" in later.get(timeout=5)
    assert text in later.get(timeout=5)
    live.scan_failed("")
    assert live.status()["state"] == "ready" and live.status()["error"] == ""
    assert events[-1]["event"] == "rendered"
