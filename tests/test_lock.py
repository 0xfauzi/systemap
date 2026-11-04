"""Write locks: one writer of the shared files at a time, and one writer of each model file.

Acceptance values:

1. While a different process holds `.systemap/write.lock`, `decisions submit`, `extract`,
   and `refresh` exit 1 with the lock path and the holder, and they change no file.
   `extract --check` does not take the lock.
2. In one process, an inner `file_write.exclusive` continues, also in a different thread.
   After the last `with` statement, also after a failure, the lock file is removed.
3. A lock that a stopped command left stays, and the error tells the person to remove it.
4. `decisions_store.save` keeps a record that a different writer stored after this
   command read the store. The records of two maps stay.
5. If the configuration does not load after the answer write, the command restores the
   previous bytes. If a different writer changed the file after the answer write, the
   command does not restore it, and the answers of that writer stay.
6. Two processes that write different model files both succeed. A write to a model file
   that a different process holds gives `HeldLock` and does not change the file. A dry
   run of `review` takes no lock. `decisions submit` takes the lock of each model file
   that it can write before its first write, so a held model file stops it with no change.

The tests send no request to a model.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_nested import CONFIG, MODELS, TREE

from systemap import config, decisions_store, decisions_submit, file_write, model_write
from systemap.cli import main

HOLD = """
import sys, time
from pathlib import Path
from systemap import file_write
target, release, kind = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
lock = file_write.exclusive(target, "holder") if kind == "root" else file_write.exclusive_file(target, "holder")
with lock:
    while not release.exists():
        time.sleep(0.01)
"""


@contextmanager
def held(target: Path, kind: str, lock: Path) -> Iterator[None]:
    """Hold a lock in a different process while the `with` statement operates."""
    release = target.parent / f"{target.name}.release"
    child = subprocess.Popen([sys.executable, "-c", HOLD, str(target), str(release), kind])
    try:
        deadline = time.monotonic() + 30
        while not lock.exists():
            assert child.poll() is None, "the holder process stopped"
            assert time.monotonic() < deadline, "the holder did not make the lock"
            time.sleep(0.01)
        yield
    finally:
        release.write_text("", encoding="utf-8")
        assert child.wait(timeout=30) == 0
        release.unlink()


@pytest.fixture
def nested(tmp_path: Path) -> Path:
    """The nested tree of test_nested, placed and with current facts."""
    write_tree(tmp_path, {**TREE, "systemap.toml": CONFIG, **MODELS})
    assert main(["--root", str(tmp_path), "place"]) == 0
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return tmp_path


def files(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".release" not in p.name
    }


def test_a_held_lock_stops_each_writer_and_no_file_changes(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 1."""
    lock = nested / file_write.WRITE_LOCK
    results = nested.parent / "results.json"
    results.write_text("[]", encoding="utf-8")
    capsys.readouterr()
    with held(nested, "root", lock):
        before = files(nested)
        for argv in (["decisions", "submit", str(results)], ["extract"], ["refresh"]):
            assert main(["--root", str(nested), *argv]) == 1, argv
            err = capsys.readouterr().err
            assert str(lock) in err and "command holder" in err, err
            assert f"remove {lock}" in err
        assert main(["--root", str(nested), "extract", "--check"]) == 0
        assert files(nested) == before
    assert not lock.exists()


def test_an_inner_lock_continues_and_the_lock_goes_away(tmp_path: Path) -> None:
    """Acceptance 2."""
    lock = tmp_path / file_write.WRITE_LOCK
    with file_write.exclusive(tmp_path, "outer"), file_write.exclusive(tmp_path, "inner"):
        assert "command outer" in lock.read_text(encoding="utf-8")
    assert not lock.exists()
    with pytest.raises(RuntimeError), file_write.exclusive(tmp_path):
        raise RuntimeError("stop")
    assert not lock.exists()


def test_a_lock_that_a_stopped_command_left_stays(tmp_path: Path) -> None:
    """Acceptance 3."""
    lock = tmp_path / file_write.WRITE_LOCK
    lock.parent.mkdir()
    lock.write_text("process 1, command systemap refresh, started 2026-11-04T10:00:00+00:00\n")
    with pytest.raises(file_write.HeldLock) as error, file_write.exclusive(tmp_path):
        pass
    assert "command systemap refresh" in str(error.value)
    assert f"remove {lock}" in str(error.value)
    assert lock.exists()


def record(map_id: str) -> dict[str, Any]:
    return {"map": map_id, "verdict": "contradicted", "attempts": 1}


def test_the_store_keeps_the_records_of_a_different_writer(tmp_path: Path) -> None:
    """Acceptance 4: this command read the store before the other writer saved its record."""
    decisions_store.save(tmp_path, {"first": record("")})
    records = decisions_store.load(tmp_path)
    decisions_store.save(tmp_path, {**decisions_store.load(tmp_path), "style": record("Style")})
    records["gateway"] = record("Gateway")
    decisions_store.save(tmp_path, records, ["gateway"])
    assert set(decisions_store.load(tmp_path)) == {"first", "style", "gateway"}
    stored = json.loads(decisions_store.path(tmp_path).read_text(encoding="utf-8"))
    assert stored["records"]["style"]["map"] == "Style"


