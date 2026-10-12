"""`systemap delta` sends a Jev request only when the user selects Jev.

The selection does not read the language of the project. The tests use a Python
fixture and a TypeScript fixture.

The user selects Jev with `--jev`, or with `[jev] enabled = true` in systemap.toml.
A key in the environment alone does not select Jev.

Each test counts the requests at a local HTTP server. The command uses its real
HTTPS transport with TYPESAFE_BASE_URL at that server. No request goes to Jev.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from jev_replay import serve
from test_delta_jev import Fake, git, renamed

from systemap import jev
from systemap.cli import main

__all__ = ["renamed"]


class Counter:
    """Keep each request that the local server receives, and answer it with a fake."""

    def __init__(self) -> None:
        self.fake = Fake()
        self.requests: list[tuple[str, str, dict[str, Any] | None]] = []

    def send(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        self.requests.append((method, path, body))
        return self.fake(method, path, body)


@pytest.fixture
def counter(monkeypatch: pytest.MonkeyPatch) -> Iterator[Counter]:
    """A key in the environment, and the transport URL at a counting server."""
    counted = Counter()
    with serve(counted) as url:
        monkeypatch.setenv(jev.KEY_ENV, "a test key")
        monkeypatch.setenv(jev.BASE_ENV, url)
        yield counted


def add_jev(root: Path, table: str) -> None:
    toml = root / "systemap.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + f"\n[jev]\n{table}\n", encoding="utf-8")


def delta(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(["--root", str(root), "delta", "--base", "HEAD~1", "--brief", *argv])
    out, err = capsys.readouterr()
    return code, out, err


# The requests that `delta` sent on the `renamed` project before this change, with a key
# and the old default. A run that selects Jev must send the same requests.
SELECTED = [("GET", "/models"), ("POST", "/systemone"), ("POST", "/systemone")]


def test_a_key_without_a_jev_table_sends_zero_requests(
    renamed: Path, counter: Counter, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: with a key and no [jev] table, delta sends 0 requests."""
    code, out, err = delta(renamed, capsys)
    assert counter.requests == []
    assert code == 1
    assert "Jev suggestions" not in out
    # One hint tells how to select Jev.
    assert err.count("hint:") == 1
    assert "--jev" in err and "[jev] enabled = true" in err


def test_jev_enabled_true_sends_the_same_requests_as_before(
    renamed: Path, counter: Counter, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: with [jev] enabled = true, delta sends the requests in SELECTED."""
    add_jev(renamed, "enabled = true")
    code, out, err = delta(renamed, capsys)
    assert [(m, p) for m, p, _ in counter.requests] == SELECTED
    assert code == 1
    assert "jev move: pkg.ledger -> pkg.records_store" in out
    assert "hint:" not in err


def test_the_jev_option_sends_requests_with_no_configuration(
    renamed: Path, counter: Counter, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: with --jev and no [jev] table, delta sends the requests in SELECTED."""
    code, out, err = delta(renamed, capsys, "--jev")
    assert [(m, p) for m, p, _ in counter.requests] == SELECTED
    assert "jev move: pkg.ledger -> pkg.records_store" in out
    assert "hint:" not in err


def test_the_option_and_the_configuration_send_the_same_bodies(
    renamed: Path, counter: Counter, capsys: pytest.CaptureFixture[str]
) -> None:
    delta(renamed, capsys, "--jev")
    by_option = list(counter.requests)
    counter.requests.clear()
    (renamed / ".systemap/jev-cache.json").unlink()
    add_jev(renamed, "enabled = true")
    delta(renamed, capsys)
    assert counter.requests == by_option


def test_no_jev_sends_zero_requests_with_jev_enabled_true(
    renamed: Path, counter: Counter, capsys: pytest.CaptureFixture[str]
) -> None:
    add_jev(renamed, "enabled = true")
    _code, out, err = delta(renamed, capsys, "--no-jev")
    assert counter.requests == []
    assert "Jev suggestions" not in out
    assert "hint:" not in err


def test_jev_enabled_false_stops_the_hint(
    renamed: Path,
    counter: Counter,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    add_jev(renamed, "enabled = false")
    assert "hint:" not in delta(renamed, capsys)[2]
    monkeypatch.delenv(jev.KEY_ENV)
    assert "hint:" not in delta(renamed, capsys)[2]
    assert counter.requests == []


def test_without_a_key_the_hint_stays(
    renamed: Path,
    counter: Counter,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv(jev.KEY_ENV)
    _code, _out, err = delta(renamed, capsys)
    assert err.count("hint:") == 1
    assert "TYPESAFE_API_KEY" in err
    assert counter.requests == []


@pytest.fixture
def renamed_ts(tmp_path: Path) -> Path:
    """The TypeScript fixture. In the head commit, src/remote.ts with other bodies
    replaces src/client.ts. Delta cannot pair the two modules."""
    fixture = Path(__file__).parent / "fixtures" / "typescript-app"
    shutil.copytree(fixture, tmp_path, dirs_exist_ok=True)
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    (tmp_path / "src/client.ts").unlink()
    remote = (
        "export interface User { id: string }\n\nexport function fetchUser(id: string): User {\n"
    )
    (tmp_path / "src/remote.ts").write_text(remote + "  return { id: id.trim() };\n}\n")
    service = tmp_path / "src/service.ts"
    service.write_text(service.read_text().replace("@/client", "@/remote"))
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "head")
    return tmp_path


def test_a_key_sends_zero_requests_for_typescript(
    renamed_ts: Path, counter: Counter, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: with a key and no [jev] table, delta on TypeScript sends 0 requests."""
    _code, _out, err = delta(renamed_ts, capsys)
    assert counter.requests == []
    assert err.count("hint:") == 1


def test_the_jev_option_sends_requests_for_typescript(
    renamed_ts: Path, counter: Counter, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: with --jev and no [jev] table, delta on TypeScript sends requests."""
    delta(renamed_ts, capsys, "--jev")
    assert counter.requests[0][:2] == ("GET", "/models")
    assert any(path == "/systemone" for _m, path, _b in counter.requests)
