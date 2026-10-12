"""Load each model file that the repository and bench/scratch contain with the safe reader.

Acceptance (written before the run): the safe reader accepts the self-map, the TypeScript
test fixture, the model that `systemap init` writes, and the worked example of the skill:
0 refusals in these four. Each other file is listed with the result and the reason for a
refusal. A refusal is a change that the person must make, or the opt-in
SYSTEMAP_TRUST_MODEL_CODE=1, so the list goes in bench/jev/README.md.

The script also extracts the Python examples that contain `MODEL = Model(` from Markdown
files. It does not load model text that a test writes at run time: the test suite does
that (tests/test_model_load.py and the other tests that load models).

Run from the repository root: uv run python bench/jev/model_census.py [ROOT ...]
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

from systemap import model_load, scaffold

SKIP = ("/.venv/", "/site-packages/", "/node_modules/", "/.git/", "/worktrees/")
FENCE = re.compile(r"```python\n(.*?)```", re.S)


def model_files(root: Path) -> list[Path]:
    found = []
    for path in sorted(root.rglob("map/*.py")):
        text = "/" + path.relative_to(root).as_posix()
        if any(part in text for part in SKIP) or "/tests/test_" in text:
            continue
        if path.name == "model.py" or "MODEL = Model(" in path.read_text(encoding="utf-8"):
            found.append(path)
    return found


def markdown_examples(root: Path) -> list[tuple[str, str]]:
    out = []
    for path in sorted(root.rglob("*.md")):
        if any(part in "/" + path.relative_to(root).as_posix() for part in SKIP):
            continue
        for k, block in enumerate(FENCE.findall(path.read_text(encoding="utf-8"))):
            if "MODEL = Model(" in block:
                out.append((f"{path.relative_to(root)} (example {k + 1})", block))
    return out


def result(path: Path, label: str) -> str:
    try:
        names = model_load.read(path, label)
    except model_load.ModelFileError as exc:
        return "refused: " + str(exc).split(" systemap does not run code")[0]
    return "accepted" if "MODEL" in names else "accepted, but it has no MODEL"


def main() -> None:
    roots = [Path(arg).resolve() for arg in sys.argv[1:]] or [Path.cwd()]
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "map"
        folder.mkdir()
        template = folder / "model.py"
        template.write_text(
            scaffold.MODEL.format(doc_name="pkg", label='"PKG"', package="pkg"), encoding="utf-8"
        )
        print(f"init template: {result(template, 'map/model.py')}")
        for root in roots:
            for path in model_files(root):
                print(f"{path.relative_to(root)}: {result(path, str(path.relative_to(root)))}")
            for name, block in markdown_examples(root):
                example = folder / "example.py"
                example.write_text(block, encoding="utf-8")
                print(f"{name}: {result(example, name)}")


if __name__ == "__main__":
    main()
