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

## The panel and the finish (2026-11-16)

- With a mouse or the keyboard, a selected card opens the Details panel. Before, only the D
  key and the Details button opened it. On a screen wider than 900 px, the open panel takes
  396 px from the canvas (`dock` in `page_canvas_details.py`). A camera at the fit fits the
  map again in the smaller canvas. An overlay was measured first: it covered the portals
  and the cards at the right, and 5 browser tests failed for that cause.
- On a touch screen, a tap still shows the plate of facts and does not open the panel. A
  second tap must go into the card, and a panel over half of a phone screen prevents that.
- `page_canvas_finish.py` adds parts of DESIGN.md: the dot grid, the legend and the dot of
  a step. The header has the mark. Card names and the names of regions and containers use
  the mono font, and the number of a region is in a ring.
- The first form of the dot grid made a pattern as large as one cell at the current zoom.
  In a deep zoom that cell is very large, and the M11 dive had a p95 frame interval of
  2,483 ms. The cell now stays from 16 px to 32 px on the screen. With two pattern fills in
  each moving frame, the dive of the map of 400 cards failed its limit of 35 ms in 2 of 4
  runs (p95 50 ms), and it passed in 4 of 4 runs at the commit before. With one fill while
  the camera moves, it passed in 4 of 4 runs. These are runs of
  `tests/test_canvas_frames.py`, not the A/B measurement with the quiet gate.
- The legend, the grid and the dot of a step have no test of their own. They were examined
  in pictures at two times the resolution, in the two themes.

## The map canvas, pass 1 (2026-11-16)

An examination of close pictures at two times the resolution found five defects. Each has a
change in `page_canvas_finish.py`, `page_canvas_view.py` or `page_canvas_draw.py`.

| Defect | Change |
|---|---|
| A selected card had a ring, and all flows of the map kept full contrast. | The flows of the selected card stay. The other flows of its map have the alpha 0.16 and no label, and the cards that no such flow connects to it are quiet (`VIEWS.map`, `selNear`). DESIGN.md gives this rule. |
| A flow label was on a plate that cut the lines under it. | The label has a halo: the text in the color of the map with a wide line, under the text (`labelHalo`). The box of the plate still keeps portals and boundary flows off the label. |
| A label grew to 13 px in a zoom. | The font size stops at 12 px. |
| The corners of a flow line were sharp. | Each corner is round: 5 units of the map, 8 px or less (`cutLine`). |
| The uppercase names had no letter spacing, and a card did not answer the pointer. | The names of regions and containers and the name in the caption have a letter spacing of 0.07 em, where the browser has `letterSpacing`. The card under the pointer of a mouse has a border in `--ink-2` of 1.5 px (`hoverAt`). |

Not done in this pass: the lines of a layer do not draw from source to target at a layer
change, a flow line does not answer the pointer, and a click on a flow line selects nothing.
The frame time after this pass has only the runs of `tests/test_canvas_frames.py`.
