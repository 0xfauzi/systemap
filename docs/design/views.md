# Views of one model: the sequence diagram and the state machine

This design is a prototype on the branch `views-prototype`. It is not a release.

## The decision

The map with its layers stays the primary view. The page gets other views that show items
of the same model in a different form. Each view answers one question. An item has one
identity: a selection in one view leads to the same item in the other views.

| View | Question | Items |
|---|---|---|
| Map, with layers | Which components and flows answer the question of the layer? | components, flows |
| Sequences, on the map | Which parts does this operation use? | the steps of a sequence, as a route |
| Sequences, as a diagram | Which component sends what to which component, in which order? | the same steps |
| States | Which states can this item have, and what causes each change? | states, transitions |
| Changes | What did this change touch? | components, flows |

A sequence needs no new data for its diagram. A step names a flow, and a flow names its two
components. The diagram is a different drawing of the same records.

## State machines

A state machine belongs to one component. An agent or a person writes it in the model
(`Meaning.machines`, `states.py`), as a flow or a sequence.

A probe of this repository examined if source facts can give the states. They cannot, with
syntax patterns: the source has no `Enum` class and no `Literal` type with three values or
more, and 41 tuples of lowercase constants, of which almost none is a set of states. The
states of a source review are separate constants (`MISSING`, `STALE`, `CURRENT` in
`card_review.py`). The probe was one script on one repository, not a recorded experiment.

Thus the model gives the states, and the check compares them with the facts:

- A state names the source symbol that defines it, for example
  `systemap.card_review.STALE`. `systemap check` gives an error if that symbol is not a
  constant of that module in the facts (`states.symbol_problems`).
- A transition names its two states, a label, and its cause in a sentence. It can name the
  flow of the map that causes it and a sequence that shows it. The model check gives an
  error for an unknown state, flow or sequence (`states.problems`).
- The page gives the structure findings of a machine: a state with no transition in,
  except a first state, and a state with no transition out (`states.findings`).

The map of this repository has two machines in `map/states.py`: the source review of a
component (missing, current, stale) and the review of a flow (missing, current, stale,
earlier). The second machine has one finding: the state `earlier` has no transition in.
That is correct for the source: only a review from an earlier version has this state.

## The page

`page_canvas_board.py` draws a board on the canvas, over the map and below the header,
with the fonts, the colors and the plates of the map.

- The Sequences toolbar has "On the map" and "As a diagram". The step buttons, the caption
  and the route in the Details panel are the same in the two forms.
- The States view is a view button in the header. It shows only when a map of the tree has
  a state machine. A bar under the header selects the machine.
- A click selects a state or a transition. The caption gives the cause of the transition.
  The Details panel gives the states, the transitions and the findings as lists with
  buttons. For a transition, it gives "Show the flow on the map" and "Show the sequence".
- The layout of the states comes from `states.layout`: the column is the smallest count of
  transitions from a first state, and two states that change into each other are one above
  the other.

## What is not done

- The lines of `states.findings` are not judgement findings. They have no finding kind, no
  explanation in `explain.py`, and no recorded answers.
- A state machine has no source review and no assurance level.
- The Map view does not show the state machines of a selected component, and the Details
  panel of a flow does not give the transitions that the flow causes. The link goes from a
  transition to its flow, not back.
- The canvas drawing of a board has no elements. The Details panel is its form for a
  keyboard and a screen reader. Tab on the canvas still goes through the cards of the map.
- A board does not zoom or pan. A machine with many states is not measured.
- The frame time with a board is not measured.
- The skill for coding agents and the schema reference do not give state machines. Thus an
  agent does not write them yet.
- No experiment shows that a coding agent writes correct state machines from source.
