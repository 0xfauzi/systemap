---
name: systemap
description: Authored system maps with evidence for directed relationships.
colors:
  primary: "#FCB442"
  dark-bg: "#0F0E0C"
  dark-surface: "#161411"
  dark-raised: "#211E1A"
  dark-map: "#12110F"
  dark-grid: "#1E1C18"
  dark-card: "#1C1A17"
  dark-card-line: "#716C63"
  dark-line: "#27241F"
  dark-line-2: "#37332D"
  dark-ink: "#F1EDE4"
  dark-ink-2: "#BEB8AC"
  dark-ink-3: "#989184"
  dark-region: "#6B665D"
  dark-flow: "#66625A"
  dark-accent: "#FCB442"
  dark-on-accent: "#1C1405"
  dark-hl: "#FCB4422E"
  dark-change: "#D4675B"
  dark-on-change: "#1E0904"
  dark-steel: "#BEB8AC"
  dark-data: "#2CB59A"
  dark-control: "#B97874"
  dark-context: "#D1EC9F"
  dark-tools: "#8A8708"
  dark-custom-1: "#8A8B22"
  dark-custom-2: "#DCE8B8"
  dark-custom-3: "#C6ED9F"
  dark-custom-4: "#7C9128"
  light-bg: "#ECE8DE"
  light-surface: "#F1EEE6"
  light-raised: "#E6E1D5"
  light-map: "#F6F3EC"
  light-grid: "#E6E1D6"
  light-card: "#FFFEFB"
  light-card-line: "#8C877D"
  light-line: "#E0DBD0"
  light-line-2: "#D3CDC0"
  light-ink: "#1D1B17"
  light-ink-2: "#4B4740"
  light-ink-3: "#686359"
  light-region: "#8F8A80"
  light-flow: "#8F8C84"
  light-accent: "#1D1B17"
  light-on-accent: "#F6F3EC"
  light-hl: "#FFD33D"
  light-hl-soft: "#FFF1BF"
  light-change: "#AC312A"
  light-on-change: "#FFFFFF"
  light-steel: "#4B4740"
  light-data: "#014438"
  light-control: "#A05B5A"
  light-context: "#497B15"
  light-tools: "#544002"
  light-custom-1: "#493901"
  light-custom-2: "#3D7C23"
  light-custom-3: "#5C5C01"
  light-custom-4: "#71640B"
  brand: "#F2B33D"
typography:
  body:
    fontFamily: 'system-ui,-apple-system,"Segoe UI",sans-serif'
    fontSize: "13px"
    lineHeight: 1.5
  project-name:
    fontFamily: 'system-ui,-apple-system,"Segoe UI",sans-serif'
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.02em"
  layer-question:
    fontFamily: 'system-ui,-apple-system,"Segoe UI",sans-serif'
    fontSize: "22px"
    fontWeight: 500
    lineHeight: "28px"
    letterSpacing: "-0.01em"
  panel-title:
    fontFamily: 'system-ui,-apple-system,"Segoe UI",sans-serif'
    fontSize: "19px"
    fontWeight: 600
    lineHeight: "25px"
  kicker:
    fontFamily: 'ui-monospace,"SF Mono",Menlo,Consolas,monospace'
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "0.08em"
  mono:
    fontFamily: 'ui-monospace,"SF Mono",Menlo,Consolas,monospace'
    fontSize: "12px"
    lineHeight: 1.5
  card-name:
    fontFamily: 'ui-monospace,"SF Mono",Menlo,Consolas,monospace'
    fontSize: "14.75 SVG units, down to 11.5 when the text does not fit"
    fontWeight: 600
  card-plain:
    fontFamily: 'system-ui,-apple-system,"Segoe UI",sans-serif'
    fontSize: "13.6 SVG units, down to 11 when the text does not fit"
  flow-label:
    fontFamily: 'system-ui,-apple-system,"Segoe UI",sans-serif'
    fontSize: "11 SVG units"
    fontWeight: 500
rounded:
  control: "6px"
  menu: "10px"
  guide: "10px"
  card: "8 SVG units"
  tag: "3px"
spacing:
  header: "52px"
  panel: "400px"
  map-gutter: "24px"
  control-gap: "8px"
  phone-margin: "16px"
