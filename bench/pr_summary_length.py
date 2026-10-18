"""Measure the length of the pull request summary of `systemap delta --comment`.

Acceptance value, written before the measurement:

- The summary of a change without an architectural effect is one line after the marker.
- Each summary has at most 26 lines after the marker. The row limit (5 rows and one
  count row in each part) gives this maximum.

The script records the lines, the words, and the characters of each summary. These
values are records. They are not acceptance values.

The measured summaries:

- This repository: HEAD against four bases. The bases are HEAD, 4d2b030 (the merge of
  issue 98), b611ede~1 (before the contract file), and 0ef6399 (an earlier merge).
- `two-card`: the two-card fixture of the tests. The head commit adds a module without
  a component, an import rule, a reason to the invariant, and a new flow artifact.

The script sends no request to a decision provider (`--no-decide`).

    uv run python bench/pr_summary_length.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from conftest import STARTER_MODULES, init_two_cards, write_tree  # noqa: E402

from systemap.cli import main  # noqa: E402

BASES = ("HEAD", "4d2b030", "b611ede~1", "0ef6399")
RULE = (
    "IMPORT_RULES: tuple[ImportRule, ...] = (\n"
    '    ImportRule("no-back", "forbid_import", src=("Reader",), dst=("Writer",), '
    'reason="The reader does not depend on the writer."),\n'
    ")"
)


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def summary(root: Path, base: str, out: Path) -> str:
    code = main(
        [
            "--root",
            str(root),
            "delta",
            "--no-decide",
            "--brief",
            "--base",
            base,
            "--comment",
            str(out),
        ]
    )
    if code not in (0, 1):
        raise SystemExit(f"delta exit {code} for base {base}")
    return out.read_text(encoding="utf-8")


def row(name: str, text: str) -> str:
    body = text.split("\n", 1)[1].rstrip("\n")
    lines = body.count("\n") + 1
    return f"| {name} | {lines} | {len(body.split())} | {len(body)} |"


def two_card(tmp: Path) -> Path:
    root = tmp / "two-card"
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(root, "--no-ci")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    write_tree(root, {"pkg/audit.py": "def audit() -> int:\n    return 1\n"})
    contract = root / "map/contract.py"
    text = contract.read_text(encoding="utf-8")
    text = text.replace("IMPORT_RULES: tuple[ImportRule, ...] = ()", RULE)
    old, new = "each request from the reader.", "each request from the reader only."
    text = text.replace(old, new)
    contract.write_text(text, encoding="utf-8")
    model = root / "map/model.py"
    model.write_text(
        model.read_text(encoding="utf-8").replace('"request", "data"', '"parsed request", "data"'),
        encoding="utf-8",
    )
    assert main(["--root", str(root), "refresh"]) in (0, 1)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "head")
    return root


def run() -> None:
    with tempfile.TemporaryDirectory(prefix="pr-summary-") as name:
        tmp = Path(name)
        out = tmp / "comment.md"
        texts = {f"systemap, base {base}": summary(ROOT, base, out) for base in BASES}
        texts["two-card, base HEAD~1"] = summary(two_card(tmp), "HEAD~1", out)
    print("| summary | lines | words | characters |")
    print("|---|---|---|---|")
    for key, text in texts.items():
        print(row(key, text))
    for key, text in texts.items():
        print(f"\n{key}:\n{text}")


if __name__ == "__main__":
    run()