def answer() -> dict[str, Any]:
    return {
        "item": "single module: Reader contains only pkg.reader",
        "evidence": "e",
        "reason": "r",
    }


def test_the_restore_keeps_the_answers_of_a_different_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 5."""
    write_tree(tmp_path, {**TREE, "systemap.toml": CONFIG})
    cfg = config.load(tmp_path)
    target = tmp_path / "systemap.toml"
    before = target.read_bytes()
    original = config.load

    def broken(root: Path) -> config.Config:
        raise config.ConfigError("systemap.toml: the test refuses the file")

    monkeypatch.setattr(config, "load", broken)
    with pytest.raises(decisions_submit.DecisionError, match="restored systemap.toml"):
        decisions_submit._write_answers(cfg, [answer()])
    assert target.read_bytes() == before
    other = before + b"\n# The other writer added this line.\n"

    def changed(root: Path) -> config.Config:
        target.write_bytes(other)
        raise config.ConfigError("systemap.toml: the test refuses the file")

    monkeypatch.setattr(config, "load", changed)
    with pytest.raises(decisions_submit.DecisionError, match="did not restore") as error:
        decisions_submit._write_answers(cfg, [answer()])
    assert target.read_bytes() == other
    assert "sha256" in str(error.value)
    monkeypatch.setattr(config, "load", original)


def test_model_files_have_a_lock_each(nested: Path) -> None:
    """Acceptance 6."""
    gateway, style = nested / "map/gateway.py", nested / "map/style.py"
    lock = gateway.with_name("gateway.py.lock")
    with held(gateway, "file", lock):
        old = gateway.read_bytes()
        model_write.write_models({style: style.read_text(encoding="utf-8") + "\n"})
        with pytest.raises(file_write.HeldLock, match="command holder"):
            model_write.write_models({gateway: gateway.read_text(encoding="utf-8") + "\n"})
        assert gateway.read_bytes() == old
    assert style.read_text(encoding="utf-8").endswith("\n\n")
    assert not lock.exists() and not style.with_name("style.py.lock").exists()


def test_a_review_holds_the_model_lock_from_the_read_to_the_write(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 6: a review of a held model file stops, and a different map is written."""
    gateway = nested / "map/gateway.py"
    capsys.readouterr()
    with held(gateway, "file", gateway.with_name("gateway.py.lock")):
        old = gateway.read_bytes()
        assert main(["--root", str(nested), "review", "App", "--map", "Gateway"]) == 1
        assert "holds this lock" in capsys.readouterr().err
        assert gateway.read_bytes() == old
        assert main(["--root", str(nested), "review", "Cache", "--map", "Style"]) == 0
    assert "source_review=" in (nested / "map/style.py").read_text(encoding="utf-8")


def test_two_threads_share_the_lock_and_the_last_one_removes_it(tmp_path: Path) -> None:
    """Acceptance 2: the thread that stops last removes the lock file of the first thread."""
    lock = tmp_path / file_write.WRITE_LOCK
    entered, release = threading.Event(), threading.Event()

    def inner() -> None:
        with file_write.exclusive(tmp_path, "inner"):
            entered.set()
            release.wait(30)

    with file_write.exclusive(tmp_path, "outer"):
        second = threading.Thread(target=inner)
        second.start()
        assert entered.wait(30)
    assert lock.exists()
    release.set()
    second.join(30)
    assert not lock.exists()


def test_a_dry_run_review_takes_no_lock(nested: Path) -> None:
    """Acceptance 6: a dry run writes no file, so a held model file does not stop it."""
    gateway = nested / "map/gateway.py"
    argv = ["--root", str(nested), "review", "App", "--map", "Gateway", "--dry-run"]
    with held(gateway, "file", gateway.with_name("gateway.py.lock")):
        assert main(argv) == 0


def source_verdicts(root: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    """Write one supported verdict for a source review of Gateway and one of Style."""
    capsys.readouterr()
    assert main(["--root", str(root), "decisions", "pending", "--json"]) == 0
    requests = json.loads(capsys.readouterr().out)["requests"]
    items = []
    for map_id in ("Gateway", "Style"):
        request = next(r for r in requests if r["type"] == "source_review" and r["map"] == map_id)
        name = request["files"][0]["file"]
        digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
        cited = {"file": name, "start_line": 1, "end_line": 1, "sha256": digest}
        items.append(
            {
                "request_id": request["id"],
                "verdict": "supported",
                "citations": [cited],
                "summary": "The source agrees with the claim.",
            }
        )
    path = root.parent / "verdicts.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


def test_a_held_model_file_stops_submit_before_the_first_write(
    nested: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 6: submit takes the model locks of all its reviews before it writes."""
    verdicts = source_verdicts(nested, capsys)
    style = nested / "map/style.py"
    with held(style, "file", style.with_name("style.py.lock")):
        before = files(nested)
        assert main(["--root", str(nested), "decisions", "submit", str(verdicts)]) == 1
        assert "holds this lock" in capsys.readouterr().err
        assert files(nested) == before