components:
  view-button:
    textColor: "{colors.dark-ink-2}"
    rounded: "{rounded.control}"
    height: "32px"
  view-button-selected:
    backgroundColor: "{colors.dark-raised}"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.control}"
  find:
    backgroundColor: "{colors.dark-map}"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.control}"
    width: "200px"
    height: "32px"
  read-panel:
    backgroundColor: "{colors.dark-surface}"
    textColor: "{colors.dark-ink}"
    width: "{spacing.panel}"
  guide-card:
    backgroundColor: "{colors.dark-surface}"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.guide}"
    width: "340px"
  map-card:
    backgroundColor: "{colors.dark-card}"
    rounded: "{rounded.card}"
  role-tag:
    backgroundColor: "{colors.dark-accent}"
    textColor: "{colors.dark-on-accent}"
    rounded: "{rounded.tag}"
  segmented-control:
    textColor: "{colors.dark-ink-2}"
    rounded: "{rounded.control}"
    height: "32px"
  segmented-control-selected:
    backgroundColor: "{colors.dark-card}"
    textColor: "{colors.dark-ink}"
  view-row:
    backgroundColor: "{colors.dark-surface}"
    height: "52px"
  step-card:
    textColor: "{colors.dark-ink-2}"
    rounded: "8px"
    padding: "10px 12px"
  step-card-current:
    backgroundColor: "{colors.dark-card}"
    textColor: "{colors.dark-ink}"
    rounded: "8px"
  control-icon:
    size: "16px"
    strokeWidth: "1.5 units on a 16 unit grid"
---

# Design System: systemap

The page shows a software map in three views: Map, Sequences, and Changes.
A component is a system part. A flow transmits an artifact between components.
A sequence shows authored operation steps. The page does not record execution.

## Appearance

The page shows one question for each view. It uses thin borders and neutral cards.
Color shows only the flow kind, the selection, and the change.

The page has two themes: Ink and Paper. Ink has dark surfaces and is the default.
Paper has light surfaces. The configuration keys are `dark` for Ink and `light` for Paper.
A first visit uses the device theme. A saved selection replaces that theme.
The More menu contains Ink and Paper. Other theme names are not available.
If the configuration names a removed theme, such as `clay`, the program gives an error.

The two themes have the same CSS tokens in `theme.py`.
The page behind the map uses `bg`. The header and the panel use `surface`.
The map uses `map` and has a grid of dots in `grid`. A card uses `card` and `card_line`.
A container has a 1px solid border in `line_2` and no fill.
A region has a 1px dashed border in `region` and a number in a ring.

### Color roles

Only the flow kinds, the selection, and the change have colors.
Cards, regions, text, and other lines are neutral.
Each flow kind has one color in each theme. The two themes use the same color family for each kind.
A layer such as System context selects lines. It does not change the color of a line.
Ink shows the selection with an amber line and ring.
Paper shows the selection with an ink line and ring on the yellow highlighter fill.
Vermilion shows a change. Only the Changes view shows vermilion.
Stroke patterns identify evidence states. External components have dashed borders.
Measurement components use `steel`, which is a neutral color.
The tokens `good`, `warn`, `bad`, and `violet` have neutral values.

Color is not the only indication of meaning.

### Measured colors

The color values come from a measurement.
The measurement uses these limits for each pair of colors that can show on one view:

- A CIEDE2000 difference of 25 or more with normal color vision.
- A CIEDE2000 difference of 12 or more with protanopia, deuteranopia, and tritanopia.
  The Brettel simulation calculates the colors for these three conditions.

Text has a contrast ratio of 4.5:1 or more on the page, panel, map, and card colors.
A flow kind color has 4.5:1 or more on the map and the card. Other lines have 3:1 or more on the map.

No flow kind color has an OKLCH hue from 180 to 350 degrees, in either theme.
This hue range contains cyan, blue, violet, purple, and magenta.
The kind colors are teal green, clay, pale green, olive, and other yellow-green colors.
Each kind has the same hue family in Ink and Paper.

The measured limit is four flow kind colors on one view. The page does not apply this limit.
In both themes, the data, control, context, and tools colors are in these limits on one view.
In both themes, the data, control, and first custom kind colors are in these limits on one view.
In Ink, the data, control, and two custom kind colors are in these limits on one view.
In Paper, a second custom kind color next to data, control, and the first custom kind is not in these limits.
In both themes, five flow kind colors on one view are not in these limits.
In both themes, the first custom kind color is near the tools color.
The second custom kind color is near the context color.
A view that shows one of these pairs does not have distinct colors for them.

