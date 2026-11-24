"""Each module of the package must import as the first import of a new interpreter.

Before this test, `import systemap.check` failed in a new interpreter: `check` imported
the figure module, the figure module imported the delta through the change module, and
the delta imported names from `check`. The commands worked only because `systemap.cli`
imported the modules in an order that did not start the cycle at `check`.
"""

from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import systemap

MODULES = sorted(
    path.stem for path in Path(systemap.__file__).parent.glob("*.py") if path.stem != "__main__"
)


def _failure(module: str) -> str:
    """Give the last error line of the import in a new interpreter, or an empty string."""
    done = subprocess.run(
        [sys.executable, "-c", f"import systemap.{module}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode == 0:
        return ""
    lines = done.stderr.strip().splitlines()
    return f"{module}: {lines[-1] if lines else done.returncode}"


def test_each_module_imports_alone() -> None:
    assert len(MODULES) > 200
    with ThreadPoolExecutor(max_workers=8) as pool:
        failures = [line for line in pool.map(_failure, MODULES) if line]
    assert failures == []
