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
  uses the position that gives the larger map. A card is an actor or a component: in a
  count, "card" is each card of the map, "actor" is a card of an actor, and "component" is
  each other card. In a nested map the words are "neighbour" and "part". A layer with no
  flow gives the cards, the regions, and the two parts of the cards, for example "37 cards
  in 6 regions: 4 actors and 33 components". The Focus view counts the same cards. A total
  is always the total of the map:
  when the layer uses fewer components than the map has, the count is "N of T
  components", and else "T components" (`countWords` in `atlas_view`). The same rule
  applies to the actors, and in a nested map to the parts and the neighbours. T parts in
  the headline of a nested map is the count of the button "See its T parts" and of the
  reading line of its card.
- **Cards.** A card shows its name. Its short name shows below when the zoom is 0.95 or
  more. An actor has round ends. A card that is not a component and not an actor has a
  small tag with its kind. A card with no flow in the layer keeps a faint outline.
- **Card names.** A card name is on one line, in Inter at weight 600 with no kerning. The
  check and the page use one measure of a name (`card_names`): the same font widths, the
  same size and the same room. Thus `systemap check` gives a warning for each name that the
  page cuts. In this release, the warning does not change the exit code. A later release
  will give an error. When the page makes a name larger than its base size, for example on
  a small card, it makes the name smaller again until it fits, but not smaller than the
  base size.
  Thus a name that the check accepts always shows in full.
- **No dashed border.** A container that holds only actors is a label, not a surface. A
  region is a faint tint with a number in a ring and a name. Adjacent regions do not
  touch.
- **Lines at rest.** One neutral color. Each line has a dot at its source and an arrowhead
  at its target.
- **Lanes.** The router puts paths that share a gap on one line. The page gives each such
  path its own lane, 4.5 map units apart, so that N flows show as N lines.
- **Edges.** No line is drawn on the edge of a surface. A part of a line that is nearer than
  7 map units to such an edge goes 7 units farther from it, on its side of the edge. The
  routes do not change (E1 in bench/jev/README.md, 2026-11-20).
- **Crossings.** Each line has a casing in the ground color below it, so that a line goes
  over a different line with a small gap.
- **Labels at rest.** A label shows at rest only when it is on its line, in the box of the
  map, on no card, on no name of a region, on no other label, and no other line goes
  through it. A horizontal part of the line comes first. The label has a constant size on
  the screen. A label at rest shows the full artifact, or it does not show: it is not cut
  with "...". In a nested map, the lines of one neighbour with one artifact are the parts of
  one flow of the map above, and they show one label at most (stage 2 of the open faults,
  2026-11-20). Outside the Sequences view, a vertical part of a line takes a label only
  when the label is 8 label heights wide or less (`UPRIGHT_MAX` in `atlas_lines`). A long
  label across a vertical line does not show which line it names. Thus on #Page the label
  of the lines of Judgement does not show at rest. It shows when the reader points at
  Judgement or at one of its lines (L3 in tests/test_atlas_page_layout_browser.py).
- **Busy layers.** With many flows, the lines go light and the labels do not show at rest.
  The dot and the arrowhead stay.
- **Pointing at a card.** The flows of the card get the color of their kind and draw one
  time in the direction of the flow. Their labels show and do not cover each other. The
  other cards and lines go back. A card with no flow in the layer does not dim the map.
- **Pointing at a line.** That flow lights. The reading line gives the source, the target,
  the artifact and the relation sentence of the model.
- **A fast pointer.** A pointer that goes across the map does not point at the cards and
  lines on its way. A move faster than 0.3 px for each ms, less than 60 ms after the move
  before it, changes no light. The light changes 60 ms after the last such move, to the
  item that is then below the pointer. A slow pointer, and the first move of a pointer that
  was at rest, change the light at once (`pointSoon` in `atlas_input`). Without this rule,
  the map changed its light many times in a second (tests/test_atlas_calm_browser.py).
- **The scrollbars of a board.** A board (the diagram of a sequence, States, Focus, History)
  scrolls in a direction only when its content with its margins does not fit in that
  direction (`boardSize` in `atlas_view`). In a direction where the content fits, the
  content is not larger than the box, and the board shows no scrollbar there.
- **The reading line.** One line of text at the bottom of the map for the thing under the
  pointer. It is a live region for a screen reader.
