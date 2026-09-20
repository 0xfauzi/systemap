"""The fifteen cases a person has to label before the drift question can ship.

`delta` would like to say "this is what changed for the people using it": for
each journey step through a card the change touched, whether the step's
sentence still describes what happens. Jev can be asked that. Whether its
answer is right is unknown, because the only labels that exist were written
by another model (`bench/jev/README.md`, test 7).

This builds the set to label, out of the real situation the feature is for:
a map drawn a month ago, and the code as it is now.

    base ..... the commit each bench map was drawn against
    head ..... that repository's origin today
    case ..... one journey step, and the diff of the modules behind the two
               cards its edge joins, between those two commits

Steps whose modules did not change are dropped: there is nothing to judge.
The rest are ranked by how much of their own code changed, because that is
where a sentence is most likely to have stopped being true, and the largest
few per repository are taken. The rule is mechanical and stated here so the
sample cannot be accused of being chosen to flatter the answer.

    uv run --project bench/jev python bench/jev/label_set.py

It writes `data/label-drift-cases.json`. Nothing is sent anywhere.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import DEV_REPOS, SCRATCH

from systemap import config, nest
from systemap.evidence import owners

DATA = Path(__file__).parent / "data"
# How many cases in all, and at most this many from any one repository, so
# that one busy month does not decide the whole measurement.
WANTED = 15
PER_REPO = 4
# A step whose code moved by fewer lines than this has nothing to judge.
LINES_AT_LEAST = 20
# How much of the diff a person is asked to read.
DIFF_LINES = 120
HTTPIE = SCRATCH / "cli-first-map-20260919T193559Z/repo"


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    return done.stdout if done.returncode == 0 else ""


def head_of(root: Path) -> str:
    for ref in ("origin/HEAD", "origin/main", "origin/master", "origin/mealie-next"):
        found = git(root, "rev-parse", ref).strip()
        if found:
            return found
    return ""


def files_of(cards: tuple[str, str], model: Any, facts: dict[str, Any]) -> list[str]:
    """The files behind the two cards a step's edge joins."""
    owner = owners(model, facts)
    out = []
    for module, record in facts.get("components", {}).items():
        if owner.get(module) in cards and record.get("file"):
            out.append(record["file"])
    return sorted(out)


def changed(root: Path, base: str, head: str, files: list[str]) -> tuple[int, str]:
    """How many lines of those files moved between the two commits, and the diff."""
    if not files:
        return 0, ""
    stat = git(root, "diff", "--numstat", f"{base}..{head}", "--", *files[:200])
    lines = 0
    for row in stat.splitlines():
        parts = row.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            lines += int(parts[0]) + int(parts[1])
    if lines < LINES_AT_LEAST:
        return lines, ""
    diff = git(root, "diff", "--unified=2", f"{base}..{head}", "--", *files[:200])
    return lines, "\n".join(diff.splitlines()[:DIFF_LINES])


def stat_of(root: Path, base: str, head: str, files: list[str]) -> list[str]:
    """Which of those files moved, and by how much: the largest first."""
    rows = []
    for row in git(root, "diff", "--numstat", f"{base}..{head}", "--", *files[:200]).splitlines():
        parts = row.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            rows.append((int(parts[0]) + int(parts[1]), f"{parts[2]} +{parts[0]} -{parts[1]}"))
    rows.sort(reverse=True)
    return [text for _n, text in rows[:12]]


def commits_of(root: Path, base: str, head: str, files: list[str]) -> list[str]:
    """The commits that touched those files, which is usually enough to judge by."""
    out = git(root, "log", "--format=%s", f"{base}..{head}", "--", *files[:200])
    return [line for line in out.splitlines() if line][:10]


def compare_url(root: Path, base: str, head: str) -> str:
    url = git(root, "remote", "get-url", "origin").strip()
    if "github.com" not in url:
        return ""
    slug = url.split("github.com")[-1].lstrip(":/").removesuffix(".git")
    return f"https://github.com/{slug}/compare/{base[:9]}...{head[:9]}"


def cases_of(name: str, root: Path) -> list[dict[str, Any]]:
    base = git(root, "rev-parse", "HEAD").strip()
    head = head_of(root)
    if not head or head == base:
        return []
    cfg = config.load(root)
    top = nest.load(cfg).top
    facts = json.loads(cfg.facts_path.read_text())
    out: list[dict[str, Any]] = []
    for journey in top.meaning.journeys:
        for k, step in enumerate(journey.steps, start=1):
            files = files_of(step.edge, top.model, facts)
            lines, diff = changed(root, base, head, files)
            if not diff:
                continue
            out.append(
                {
                    "id": f"{name}#{journey.id}#{k}",
                    "repo": name,
                    "journey": journey.label,
                    "step": k,
                    "of": len(journey.steps),
                    "edge": list(step.edge),
                    "acts": list(step.acts),
                    "says": step.say,
                    "cards": {
                        cid: (top.meaning.plain.get(cid) or _does(top.model, cid))
                        for cid in step.edge
                    },
                    "base": base[:9],
                    "head": head[:9],
                    "lines": lines,
                    "files": len(files),
                    "stat": stat_of(root, base, head, files),
                    "commits": commits_of(root, base, head, files),
                    "compare": compare_url(root, base, head),
                    "diff": diff,
                }
            )
    out.sort(key=lambda c: -c["lines"])
    return out[:PER_REPO]


def _does(model: Any, cid: str) -> str:
    for c in model.components:
        if c.id == cid:
            return c.does
    return ""


def main() -> int:
    repos = dict(DEV_REPOS)
    if (HTTPIE / "docs/map/map.json").exists():
        repos["httpie"] = HTTPIE
    found: list[dict[str, Any]] = []
    for name, root in repos.items():
        mine = cases_of(name, root)
        print(f"{name}: {len(mine)} steps whose code moved since the map was drawn")
        found += mine
    found.sort(key=lambda c: -c["lines"])
    kept = found[:WANTED]
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "label-drift-cases.json").write_text(json.dumps(kept, indent=1))
    print(f"\n{len(kept)} cases written to data/label-drift-cases.json")
    for case in kept:
        print(f"  {case['id']}: {case['lines']} lines over {case['files']} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
