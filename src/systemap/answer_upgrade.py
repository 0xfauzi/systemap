"""The answer upgrade writes the current evidence digest of each current answer from 2.0.0.

systemap 2.0.0 recorded the evidence of an exact answer in an earlier form: the full module
records and the source files (`judgement_evidence`, `earlier`). The current evidence has
the facts that the finding cites. Thus each digest from 2.0.0 is different from the
current digest.

`systemap refresh` and `systemap extract` replace a 2.0.0 digest one time, but only if it
agrees with the earlier form of the evidence at this source. Then the answer was current
before the update, and nothing changed after it. The new digest keeps the answer current.
A 2.0.0 digest that does not agree with the source stays in the file, and the answer
stays pending, as before. Each release does the replacement, as for the flow reviews
(`flow_review.needs_record`). Thus a project can go from 2.0.0 to any later release.

The replacement does not examine an answer. It writes only the `evidence` value, and it
keeps all other text of the configuration file (`answer_write.renew_evidence`).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from systemap import (
    answer_migrations,
    answer_write,
    audit,
    decision_kinds,
    judgement,
    nest,
)
from systemap.config import Answer, Config

_DIGEST = re.compile(r"[0-9a-f]{64}")


def record(cfg: Config, tree: nest.Tree, facts: dict[str, Any]) -> list[str]:
    """Write the current digest of each current answer from 2.0.0.

    Give one line if the command wrote the file, or one warning line if it cannot write
    it. Without such answers, give no line."""
    if not cfg.source:
        return []
    exact = [a for a in cfg.judgement_answered if a.items and _DIGEST.fullmatch(a.evidence)]
    if not exact:
        return []
    found = _renewed(cfg, tree, facts, exact)
    if not found:
        return []
    try:
        written = answer_write.renew_evidence(cfg.root, cfg.source, found)
    except answer_write.AnswerWriteError as exc:
        return [f"warning: the command cannot write the evidence of the answers from 2.0.0: {exc}"]
    return [
        f"answers: the command wrote the current evidence digest of {len(found)} answers "
        f"from systemap 2.0.0 in {cfg.rel(written)}. Each answer agreed with the source."
    ]


def _renewed(
    cfg: Config, tree: nest.Tree, facts: dict[str, Any], exact: list[Answer]
) -> dict[str, str]:
    """Give the current digest for each 2.0.0 digest that agrees with the source."""
    keys = {item: _evidence_line(a, item) for a in exact for item in a.items}
    now = judgement.evidence_for_tree(tree, facts, cfg.root, list(dict.fromkeys(keys.values())))
    # Only an answer that is not current can have a 2.0.0 digest. The 2.0.0 form hashes
    # source files, so the command calculates it only for the lines of such answers.
    changed = [
        (a, d) for a in exact if (d := _digest(a, keys, now)) not in (a.evidence, "unavailable")
    ]
    if not changed:
        return {}
    lines = list(dict.fromkeys(keys[item] for a, _d in changed for item in a.items))
    before = judgement.evidence_for_tree(tree, facts, cfg.root, lines, earlier=True)
    return {a.evidence: d for a, d in changed if a.evidence == _digest(a, keys, before)}


def _evidence_line(answer: Answer, item: str) -> str:
    """Give the line whose evidence an item has. A decision line has the evidence of the
    line with its previous kind name (`audit.evidence`)."""
    line = answer_migrations.current_line(item)
    return decision_kinds.previous_line(line) if audit.is_audit_answer(answer) else line


def _digest(answer: Answer, keys: Mapping[str, str], evidence: Mapping[str, str]) -> str:
    """Give the digest that the answer must have, as `judgement.answer_digest` gives it."""
    by_line = {
        answer_migrations.current_line(item): evidence.get(keys[item], "unavailable")
        for item in answer.items
    }
    return judgement.answer_digest(answer.items, by_line)