- **Selecting a card.** The details open at the side. The camera keeps its scale and its
  place: a selection of a card that is fully on the screen and not under the details does
  not move the camera, always. When the details would cover the card, the camera moves the
  smallest distance that keeps the card out from under the details. Only for that move, the
  cards at the other end of the flows of the card that were on the screen stay out from
  under the details when that is possible. A close of the details does not move the camera. A result of Find and a
  link with the hash of a card fit the map of the card with the space of the details,
  because that card can be in a different part of the map or in a different map. On a phone the details are a sheet at the bottom, and the selected card
  goes to the part of the screen above the sheet. While the sheet is open, the headline does
  not show: that part of the screen is too short for the map, and the headline must not cover
  a card. Each flow row in the details lights its flow on the map.
- **The details keep the content of the canvas page:** the description, the assurance
  level and the freshness, the flows in and out with the evidence state, the source
  modules, the source records, and the sequences that use the card. The rules of the map
  (invariants and import rules) stay available.
- **Nested maps.** A card that opens a map has a second edge behind it and a small picture
  of its parts. The small picture is at the right, below the line of the name. Thus the
  name has the full width of the card, as on each other card. The reader goes in with zoom,
  with a double-click, or with a button in the details. The map above fades as the nested map takes the screen. The headline shows
  the path, and each part of the path goes to that map. Esc goes out one level.
- **Inside a nested map.** The page shows five signs, so that a reader cannot think that a
  nested map is the top map. They apply to each nested map at each depth, in the Map view
  (`atlas_inside`). The top map has none of them. A reader must always see that the page
  shows a nested map: the bar (sign 1) and the ground `--inside` (sign 4) also show in each
  other view that shows a nested map. That is the Sequences view for a sequence of a nested
  map, the States view for a machine of a nested map, and the Focus view for a card of a
  nested map. The History view shows the top map, thus it has no sign.
  1. *The bar.* A bar at the top of the map area gives "Inside" and the name of the map,
     and the button "Back to" and the name of the map above, with the key Esc. At depth 2
     or more, the bar also gives the path, for example "systemap / P0 / Q0", and each name
     in the path goes to that map. The bar is fully on the screen at the fit, its text is
     14 px or more, and the contrast of its text is 4.5 or more. The fit keeps the height of
     the bar free, and the headline is below the bar. Esc or Back during a move out goes out
     one more level after the movement: each level has its own movement, and the last one
     selects its card. In a view other than the Map view, Back and Esc open the Map view of
     the map above with the card of the nested map selected.
     A change of the URL hash in a view other than the Map view opens the Map view of the
     map that the hash names, with the bar when that map is a nested map.
  2. *The zoom movement.* A move into a nested map goes from the box of its card on the map
     above to the fit of the nested map. A move out goes back to that card, and the card is
     then selected. Each movement takes 360 ms (250 ms to 450 ms). The last frame of a move
     out shows the nested map at the box of its card. With reduced motion, the camera goes
     to the end at once, in one frame.
  3. *The locator.* A small picture of the map above, with the card of the nested map
     marked, is in a corner of the screen where it covers no card and no label at rest of
     the nested map at the fit. When no corner is free, the locator does not show. A click
     on it goes out one level.
  4. *The inside look.* The frame of the nested map has its name as a title, 18 px or more
     on the screen at the fit of a wide screen. The ground around the frame has the color
     `--inside`, which is different from the ground of the top map in the light scheme and
     in the dark scheme.
  5. *The neighbours.* A neighbour card has the line "on" and the name of the map above
     below its name, so that a reader expects a selection to go out. The line is 10 px or
     more at the fit of a wide screen, its contrast is 4.5 or more, and it stays in the
     card. At each zoom, it is 0.75 times the size of the name or more (`upTag` in
     `atlas_draw`).
