# The atlas page: the design and the plan

Status: accepted direction, 2026-11-18. The maintainer examined six versions of a design
study and said that the direction is right. This document is the specification for the
implementation. The study is the reference for the look and the behavior.

## The reference

- `docs/design/atlas/study.html` is the study. Open it in a browser. It is one file with
  real data for two systems: the map of this repository, and an anonymous real project
  with agents, stores and tools (`tests/fixture_workspace.py`).
- `docs/design/atlas/study-head.html` has the styles and the markup of the study.
- `docs/design/atlas/study-script.html` has the script of the study.
- `docs/design/atlas/tools/` has the scripts that made the study data. They are text
  copies and they are not product code.

The study is not product code. It uses fonts from a font host, style attributes, and one
large script. The product page must not do these things. When this document and the study
disagree, this document applies.

## Why a new page

The maintainer refused the look of the canvas page two times after polish passes. The
measurements L2, A1, A2 and A3 in `bench/jev/README.md` show the cause for the Map view:
the lines of the flows cross, and a different position of labels or actors does not
remove that. The study changes what the reader sees first.

## The design in one paragraph

At rest the map is calm: the reader sees the system, its regions and its cards first. The
lines are thin and neutral. A path gets its color only when the reader points at a card or
at a line, and then the page says one sentence about it. Each other view answers one
question that the map cannot answer well.

## The views

The page has these views. The maintainer accepted this set. Do not add a Matrix view, a
Trust view or a comparison view.

1. **Map.** The cards, regions and flows of one map, with the layers as tabs.
2. **Sequences.** One sequence, on the map or as a diagram, one step at a time.
3. **States.** One state machine.
4. **Focus.** One card in the middle. The cards that give to it are at the left and the
   cards that it gives to are at the right, two steps deep.
5. **History.** Where the source files of each component changed, and when.

A view shows only when the map has data for it: Sequences needs a sequence, States needs a
state machine, History needs commit data.

## Map view: the rules

- **Headline.** The name of the layer, the question of the layer and the counts are type
  on the ground, not in a plate. The headline is beside the map or above it. The page
  uses the position that gives the larger map.
- **Cards.** A card shows its name. Its short name shows below when the zoom is 0.95 or
  more. An actor has round ends. A card that is not a component and not an actor has a
  small tag with its kind. A card with no flow in the layer keeps a faint outline.
- **No dashed border.** A container that holds only actors is a label, not a surface. A
  region is a faint tint with a number in a ring and a name. Adjacent regions do not
  touch.
- **Lines at rest.** One neutral color. Each line has a dot at its source and an arrowhead
  at its target.
- **Lanes.** The router puts paths that share a gap on one line. The page gives each such
  path its own lane, 4.5 map units apart, so that N flows show as N lines.
- **Crossings.** Each line has a casing in the ground color below it, so that a line goes
  over a different line with a small gap.
- **Labels at rest.** A label shows at rest only when it is on its line, on no card, on no
  name of a region, on no other label, and no other line goes through it. A horizontal
  part of the line comes first. The label has a constant size on the screen.
- **Busy layers.** With many flows, the lines go light and the labels do not show at rest.
  The dot and the arrowhead stay.
- **Pointing at a card.** The flows of the card get the color of their kind and draw one
  time in the direction of the flow. Their labels show and do not cover each other. The
  other cards and lines go back. A card with no flow in the layer does not dim the map.
- **Pointing at a line.** That flow lights. The reading line gives the source, the target,
  the artifact and the relation sentence of the model.
- **The reading line.** One line of text at the bottom of the map for the thing under the
  pointer. It is a live region for a screen reader.
- **Selecting a card.** The details open at the side and the map moves to keep its full
  frame in view. On a phone the details are a sheet at the bottom, and the selected card
  goes to the part of the screen above the sheet. Each flow row in the details lights its
  flow on the map.
- **The details keep the content of the canvas page:** the description, the assurance
  level and the freshness, the flows in and out with the evidence state, the source
  modules, the source records, and the sequences that use the card. The rules of the map
  (invariants and import rules) stay available.
- **Nested maps.** A card that opens a map has a second edge behind it and a small picture
  of its parts. The reader goes in with zoom, with a double-click, or with a button in
  the details. The map above fades as the nested map takes the screen. The headline shows
  the path, and each part of the path goes to that map. Esc goes out one level.
- **Neighbours of a nested map.** They sit around the frame of the nested map, each near
  the parts that it has flows with, not in one column. A neighbour is a card of the map
  above: selecting it goes out to that card.
- **Phone.** The map opens at a zoom of 0.5 or more at its top left part. The Fit control
  still shows the whole map.
- **Motion.** A motion shows a direction or an order and occurs one time. With reduced
  motion, no line draws and no value fades.

## The other views: the rules

- **Sequences.** A list of the sequences is at the left. The map shows only the flows of
  the sequence, with the step numbers on the lines. A bar at the bottom has the two forms,
  the step count, the sentence of the step, and the step controls. The current step has
  its color and draws one time. Earlier steps are dark. Later steps are faint. The left
  and right arrow keys change the step. As a diagram: one column for each card and one row
  for each step, with the same step state. A click on a row goes to that step.
- **States.** A state has round ends, because a state is not a component. The first state
  has a dot and a short line before it. A straight transition has its label above the
  line. Two transitions between the same two states bend apart, with their labels at the
  outer sides. The reading line gives the cause of a transition, and the meaning of a
  state.
