"""Measure issue 143: does the 2.0.0 form of the evidence agree after facts format 14?

At 80e418b, `systemap.toml` of this repository has 6 exact answers with 2.0.0 evidence
digests. 3.0.0 calculated the 2.0.0 form of the evidence from facts format 13, with the
`ast.unparse` text of the signatures and previews. Facts format 14 gets this text from the
source lines. `python_earlier_text` gets the `ast.unparse` text again for the 2.0.0 form.

Acceptance values, written on 2026-11-09 after a first probe in the scratchpad and before
the run of this script:

(a) With `python_earlier_text`, the 2.0.0 form gives 6 of the 6 recorded digests.
(b) No acceptance value. The script gives the number of digests without `python_earlier_text`.
(c) No acceptance value. The script gives the time of `answer_upgrade._earlier_facts` for
    the tree at 80e418b and for the tree of TARGET: the median of 5 calls in one process.
    The upgrade calls it only if an exact answer is not current.

Run from the repository root:

    git archive 80e418b | tar -x -C OLD
    uv run python bench/jev/earlier_text_probe.py OLD TARGET

OLD is an empty directory. TARGET is the repository of the current revision.
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path
from typing import Any

from systemap import answer_migrations, answer_upgrade, config, extract, judgement, nest


def agreements(root: Path, use_text: bool) -> tuple[int, int]:
    """Give the number of recorded 2.0.0 digests that the 2.0.0 form gives, and the total."""
    cfg = config.load(root)
    facts: dict[str, Any] = extract.build(cfg)
    if use_text:
        facts = answer_upgrade._earlier_facts(cfg, facts)
    answers = [a for a in cfg.judgement_answered if a.items and len(a.evidence) == 64]
    lines = {item: answer_migrations.current_line(item) for a in answers for item in a.items}
    tree = nest.load(cfg)
    before = judgement.evidence_for_tree(
        tree, facts, root, list(dict.fromkeys(lines.values())), earlier=True
    )
    found = 0
    for answer in answers:
        by_line = {lines[i]: before.get(lines[i], "unavailable") for i in answer.items}
        found += judgement.answer_digest(answer.items, by_line) == answer.evidence
    return found, len(answers)


def seconds(root: Path) -> tuple[int, float]:
    """Give the number of module records and the median time of `_earlier_facts`."""
    cfg = config.load(root)
    facts = extract.build(cfg)
    runs = []
    for _ in range(5):
        start = time.perf_counter()
        answer_upgrade._earlier_facts(cfg, facts)
        runs.append(time.perf_counter() - start)
    return len(facts["components"]), statistics.median(runs)


def main(old: Path, target: Path) -> None:
    for use_text in (True, False):
        found, total = agreements(old, use_text)
        label = "with python_earlier_text" if use_text else "without python_earlier_text"
        print(f"{label}: {found} of {total} digests agree")
    for name, root in (("80e418b", old), ("target", target)):
        count, median = seconds(root)
        print(f"{name}: {count} module records, _earlier_facts median {median:.3f} s")
    print(f"python {sys.version.split()[0]}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
