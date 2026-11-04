"""Measure issue 136: do the stored syntax values change with the Python interpreter?

The stored values are the source-review digest (`syntax_sha`), the `api` fingerprints,
the `constants` previews and the function signatures (`functions` and the `methods` of
`classes` and `errors`). The script reads them from two inputs:

- an extraction of this repository (the `components` section of the facts);
- `collect_module` for each file of the 3.12.13 standard library, without `test/`,
  `lib2to3/` and `site-packages/`.

Acceptance values, written on 2026-11-04 before the first run:

(a) With the change, each interpreter gives the same stored values as each other
    interpreter: CPython 3.11.18, 3.12.3, 3.12.13, 3.13.18 and 3.14.6. The repository
    comparison uses the full `components` section. The standard library comparison uses
    the files that each interpreter parses. 0 values differ.
(b) The extraction time of this repository with the change is at most 1.10 times the
    time of main. The value is the median of 5 alternating runs on 3.11.18. Each run is
    a new process.
(c) No acceptance value. The script gives, for each interpreter, the number of stored
    values that change one time for a user: main on that interpreter against the change
    on that interpreter.

Main is measured first. For main, the script also gives the number of values that are
different from 3.11.18 on each interpreter.

Run from the repository root:

    uv run python bench/jev/stored_syntax.py drive MAIN CHANGE TARGET LISTING OUT

MAIN and CHANGE are checkouts of the two revisions. TARGET is the repository to extract
(a checkout of main). LISTING is a text file with one standard library path on each line.
OUT is a directory for the JSON output of each run. The `drive` step starts each run with
`uv run --isolated --python VERSION --project CHECKOUT`. To measure main only, give the
same checkout as MAIN and CHANGE. To print the report again from OUT:

    uv run python bench/jev/stored_syntax.py report OUT
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

VERSIONS = ("3.11.18", "3.12.3", "3.12.13", "3.13.18", "3.14.6")
TIME_VERSION = "3.11.18"
TIME_RUNS = 5
LIMIT = 1.10
STDLIB = Path("/root/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12")
KINDS = ("syntax digests", "fingerprints", "previews", "signatures")


def stored(record: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Give the four kinds of stored values of one module record, each by a key."""
    signatures = {f"f{n}:{f['name']}": f["signature"] for n, f in enumerate(record["functions"])}
    for group in ("classes", "errors"):
        for item in record[group]:
            for n, method in enumerate(item["methods"]):
                signatures[f"{group}:{item['name']}:{n}"] = method
    return {
        "syntax digests": {"": record["syntax_sha"]},
        "fingerprints": {
            f"{a['bucket']}:{a['name']}:{n}": a["fingerprint"] for n, a in enumerate(record["api"])
        },
        "previews": {c["name"]: c["value"] for c in record["constants"]},
        "signatures": signatures,
    }


def values(target: Path, listing: Path) -> None:
    """Print the stored values of the repository and of the standard library files."""
    from systemap import config, extract, extraction, python_tree

    components = extraction.build(config.load(target))["components"]
    python_tree.clear()
    stdlib: dict[str, Any] = {}
    for line in listing.read_text(encoding="utf-8").splitlines():
        path = Path(line)
        record = extract.collect_module(path, STDLIB)
        python_tree.clear()
        if record is not None and "parse_error" not in record:
            stdlib[path.relative_to(STDLIB).as_posix()] = stored(record)
    out = {"version": sys.version.split()[0], "components": components, "stdlib": stdlib}
    print(json.dumps(out, sort_keys=True))


def timed(target: Path) -> None:
    """Print the time in seconds of one extraction of the target."""
    from systemap import config, extraction

    cfg = config.load(target)
    start = time.perf_counter()
    extraction.build(cfg)
    print(f"{time.perf_counter() - start:.4f}")


def run(checkout: Path, version: str, *args: str) -> str:
    command = [
        "uv",
        "run",
        "--quiet",
        "--isolated",
        "--python",
        version,
        "--project",
        str(checkout),
    ]
    command += ["python", str(Path(__file__).resolve()), *args]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        print(done.stderr, file=sys.stderr)
        raise SystemExit(f"the run failed: {' '.join(command)}")
    return done.stdout


