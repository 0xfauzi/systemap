# Read the map

The page that systemap renders is the atlas page. It shows the map in these views: Map, Sequences, States, Focus, and History.
This page gives the controls and the keys of each view.

To try each control, open the [live example](../map/). It is the map of systemap itself.

## The page

The page draws all maps of the map tree on one canvas.
The header has the name of the project, the views, the layers, and the tools.

- **Map** shows the cards, the regions, and the flows of one map, with the layers as tabs.
- **Sequences** shows one sequence, on the map or as a diagram, one step at a time.
- **States** shows one state machine.
- **Focus** puts one card in the middle, with the cards that give to it and the cards that it gives to.
- **History** shows where the source files of each component changed, and when.

A view shows only when the map has data for it. Sequences needs a sequence, States needs a state machine, Focus needs a flow, and History needs commits.

The headline is beside the map or above it. It gives the path of the open maps, the name of the layer, the question of the layer, and the counts.
The reading line at the bottom of the map gives one sentence about the thing under the pointer.

## Read the map at rest

At rest, the map is calm. The lines of the flows are thin and have one neutral color.
Each line has a dot at its source and an arrowhead at its target.
When two lines go through the same gap, each line has its own lane. Thus N flows show as N lines.
A line that goes over a different line has a small gap on each side.
A label shows at rest only where it covers no card, no name, and no other line. Point at a card to see all its labels.
When a layer has many flows, the lines are lighter and no label shows at rest. The dots and the arrowheads stay.

| Mark | Meaning |
|---|---|
| Card with round ends | An actor: a part outside the source code. |
| Small tag on a card | The kind of a card that is not a component and not an actor, for example a store. |
| Faint card | The card has no flow in this layer. |
| Second edge behind a card, with a small picture | The card opens a nested map. |
| Faint tint with a number in a ring | A region. |
| Name with no surface above actors | A container that holds only actors. |

## Point and select

Point at a card. Its flows get the colors of their kinds and draw one time in the direction of the flow.
Their labels show, and the other cards and lines go back.
Point at a line. That flow lights, and the reading line gives the source, the target, the artifact, and the sentence of the model about the flow.
A click on a line keeps it lit.

Select a card to open its details at the side. On a phone, the details are a sheet at the bottom.
The details give the kind, the description, the assurance level and the freshness, the flows in and out with their evidence, the source modules, the source records, and the sequences that use the card.
Point at a flow row in the details to light that flow on the map. "All rules of this map" gives the invariants and the import rules of the map.
"Focus on this card" opens the card in the Focus view.

## Move the camera

| Input | Action |
|---|---|
| Wheel or pinch | Zoom at the pointer. |
| Drag | Move the map. |
| Click or tap a card | Select the card. |
| Double-click a card | Go into the map of the card. |
| Tab | Move the keyboard focus through the cards and the lines of the map. |
| Enter | Select the focused card, or keep the focused line lit. |
| Shift Enter | Go into the map of the focused card. |
| Esc | Close the details, or go out one level. |
| F | Fit the current map. |
| + and - | Zoom. |
| Arrow keys | Move the map. |
| Ctrl K, Cmd K, or / | Find a card, a flow, a sequence, or an action. |
| ? | Show the keyboard keys of the page. |

The zoom control has zoom out, the scale, zoom in, and Fit.
On a phone, the map opens at its top left part. Fit shows the whole map.

## Nested maps

A card that opens a map has a second edge behind it and a small picture of its parts.
When you zoom in, the small picture grows into the nested map, and the map above fades. Nothing appears at one time.
You can also double-click the card, or select it and use the button in the details.
When you double-click the card or use the button, the card grows into the nested map.

The page shows five signs that you are inside a nested map:

- A bar at the top of the map gives "Inside" and the name of the map. Its button "Back to" goes out to the map above, as Esc does. In a map at depth 2 or more, the bar also gives the path, and each name in the path goes to that map.
- When you go out, the nested map becomes its card again, and that card is selected.
- A small picture of the map above is in a corner of the screen. The card of the nested map has a mark. A click on the picture goes out.
- The frame of the nested map has the name of the map as a title. The ground around the frame has a different color from the ground of the top map.
- A nested map opens on its Neighbours layer. A neighbour is a card of the map above. It has the line "on" and the name of that map below its name. Select it to go out to that card.

Each part of the path in the headline also goes to that map. Esc goes out one level.

The URL hash holds the open map and the selected card, for example `index.html#Gateway/Routes`.
A link with this hash opens the page at that map and selects the card.
The page of a nested map, for example `Gateway/index.html`, is a redirect page.
It opens the top page at that map. Thus earlier links stay correct.

