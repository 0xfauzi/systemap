"""The contract move writes the rules of an earlier map into its contract file one time.

A map from before the contract file gives its invariants and import rules in its model
file. `systemap refresh` and `systemap extract` move them to the contract file of the map
(`contract.path_for`) before they write the facts. The move does this for each map of the
tree, also for each nested map. If the contract file of a map gives rules, or if its
model file gives no rules, the map does not change. Thus a second command writes nothing.

The move keeps all other text of the model file (`contract_edit`). It writes the files
only if the reader gives the same MODEL and MEANING from the new files, and the contract
file gives the rules. If not, it gives a warning line and writes no file. The reader
examines the two changed files in the pull request.

The rules do not change. Thus no source review digest, no flow review digest, and no
evidence of a line that names a component changes. The evidence of a line that names
nothing contains the digest of the map files (`judgement_evidence.model_digest`), and
the move changes that digest. Thus the move writes the new digest of each answer that
was current before the move, as `answer_upgrade` does.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from systemap import (
    answer_upgrade,
    answer_write,
    config,
    contract,
    contract_edit,
    contract_file,
    file_write,
    judgement,
    model_load,
    model_write,
    nest,
    source_text,
)
from systemap.config import Answer, Config, ConfigError

_DIGEST = re.compile(r"[0-9a-f]{64}")
_ERRORS = (
    contract_edit.EditError,
    ConfigError,
    model_load.ModelFileError,
    OSError,
    SyntaxError,
    UnicodeError,
)


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def needs_move(m: nest.Map) -> bool:
    """Tell if the model file of the map gives the rules: the rules are not in the
    contract file."""
    if not contract.has_rules(m.model):
        return False
    found = contract_file.read(m.path, m.rel)
    return found is None or not contract.has_rules(found)


def record(cfg: Config, tree: nest.Tree, facts: dict[str, Any]) -> list[str]:
    """Move the rules of each earlier map to its contract file.

    Give one line for each map with moved rules. Give one warning line for each map that
    the command cannot change. Give one line if the command wrote answer evidence."""
    chosen = [m for m in tree.maps if needs_move(m)]
    if not chosen:
        return []
    current, keys, lines = _current_answers(cfg, tree, facts)
    out: list[str] = []
    for m in chosen:
        try:
            out.append(_move(cfg, m))
        except _ERRORS as exc:
            out.append(f"warning: {m.prefix}the command cannot move the contract of {m.rel}: {exc}")
    if current and any(not line.startswith("warning:") for line in out):
        out += _renew(cfg, facts, current, keys, lines)
    return out


def _move(cfg: Config, m: nest.Map) -> str:
    source = source_text.decode(m.path.read_bytes())
    moved = contract_edit.taken(source)
    new_model = contract_edit.model_text(source, moved)
    target = contract.path_for(m.path)
    present = target.is_file()
    base = source_text.decode(target.read_bytes()) if present else contract.text(m.rel)
    new_contract = contract_edit.contract_text(base, moved)
    _same(m, target, new_model, new_contract)
    if present:
        model_write.write_models({target: new_contract, m.path: new_model})
    else:
        file_write.write_atomic(cfg.root, target, new_contract)
        try:
            model_write.write_models({m.path: new_model})
        except OSError:
            target.unlink(missing_ok=True)
            raise
    rules = _plural(len(m.model.invariants), "invariant")
    imports = _plural(len(m.model.import_rules), "import rule")
    return (
        f"contract: {m.prefix}the command moved {rules} and {imports} from {m.rel} to "
        f"{cfg.rel(target)}. Examine the two files. Then commit them."
    )


def _same(m: nest.Map, target: Path, new_model: str, new_contract: str) -> None:
    """Read the new texts in a copy of the map files. Refuse a different model or meaning."""
    with tempfile.TemporaryDirectory(prefix="systemap-contract-") as folder:
        copy = Path(folder)
        for each in contract_file.map_files(m.path, m.rel):
            shutil.copyfile(each, copy / each.name)
        (copy / m.path.name).write_text(new_model, encoding="utf-8", newline="")
        (copy / target.name).write_text(new_contract, encoding="utf-8", newline="")
        model, meaning = config.load_model(copy / m.path.name, m.rel)
        found = contract_file.read(copy / m.path.name, m.rel)
    if found is None or not contract.has_rules(found):
        raise contract_edit.EditError("the new contract file gives no rules")
    if (model, meaning) != (m.model, m.meaning):
        raise contract_edit.EditError("the new files do not give the same model")


def _current_answers(
    cfg: Config, tree: nest.Tree, facts: dict[str, Any]
) -> tuple[list[Answer], dict[str, str], list[str]]:
    """Give the exact answers that are current before the move, the evidence line of each
    item, and the evidence lines."""
    if not cfg.source:
        return [], {}, []
    exact = [a for a in cfg.judgement_answered if a.items and _DIGEST.fullmatch(a.evidence)]
    keys = {item: answer_upgrade._evidence_line(a, item) for a in exact for item in a.items}
    lines = list(dict.fromkeys(keys.values()))
    before = judgement.evidence_for_tree(tree, facts, cfg.root, lines)
    current = [a for a in exact if a.evidence == answer_upgrade._digest(a, keys, before)]
    return current, keys, lines


def _renew(
    cfg: Config,
    facts: dict[str, Any],
    current: list[Answer],
    keys: dict[str, str],
    lines: list[str],
) -> list[str]:
    """Write the new digest of each answer that was current before the move."""
    try:
        after = judgement.evidence_for_tree(nest.load(cfg), facts, cfg.root, lines)
    except ConfigError as exc:
        return [f"warning: the command cannot read the map after the move: {exc}"]
    found: dict[str, str] = {}
    for answer in current:
        new = answer_upgrade._digest(answer, keys, after)
        if new not in (answer.evidence, "unavailable"):
            found[answer.evidence] = new
    if not found:
        return []
    try:
        written = answer_write.renew_evidence(cfg.root, cfg.source, found)
    except answer_write.AnswerWriteError as exc:
        return [f"warning: the command cannot write the evidence of the answers: {exc}"]
    return [
        f"answers: the command wrote the current evidence digest of {len(found)} answers in "
        f"{cfg.rel(written)}. Each answer was current before the move of the contract."
    ]
