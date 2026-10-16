"""The contract gives the rules of a map: the invariants and the import rules.

The contract file is in the folder of the model file of its map. For `map/model.py`, it is
`map/contract.py`. For a different model file, such as the nested map `map/gateway.py`, it
is `map/gateway_contract.py`. The file gives CONTRACT, a `Contract` value.

The map files give the description of the code. An agent changes them freely. The
contract file gives the boundaries of the code. An agent changes a rule only with a
reason. A change to a rule is a change to this file in a pull request.

Each rule must have a reason. A rule without a reason gives a `contract reason` line. The
line contains the kind of rule and its number or id, and no value that changes while the
finding stays the same.

The reason of an invariant is not a claim of a component (`claim`). Thus a new reason
changes no source review digest and no answer evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap.model import ImportRule, Invariant, Model

KIND = "contract reason"
NAME = "CONTRACT"
# The contract file of the model file `model.py` has this name.
FILE_NAME = "contract.py"
SUFFIX = "_contract.py"

TEMPLATE = '''# ruff: noqa: E501
"""The architecture contract of the map in {model}.

The contract gives the rules of the system: the invariants and the import rules.
Each rule has a reason from the code, the documentation, or the history of the repository.
An agent changes the map freely. An agent changes a rule of this file only with a reason.
If a reviewer refuses a change to a rule, add the cause to the reason of the rule that stays.
"""

from __future__ import annotations

# The contract uses the systemap tool package.
from systemap import (  # type: ignore[import-not-found, unused-ignore]
    Contract,
    ImportRule,
    Invariant,
)

# Each invariant gives a number, the rule, the applicable components, and the reason.
INVARIANTS: tuple[Invariant, ...] = ()

# Each import rule gives an id, a kind, the components, and the reason.
IMPORT_RULES: tuple[ImportRule, ...] = ()

CONTRACT = Contract(invariants=INVARIANTS, import_rules=IMPORT_RULES)
'''


@dataclass(frozen=True)
class Contract:
    """The rules of one map: the invariants and the import rules."""

    invariants: tuple[Invariant, ...] = ()
    import_rules: tuple[ImportRule, ...] = ()


# The Model fields that the contract gives.
FIELDS = ("invariants", "import_rules")


def path_for(model_path: Path) -> Path:
    """Give the contract file of a model file, in the same folder."""
    if model_path.name == "model.py":
        return model_path.with_name(FILE_NAME)
    return model_path.with_name(model_path.stem + SUFFIX)


def has_rules(value: Model | Contract) -> bool:
    """Tell if a model or a contract contains an invariant or an import rule."""
    return bool(value.invariants or value.import_rules)


def text(model_label: str) -> str:
    """Give the text of a new contract file for the map in the model file."""
    return TEMPLATE.format(model=model_label)


def claim(invariant: Invariant) -> dict[str, Any]:
    """Give the claim of an invariant for a component: the number, the rule, and the
    applicable components. The reason is not a claim."""
    return {"n": invariant.n, "text": invariant.text, "governs": invariant.governs}


def unreasoned(model: Model) -> list[str]:
    """Give one `contract reason` line for each rule without a reason."""
    out = [
        f"{KIND}: invariant {rule.n} has no reason"
        for rule in model.invariants
        if not rule.reason.strip()
    ]
    out += [
        f"{KIND}: import rule {rule.id} has no reason"
        for rule in model.import_rules
        if not rule.reason.strip()
    ]
    return out