def changed(one: dict[str, Any], two: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Count the values of each kind that are different or only in one of the two runs."""
    out: dict[str, dict[str, int]] = {}
    repo_one = {m: stored(r) for m, r in one["components"].items()}
    repo_two = {m: stored(r) for m, r in two["components"].items()}
    for where, left, right in (
        ("repository", repo_one, repo_two),
        ("stdlib", one["stdlib"], two["stdlib"]),
    ):
        counts = out[where] = dict.fromkeys(KINDS, 0)
        for name in sorted(set(left) & set(right)):
            for kind in KINDS:
                a, b = left[name][kind], right[name][kind]
                counts[kind] += sum(a.get(k) != b.get(k) for k in set(a) | set(b))
    return out


def totals(one: dict[str, Any]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    repo = {m: stored(r) for m, r in one["components"].items()}
    for where, records in (("repository", repo), ("stdlib", one["stdlib"])):
        counts = out[where] = dict.fromkeys(KINDS, 0)
        for record in records.values():
            for kind in KINDS:
                counts[kind] += len(record[kind])
    return out


def common(runs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Keep only the standard library files that each run parsed."""
    keep = set.intersection(*(set(r["stdlib"]) for r in runs.values()))
    return {v: {**r, "stdlib": {k: r["stdlib"][k] for k in keep}} for v, r in runs.items()}


def zero(counts: dict[str, dict[str, int]]) -> bool:
    return all(n == 0 for where in counts.values() for n in where.values())


def drive(main: Path, change: Path, target: Path, listing: Path, out: Path) -> None:
    """Make each run, write its output to `out`, and print the report."""
    out.mkdir(parents=True, exist_ok=True)
    for label, checkout in (("main", main), ("change", change)):
        for version in VERSIONS:
            text = run(checkout, version, "values", str(target), str(listing))
            (out / f"{label}-{version}.json").write_text(text, encoding="utf-8")
    times: dict[str, list[float]] = {"main": [], "change": []}
    for _round in range(TIME_RUNS):
        for label, checkout in (("main", main), ("change", change)):
            times[label].append(float(run(checkout, TIME_VERSION, "time", str(target))))
    (out / "time.json").write_text(json.dumps(times), encoding="utf-8")
    report(out)


def report(out: Path) -> None:
    """Print the report from the output files of `drive`."""
    results: dict[str, dict[str, dict[str, Any]]] = {"main": {}, "change": {}}
    for label in results:
        for version in VERSIONS:
            text = (out / f"{label}-{version}.json").read_text(encoding="utf-8")
            results[label][version] = json.loads(text)
    summary: dict[str, Any] = {}
    for label in ("main", "change"):
        runs = common(results[label])
        base = runs[VERSIONS[0]]
        summary[label] = {
            "files": len(base["stdlib"]),
            "modules": len(base["components"]),
            "totals": totals(base),
            "components_equal": {v: r["components"] == base["components"] for v, r in runs.items()},
            "against_3.11": {v: changed(base, r) for v, r in runs.items()},
        }
    both = common({f"{label[0]}{v}": r for label, runs in results.items() for v, r in runs.items()})
    summary["once_for_a_user"] = {v: changed(both[f"m{v}"], both[f"c{v}"]) for v in VERSIONS}
    times = json.loads((out / "time.json").read_text(encoding="utf-8"))
    medians = {k: statistics.median(v) for k, v in times.items()}
    summary["time"] = {
        "runs": times,
        "medians": medians,
        "ratio": medians["change"] / medians["main"],
    }
    summary["acceptance"] = {
        "a": all(summary["change"]["components_equal"].values())
        and all(zero(counts) for counts in summary["change"]["against_3.11"].values()),
        "b": summary["time"]["ratio"] <= LIMIT,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    step, *rest = sys.argv[1:]
    if step == "values":
        values(Path(rest[0]), Path(rest[1]))
    elif step == "time":
        timed(Path(rest[0]))
    elif step == "report":
        report(Path(rest[0]))
    elif step == "drive":
        drive(*(Path(item) for item in rest))
    else:
        raise SystemExit(f"unknown step: {step}")
