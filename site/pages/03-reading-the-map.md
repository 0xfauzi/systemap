# Read the map

The page that systemap renders shows the map in three views: Map, Sequences, and Changes.
This page tells you how to use each view and its controls.

To try each control, open the [live example](../map/). It is the map of systemap itself.

## The header

At the left, the header shows the systemap symbol, the project name, and the commit of the facts, for example `at 42172a9`.
Select the commit to see the source records of the page.
A small panel gives the commit at extraction, the source files, and the limits of the stored snapshot.
Then the header has the three view buttons. A dot on Changes shows that the page has a revision comparison.

At the right, the header has these controls:

| Control | Action |
|---|---|
| Find | Opens one search field for views, layers, components, flows, sequences, steps, rules, and actions. |
| Theme | Changes the theme between Ink and Paper. A sun selects Paper. A moon selects Ink. |
| Reduce motion | Stops the motion of the page. |
| Keyboard keys (?) | Opens the list of keyboard keys. |
| Details | Opens or closes the Details panel at the right of the map. |

## The three views

Each view asks one question above the map.

| View | Question | Contents |
|---|---|---|
| Map | The question of the current layer, for example "Which actors connect to the system?" | The components and the flows of one layer. |
| Sequences | "Which parts does this operation use?" for the whole route. "What occurs at each step?" for one step. | One sequence as a route on the map, then one step at a time. |
| Changes | "What did this change touch?" | The components and the flows that a revision comparison changed. |

The three views have the same parts.
A row of controls is under the header. A small label and the question are above the map.
The legend is at the bottom left of the map, and the readout is at the bottom right.
The Details panel is at the right.

## Layers

In the Map view, the row gives the layers of the map, for example System context, Structure, Data flow, Control flow, and All.
[Concepts](concepts.html#layer) tells which flows each layer shows.
Select a layer in the row. You can also press a number key.
The left and right arrow keys select the previous or the next layer.

The small label above the map gives the layer name and its position, for example `SYSTEM CONTEXT · LAYER 1 OF 5`.
The readout gives the counts of the view or of the selected item, for example `15 flows · 4 actors`.
When a label does not fit on its line, the readout tells you that it is in the list of the Details panel.

A layer with more than 20 flows shows its flows in groups.
One grey line shows all the flows of the layer between two regions, with the number of flows.
Flows inside one region stay as routes.
Select a group on the map or in the Details panel to show its routes. Show all routes in the panel shows each flow.

On the first visit, a guide card at the bottom right gives up to five steps.
Each step selects a layer or starts a sequence. The Details panel gives the same steps.

## Select a component or a flow

Select a card to select its component.
The selected card has a ring, and its flows show at full contrast. The other cards and lines have low contrast.
The Structure layer shows no flow lines after a component selection.

The Details panel of a component gives:

- its description and its short name,
- the flows that it receives and sends, with the artifact and the other component,
- the sequences that use it,
- the rules that apply to it,
- the source modules that it contains.

Point to a line, or move the keyboard focus to it, to see a preview of that flow.
Select a line to see its artifact, its direction, its evidence state, and its source records.
Press Escape to clear the selection.

## The Details panel

Details, or the D key, opens and closes the panel.
On a window wider than 820 pixels, the Map view opens the panel with the page.

With no selection, the panel shows the current layer.
It gives one card for each flow, actor, or region of the layer, and then the guide steps.
Two more sections open on a click:

- **Lines and cards** tells how to read the line patterns, the card marks, and the evidence states.
- **Rules** gives all the invariants of the system. Each rule has a button for each component to which it applies.

## Find

Ctrl+K opens Find. On a Mac, use Cmd+K. The / key also opens it.
Type part of a name. A name that starts with the text comes first.
The up and down arrow keys move the selection. Enter does the action of the result. Escape closes the dialog.

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

Escape closes the newest item first.
The order is the Find dialog, the list of keys, the source records, full screen, the sequence, the selection, and then the panel.

## Fit and zoom

The zoom controls are at the end of the row: zoom out, the zoom value, zoom in, and Fit.
The zoom value sets the actual size. Fit shows the full map as large as the map area permits.
When the window or the panel changes the map area, a map at Fit stays at Fit.

When the zoom is less than 100 percent, the flow labels and the region labels become larger, so that you can read them.
A label then moves along its line to a place where it touches no card and no other label.
A label without such a place shows only for a pointer, keyboard focus, or a selection.

The full-screen button, or the F key, shows the map alone. Escape or F ends full screen.
In the Sequences view, full screen shows the map and a bar with the current step.

## Sequences

The sequence button in the row opens the list of sequences.
Whole route shows all the steps on the map, with a number on each line.
The START tag marks the component where the sequence starts.

Steps shows one step at a time. Use Previous and Next, or the left and right arrow keys.
A note next to the line gives the step number, the artifact, the two ends, and the step sentence.
The acting component has an ACTS tag. A measurement component has a MEASURES tag.
The Details panel gives the route in order, all sequences, and the entry points that have a sequence.

The steps are an authored order. They do not record a run of the program.

## Changes

The Changes view needs a page with a revision comparison.
`systemap render --base REF` writes such a page, and `systemap live` supplies one.
Without a comparison, the view shows "This page has no revision comparison" and the command to make one.
The live example has no revision comparison.

| Mark | Meaning |
|---|---|
| CHANGED tag | The source of the component changed. |
| TESTS tag | Only the tests of the component changed. |
| IMPORTS tag | The component imports changed source. |
| Vermilion dashed line | The flow must have a new source review. |

Hold the B key, or the Hold B button, to show the map without the change marks.
The Details panel gives a summary, the changed components, the map changes, and the flows to examine.
The map changes are the components, flows, sequences, and rules that the change added, removed, or changed in the model.
A page link that ends in `#changes` opens the Changes view.
[Pull requests and CI](pull-requests-and-ci.html#the-changes-view) tells how to make this page.

## The legend and the line marks

The legend shows only the items that the current view uses. Each flow kind has one color in all views.
Color shows only the flow kind, the selection, and the change. Cards, regions, and text are neutral.

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

The page has two themes. Ink has dark surfaces. Paper has light surfaces.
The first visit uses the device theme: Paper for a light setting, and Ink for other settings.
The theme button changes the theme, and the browser keeps your selection.

Motion is on until you set Reduce motion on the page. The browser keeps this setting.
The system setting for reduced motion does not change the page.

## Phone layout

At a width of 640 pixels or less, the page uses the phone layout.
The Map view shows the regions as a grid. Select a region to open the map at a size that you can read.
Open the full map shows the complete map.
A sequence shows one step below the map, with a button for each step, and Previous and Next.
The header shows Find, the theme, and Reduce motion.
