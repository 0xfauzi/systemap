# The views of the page and state machines

Read this file before you write a state machine, and before you tell a person how to read the page.

## The views of the page

`systemap refresh` and `systemap render` write the atlas page `docs/map/index.html`.
`[render] page = "canvas"` writes the earlier canvas page. `[render] canvas = false` writes the linked pages.

The atlas page has these views. A view shows only when the map has data for it.

| View | What it shows | The data that it needs |
|---|---|---|
| Map | The cards, the regions, and the flows of one map, with the layers as tabs. | The model. |
| Sequences | One sequence, on the map or as a diagram, one step at a time. | A `Journey` in `MEANING.journeys` of a map of the tree. |
| States | One state machine. | A `StateMachine` in `MEANING.machines` of a map of the tree. |
| Focus | One card in the middle, the cards that give to it at the left, and the cards that it gives to at the right, two steps deep. | A flow between two cards of a map. In a nested map, a flow between two parts. |
| History | One row for each component with a change, and one column for each of 12 equal parts of the time. | Commits that Git can read. `[render] history = false` removes the view. |

The page shows the text of the model. Thus each text obeys `references/language.md`:

- The reading line gives the source, the target, the artifact, and the relation sentence of a flow. Write a relation sentence in `MEANING.relations` for each flow.
- The headline gives the question of the layer. The Focus view gives the reach of a card: the count of the cards on a path of flows from the card.
- The History view uses the source modules of each component (`implemented_by`). It does not use the flows.
- With `render --base REF`, the change marks are on the Map view. The atlas page has no Changes view.

Do not add data to the model only to make a view show. Write a sequence, a state machine, or a flow only when the source supports it.

## State machines

A state machine gives the states of one item and the cause of each transition.
Source facts do not give the states of an item. Thus you write each state machine in the model, as you write a flow or a sequence.
Write a state machine only when the source defines each state as a constant.

Put the state machines in `MEANING.machines`. A large map can keep them in a separate file, for example `map/states.py`, and import them into `map/model.py`:

```python
from systemap import State, StateMachine, Transition

MACHINES = (
    StateMachine(
        id="source-review",
        label="Source review of a component",
        of="Model",
        start=("missing",),
        states=(
            State(
                "missing",
                "systemap.card_review.MISSING",
                "The component has no source_review value.",
            ),
            State(
                "current",
                "systemap.card_review.CURRENT",
                "The source_review value is the current digest.",
            ),
            State(
                "stale",
                "systemap.card_review.STALE",
                "The source_review value is not the current digest.",
            ),
        ),
        transitions=(
            Transition(
                "missing",
                "current",
                "review",
                cause="systemap review COMPONENT writes the current digest in the model file.",
                flow="Agent->CLI",
                journey="record-review",
                source="systemap.card_review.state",
            ),
        ),
    ),
)
```

- `StateMachine(id, label, of, states, transitions=(), start=())`. `of` is the component that owns the item. `start` gives the first states.
- `State(id, symbol="", say="")`. `symbol` is the source constant that defines the state, as `module.NAME`. `say` is one sentence about the meaning of the state.
- `Transition(src, dst, label, cause="", flow="", journey="", source="")`. `label` is a short label on the line. `cause` is one sentence about the cause. `flow` is the identifier of a flow that shows the same change (`Flow.key`: the `id`, or `SRC->DST`). `journey` is the identifier of a sequence that shows it. `source` is the source symbol that decides the transition.

`systemap check` gives an error for:

- a machine whose `of` is not a component of the map,
- a machine with no states, or a machine or a state that is in the model two times,
- a first state or a transition with a state that the machine does not have,
- a `flow` or a `journey` that the map does not have,
- a state `symbol` that is not a constant in the facts.

The States view also gives a state with no transition in, except a first state, and a state with no transition out.
These lines are not judgement findings. They have no finding kind and no recorded answers. Examine each line against the source.

The States view puts each state in a column by its count of transitions from a first state.
Two states that change into each other are one above the other.
The reading line gives the `say` text of a state and the `cause` text of a transition.
