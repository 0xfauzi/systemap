"""A round trip of one nested part through a Git worktree.

Acceptance values:

1. The plan and the result files are in the folder `map/parts`, which Git tracks. Thus a
   worktree branch has the plan of the contract commit.
2. In the worktree, `parts --map P0 --json` gives the record and the digests of the
   part. The part agent writes its result file with these digests and commits it with
   its model file.
3. After `git merge` of the worktree branch, the files of the part commit are in the
   write set of the part, and `parts --results` reads the result file of P0 with no
   problem.
4. A result file with a different `contract_digest` gives a problem after the merge.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import three_levels
from conftest import write_tree

from systemap.cli import main


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return proc.stdout.strip()


def run(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    capsys.readouterr()
    code = main(["--root", str(root), *argv])
    return code, capsys.readouterr().out


def _contract_commit(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(root, three_levels.files())
    git(root, "init", "-q", "-b", "main")
    for argv in (("place",), ("extract",), ("refresh", "--quiet"), ("parts",)):
        assert run(root, capsys, *argv)[0] == 0
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "contract")


def _part_commit(tree: Path, capsys: pytest.CaptureFixture[str], digest: str = "") -> str:
    """Do the work of the part agent of P0 in its worktree. Give the commit."""
    code, out = run(tree, capsys, "parts", "--map", "P0", "--json")
    assert code == 0
    record: dict[str, Any] = json.loads(out)
    part = record["part"]
    model = tree / part["model_file"]
    model.write_text(model.read_text(encoding="utf-8") + "\n# The part agent of P0.\n")
    result = {
        "map": "P0",
        "base_commit": record["base_commit"],
        "facts_digest": record["facts_digest"],
        "contract_digest": digest or record["contract_digest"],
        "files": [part["model_file"], part["result_file"]],
        "check_exit": run(tree, capsys, "check", "--map", "P0")[0],
        "open_lines": [],
        "verdicts": [],
        "answers": [],
        "proposed_answers": [],
        "boundary_requests": [],
        "questions": [],
    }
    (tree / part["result_file"]).write_text(json.dumps(result, indent=2) + "\n")
    git(tree, "add", part["model_file"], part["result_file"])
    git(tree, "commit", "-q", "-m", "part P0")
    return git(tree, "rev-parse", "HEAD")


@pytest.mark.parametrize("digest", ["", "0" * 64], ids=["same", "different"])
def test_a_part_goes_through_a_worktree_and_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], digest: str
) -> None:
    """Acceptance 1 to 4."""
    root = tmp_path / "main"
    _contract_commit(root, capsys)
    assert "map/parts/plan.json" in git(root, "ls-files", "map/parts")
    base = git(root, "rev-parse", "HEAD")
    tree = tmp_path / "part-p0"
    git(root, "worktree", "add", "-q", "-b", "part-p0", str(tree))
    assert (tree / "map/parts/plan.json").is_file()
    commit = _part_commit(tree, capsys, digest)
    git(root, "merge", "-q", "--no-edit", "part-p0")
    changed = git(root, "diff", "--name-only", base, commit).splitlines()
    plan = json.loads((root / "map/parts/plan.json").read_text(encoding="utf-8"))
    part = next(r for r in plan["parts"] if r["map"] == "P0")
    allowed = {part["model_file"], part["contract_file"], part["result_file"]}
    assert all(name in allowed or name.startswith(part["file_prefix"]) for name in changed)
    code, out = run(root, capsys, "parts", "--results", "--json")
    found = json.loads(out)["problems"]
    assert code == 1
    assert found["P1"] == ["the result file map/parts/p1.json is missing"]
    if digest:
        assert found["P0"] == [
            "the contract_digest is not the contract_digest of the plan. Send the part back."
        ]
    else:
        assert found["P0"] == []
