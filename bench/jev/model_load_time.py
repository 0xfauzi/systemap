"""Measure the load time of the self-map with the code loader and the safe reader.

Acceptance (written before the run): the safe reader (`model_load.read`) takes at most
twice the time of the code loader (`model_load.run_code`, the loader of systemap 2.0) for
`map/model.py` and the files that it imports. Each loader loads the same files 30 times in one
process after one load that is not counted. The script gives the median and the minimum.

The code loader imports the files in the directory of the model file. Python keeps their bytecode in
`map/__pycache__` after the first load, unless PYTHONDONTWRITEBYTECODE is set. If the safe
reader refuses the file, the script gives the refusal and the code loader time only.

Run from the repository root: uv run python bench/jev/model_load_time.py [MODEL_PATH]
"""

from __future__ import annotations

import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from systemap import model_load

RUNS = 30


def timed(load: Callable[[Path, str], dict[str, Any]], path: Path) -> list[float]:
    load(path, "map/model.py")
    out = []
    for _ in range(RUNS):
        start = time.perf_counter()
        names = load(path, "map/model.py")
        out.append(time.perf_counter() - start)
        assert "MODEL" in names and "MEANING" in names
    return out


def line(name: str, times: list[float]) -> str:
    return (
        f"{name}: median {statistics.median(times) * 1000:.1f} ms, "
        f"minimum {min(times) * 1000:.1f} ms, {RUNS} runs"
    )


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "map/model.py")
    code = timed(model_load.run_code, path)
    print(line("code loader", code))
    try:
        safe = timed(model_load.read, path)
    except model_load.ModelFileError as exc:
        print(f"safe reader: refused: {str(exc).split(' systemap does not')[0]}")
        return
    print(line("safe reader", safe))
    ratio = statistics.median(safe) / statistics.median(code)
    print(f"ratio of the medians: {ratio:.2f} ({'passes' if ratio <= 2 else 'fails'} at 2.00)")


if __name__ == "__main__":
    main()