- **Neighbours of a nested map.** They sit around the frame of the nested map, each near
  the parts that it has flows with, not in one column. A neighbour is a card of the map
  above: selecting it goes out to that card.
  Met (2026-11-19, N5 in bench/jev/README.md). N1, N2 and N4 failed, and N3 changed two
  acceptance values after the results were known. N5 added one step to the rule: when the
  sides layout has a label collision or a refused route, the placer moves actors to a
  different side while a move removes one (`place_order._clear_sides`). N5 passed the six
  acceptance values of N4. On Page it is not a blind test, because the step was written
  after N4 failed on Page. The commands use the rule for the atlas page
  (`place.SIDES_IN_COMMANDS = True`). The neighbours of Page are at the four sides of its
  frame (tests/test_atlas_browser.py, acceptance 26). Their positions are not those of the
  study, and Page shows at 81 percent at 1440 x 900, against 103 percent in the study. From
  stage 11 the bar of a nested map takes 49 px at the top, and Page shows at 76 percent.
  Stage 2 of the open faults (2026-11-20, N6 and N7 in bench/jev/README.md) tried more
  region columns and a rank by the fit of the atlas page at 1440 x 900. Page then had its
  four regions in one row, and at 390 x 844 two regions and two neighbours were outside the
  phone view. The repair of that stage (N8, N9 and P6 to P8 in bench/jev/README.md)
  changed the rule again. The frame keeps two region columns, as each other map, because
  the phone opens a map at its top left part. The form of the commands is ATLAS: no room
  for the label of the actor container, because the atlas page draws that label only in
  the top map. The placer keeps the layout with the fewest label collisions and refused
  routes, then the neighbours at three sides or more (`place_sides.few_sides`), then the
  smallest area of the map (`place_sides.size_rank`). The rule uses no size of a screen.
  When the sides layout has more label collisions or more refused routes than the column
  layout, the placer keeps the column layout (`place_sides.kept_or_column`, the column
  step). Thus the column step always meets acceptance 1 of N4, and the scripts now measure
  that value on the layout before the column step. No form of the rule has a blind pass of
  the six values of N4 (N6 to N9 and the corrections after the second review in
  bench/jev/README.md), and the commands keep the rule against the gate of N4, because the
  column layout fails acceptance 20 and 26. Page is now 928 x 860. At 390 x 844
  its four regions show, and seven neighbours at the right show 7 percent of their width
  (five before stage 2). At 1440 x 900 it shows at 87 percent, against 90 percent in P3.
  Judgement is at the bottom after a side move, not at its nearest side (P4): the move
  removes two label collisions of its long label (M1 in bench/jev/README.md). P9 measured
  each layout of the rule with 2, 3 and 4 region columns and each region order (118
  layouts): no layout meets P1 to P4, acceptance 26 and the phone test of stage 11
  together. P3 and the phone test hold together only with two region columns and two
  sides. A decision of the maintainer is necessary. N7r, N8r and N9r ran N7, N8 and N9
  again with value 1 read before the column step: each fails one value or more. The
  label of the lines of Judgement no longer shows at rest across a vertical line (L3), but
  the layout of Page did not change.
  Decision of the maintainer (2026-11-20): the rule stays on for its look, although no form
  of it has a blind pass (N6, N7r, N8r, N9r). It can give a worse layout on a nested map that
  it was not made on. See "The decision of the maintainer on the side rule" in
  bench/jev/README.md.
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
  outer sides. Each transition starts and ends on the outline of its states, and it goes
  through no other state. A state is as wide as its full ID. The reading line gives the
  cause of a transition, and the meaning of a state.
- **Focus.** The headline gives the counts, the reach and the importers, for example
  "through flows, a change here can reach 15 of 36 other cards · modules of 18 other cards
  import modules of this card". Reach is the count of the other cards on a path of flows
  from the card. The importers are the other cards with a module that imports a module of
  the card directly, from the module imports of the facts that the Uses and Used by lists
  use. Before, the reach did not count the imports, and no count of Focus told them: on the
  Django map, modules of 18 other cards import modules of Orm. The importers are one step only, because a path of imports with
  more steps gets to almost each card of a framework (34 of 36 for Orm). The two counts
  have different meanings, thus the page does not add them. A
  column shows nine cards at most and then the count of the others. Selecting a card
  focuses on it. The view opens on the selected card of the Map view when that card has a
  flow. On a narrow screen the view shows one step at each side.
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
  screen reader. The page keeps a text list of the map tree for a screen reader. The links of
  the list are not in the order of Tab: the canvas gives Tab to the cards and the lines. The
  contrast of each text and mark has a row in a contrast test. The page passes axe-core.