## Navigation and layout

The page has three views: Map, Sequences, and Changes. Each view answers one question.
The header is 52px high. It contains the systemap symbol, the project name, and the stored commit.
It also contains the three view buttons, Find, Read, and the More menu.
A dot on Changes shows that the page has a revision comparison.
The More menu contains Reference, Text view, Map view, the theme, Reduce motion, and Keyboard keys.

The three views have the same parts: a row of controls under the header, a title block above the map,
the legend and the readout below the map, and the panel at the right. The map uses the remaining area.

The row is 52px high. In the Map view, it has the label Layer and a segmented control:
System context, Structure, Data flow, Control flow, Map review, and All.
This control has the design of Whole route and Steps in the Sequences toolbar.
A selected segment has the card color and ink text. The focus ring of a segment is inside the segment.

The title block has a small label and the question. The label uses the kicker type.
In the Map view, it gives the layer name and its position, for example SYSTEM CONTEXT · LAYER 1 OF 5.
The All segment gives ALL LAYERS. The question shows in 22px type.

The zoom controls are at the end of the row in each view: zoom out, the zoom value, zoom in, and Fit.
Zoom out, the zoom value, and zoom in are one segmented group. Fit is a separate button.
The buttons have icons on a 16-unit grid with a 1.5-unit line, round ends, and round joins.
Each icon button has a name and a tooltip. The zoom value button sets the actual size. Fit shows the full map.
The legend is at the bottom left of the map. The legend shows only the items that the current view uses.
The readout is at the bottom right. It gives the counts of the view or the selected item.

The panel is at the right of the map, under the row. The panel is 400px wide.
On a window wider than 820px, the Map view opens the panel with the page, as the Sequences view does.
Read closes the panel and opens it again.
With no selection, the panel shows the current layer in the style of the sequence steps.
A head row gives the label LAYER and the counts. The layer name is the panel title.
The guide text of the layer, or else its description, follows.
A card shows each flow: a line in the color of its kind, the two ends, the artifact, and the first sentence of the flow.
The line is dashed when the flow has no recorded source review.
A pointer or keyboard focus on a flow card shows a preview of the flow. A click selects the flow.
In System context, a card shows each actor and the artifacts that it receives and sends.
In Structure, a card shows each region with its number and its components. A click frames the region.
The guide steps follow the layer as a short numbered list. The step of the current layer has the accent number.
A layer with more than 20 flows shows its flows in groups. The panel lists the groups with their counts in rings.
The open group is the current card: an accent border and the highlight fill.
A group line, like a flow line, has only horizontal and vertical parts.
A component selection shows its description, the flows that it receives and sends, its sequences, and its source modules.
A flow selection shows its artifact, its direction, its evidence state, and its source records.
The panel title of a component has the 19px panel title size.
The map moves so that the panel does not cover the selection.
The selection also stays above the legend and the readout, as a sequence step does.

On the first visit, a guide card at the bottom right gives five steps. Each step selects a layer or a sequence.
The map moves left so that the card does not cover it. The map goes back to Fit when the card closes.
The page records the first visit in the browser. Read shows the same steps again.

Find searches component names, descriptions, and source modules. The / key gives Find the focus.
The arrow keys move through the results. Enter selects a component.

At widths of 1100px or less, the panel is 340px wide, Find is smaller, and the header does not show the commit.
At widths of 820px or less, the panel covers the right side of the map, under the row.
The zoom controls go below the row, at the right of the title block. The Map view does not open the panel with the page.
At widths of 640px or less, the phone layout replaces the map frame.
The phone layout shows the regions as a grid. A region opens the map at a size that you can read.
A sequence shows one step: the map frame, the step note, the step buttons, and Previous and Next.
Phone controls are 44px high or more.

## Map and text