## Layers

The page opens with the layer System context when the top map has flows in that layer. Else it opens with All.
Select a layer tab. [Concepts](concepts.html#layer) tells which flows each layer shows.
A layer shows only its flows. A card that no flow of the layer touches becomes faint.
Each tab gives the count of the flows of its layer.
On a phone, the tabs are a strip under the header.

## Open boundary findings

In the Map view, a dotted ring on an actor card shows an open boundary finding of the judgement.
A tag near the card gives the finding, for example "No flow inside" or "Import with no flow".
The list for a screen reader and the reading line give the same words.
When you record an answer to the finding, the ring goes.

## Text for a screen reader

A list after the canvas gives the maps, the cards, the flows, and the facts of each card.
Each link in the list moves the camera to its item.
The reading line is a live region. It also gives the new map, view, and layer.

## Sequences

- The list at the left gives the sequences, each with its count of steps. After the list, it gives the entry points that have no sequence.
- The map shows only the flows of the sequence, with the step numbers on the lines. The cards that no step uses are faint.
- The bar at the bottom has the two forms (On the map, As a diagram), the step count, the sentence of the step, and the step controls.
- At the start, the bar gives "Whole route". Next goes to the first step.
- The current step has the color of its kind and draws one time. Earlier steps are dark. Later steps are faint.
- The left and right arrow keys change the step.
- The acting card has an ACTS tag. A measurement card has a MEASURES tag. The START tag marks the card where the sequence starts.
- As a diagram, the view has one column for each card and one row for each step. Select a row to go to that step.

## States

- The list at the left gives the state machines.
- A state has round ends, because a state is not a component. The first state has a dot and a short line before it.
- A transition has its label above its line. Two transitions between the same two states bend apart.
- Point at a state or a transition, or give it the keyboard focus. The reading line gives the meaning of the state or the cause of the transition.
- The arrow keys move the keyboard focus through the states and the transitions. Home and End go to the first item and the last item. Esc removes the light.

## Focus

- One card is in the middle. The cards that give to it are at the left, and the cards that it gives to are at the right, two steps deep.
- On a narrow screen, the view shows one step at each side.
- The headline gives the counts, the reach and the importers, for example "through flows, a change here can reach 15 of 36 other cards · modules of 18 other cards import modules of this card". The reach is the count of the other cards on a path of flows from the card. The importers are the other cards with modules that import modules of the card directly. A change of a card can also reach each of these cards.
- A column shows nine cards at most and then the count of the other cards.
- Select a card to put it in the middle. The list at the left gives the cards with flows.
- In a nested map, the view uses only the parts of the map and the flows between them.

## History

- One row for each component with a change, and one column for each of 12 equal parts of the time.
- A darker cell has more changed lines. A dot marks a cell with a new source module.
- The bars at the top give the total of each column.
- Point at a cell, or give it the keyboard focus. The reading line gives the dates, the count of file changes and of lines, and the new modules.
- The headline gives the count of commits and the dates. If the clone is shallow, the page says that earlier commits are not there.
- `[render] history = false` removes the view. The [reference](reference.html) gives the settings.

## Changes

`systemap render --base REF` and `systemap live` make a page with a revision comparison.
The atlas page shows the changes on the Map view. It has no Changes view.
[Pull requests and CI](pull-requests-and-ci.html#the-changes-on-the-map-page) tells how to make this page.

| Mark | Meaning |
|---|---|
| Ring and CHANGED tag | The source of the component changed. |
| Thin ring and TESTS tag | Only the tests of the component changed. |
| Dashed ring and IMPORTS tag | The component imports changed source. |
| CHANGED INSIDE tag | The card opens a map with a change in it. |
| Dashed line in the change color | The flow must have a new source review. |

The headline gives the count of the cards with changed source.
Under the counts, "Not in this comparison" opens the limits of the comparison. For example, it gives the files that systemap cannot compare, and it tells when the effects on other modules are unknown.

## Themes and motion

The theme control in the header has Device, Light, and Dark. Device follows the theme of the device.
The page obeys the system setting for reduced motion, and the Reduce motion button does the same. Then no line draws and no value fades.
On a narrow screen, the tools are in one Tools menu.

## The canvas page and the linked pages

With `[render] page = "canvas"` in `systemap.toml`, systemap writes the canvas page. It was the default page before the atlas page.
The canvas page has the views Map, Sequences, States, and Changes, with a Details panel.
On the canvas page, a link that ends in `#changes` opens the Changes view.

With `[render] canvas = false`, systemap writes one linked page for each map, as before.
The linked page has the full source records, the snapshot button, full screen, and a grid of the regions on a phone.
A later release removes the linked pages.
