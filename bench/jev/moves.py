"""Idea 3: which old module became which new one, measured on the renames git reports.

    uv run python moves.py build   # facts at each commit, delta's own pairing, rows for Jev
    uv run python run.py moves
    uv run python moves.py score

Truth is git's rename detection (-M50) on commits that rename a .py file inside
a package root. Every module that disappears in the commit is asked about: a
renamed one should be paired with its new path, a deleted one with nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys

from common import DATA, REPOS, choice, first_sentence, load, row, write

from systemap.delta import facts_at
from systemap.extract import is_empty_marker
from systemap.moves import find as _moves

NOT_MOVED = "not moved: deleted"
PER_REPO = 12


def module_of(path: str, records: dict) -> str | None:
    for m, r in records.items():
        if r.get("file") == path:
            return m
    return None


def rename_commits(root, limit: int) -> list[tuple[str, list[tuple[str, str]]]]:
    out = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "log",
            "-M50%",
            "--diff-filter=R",
            "--name-status",
            "--format=@%H",
            "--no-merges",
            "-n",
            "3000",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    commits, cur = [], None
    for line in out.splitlines():
        if line.startswith("@"):
            cur = (line[1:], [])
            commits.append(cur)
        elif line.startswith("R") and cur is not None:
            _, old, new = line.split("\t")
            if old.endswith(".py") and new.endswith(".py") and "test" not in old:
                cur[1].append((old, new))
    return [c for c in commits if c[1]][:limit]


def brief(r: dict) -> str:
    names = ", ".join(n["name"] for n in r.get("names", [])[:12])
    return f"{r.get('file')}: {first_sentence(r.get('docstring') or '', 160)} Names: {names}"


BECAME_Q = (
    "In one commit `old_module` disappeared and the modules in the options "
    "appeared. Which new module is the old one, moved or renamed and perhaps "
    "edited? If it was deleted, say so."
)


def appeared_and_gone(b: dict, h: dict) -> tuple[list[str], list[str]]:
    gone = sorted(m for m in b if m not in h and not is_empty_marker(b[m]))
    new = sorted(m for m in h if m not in b and not is_empty_marker(h[m]))
    return gone, new


def wanted(
    renames: list[tuple[str, str]], b: dict, h: dict, gone: list[str], new: list[str]
) -> dict:
    """old module -> new module, for every rename git reports between modules that came and went."""
    pairs = [(module_of(old, b), module_of(newp, h)) for old, newp in renames]
    return {o: n for o, n in pairs if o in gone and n in new}


def old_state(b: dict, o: str) -> dict:
    return {
        "old_module": {
            "module": o,
            **{k: b[o].get(k) for k in ("file", "docstring")},
            "names": [n["name"] for n in b[o].get("names", [])][:40],
        }
    }


def moves_rows(name, sha, b, h, gone, new, want, got) -> list[dict]:
    crit = {m: brief(h[m]) for m in new[:250]}
    crit[NOT_MOVED] = "The old module was deleted; none of the new modules continues it."
    return [
        row(
            "moves",
            name,
            f"{name}@{sha[:8]}:{o}",
            old_state(b, o),
            {"became": choice(BECAME_Q, crit)},
            {"became": want.get(o, NOT_MOVED), "delta": got.get(o, NOT_MOVED)},
        )
        for o in gone
    ]


def commit_rows(
    name: str, repo, sha: str, renames: list[tuple[str, str]]
) -> tuple[list[dict], dict | None]:
    """The rows for one renaming commit, and its truth record; nothing when it has no usable rename."""
    try:
        base, head = facts_at(repo.cfg, f"{sha}^"), facts_at(repo.cfg, sha)
    except Exception as e:  # noqa: BLE001 - a commit the extractor cannot read is skipped and said
        print(f"  skip {name}@{sha[:7]}: {e!r}"[:200])
        return [], None
    b, h = base["components"], head["components"]
    gone, new = appeared_and_gone(b, h)
    want = wanted(renames, b, h, gone, new)
    if not gone or not new or not want:
        return [], None
    got = {o: c for o, (c, _) in _moves(b, h, gone, new).items()}
    rows = moves_rows(name, sha, b, h, gone, new, want, got)
    truth = {"repo": name, "sha": sha, "want": want, "delta": got, "gone": gone, "new": new}
    return rows, truth


def build() -> None:
    rows, truth = [], []
    for name in REPOS:
        repo = load(name)
        kept = 0
        for sha, renames in rename_commits(repo.root, PER_REPO * 3):
            if kept >= PER_REPO:
                break
            got, record = commit_rows(name, repo, sha, renames)
            if record is not None:
                rows += got
                truth.append(record)
                kept += 1
    write("moves", rows)
    (DATA / "moves-truth.json").write_text(json.dumps(truth, indent=1))


def tally(pairings: list[tuple[str, str]]) -> tuple[int, int, int]:
    """(renames found, wrong pairings, renames missed) for (answer, truth) pairs."""
    right = sum(got != NOT_MOVED and got == want for got, want in pairings)
    wrong = sum(got != NOT_MOVED and got != want for got, want in pairings)
    missed = sum(got == NOT_MOVED and want != NOT_MOVED for got, want in pairings)
    return right, wrong, missed


def hybrid(d: dict, answer: dict, threshold: float) -> str:
    """delta's pairing when it has one, else Jev's at or above the confidence threshold."""
    if d["label"]["delta"] != NOT_MOVED:
        return d["label"]["delta"]
    return answer["choice"] if answer["confidence"] >= threshold else NOT_MOVED


def score() -> None:
    from score import results, rows

    data, res = rows("moves"), results("moves")
    both = [(d, res[i]["answers"]["became"]) for i, d in data.items() if i in res]
    renames = sum(d["label"]["became"] != NOT_MOVED for d in data.values())
    print(f"== moves (idea 3): {len(data)} disappeared modules, {renames} of them renamed per git")
    lines = {
        "delta": [(d["label"]["delta"], d["label"]["became"]) for d, _ in both],
        "jev": [(a["choice"], d["label"]["became"]) for d, a in both],
    }
    for t in (0.0, 0.8, 0.9, 0.95):
        lines[f"delta then Jev at conf>={t}"] = [
            (hybrid(d, a, t), d["label"]["became"]) for d, a in both
        ]
    for who, pairings in lines.items():
        right, wrong, missed = tally(pairings)
        print(f"   {who}: {right} renames found, {wrong} wrong pairings, {missed} renames missed")


def file_at(repo, sha: str, path: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo.root), "show", f"{sha}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout


def label_item(d: dict, answer: dict) -> dict:
    """One pairing for a person to judge: the old file, the new one and the diff between them."""
    import difflib

    name, rest = d["id"].split("@", 1)
    sha = rest.split(":", 1)[0]
    repo = load(name)
    full = subprocess.run(
        ["git", "-C", str(repo.root), "rev-parse", sha], capture_output=True, text=True, check=True
    ).stdout.strip()
    old_path = d["state"]["old_module"]["file"]
    new_path = d["questions"]["became"]["criteria"][answer["choice"]].split(":", 1)[0]
    old, new = file_at(repo, f"{full}^", old_path), file_at(repo, full, new_path)
    diff = "".join(
        difflib.unified_diff(old.splitlines(True), new.splitlines(True), old_path, new_path, n=2)
    )
    return {
        "id": d["id"],
        "set": "moves",
        "old": old_path,
        "new": new_path,
        "confidence": answer["confidence"],
        "similarity": round(difflib.SequenceMatcher(None, old, new).ratio(), 2),
        "diff": diff[:12000],
        "truncated": len(diff) > 12000,
    }


def pick() -> None:
    """Every pairing Jev made that git's rename detection does not share."""
    from score import results, rows

    data, res = rows("moves"), results("moves")
    items = [
        label_item(d, res[i]["answers"]["became"])
        for i, d in data.items()
        if i in res
        and res[i]["answers"]["became"]["choice"] not in (NOT_MOVED, d["label"]["became"])
    ]
    (DATA / "label-moves.json").write_text(json.dumps(items, indent=1))
    print(f"picked {len(items)} pairings git does not share")


