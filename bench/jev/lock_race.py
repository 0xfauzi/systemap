"""M6: two writer processes at the same time, with the write locks of systemap.

Acceptance (written before the run, from M6 of docs/design/nested-parts.md):

- Part A. 100 runs of two `decisions submit` processes that start at the same time. Each
  process has a different verdict file: one `supported` verdict for a judgement line of the
  nested map Gateway, and one for a line of the nested map Style. The result is 0 lost
  answer rows and 0 lost store records. Each process that exits 0 has its answer row in
  systemap.toml and its record in the store. Each process that does not exit 0 gives the
  lock error ("holds this lock") on stderr.
- Part B. 100 runs of two processes that write different nested model files at the same
  time. 100 percent of the runs exit 0 in the two processes, and each file has its new
  review digest. `place --map` is not available before step 2 of the design. Thus each
  process is `review --map MAP CARD`, which writes only the model file of that map.
- Part C, for information only, with no acceptance value. 100 runs of two `review`
  processes on two cards of the same model file. The script counts the runs with a lock
  error, and the runs in which a digest is lost.

Each run uses a new copy of the fixture. The fixture is the nested tree of
tests/test_nested.py, after `place` and `extract`. The script sends no data out.

Run from the repository root: uv run python bench/jev/lock_race.py [RUNS]
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from test_nested import CONFIG, MODELS, TREE  # noqa: E402

from systemap import config, decisions_store  # noqa: E402

LOCK_ERROR = "holds this lock"


def systemap(root: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "systemap", "--root", str(root), *argv]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def start(root: Path, *argv: str) -> subprocess.Popen[str]:
    command = [sys.executable, "-m", "systemap", "--root", str(root), *argv]
    return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def fixture(folder: Path) -> Path:
    root = folder / "fixture"
    for rel, text in {**TREE, "systemap.toml": CONFIG, **MODELS}.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    for argv in (["place"], ["extract"]):
        done = systemap(root, *argv)
        if done.returncode != 0:
            raise SystemExit(f"fixture: {argv} gave {done.returncode}: {done.stderr}")
    return root


def verdict(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    name = request["files"][0]["file"]
    digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
    cited = {"file": name, "start_line": 1, "end_line": 1, "sha256": digest}
    return {
        "request_id": request["id"],
        "verdict": "supported",
        "citations": [cited],
        "summary": "The source agrees with the claim.",
    }


def verdict_files(root: Path, folder: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Write one verdict file for a judgement line of Gateway and one of Style."""
    done = systemap(root, "decisions", "pending", "--json")
    requests = json.loads(done.stdout)["requests"]
    out = []
    for map_id in ("Gateway", "Style"):
        request = next(
            r for r in requests if r["type"] == "judgement" and r["map"] == map_id and r["files"]
        )
        path = folder / f"{map_id.lower()}.json"
        path.write_text(json.dumps([verdict(root, request)]), encoding="utf-8")
        out.append((path, request))
    return out


def lost_rows(root: Path, request: dict[str, Any]) -> tuple[int, int]:
    """Give the lost answer rows and the lost store records for one recorded verdict."""
    answered = config.load(root).judgement_answered
    row = any(request["target"] in answer.items for answer in answered)
    stored = any(r.get("id") == request["id"] for r in decisions_store.load(root).values())
    return int(not row), int(not stored)


def part_a(base: Path, folder: Path, runs: int) -> None:
    files = verdict_files(base, folder)
    lost_answers = lost_records = refused = wrong_refusals = 0
    for k in range(runs):
        root = folder / f"a{k}"
        shutil.copytree(base, root)
        started = [start(root, "decisions", "submit", str(path)) for path, _request in files]
        for child, (_path, request) in zip(started, files, strict=True):
            _out, err = child.communicate()
            if child.returncode == 0:
                answers, records = lost_rows(root, request)
                lost_answers, lost_records = lost_answers + answers, lost_records + records
            else:
                refused += 1
                wrong_refusals += int(LOCK_ERROR not in err)
        shutil.rmtree(root)
    print(
        f"part A: {runs} runs, {refused} refused processes, {wrong_refusals} refusals "
        f"without the lock error, {lost_answers} lost answer rows, {lost_records} lost "
        "store records"
    )


def digest_in(path: Path, card: str) -> bool:
    text = path.read_text(encoding="utf-8")
    start_at = text.index(f'id="{card}"')
    end_at = text.find("Component(", start_at)
    return "source_review=" in text[start_at : end_at if end_at > 0 else len(text)]


def reviews(base: Path, folder: Path, runs: int, pairs: list[tuple[str, str]]) -> list[int]:
    """Give the runs that exit 0 two times, the runs with a lock error, the lost digests."""
    both = locked = lost = 0
    for k in range(runs):
        root = folder / f"r{k}"
        shutil.copytree(base, root)
        started = [start(root, "review", card, "--map", map_id) for map_id, card in pairs]
        codes = []
        for child in started:
            _out, err = child.communicate()
            codes.append(child.returncode)
            locked += int(child.returncode != 0 and LOCK_ERROR in err)
        both += int(codes == [0, 0])
        for (map_id, card), code in zip(pairs, codes, strict=True):
            path = root / "map" / f"{map_id.lower()}.py"
            lost += int(code == 0 and not digest_in(path, card))
        shutil.rmtree(root)
    return [both, locked, lost]


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    with tempfile.TemporaryDirectory(prefix="lock-race-") as name:
        folder = Path(name)
        base = fixture(folder)
        part_a(base, folder, runs)
        both, locked, lost = reviews(base, folder, runs, [("Gateway", "App"), ("Style", "Cache")])
        print(
            f"part B: {runs} runs, {both} runs with exit 0 in the two processes, "
            f"{locked} lock errors, {lost} lost digests"
        )
        both, locked, lost = reviews(
            base, folder, runs, [("Gateway", "App"), ("Gateway", "Routes")]
        )
        print(
            f"part C: {runs} runs, {both} runs with exit 0 in the two processes, "
            f"{locked} lock errors, {lost} lost digests"
        )


if __name__ == "__main__":
    main()
