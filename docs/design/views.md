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

## The Details panel, pass 1 (2026-11-16)

- The heading "Details" is a small label in the mono font. The name of the card is the title
  of the panel, in the mono font, as on the card.
- The kind of the card (Component, Actor, Flow) is a tag. The assurance level and the
  freshness are two tags. A screen reader gets the full sentence: the words between the tags
  are in the page for it only.
- A row of facts gives the count of module claims and of flows in and out.
- A flow is one row: a line in the color of its kind, the artifact in bold, the other
  component, and the evidence state below. The color is set through the style object, because
  the page policy permits no style attribute.
- A sequence in the panel is a button that opens that sequence in the Sequences view. The
  step numbers are at the right of the row.
- The sticky head of the panel has a line below it.
- The panel opens 240 ms after the selection, after the fade of the selection and after the second click of a usual double-click. A double-click or Enter that goes into a card opens no panel, and it closes a panel that the first click opened (`panelDrop`). With the
  panel in the frame of the click, that frame was long, and the fade of the selection changed
  by more than 0.25 between two recorded frames in 2 of 3 runs of
  `tests/test_canvas_details_browser.py`. With the delay, it passed in 4 of 4 runs.
- The limit of the size test of the panel is 44,000 bytes (before: 41,000).
  On 2026-11-19 this sum failed because the map of this repository had more modules (241, before: 218), with no change to the panel. The test now has two limits: the code of the panel 25,000 bytes or less (24,689 at c28ebd5), and the data 85 bytes or less for each module record (84.5 at c28ebd5).

Not done: the list of rules, the source records, the panel of a flow and the panel of a map
have the new type and spacing, but their structure did not change.

## The header and the toolbars, pass 1 (2026-11-16)

These changes are CSS only, and they apply with a mouse (`pointer:fine`). On a touch screen,
each control keeps its box of 44 px.

- The views are one segmented control: one frame, and the pressed view is a raised button.
- The layers are tabs: no frame, and a line of 2 px under the pressed tab, on the bottom
  line of the header. Before this change, the views and the layers had the same look.
- In the Sequences toolbar, "Whole route / Steps" and "On the map / As a diagram" are two
  segmented controls. A line divides them from the step buttons. This line shows only when
  the header has its full width, because the step buttons go to a second row on a narrow
  screen.
- The labels "Sequence" and "State machine" are small labels in the mono font, as the name
  of the layer in the caption is.
- A change of the pointer state of a button takes 160 ms. With reduced motion, it takes no
  time.

Not done: the icon buttons at the right did not change. The select controls have the look
that the browser gives them.

## The website, pass 1 (2026-11-16)

The pages of the website did not get a new design. The examination found three faults, and
this pass corrects them.

- The pictures of the canvas page were from before the changes on this branch.
  `scripts/screenshots.py` made them again. The Map picture is the System context layer. The
  Sequences picture is the sequence diagram. A States picture is new, and the landing page
  has a States tab for it.
- At a width of 320 px, the landing page and the guide pages were 341 px wide, because the
  links in the header did not fit. After the change, they are 320 px wide (measured with
  Playwright). With four tabs, the tab row of the tour fits at 390 px and at 360 px. At
  320 px, the row scrolls.
- On a screen of 390 px, the sequence diagram had a scale of 0.4, and it showed no names and
  no labels. Now the columns come nearer, the text keeps its size, and each second name box
  is one row lower. A long name can end with "...".
- The refined header applies when the pointer is not coarse (`not (pointer:coarse)`), not
  only when it is fine. Headless Chrome reports no fine pointer, so the pictures did not
  show the refined header.

Not done: the guide page "Read the map" names three views, because the States view is a
prototype. On a phone, the state machine has a scale of approximately 0.6, and it does not
show the source symbol of a state. The layer list in the narrow header shows only a part of
its text. No test examines the narrow sequence diagram.

## The flow labels at rest (2026-11-17)

L2, A1, A2 and A3 of `bench/jev/README.md` have the measured values.

- The fault: in the System context layer, 12 of 17 labels had the path of a different flow
  through their text.
- Three changes did not correct it: a different label position only (L2b), the actors at
  more than one side (A1), and one line for each pair of cards (A2).
- The kept change has three parts. A label goes to a position on its path that no other
  path goes through, when there is one. A label with a path through it does not show at
  rest. In the map of this repository, the strip at the right of the actors is 80 units
  wider.
- The legend tells the reader how to show the other labels, for example "point at a card
  for 5 more labels". On a touch screen it says "select a card".

Not done: the placer has no rule for the wider strip, so a different map does not get it.
A flow line has no pointer state, so a reader cannot point at one line to show its label.
The maintainer said that a map with many flows has lines that cross in each case, and that
other views and nested maps are the answer to that.