def score_labels(path: str) -> None:
    """labels.json: {item id: "successor" | "unrelated" | "unsure"}. The truth becomes git's
    renames plus every pairing a person called a successor."""
    from score import results, rows

    labels = json.loads(open(path).read())
    data, res = rows("moves"), results("moves")
    both = [(d, res[i]["answers"]["became"]) for i, d in data.items() if i in res]

    def truth(d, a) -> str:
        return a["choice"] if labels.get(d["id"]) == "successor" else d["label"]["became"]

    print(
        f"== test 8: {sum(v == 'successor' for v in labels.values())} successors, "
        f"{sum(v == 'unrelated' for v in labels.values())} unrelated, {sum(v == 'unsure' for v in labels.values())} unsure"
    )
    base = tally([(d["label"]["delta"], truth(d, a)) for d, a in both])
    print(f"   delta alone: {base[0]} found, {base[1]} wrong, {base[2]} missed")
    for t in (0.8, 0.9, 0.95):
        right, wrong, missed = tally([(hybrid(d, a, t), truth(d, a)) for d, a in both])
        added = [
            (d, a)
            for d, a in both
            if d["label"]["delta"] == NOT_MOVED
            and a["confidence"] >= t
            and a["choice"] != NOT_MOVED
        ]
        good = sum(a["choice"] == truth(d, a) for d, a in added)
        print(
            f"   delta then Jev at {t}: {right} found (+{right - base[0]}), {wrong} wrong; "
            f"Jev's additions right {good}/{len(added)} (pass: +8 or more at 90% right)"
        )


if __name__ == "__main__":
    {"build": build, "score": score, "pick": pick, "labels": lambda: score_labels(sys.argv[2])}[
        sys.argv[1]
    ]()