- **Parity.** Find, the URL hash of a card or a map, the theme control (device, light,
  dark), the Reduce motion control, the keyboard help, the live page (`systemap live`),
  the boundary finding marks, and the changed cards with `--base` all work.
  Met in stage 8 (2026-11-19). The atlas page has no Changes view, because this document
  adds no comparison view: the change marks are on the Map view (`atlas_marks`). On a
  phone the tools are in one Tools menu (`atlas_tools`). The contrast test
  (tests/test_atlas_contrast.py) gives eight quiet marks below the floor of 3.0, for example
  the wire of a line at rest. It also gives each text and mark that the page draws at a
  reduced alpha, with that alpha in its ratio: 39 of them are below their floor, for example
  the label of a later step (1.92 in the light scheme). These are decisions for the
  maintainer, because this document makes later steps faint and makes the other cards and
  lines go back. In a busy layer, the alpha of the dot and the arrowhead is 0.8 or more, so
  that they keep a contrast of 3.0 or more.
- **Text.** All text for a reader obeys the language policy of the repository.
- **Measurement.** Follow `AGENTS.md`: write the acceptance value in the docstring before
  a run, and record each result in `bench/jev/README.md`, including a failure.

## The architecture

The gate failed for SVG (G1 in `bench/jev/README.md`, 2026-11-18): the zoom into a nested
map was 1.67 to 4.49 times slower than the canvas page in 18 runs. The first frame, the
pan and the element count passed. Thus the architecture is this:

- **The map draws on the canvas engine.** The Map view, the nested maps and a sequence on
  the map use the renderer of the canvas page: its camera, its level of detail, its
  stored images and its frame budget. The look and the behavior change to the rules of
  this document: lanes, casing, the cards, the regions, the labels at rest, the lit paths
  with one draw in the direction of the flow.
- **The parts that do not zoom are HTML and SVG, as in the study.** The header, the
  headline, the reading line, the details, the lists, the step bar, the sequence diagram,
  States, Focus and History. These parts have no deep zoom, so the gate result does not
  apply to them. Take them from the study, changed to the requirements of the product
  page.
- **A fork, not a flag.** Copy the canvas page modules (`page_canvas*.py`, `canvas_*.py`
  where the page part changes) to `atlas_*.py` modules and change the copies. The canvas
  page and its tests stay as they are until the atlas page is the default and the
  maintainer removes the canvas page. Do not put the two looks in one module with a
  switch.
- `[render] page` selects the page: `"atlas"`, `"canvas"` or `"linked"`. From stage 9 the
  default is `"atlas"` (2026-11-19). `[render] canvas` keeps its meaning: `canvas = false`
  gives the linked pages, and `canvas = true` gives the default page.
- The page data is the canvas data object (`canvas_data.build`) with additions: the
  relation sentence of each flow, and the history. Do not make a second copy of the map
  data in the page.
- `history_data.py` reads the commits.

## The gate (done, FAIL for SVG)

The gate measured an SVG page on the generated tree with 50 maps. The record is G1 in
`bench/jev/README.md`. The script is `bench/jev/atlas_frames.py`. The architecture above
is the result. The gate does not run again.

## The performance budget

The maintainer said on 2026-11-18: a small loss of speed against the canvas page is
acceptable, and a large loss is not. These limits make that rule exact. They apply to the
atlas page against the canvas page, measured in the same run on the same machine, at 4
times CPU slowdown. An absolute limit of the gate also applies.

| Measure | Limit against the canvas page |
|---|---|
| Time to the first complete frame | 1.5 times or less |
| 95th percentile of the frame time, pan of 2 s | 1.25 times or less, or 35 ms or less |
| 95th percentile of the frame time, zoom into a nested map | 1.25 times or less, or 35 ms or less |
| Time from a pointer move onto a card to the lit paths on the screen | 100 ms or less (the canvas page has no equal measure) |
| Size of the page file | 1.5 times or less |

Measure on three inputs: the map of this repository, `tests/fixture_workspace.py`, and the
generated tree with 50 maps.

- Stage 1 measures the budget for the first time and records it.
- Stage 8 adds a test in the suite that fails when a limit of the budget fails.
- Stage 10 measures the budget again on the finished page and records it. The work is
  not complete while a limit fails.
