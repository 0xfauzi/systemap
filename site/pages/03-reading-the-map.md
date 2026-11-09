# Read the map

The page that systemap renders shows the map in three views: Map, Sequences, and Changes.
This page gives the controls and the keys of each view.

To try each control, open the [live example](../map/). It is the map of systemap itself.

## The page

The page draws all maps of the map tree on one canvas.
The header has the views, the layers, and Find.

- **Map** shows the components and the flows of one layer, or of all layers.
- **Sequences** shows one sequence as a route, then one step at a time.
- **Changes** shows the components and the flows that a revision comparison changed.

The path of the open maps is at the top left. Select a part of the path to go to that map.
A help line at the bottom left gives the inputs for the camera.

## Move the camera

| Input | Action |
|---|---|
| Wheel or pinch | Zoom at the pointer. |
| Drag | Move the map. |
| Click or tap a card | Select the card. |
| Double-click a card | Go into the card. |
| Tab | Move the keyboard focus to the next card of the current map. |
| Enter | Go into the focused card, or select it if it opens no map. |
| Esc | Go out one level. |
| F | Fit the current map. |
| + and - | Zoom. |
| Arrow keys | Move the map. |
| Ctrl K, Cmd K, or / | Find a view, layer, component, flow, sequence, or action. |
| D | Open or close the Details panel. |
| ? | Show the keyboard keys of the canvas. |

The camera keys do not operate while the keyboard focus is in the header or in a dialog.

## Nested maps

A card that opens a map has a second card behind it. It shows a preview of that map.
When you zoom in, the preview grows into the nested map. Nothing appears at one time.
When a neighbour of the open map is not on the screen, a portal at the screen edge gives its name.
Select a portal to move the camera to that neighbour.
When the frame of an open map is larger than the screen, a ring stays at the screen edge.

The URL hash holds the open map and the selected card, for example `index.html#Gateway/Routes`.
A link with this hash opens the canvas at that map.
The page of a nested map, for example `Gateway/index.html`, is a redirect page.
It opens the canvas page at that map. Thus earlier links stay correct.

## Layers

Select a layer in the header. [Concepts](concepts.html#layer) tells which flows each layer shows.
A layer shows only its flows. A card that no flow of the layer touches becomes quiet.
When the layer buttons do not fit, a list shows in their place.

## The Details panel

Select a card, then select Details or push D. The panel gives the kind and the text of the card, the map that it opens, its flows with their evidence, its sequences, and its rules with their assurance.
The panel gives the counts of the public names and the tests of each module. The facts file has the full source records.
Select a flow in the panel to see its details. "Show the flow on the map" moves the camera to the flow.
With no selection, the panel gives the rules of the current map. Esc closes the panel.

## Open boundary findings

In the Map view, a dotted ring on an actor card shows an open boundary finding of the judgement.
A tag at the top right of the card gives the finding, for example "No flow inside" or "Import with no flow".
The list for a screen reader and the live region give the same words.
When you record an answer to the finding, the ring goes.

## Text for a screen reader

A list after the canvas gives the maps, the cards, the flows, and the facts of each card.
Each link in the list moves the camera to its item.
A live region gives the new map, view, and layer.

## Sequences

- The Sequences view has a toolbar under the header. The chooser opens the list of sequences.
- **Whole route** shows all the steps, with a number on each line. The START tag marks the component where the sequence starts.
- **Steps** shows one step at a time. Use Previous and Next.
- The acting component has an ACTS tag. A measurement component has a MEASURES tag.

## Changes

`systemap render --base REF` and `systemap live` make a page with a revision comparison.
Without a revision comparison, the Changes view gives the command that makes one. The live example has none.
[Pull requests and CI](pull-requests-and-ci.html#the-changes-view) tells how to make this page.

| Mark | Meaning |
|---|---|
| CHANGED tag | The source of the component changed. |
| TESTS tag | Only the tests of the component changed. |
| IMPORTS tag | The component imports changed source. |
| Vermilion dashed line | The flow must have a new source review. |

A card that opens a map with a change in it or below it has the note "changed inside".
A bar under the header gives the changes of the current map in words.
A page link that ends in `#changes` opens this view.

## The legend and the line marks

Color shows only the flow kind, the selection, and the change.

| Mark | Meaning |
|---|---|
| Solid internal line | The flow has a current source review. |
| Short dashed line | Structural evidence only: an import, a shared module, or a configured mechanism. |
| Long dashed line | A declared flow without structural evidence. |
| Dashed card border | An actor outside the source code. |
| Second card behind a card | The component opens a nested map. |

[Concepts](concepts.html#evidence-states) gives the evidence states, and [Concepts](concepts.html#component) gives the card marks of each component kind.

## Themes and motion

Ink has dark surfaces. Paper has light surfaces. The page starts with the device theme. The theme button in the header changes it.
The page obeys the system setting for reduced motion, and the Reduce motion button does the same. Then each camera move occurs at one time.
The source button gives the commit of the map, the facts file, and the model file.
On a narrow screen, these buttons are in one Tools menu.

## Phone layout

On a phone, the page shows the same canvas.
A pinch zooms, and a drag moves the map.
A tap selects a card. A plate gives the name and the facts of the card.
A second tap on a card that opens a map goes into it.
Each part of the path and each portal is 44 by 44 pixels or more.
The page has no horizontal scroll.

## The linked pages for one release

With `[render] canvas = false` in `systemap.toml`, systemap writes one linked page for each map, as before.
The linked page has the full source records, the snapshot button, full screen, and a grid of the regions on a phone. The canvas page does not have these parts.
A later release removes the linked pages.