- **Focus.** The headline gives the counts and the reach, for example "a change here can
  reach 16 of 27 cards". Reach is the count of cards on a path of flows from the card. A
  column shows nine cards at most and then the count of the others. Selecting a card
  focuses on it. On a narrow screen the view shows one step at each side.
- **History.** One row for each component with a change, one column for each of 12 equal
  parts of the time. The opacity of a cell is the square root of the changed lines of the
  cell divided by the largest cell. A dot marks a cell with a new source module. Bars at
  the top give the total of each column. The reading line gives the dates, the count of
  file changes and lines, and the new modules. The headline gives the count of commits and
  the dates. If the clone is shallow, the page says that earlier commits are not there.

## Requirements of the product page

These are not in the study. They are necessary.

- **No external file.** The page uses no font host and no script host. It uses the
  embedded Inter font of the product (`page_font`) and a system mono font.
- **Content security policy.** The page must pass the policy that the canvas page has
  (`page_csp`). No `style` attribute and no inline handler. Set a custom property with the
  style object in script.
- **File length.** A Python file has 800 lines or less. Divide the script into parts, as
  the canvas page does (`page_canvas_*.py`).
- **Large maps.** Build the elements of a nested map only when the camera is near it.
  Remove them when it is far. The gate below gives the limits.
- **Access.** Each card, line and control works with the keyboard and has a name for a
  screen reader. The page keeps a text list of the map tree for a screen reader. The
  contrast of each text and mark has a row in a contrast test. The page passes axe-core.
- **Parity.** Find, the URL hash of a card or a map, the theme control (device, light,
  dark), the Reduce motion control, the keyboard help, the live page (`systemap live`),
  the boundary finding marks, and the changed cards with `--base` all work.
- **Text.** All text for a reader obeys the language policy of the repository.
- **Measurement.** Follow `AGENTS.md`: write the acceptance value in the docstring before
  a run, and record each result in `bench/jev/README.md`, including a failure.

## The architecture

- A new page, the atlas page, is built beside the canvas page. The canvas page and its
  tests stay until the atlas page is the default and the maintainer removes them.
- `[render] page` selects the page: `"atlas"`, `"canvas"` or `"linked"`. Until stage 9 the
  default stays `"canvas"`. `[render] canvas` keeps its meaning.
- The page data is the canvas data object (`canvas_data.build`) with additions: the
  relation sentence of each flow, and the history. Do not make a second copy of the map
  data in the page.
- Modules: `atlas_page.py` builds the page. `atlas_*.py` modules hold the style, the
  markup and the parts of the script. `history_data.py` reads the commits.
- The page draws with SVG. The gate examines this decision.

## The gate

Before stage 1, measure the SVG approach on the generated tree with 50 maps
(`bench/jev/canvas_frames.py`, `m11_tree`), with nested maps built only near the camera.
Write the acceptance values before the run:

1. The time to the first complete frame is 1,500 ms or less at 4 times CPU slowdown.
2. The 95th percentile of the frame time is 35 ms or less at 4 times CPU slowdown, for a
   pan of 2 s on the top map and for a zoom from the top map into a nested map.
3. The count of SVG elements in the document is 6,000 or less at each moment of that zoom.

A second rule applies to the zoom of value 2. It was added on 2026-11-18, before the first
run. The measurement host has no GPU and is slow: the canvas page itself has a p95 of more
than 35 ms for its dive on this host (the cases "400 cards-dive" and "M11 shape-dive" of
`tests/test_canvas_frames.py` fail at commit c96e021). Thus the run also measures the dive
of the canvas page (`bench/jev/canvas_frames.py`, scenario `dive`) on the same tree, in the
same run. If the p95 of the zoom of the atlas page is more than 35 ms, the value passes only
if it is not more than 1.1 times the p95 of the dive of the canvas page in the same run. This
rule does not apply to the pan. The script is `bench/jev/atlas_frames.py`.

If a value fails, stop. Do not start stage 1. Report the numbers.

## The stages

Each stage ends with the required checks of `AGENTS.md`, one commit and one push to the
branch `views-prototype`. No stage makes a pull request.

1. **Scaffold and the Map view at rest.** `[render] page`, `atlas_page.py`, the data
   additions, the headline, the cards, the regions, the lanes, the casing, the labels at
   rest, the busy layer rule, the layers, the camera, the dot grid, the nested maps built
   near the camera, the redirect pages, the policy and the fonts.
2. **Pointing and selecting.** The lit paths, the reading line, the details with the
   content of the canvas page, the keyboard, reduced motion, the phone sheet.
3. **Sequences**, on the map and as a diagram.
4. **States.**
5. **Focus.**
6. **History.** `history_data.py`, the setting, the cache, the shallow clone notice, the
   view.
7. **Neighbours around the frame.** Divide `place.py` first, because it is over the length
   limit. Then the placer rule for a nested map. Measure the result on the nested
   fixtures before the rule is kept.
8. **Parity.** Find, the URL hash, the theme, the keyboard help, the live page, the
   boundary marks, the changed cards, the text list of the tree, the contrast test, axe,
   and a frame time test in the suite.
9. **The default.** The atlas page becomes the default. The pictures
   (`scripts/screenshots.py`), the website, the guide page "Read the map", the reference,
   the changelog, the skill references in the three skill directories, and the map of this
   repository.
10. **The nested map of Page** in the map of this repository
    (`docs/design/atlas/tools/page_model.py.txt` is a draft), and the final checks.

## What is not decided

- The time of the removal of the canvas page and of the linked page.
- A history of the flows, not only of the files.