The map has one flat view. Card positions and flow paths come from the model.
Cards have an 8-unit corner radius. Card text is centered in the card.
On the page, a shade under each card gives it depth. The shade is a copy of the card shape
1.6 units lower, with no blur. When the pointer is on a card, the shade moves lower
and the card border changes to `ink_3` in 160 ms. A selected card and the ends of a selected line keep their accent border.
After 120 ms on a card, its lines get thicker and the cards at their other ends stay at full contrast.
The other cards go to 60 percent opacity, and the other lines and labels fade.
A press on the map ends this state. A drag of the map does not start it.
The selected card has a soft glow: amber in Ink, the highlighter yellow in Paper.
The map surface has a fine static grain under the dot grid and a soft dark edge.
All cards of a map use one type size. The page uses the largest size at which the text of all cards fits.
The maximum size is a 13px name and a 12px description at 88 percent zoom.
The minimum size is the base size that the map check examines. Card text changes size with the zoom.

Flow labels show on their line at rest. A label that does not fit on its line shows only for a pointer, focus, or selection.
The readout and the panel tell the reader that such labels are in the list.
A layer change draws the lines of the new layer in model order. Each line draws from its source to its target.

Text view shows the same components and flows as a list. It keeps the selection.
Document figures use the same card type size and keep the authored coordinate plane.

System sans fonts show controls and descriptions.
System monospace fonts show identifiers, paths, commands, counts, and finding lines.
The page loads no font files.

## Sequences

Sequences shows one operation at a time. The toolbar contains the sequence selector,
Whole route and Steps, the step controls, End sequence, and Full screen.
Whole route shows all the steps of the sequence on the map. Each step has a number on its line.
The entry point component has a START tag. Cards that the sequence does not use have low contrast.
The route draws in step order.

Steps shows one step. The current line has the accent color. The lines of earlier steps are solid.
The lines of later steps have low contrast. The acting component has an ACTS tag.
A measurement component has a MEASURES tag. A note next to the line gives the step number, the artifact,
the two ends, and the step sentence.
The camera keeps the zoom. It moves only when the step is not in view. Then it moves only as far as necessary.

The panel gives the route in order, all sequences with a small map of their regions, and the entry point coverage.
Full screen shows the map and a step bar with the step number, the sentence, and Previous and Next.
The steps are an authored order. They do not record a run of the program.

## Changes

Changes compares two revisions on the map.
The toolbar gives the base and the head revisions. Hold the B key or the Hold B button to show the map without change marks.
A component with changed source has a CHANGED tag. A component with only test changes has a TESTS tag.
A component that imports changed source has an IMPORTS tag.
A flow that needs a new source review has a vermilion dashed line. Other cards and lines have low contrast.
The marks show in a fixed order: the changed cards, the tagged cards, and then the flows.
The panel gives a summary, the changed components, the flows to examine, the sequences with a changed step,
the decisions, and the limits of the comparison.

## Selection and evidence

A selected component has an accent ring. Its flows show at full contrast. Other cards and lines have low contrast.
Structure shows no flow lines after a component selection.
A pointer or keyboard focus on a line shows a preview of that flow. The label of the line gets a thin outline.
A declared flow keeps its dash pattern during selection.
No more than one directional cue moves. The cue does not show a recorded run.

Escape closes the menu, the sequence, the selection, the panel, and Reference, in that order.
A nested map opens in a dialog above an inert background.
The dialog gives the keyboard focus back to its control when it closes.
Finding identifiers, authored claims, and evidence states keep their meaning.
Source records show missing evidence without a different claim.

## Motion

Each motion occurs one time and shows a direction or an order.
The systemap symbol draws one time when the page opens: the route in 600 ms, then its two ends.
The camera moves in 300 ms with an ease-in-out curve.
A new layer draws its lines in 600 ms or less.
In the Map view, a layer change fades in the title block and the panel in 180 ms. The text does not move.
A sequence step shows its note after the camera stops.
When the page opens, the cards come in one time in reading order, in 360 ms or less.
A theme change fades the colors in 240 ms.
A selected line and the current sequence line have a soft glow.
With Reduce motion or the system setting for reduced motion, the page shows the final state with no motion.

The source modules are `page.py`, `page_assets.py`, `page_script.py`, `page_workspace.py`, `page_guide.py`,
`page_atlas.py`, `page_groups.py`, `page_sequences.py`, `page_sequence_script.py`, `page_present.py`,
`page_changes.py`, `page_changes_script.py`, `page_phone.py`, `page_motion.py`, `page_mapview.py`,
`page_map_icons.py`, `schematic_style.py`, `schematic_script.py`, and `schematic_relations.py`.
The build removes the comments, line breaks, and indentation from the page styles and scripts.
The browser measurements and test results are in `bench/jev/README.md`.
