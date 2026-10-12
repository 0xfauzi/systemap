# Read the map

The page that systemap renders shows the map in three views: Map, Sequences, and Changes.
This page gives the controls and the keys of each view.

To try each control, open the [live example](../map/). It is the map of systemap itself.

## The page

- **Map** shows the components and the flows of one layer.
- **Sequences** shows one sequence as a route, then one step at a time.
- **Changes** shows the components and the flows that a revision comparison changed.

The header gives the commit of the facts, for example `at 42172a9`. Select it to see the source records of the page.
At the right, the header has Find, Theme, Reduce motion, Keyboard keys (?), and Details.

The question of the view is above the map. The legend is at the bottom left, and the readout is at the bottom right.
If a label does not fit on its line, the readout tells you that it is in the list of the Details panel.

## Keyboard keys

Press ? to see this list on the page:

| Key | Action |
|---|---|
| Ctrl K or / | Find a component, flow, layer or action. |
| 1 to 6 | Select a layer. The last number is the number of layer buttons on the map. |
| Left and right arrows | Previous or next layer or step. |
| W | Whole route of a sequence. |
| F | Full screen. |
| B | Hold to show the base, in the Changes view. |
| D | Open or close the Details panel. |
| ? | Keyboard keys. |
| Esc | Close, or go back one view. |

On a Mac, use Cmd+K for Find.

## Layers

Select a layer in the row under the header. [Concepts](concepts.html#layer) tells which flows each layer shows.
A layer with more than 20 flows shows one grey line for the flows between two regions. Select the line to show its routes.

## Select a component or a flow

- Select a card. The Details panel gives its flows, sequences, rules, and source modules.
- Move the pointer or the keyboard focus to a line to see a preview of the flow.
- Select a line. The Details panel gives its artifact, direction, evidence state, and source records.
- Press Escape to clear the selection.

## The Details panel

With no selection, the panel shows the current layer and a guide with up to five steps.
**Lines and cards** tells how to read the line patterns and the card marks. **Rules** gives all the invariants.

## Fit and zoom

The zoom controls are at the end of the row: zoom out, the zoom value, zoom in, and Fit.
Fit shows the full map as large as the map area permits.

## Sequences

- The sequence button in the row opens the list of sequences.
- **Whole route** shows all the steps, with a number on each line. The START tag marks the component where the sequence starts.
- **Steps** shows one step at a time. Use Previous and Next, or the left and right arrow keys.
- The acting component has an ACTS tag. A measurement component has a MEASURES tag.

## Changes

`systemap render --base REF` and `systemap live` make a page with a revision comparison.
A dot on Changes shows that the page has a revision comparison. The live example has none.
[Pull requests and CI](pull-requests-and-ci.html#the-changes-view) tells how to make this page.

| Mark | Meaning |
|---|---|
| CHANGED tag | The source of the component changed. |
| TESTS tag | Only the tests of the component changed. |
| IMPORTS tag | The component imports changed source. |
| Vermilion dashed line | The flow must have a new source review. |

Hold B to show the map without the change marks. A page link that ends in `#changes` opens this view.

## The legend and the line marks

Color shows only the flow kind, the selection, and the change.

| Mark | Meaning |
|---|---|
| Solid internal line | The flow has a current source review. |
| Short dashed line | Structural evidence only: an import, a shared module, or a configured mechanism. |
| Long dashed line | A declared flow without structural evidence. |
| Dashed card border | An actor outside the source code. |
| Dot on a card | The component has a note. The Details panel gives it. |
| Stacked card | The component opens a nested map. |

[Concepts](concepts.html#evidence-states) gives the evidence states, and [Concepts](concepts.html#component) gives the card marks of each component kind.

## Themes and motion

Ink has dark surfaces. Paper has light surfaces. The first visit uses the device theme.
The system setting for reduced motion does not change the page. Use Reduce motion on the page.

## Phone layout

At a width of 640 pixels or less, the Map view shows the regions as a grid.
Select a region to open the map at a size that you can read.
