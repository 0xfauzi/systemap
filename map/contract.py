# ruff: noqa: E501
"""The architecture contract of the map in map/model.py.

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
# The rules that the repository states, each with its documentation, guard clause or test.
INVARIANTS: tuple[Invariant, ...] = (
    Invariant(
        1,
        "Do not show code or test counts on the page. The map shows system functions, not code quantity (src/systemap/skill/references/schema.md, Component).",
        governs=("Page", "Schematic", "Figures"),
        reason="A count of code or tests does not tell the reader the function of a component. The map keeps relationships on flows, not in prose or numbers (src/systemap/skill/SKILL.md, Completion).",
    ),
    Invariant(
        2,
        "A component must have a function that a reader can identify. A module alone does not identify a component (README, What are a component, a flow, and a sequence?).",
        governs=("Model", "Skill", "Judgement"),
        reason="A component for each file gives no information that the file tree does not give (src/systemap/explain.py, single module).",
    ),
    Invariant(
        3,
        "Flow lines show relationships. Each flow must have an explanation (src/systemap/skill/references/schema.md, Flow).",
        governs=("Model", "Schematic"),
        reason="A flow without a description does not tell the reader which data moves or why (src/systemap/explain.py, no sentence).",
    ),
    Invariant(
        4,
        "The map shows code in the repository. Each module in a component claim must be in the facts. The map is not a plan (src/systemap/check.py, check_entry).",
        governs=("Model", "Check", "FactsExtractor"),
        reason="The checks compare each claim with the source facts. A claim about code that is not in the facts has no evidence, and the map then shows a plan, not the system (src/systemap/model.py, docstring).",
    ),
    Invariant(
        5,
        "Keep positions in the model. systemap place or a person writes positions. The check rejects layout errors (src/systemap/skill/references/layout.md, Component positions and routes).",
        governs=("Model", "Placer", "Router", "Check", "Schematic"),
        reason="The model records fixed card positions, and the placement command keeps the positions that are present. The layout checks examine these positions (src/systemap/model.py, docstring).",
    ),
    Invariant(
        6,
        "The agent writes the model. The check rejects errors. The maintainer examines the model (README, How do you install systemap?).",
        governs=("Agent", "Check", "Maintainer", "Judgement"),
        reason="A structural check without failures does not show that a claim is correct. Thus a person must examine the claims against the source (src/systemap/skill/SKILL.md, Make or update a system map).",
    ),
    Invariant(
        7,
        "Make the map with more than one examination. A second examination is necessary (src/systemap/skill/SKILL.md, The loop).",
        governs=("Skill", "Judgement", "Agent"),
        reason="A first draft can omit flows or give a module an incorrect component. Structural checks cannot find every omission (src/systemap/skill/SKILL.md, The loop).",
    ),
    Invariant(
        8,
        "The page has no external file requests or dependencies (src/systemap/page.py, build).",
        governs=("Page",),
        reason="The page builder makes the page from the model and the stored facts, without external files. A request for an external file sends data about the reader to a different server (src/systemap/page.py, build).",
    ),
    Invariant(
        9,
        "Reject unknown configuration keys. Do not ignore them (src/systemap/config.py, load: 'unknown key').",
        governs=("Config",),
        reason="A key with an incorrect name gives an error. Thus the configuration reader does not ignore it without a notice (src/systemap/config.py, load; docs/reference.md, What can you configure?).",
    ),
    Invariant(
        10,
        "Each ignored module must have a reason (tests/test_coverage.py: test_ignore_without_reason_is_a_config_error).",
        governs=("Config", "Check"),
        reason="Each source module must have one component or a recorded ignore with an explanation. Without a reason, an ignore can remove a part of the system from the map (src/systemap/check.py, docstring).",
    ),
    Invariant(
        11,
        "check does not use the network. judgement uses the network only with --order-by-drift (src/systemap/drift_order.py, docstring). A different Jev command sends requests only with a key (src/systemap/jev_cli.py, docstring).",
        governs=("Check", "Judgement", "SecondOpinion"),
        reason="CI runs check for each pull request. A network request makes the result depend on a service and a key. Network requests occur only with an explicit option or a key (src/systemap/drift_order.py, src/systemap/jev_cli.py, docstrings).",
    ),
    Invariant(
        12,
        "Use ASD-STE100 Issue 9 for all names and all text that a person reads (AGENTS.md, Language requirement).",
        governs=(
            "Agent",
            "Maintainer",
            "CLI",
            "Scaffold",
            "Config",
            "FactsExtractor",
            "ChangeDetector",
            "Placer",
            "Skill",
            "Model",
            "Router",
            "Schematic",
            "Page",
            "Figures",
            "Check",
            "Judgement",
            "SecondOpinion",
            "Describe",
        ),
        reason="The maintainer requires ASD-STE100 Issue 9 for all text that a person reads, also for all new names and map updates (AGENTS.md, Language requirement).",
    ),
)

# Each import rule gives an id, a kind, the components, and the reason.
IMPORT_RULES: tuple[ImportRule, ...] = ()

CONTRACT = Contract(invariants=INVARIANTS, import_rules=IMPORT_RULES)