- If a stage makes a measure fail, that stage must correct it or stop and report. Do not
  change a limit.

## The stages

Each stage ends with the required checks of `AGENTS.md`, one commit and one push to the
branch `views-prototype`. No stage makes a pull request.

1. **Scaffold and the Map view at rest.** `[render] page`, `atlas_page.py`, the data
   additions, the headline, the cards, the regions, the lanes, the casing, the labels at
   rest, the busy layer rule, the layers, the camera, the dot grid, the nested maps built
   near the camera, the redirect pages, the policy and the fonts. The map is on the
   canvas engine (see the architecture).
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
   Done (2026-11-19). The URL hash `#changes` of a pull request comment opens the top map
   of the atlas page, because the atlas page has no Changes view (`atlas_tree`). The
   landing page of the website shows the five views of the atlas page, and its Changes tab
   is removed. The skill has the new reference `references/views.md` for the views and the
   state machines.
   After the review of stage 9 (2026-11-19): with a revision comparison, the headline ends
   with the disclosure "Not in this comparison" (`atlas_marks.limits`). It gives the limits
   of the comparison of the linked page (`page_changes.comparison_limits`), for example the
   paths of a Git filter and an unknown reach. This is not a comparison view: it shows only
   in the Map view, under the counts. The text of the product (the pull request link, the
   first lines of `systemap live`, the help of `--base`) names the changes on the map page,
   and it names the Changes view only for the canvas page and the linked page.
   After the second review of stage 9 (2026-11-19): the headline is the first part of `main`,
   before the canvas (`atlas_header.headline`), so that the order of the keyboard focus agrees
   with the order on the screen. Tests make the disclosure with `render --base` and with the
   render of `systemap live` (tests/test_atlas_limits.py), and drive it in a browser
   (tests/test_atlas_limits_browser.py). axe-core runs on the committed self-map
   (tests/test_atlas_parity_browser.py, acceptance 21).
   After the third review of stage 9 (2026-11-19): `scripts/screenshots.py` ran again, and
   `docs/screenshots/tour.gif` is new. Frame 12 ("compare") is the only frame that shows the
   disclosure "Not in this comparison", under the counts of the headline. Frame 6 ("card")
   also changed: the evidence text of the flow "loaded map" is current. The other files of
   the run are identical to the committed files, except the History images of the landing
   page, which show the Git log and change at each commit. They stay as they are. No test
   finds a committed image that is older than the page. A test holds the script to the claim
   that only the frame "compare" uses the page with the disclosure.
