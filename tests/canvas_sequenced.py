"""The fixture of tests/test_nest_join.py with sequences, for the canvas Sequences view.

The top map has one sequence of two steps. The nested map Gateway has two sequences: one
of two steps, and one of one step. A model check refuses a step that names no flow.
Thus the browser test adds such a step to the canvas data of the page.
"""

from __future__ import annotations

from test_nest_join import CONFIG, NESTED, SOURCE, TOP

IMPORTS = (
    "from systemap import Component, Container, Flow, Meaning, Model, Region\n",
    "from systemap import Component, Container, Flow, Journey, Meaning, Model, Region, Step\n",
)

TOP_SEQUENCES = """    journeys=(
        Journey(
            id="ask",
            label="Ask for a token",
            starts="route",
            steps=(
                Step(acts=("Gateway",), measures=(), edge=("Gateway", "Auth"), say="The gateway asks the auth for a token."),
                Step(acts=("Gateway",), measures=("Store",), edge=("Gateway", "Store"), say="The gateway sends the record to the store."),
            ),
        ),
    ),
"""

NESTED_SEQUENCES = """    journeys=(
        Journey(
            id="serve",
            label="Serve a request",
            steps=(
                Step(acts=("Routes",), measures=(), edge=("Routes", "Auth"), say="The routes get a token from the auth."),
                Step(acts=("Views",), measures=(), edge=("Views", "Store"), say="The views send the record to the store."),
            ),
        ),
        Journey(
            id="keep",
            label="Keep a record",
            drafted=True,
            steps=(
                Step(acts=("Views",), measures=(), edge=("Views", "Store"), say="The views keep the record in the store."),
            ),
        ),
    ),
"""


def _with(text: str, journeys: str) -> str:
    head, rest = text.split("MEANING = Meaning(\n", 1)
    return head.replace(*IMPORTS) + "MEANING = Meaning(\n" + journeys + rest


def files(top: bool = True) -> dict[str, str]:
    """Give the files of the fixture. With `top` false, only the nested map has sequences."""
    return {
        "systemap.toml": CONFIG + "[render]\ncanvas = true\n",
        "map/model.py": _with(TOP, TOP_SEQUENCES) if top else TOP,
        "map/gateway.py": _with(NESTED, NESTED_SEQUENCES),
        **SOURCE,
    }
