"""P1 and P2 of step 5 of the nested canvas design: the cost of the open ports.

Step 5 gives the canvas page the open lines of the judgement (`canvas_page.pages` calls
`judgement_json.open_boundary`), and the page marks the actor card of each open port
(`page_canvas_ports`). This script compares the code of the base commit (A) with the code
of the change (B). Other agents can run Chromium on the same host. Thus the runs of A and
B are interleaved (A B, then B A), and each run waits for a quiet host.

Acceptance values, written before the first run on 2026-11-08:

- P1 (acceptance 8 of part C): the M11 tree (50 maps, the fixture of
  `canvas_data_size.py`) with `[render] canvas = true`, after `place` and `extract`. In 5
  interleaved pairs on a quiet host, the median time of `systemap render` with B is at
  most the median with A plus 1.0 s, and the same for `systemap check`. A and B give the
  same exit code. Pass or fail for each command. These values are also given, with no
  acceptance value: the count of open boundary lines of the tree, and the time of
  `judgement_json.open_boundary` alone (3 runs). The judgement of the M11 tree took 6.0 s
  (bench/jev/README.md), thus a call of `evaluate` in place of `open_boundary` fails P1.
- P2 (acceptance 7 of part C): C2 with open ports. The M11 shape of `canvas_frames.py`
  (`nested_tree`) with `judged` true and one open `boundary flow` line on the port of the
  actor of each nested map. Thus each of the 49 actor cards has a mark. The page of B is
  `canvas_page.build` of B, and the page of A is the same data with the code of A (A has
  no marks). At 4 times CPU throttling, the p95 frame interval of each of pan-fit,
  all-open and dive with B is at most 35.0 ms in each of 3 interleaved pairs. The values
  of A are given for the comparison, with no acceptance value.
- The quiet host: before each run, the 1-minute load average is 1.5 or less (the host has
  4 cores). The script waits up to 300 s for it. A run that starts on a host that is not
  quiet has the label "not quiet", and a result with fewer than 3 quiet pairs has no
  verdict.

Run from the repository root, with the source of the base commit in a folder:
    git archive 0254afb src | tar -x -C BASE
    uv run python bench/jev/canvas_ports_ab.py BASE/src
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
NEW_SRC = HERE.parent.parent / "src"
PAIRS = 5
FRAME_PAIRS = 3
SLACK = 1.0
QUIET = 1.5
WAIT = 300
SCENARIOS = ("pan-fit", "all-open", "dive")


def quiet() -> bool:
    """Wait until the 1-minute load average is QUIET or less. Give False after WAIT s."""
    end = time.monotonic() + WAIT
    while os.getloadavg()[0] > QUIET:
        if time.monotonic() > end:
            return False
        time.sleep(5)
    return True


def child(src: Path, code: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(src)}
    return subprocess.run(
        [sys.executable, "-c", code, *args], env=env, capture_output=True, text=True, check=False
    )


CLI = "import sys; from systemap.cli import main; sys.exit(main(sys.argv[1:]))"
WHERE = "import systemap; print(systemap.__file__)"
PAGE = """
import json, sys
from pathlib import Path
from systemap import canvas_page, config, nest
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
theme = nest.load(config.load(Path(sys.argv[3]))).top.theme
Path(sys.argv[2]).write_text(canvas_page.build(theme, data), encoding="utf-8")
"""


def timed(src: Path, root: Path, command: str) -> tuple[int, float]:
    began = time.perf_counter()
    proc = child(src, CLI, "--root", str(root), command)
    return proc.returncode, time.perf_counter() - began


def _m11(root: Path) -> None:
    import canvas_data_size as c1  # noqa: PLC0415  (a neighbour script in bench/jev)

    c1._write(root)
    toml = root / "systemap.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + "[render]\ncanvas = true\n", "utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        codes = c1._commands(root)
    if any(code != 0 for code, _t in codes.values()):
        raise SystemExit(f"failure: place or extract did not exit 0: {codes}")


def _open_lines(root: Path) -> tuple[int, list[float]]:
    from systemap import config, facts_file, judgement_json, nest  # noqa: PLC0415

    cfg = config.load(root)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    tree = nest.load(cfg)
    times, found = [], frozenset[str]()
    for _run in range(3):
        began = time.perf_counter()
        found = judgement_json.open_boundary(tree, facts, cfg)
        times.append(time.perf_counter() - began)
    return len(found), times


def p1(base: Path) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _m11(root)
        count, times = _open_lines(root)
        print(f"open boundary lines: {count}; open_boundary s: {[round(t, 2) for t in times]}")
        found: dict[tuple[str, str], list[tuple[int, float, bool]]] = {}
        for k in range(PAIRS):
            sides = (("A", base), ("B", NEW_SRC)) if k % 2 == 0 else (("B", NEW_SRC), ("A", base))
            for name, src in sides:
                for command in ("render", "check"):
                    calm = quiet()
                    code, seconds = timed(src, root, command)
                    found.setdefault((name, command), []).append((code, seconds, calm))
                    print(
                        f"pair {k + 1} {name} {command}: exit {code}, {seconds:.2f} s, "
                        f"{'quiet' if calm else 'not quiet'}"
                    )
        return _p1_rows(found)


def _verdict(calm: int, passed: bool) -> str:
    """Give the verdict of a row: no verdict with fewer than 3 quiet pairs."""
    if calm < 3:
        return "no verdict"
    return "pass" if passed else "fail"


def _p1_row(
    command: str, a: list[tuple[int, float, bool]], b: list[tuple[int, float, bool]]
) -> str:
    calm = sum(1 for x, y in zip(a, b, strict=True) if x[2] and y[2])
    ma = statistics.median([t for _c, t, _q in a])
    mb = statistics.median([t for _c, t, _q in b])
    same = {c for c, _t, _q in a} == {c for c, _t, _q in b}
    verdict = _verdict(calm, same and mb <= ma + SLACK)
    print(f"| {command} | {ma:.2f} | {mb:.2f} | {mb - ma:+.2f} | {calm} | {verdict} |")
    return verdict


def _p1_rows(found: dict[tuple[str, str], list[tuple[int, float, bool]]]) -> bool:
    print("| Command | A median (s) | B median (s) | B - A (s) | Quiet pairs | Result |")
    print("|---|---|---|---|---|---|")
    verdicts = [_p1_row(c, found[("A", c)], found[("B", c)]) for c in ("render", "check")]
    return "fail" not in verdicts


def shape_data() -> dict[str, Any]:
    """The M11 shape with one open line on the port of the actor of each nested map."""
    from canvas_frames import nested_tree  # noqa: PLC0415

    data = nested_tree()
    data["judged"] = True
    for m in data["maps"][1:]:
        port = m["ports"][0]
        port["n"] = [
            f"{m['id']}: boundary flow: {port['i']} sends to actor {port['x']}, "
            f"and the parent map has no flow from {port['x']} to {m['id'].split('/')[-1]}"
        ]
    return data


def p2(base: Path) -> bool:
    import canvas_frames as c2  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / "data.json").write_text(json.dumps(shape_data()), encoding="utf-8")
        pages = {}
        for name, src in (("A", base), ("B", NEW_SRC)):
            page = out / f"{name}.html"
            proc = child(src, PAGE, str(out / "data.json"), str(page), str(HERE.parent.parent))
            if proc.returncode != 0:
                raise SystemExit(proc.stderr)
            pages[name] = page
        rows: dict[tuple[str, str], list[tuple[float, bool]]] = {}
        for k in range(FRAME_PAIRS):
            order = ("A", "B") if k % 2 == 0 else ("B", "A")
            for mode in SCENARIOS:
                for name in order:
                    calm = quiet()
                    p95 = float(c2.run(pages[name], mode, 4)["p95"])
                    rows.setdefault((name, mode), []).append((p95, calm))
                    print(
                        f"pair {k + 1} {name} {mode}: p95 {p95:.1f} ms, "
                        f"{'quiet' if calm else 'not quiet'}"
                    )
        return _p2_rows(rows)


def _p2_row(mode: str, a: list[tuple[float, bool]], b: list[tuple[float, bool]]) -> str:
    calm = sum(1 for x, y in zip(a, b, strict=True) if x[1] and y[1])
    verdict = _verdict(calm, all(p <= 35.0 for p, _q in b))
    shown_a = ", ".join(f"{p:.1f}" for p, _q in a)
    shown_b = ", ".join(f"{p:.1f}" for p, _q in b)
    print(f"| {mode} | {shown_a} | {shown_b} | {calm} | {verdict} |")
    return verdict


def _p2_rows(rows: dict[tuple[str, str], list[tuple[float, bool]]]) -> bool:
    print("| Scenario 4x | A p95 (ms) | B p95 (ms) | Quiet pairs | Result |")
    print("|---|---|---|---|---|")
    verdicts = [_p2_row(m, rows[("A", m)], rows[("B", m)]) for m in SCENARIOS]
    return "fail" not in verdicts


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: canvas_ports_ab.py BASE_SRC")
        return 2
    base = Path(argv[0]).resolve()
    for src in (base, NEW_SRC):
        print("source:", child(src, WHERE).stdout.strip())
    ok = p1(base)
    ok &= p2(base)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    sys.exit(main(sys.argv[1:]))