10. **The nested map of Page** in the map of this repository
    (`docs/design/atlas/tools/page_model.py.txt` is a draft), and the final checks.
    Not complete (2026-11-19). One measure fails: acceptance 1 of
    tests/test_canvas_reading_browser.py on the canvas page (see below). A decision of the
    maintainer is necessary. The rule "Neighbours of a nested map" is met from N5.
    `map/page.py` is the nested map of Page. It has 11 parts: PageWriter,
    PageData and PageAssets (shared parts), AtlasPage, AtlasDrawing and AtlasViews (the
    atlas page), CanvasPage, CanvasDrawing and CanvasViews (the canvas page), and LinkedPage
    and LinkedViews (the linked page). Each part has 10 modules or fewer. The 10 neighbours
    are the components of the top map that have a flow with Page. After the third review of
    stage 10, the placer puts them at the four sides of the frame (N5 in
    bench/jev/README.md). Each flow between
    two parts has its source records and its review digest. A flow with a neighbour has the
    artifact of the flow of the top map. `systemap check` and `systemap judgement --strict`
    give no open line.
    The walk through the page in a browser found two faults, and both are repaired. A label
    at rest could go out of the box of its map, and then the phone view cut it
    (`atlas_lines`: the four sides of the map are walls for a label at rest). Two tests
    assumed a map tree with no nested map: the name of a container of actors and the
    regions of a small picture (tests/test_atlas_browser.py, acceptance 14).
    After the review of stage 10 (2026-11-19): a test holds a label at rest in the box of
    its map, at the fit and on a phone, on the top map and on Page
    (tests/test_atlas_browser.py, acceptance 22). Without the four sides as walls, it fails.
    A test drives the canvas page of the real tree with the nested map Page
    (tests/test_canvas_reading_browser.py, acceptance 12). On that page the smallest label
    at the fit is 8.5 px in each layer (System context, Data flow, Control flow and Map
    review), not the 9 px of the page with no nested map, because the ports make the fit
    smaller. The canvas page stays as it is, thus this is a decision for the maintainer.
    After the second review of stage 10 (2026-11-19): the 9 px check of acceptance 1 of
    that test is an expected failure (`xfail`, strict) on the real tree until the
    maintainer makes a decision, and acceptance 1 to 9 and 11 drive the real tree with the
    nested map Page again. Only acceptance 10, which is for a tree with no port, uses the
    top map with no nested map. A test holds the rules of the nested map Page on the atlas
    page (tests/test_atlas_browser.py, acceptance 23): its 11 parts, its neighbours as the
    cards of the top map that have a flow with Page, a click on a neighbour that goes out
    to its card, and the counts of the headline in each layer as the model gives them.
    The budget passes for each value on the finished page (B19 in `bench/jev/README.md`,
    and B20 after the third review).
    The History view gives the components of the top map, also when the nested map Page is
    open. This document gives no rule for the history of the parts of a nested map.
    After the third review of stage 10 (2026-11-19): the actor container of a nested map with
    the actors around the frame is a label, not a surface (`boxKind` in `atlas_draw.py`).
    Tests hold the counts of the headline of Page to counts from the text of map/page.py
    (acceptance 24), a neighbour selected with the keyboard (acceptance 25), and the
    neighbours at three sides or more, at 1440 x 900 and 390 x 844, light and dark
    (acceptance 26). The 9 px check of the canvas page stays an expected failure. The
    canvas page keeps a band for the portals at the fit of a tree with ports, also at the
    top map, and acceptance 10 of that test holds those bands (155 px and 75 px) on the
    fixture with a nested map. A larger fit of the top map would change that written value.
    Thus the canvas page does not change, and the maintainer must decide.

11. **A zoomed-in view that a reader cannot mistake.** The five signs of "Inside a nested
    map". tests/test_atlas_inside_browser.py holds the acceptance values A1 to A8 on the
    nested map Page and on the three depths of the generated M11 tree. The budget is B21 in
    `bench/jev/README.md`, and B22 after the examination of the work (2026-11-20). Both pass.
    tests/test_atlas_inside_contrast.py gives the contrast of each sign. The CI job
    canvas-browser runs the browser test of the signs.

12. **The final review** (2026-11-20). The review found faults in the finished page, and
    the repair corrects them. tests/test_atlas_final_browser.py holds the acceptance values.
    With reduced motion, a double-click goes into a nested map: a mouse click on a card
    that opens a map opens the details after a short wait, so the camera does not move
    before the second click. A selection hides the help note. The reading line is one line of text, in the
    middle of the map area. A label at rest is not on the edge of a surface or of a region,
    and its halo has the color of the ground under it. A label of a sequence with no other
    place can still cross such an edge, because each label of a sequence shows at rest
    (acceptance 2 of tests/test_atlas_sequences_browser.py). The regions have numbers in reading
    order. In the sequence diagram, each label has a plate, so no lifeline goes through it.
    On a phone, the headline of the Map view gives the counts. The key gives "Color when
    you point:", and the details give the assurance level and the freshness in the words of
    the study. In the History view, a dashed line marks where a shallow clone starts. The
    budget is B23 in `bench/jev/README.md`.
    Not changed: the many parallel lines between the actors of the System context layer of
    the top map. They come from the placer and the router, which the canvas page and the
    linked page also use, and from the positions in `map/model.py`. A change needs a
    decision of the maintainer.

13. **The repair of the zoomed-in view** (2026-11-20). This stage repairs five faults that
    stayed open after stage 12. tests/test_atlas_inside_browser.py holds the acceptance
    values Z1 to Z5: the line of a neighbour is readable (Z1), a total in the headline is
    the total of the map (Z2), Esc and Back during a move out go out one more level (Z3),
    the tests that the review of stage 11 asked for (Z4), and the bar and the ground in each
    view that shows a nested map (Z5). Acceptance 27 of tests/test_atlas_browser.py holds
    the counts of the top map.

## What is not decided

- The time of the removal of the canvas page and of the linked page.
- A history of the flows, not only of the files.
