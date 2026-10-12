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
  light-bg: "#F1EFEC"
  light-surface: "#FCFAF7"
  light-raised: "#EDEAE6"
  light-map: "#F4F2EF"
  light-grid: "#E6E3DF"
  light-card: "#FFFEFC"
  light-card-line: "#8F8B85"
  light-line: "#E4E2DF"
  light-line-2: "#D4D1CD"
  light-ink: "#1D1B17"
  light-ink-2: "#524F4A"
  light-ink-3: "#6D6963"
  light-region: "#8F8B85"
  light-flow: "#8E8C85"
  light-accent: "#1D1B17"
  light-on-accent: "#FCFAF7"
  light-hl: "#FFEBA0"
  light-hl-soft: "#FFF5D6"
  light-change: "#AC312A"
  light-on-change: "#FFFFFF"
  light-steel: "#524F4A"
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
    fontFamily: '"systemap Inter",system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "13px"
    lineHeight: 1.5
  project-name:
    fontFamily: '"systemap Inter",system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.02em"
  layer-question:
    fontFamily: '"systemap Inter",system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "22px"
    fontWeight: 500
    lineHeight: "28px"
    letterSpacing: "-0.01em"
  panel-title:
    fontFamily: '"systemap Inter",system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "19px"
    fontWeight: 600
    lineHeight: "25px"
  secondary:
    fontFamily: '"systemap Inter",system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "12px"
    lineHeight: "18px"
  kicker:
    fontFamily: 'ui-monospace,"SF Mono",SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace'
    fontSize: "11px"
    fontWeight: 600
    lineHeight: "16px"
    letterSpacing: "0.08em"
  tag:
    fontFamily: 'ui-monospace,"SF Mono",SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace'
    fontSize: "11px"
    fontWeight: 700
    lineHeight: "16px"
    letterSpacing: "0.06em"
  mono:
    fontFamily: 'ui-monospace,"SF Mono",SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace'
    fontSize: "12px"
    lineHeight: 1.5
  card-name:
    fontFamily: 'ui-monospace,"SF Mono",SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace'
    fontSize: "14.75 SVG units, down to 11.5 when the text does not fit"
    fontWeight: 600
    lineHeight: 1.23
  card-plain:
    fontFamily: 'Arial,"Liberation Sans",Arimo,sans-serif'
    fontSize: "13.6 SVG units, down to 11 when the text does not fit"
    fontWeight: 400
    lineHeight: 1.08
  flow-label:
    fontFamily: 'system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "11 SVG units, up to the card description size when the zoom is less than 100 percent"
    fontWeight: 500
  container-description:
    fontFamily: 'system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "11 SVG units"
    fontWeight: 400
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
  find-button:
    backgroundColor: "{colors.dark-map}"
    textColor: "{colors.dark-ink-3}"
    rounded: "{rounded.control}"
    width: "200px"
    height: "32px"
  icon-button:
    textColor: "{colors.dark-ink-2}"
    rounded: "{rounded.control}"
    size: "32px"
  icon-button-pressed:
    backgroundColor: "{colors.dark-raised}"
    textColor: "{colors.dark-ink}"
  find-dialog:
    backgroundColor: "{colors.dark-surface}"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.menu}"
    width: "600px"
  details-panel:
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
  sequence-button:
    backgroundColor: "{colors.dark-card}"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.control}"
    width: "320px"
    height: "32px"
  sequence-list:
    backgroundColor: "{colors.dark-surface}"
    rounded: "{rounded.menu}"
    width: "{spacing.panel}"
  flow-line:
    strokeWidth: "1.6px"
  flow-line-emphasis:
    strokeWidth: "2.6px"
  flow-line-under:
    color: "{colors.dark-accent} at 30 percent opacity in Ink, and the highlighter fill in Paper"
    strokeWidth: "12px"
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
The theme button in the header changes the theme between Ink and Paper. Other theme names are not available.
If the configuration names a removed theme, such as `clay`, the program gives an error.

The two themes have the same CSS tokens in `theme.py`.
The page behind the map uses `bg`. The header and the panel use `surface`.
The map uses `map` and has a grid of dots in `grid`. A card uses `card` and `card_line`.

A container has a 1px solid border in `line_2` and no fill.
A region has a 1px dashed border in `region` and a number in a ring.

In Paper, each surface color is a neutral color with an OKLCH chroma of 0.007 or less.
Thus the surfaces do not have the color of the yellow highlighter.
The map is darker than the header, the row, and the panel. A card is the lightest surface.
Thus the panel and the map are different areas, and each card is easy to see on the map.

### Color roles

Only the flow kinds, the selection, and the change have colors.
Cards, regions, text, and other lines are neutral.
Each flow kind has one color in each theme. The two themes use the same color family for each kind.

A layer such as System context selects lines. It does not change the color of a line.
A line has the color of its flow kind in all views and in all states.
A selected flow, the current sequence step, and the lines of a sequence route keep that color.

The selection color identifies only the current item. It is amber in Ink and ink in Paper.
It shows on the ring of the selected card, the step numbers, the ACTS and START tags,
the current step card, and the step note.

A wider line is under the selected line and under the current step line. It is 12 px wide.
In Ink, it is amber at 30 percent opacity. In Paper, it is the yellow highlighter fill.

Vermilion shows a change. Only the Changes view shows vermilion.

Stroke patterns identify evidence states. External components have dashed borders.
Measurement components use `steel`, which is a neutral color.
The tokens `good`, `warn`, `bad`, and `violet` have neutral values.

Color is not the only indication of meaning.

### Line widths

All flow lines use one width scale. A line at rest is 1.6 px wide at all zoom values.
A line with emphasis is 2.6 px wide. The selected line, the current step line,
a preview, and the lines of a card under the pointer have emphasis. Group lines keep the widths from their flow counts.

A sequence shows its progress with the width and the opacity of its lines, not with their color.
A dash shows only an evidence state.

### Measured colors

The color values come from a measurement.
The measurement uses these limits for each pair of colors that can show on one view:

- A CIEDE2000 difference of 25 or more with normal color vision.
- A CIEDE2000 difference of 12 or more with protanopia, deuteranopia, and tritanopia.
  The Brettel simulation calculates the colors for these three conditions.

Text has a contrast ratio of 4.5:1 or more on the page, panel, map, and card colors.
A flow kind color has 4.5:1 or more on the map and the card. Other lines have 3:1 or more on the map.
In Paper, a flow kind color also has 3:1 or more on the yellow highlighter under a selected line.

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

The header is 52px high. At the left, it contains the systemap symbol, the project name, the stored commit,
and the three view buttons. A dot on Changes shows that the page has a revision comparison.
At the right, it contains Find, the theme, Reduce motion, Keyboard keys, and Details. No menu hides a control.

Find is a button in the shape of a field: a search icon, the word Find, and its key.
The other controls are icon buttons. Each icon button has a name and a tooltip.
A pressed button has the raised color and a border.
The theme button shows the theme that it selects: a sun for Paper and a moon for Ink.

Reduce motion is in the header because the system setting does not stop motion on the page (see Motion).
Keyboard keys is the ? icon. It opens the list of keys, as the ? key does.

Details is at the right end of the header, above the panel that it opens. It opens and closes the panel, as the D key does.
The panel shows the details of the layer, the selection, the sequence, or the change. The name Details applies to each state.

The stored commit is a button. It opens a small panel with the source records of the page.
This small panel gives the commit at extraction, the source files, and the limits of the stored snapshot.
Escape or a click outside the small panel closes it.

The three views have the same parts. Each view has a row of controls under the header and a title block above the map.
The legend and the readout are below the map, and the panel is at the right. The map uses the area that the other parts do not use.

The row is 52px high. In the Map view, it has the label Layer and a segmented control:
System context, Structure, Data flow, Control flow, Map review, and All.
This control has the design of Whole route and Steps in the Sequences toolbar.

A selected segment has the card color and ink text. The focus ring of a segment is inside the segment.
In Paper, the segmented control and the zoom buttons have the map color. Thus the selected segment shows on the row.

The title block has a small label and the question on one line. The label uses the kicker type.
In the Map view, it gives the layer name and its position, for example SYSTEM CONTEXT · LAYER 1 OF 5.
The All segment gives ALL LAYERS. The question shows in 22px type.

On a window of 1259px or less, the title block shows only the question.
Thus the title block has one line in each layer, and a layer change does not change Fit.
The map starts 2px below the title block.

The zoom controls and the full-screen button are at the end of the row in each view.
Zoom out, the zoom value, zoom in, and Fit are one segmented group. The full-screen button follows the group.

The buttons have icons on a 16-unit grid with a 1.5-unit line, round ends, and round joins.
Each icon button has a name and a tooltip. The zoom value button sets the actual size. Fit shows the full map.
The Fit icon has small corners around a rectangle. The full-screen icon has large corners.

Fit shows the drawn map: the containers, the regions, the cards, the lines, and the labels.
It does not show the empty space around them. The map is 8px or more from the edges of the map area.
It is above one line of the legend and the readout.

On a narrow window, a legend with two lines can cover the bottom of the map.
The page opens at Fit. When the window, the panel, or the legend changes the map area, a map at Fit stays at Fit.
The zoom value then shows the new zoom. Fit is 150 percent or less.

The full-screen button and the F key open full screen in each view.
In Map and Changes, the header, the row, and the panel go. The browser shows the page in full screen if it can.
The map, the title block, the legend, the readout, and the zoom controls stay.
The full-screen button then shows Exit full screen and the Esc key.

Escape, the F key, and the button end full screen. If the panel was open before, it opens again.
A selection in full screen opens the panel.
In Sequences, full screen is the step overlay (see Sequences).
In Changes, the button is not available when the page has no revision comparison.

The legend is at the bottom left of the map. The legend shows only the items that the current view uses.

The map has no browser tooltips. The text that a tooltip gave is on the screen.
The legend names the note dot and the mark of a card that opens a map.
The Details panel gives the note and the inner map.
Only an icon button has a tooltip, which gives its name.

The readout is at the bottom right. It gives the counts of the view or the selected item.

The panel is at the right of the map, under the row. The panel is 400px wide.
On a window wider than 820px, the Map view opens the panel with the page, as the Sequences view does.
Details closes the panel and opens it again.

With no selection, the panel shows the current layer in the style of the sequence steps.
A head row gives the label LAYER and the counts. The layer name is the panel title.
The guide text of the layer follows, or its description if the layer has no guide text.

A card shows each flow: a line in the color of its kind, the two ends, the artifact, and the first sentence of the flow.
The line is dashed when the flow has no recorded source review.
A pointer or keyboard focus on a flow card shows a preview of the flow. A click selects the flow.

In System context, a card shows each actor and the artifacts that it receives and sends.
In Structure, a card shows each region with its number and its components. A click moves the camera to show the full region.

The guide steps follow the layer as a short numbered list. The step of the current layer has the accent number.
Two sections follow the guide steps. Each section opens on a click.

Lines and cards tells the reader how to read the line patterns, the card marks, and the evidence states.
Rules gives all rules of the system. Each rule has buttons for the components to which it applies.
The panel of a component gives the rules of that component.

A layer with more than 20 flows shows its flows in groups. The panel lists the groups with their counts in rings.
The open group is the current card: an accent border and the `hl_soft` fill.
A group line, like a flow line, has only horizontal and vertical parts.

A component selection shows its description, the flows that it receives and sends, its sequences, and its source modules.
A flow selection shows its artifact, its direction, its evidence state, and its source records.
The panel title of a component has the 19px panel title size.
The map moves so that the panel does not cover the selection.
The selection also stays above the legend and the readout, as a sequence step does.

On the first visit, a guide card at the bottom right gives five steps. Each step selects a layer or a sequence.
The map moves left so that the card does not cover it. The map goes back to Fit when the card closes.
The page records the first visit in the browser. The Details panel shows the same steps.

Find opens the Find dialog. Ctrl+K, Cmd+K on a Mac, and the / key also open it.
The Find dialog is above the page. It has a search field and a list of results in groups:
views, layers, components, flows, sequences, steps, rules, and actions.
With no text, the list gives the views, the layers, the sequences, and the actions.

A name that starts with the text comes first. A name with a word that starts with the text comes next.
Other text, such as a description or a source module, comes after the names.
A group name is also a match: "rule" gives the rules first.
A component that matches only in a source module shows that module.

The up and down arrow keys move the selection. Enter does the action of the result. Escape closes the dialog.

Each result shows its key, if it has one. The current view and the current layer show Current.
The actions are the theme, Reduce motion, full screen, Details, and Keyboard keys.
A rule opens the Rules section of the Map panel at that rule.

The dialog is 600px wide. It has the surface color, a 10px corner radius, and group names in the kicker type.
On a phone, the dialog fills the width of the screen from the top. A Close button replaces the Esc key.

At widths of 1100px or less, the panel is 340px wide, Find is smaller, and the commit shows without the word at.
At widths of 820px or less, the panel covers the right side of the map, under the row.
The zoom controls go below the row, at the right of the title block. The Map view does not open the panel with the page.
Find shows only its icon.

At widths of 640px or less, the phone layout replaces the map area.
The phone layout shows the regions as a grid. A region opens the map at a size that you can read.

A sequence shows one step: the sequence button, the map area, the step note, the step buttons, and Previous and Next.
The map area of a step shows the two cards and the line of the step. Its zoom is not less than the zoom
at which card names show at 12px and card descriptions at 11px. If the step does not fit at that zoom,
the acting component stays in the map area. It is as near to the middle of the step as possible.

The step fills the height of the screen. The map area has the height that the other parts do not use.
The space under Previous and Next is 16px, or the bottom safe area of the device when that area is larger.
On a phone, the sequence button is in the head under the views. Its list has the width of the button.

Phone controls are 44px high or more.
On a phone, the header shows Find, the theme, and Reduce motion as 40px icons.
It does not show Keyboard keys or Details.

## Map and text

The map has one flat view. Card positions and flow paths come from the model.
Cards have an 8-unit corner radius. Card text is in the center of the card.

On the page, a shade under each card gives it depth. The shade is a copy of the card shape
1.6 units lower, with no blur. When the pointer is on a card, the shade moves lower
and the card border changes to `ink_3` in 160 ms. A selected card and the ends of a selected line keep their accent border.

After 120 ms on a card, its lines become thicker and the cards at their other ends stay at full contrast.
The other cards go to 60 percent opacity, and the other lines and labels fade.
A press on the map ends this state. A drag of the map does not start it.

In Ink, the selected card has a soft amber glow. In Paper, it has no glow.
The highlighter fill and the ink ring show the selection.
In Ink, the map surface has a fine static grain under the dot grid and a soft dark edge.
In Paper, the map surface has only the dot grid.

All cards of a map use one type size. The page uses the largest size at which the text of all cards fits.
The maximum size is a 13px name and a 12px description at 88 percent zoom.
The minimum size is the base size that the map check examines. Card text changes size with the zoom.

Flow labels show on their line at rest. A label that does not fit on its line shows only for a pointer, focus, or selection.
The readout and the panel tell the reader that such labels are in the list.

When the zoom is less than 100 percent, the flow labels, the region labels, and the container labels become larger.
They show at 11px on the screen, but they do not become larger than the card descriptions.
A container label becomes larger from the top left corner of its container. A region label becomes larger from the left edge
of its region, at the middle of its number ring. Each becomes as large as the space in its box permits.

A larger flow label moves along the nearest part of its own line to the nearest free place.
At a free place, the label text touches no card and no other label.
It also touches no line that it did not touch at its layout size.
A label that has no such place shows only for a pointer, focus, or selection, as a label beside its line does. The readout counts it with those labels.

The layout sizes do not change, so the map check and the placement give the same results.
A layer change draws the lines of the new layer in model order. Each line draws from its source to its target.

Document figures use the same card type size and keep the authored coordinate plane.

## Type

The page contains one font: a subset of Inter with the family name "systemap Inter".
The font is in the page style as a data URI. The page loads no font files.
Thus the page text has the same font on macOS, Windows, and Linux.

Inter shows the sans text of the page. This text is in the header, the controls, the title block, the panel, and the Find dialog.
It is also in the guide, the legend, the readout, the list of keyboard keys, and the phone layout.
On the map, Inter shows the step labels of a sequence. The browser measures these labels.

The monospace font of the computer shows identifiers, paths, commands, counts, finding lines, small labels, and tags.
The page does not contain a monospace font.
A layer name is text, not an identifier. It uses the sans font, also in the guide steps of the panel.

The subset contains the ASCII characters, the middle dot, the right arrow, and the minus sign.
Its `wght` axis is from 400 to 700, and its `opsz` axis is 14. It keeps only the `kern` feature.
Inter has no U+21C4. The system sans font shows that character.
The left, up, and down arrows and the command key symbol show only in keyboard keys, in the monospace font.

Inter has the SIL Open Font License 1.1 with no Reserved Font Name.
`src/systemap/fonts/Inter-OFL.txt` contains the license.
The name table of the subset contains the copyright, the version, and the license URL.
`scripts/inter_subset.py` makes the subset from the npm package inter-ui 4.1.1 and writes `page_font.py`.

Map text with a measured width keeps its font.
The renderer gives each character of a flow label and of a container description a fixed width.
Inter is wider than that width for most characters. Thus these labels use the system sans font:
SF Pro on macOS, Segoe UI on Windows, and the desktop font on Linux.

Card descriptions use Arial. Liberation Sans and Arimo have the same character widths.
The page uses one of them when Arial is not available.
The renderer measures each description with these widths, so a description stays in its card.

A separate SVG figure does not contain Inter. Its sans text uses the system sans font.
On GitHub, the fonts of the computer of the reader show the figures.

The renderer gives each character of a card name 0.6021 em.
DejaVu Sans Mono has 0.60205 em, and JetBrains Mono and Liberation Mono have 0.600 em.
The widths of SF Mono, Menlo, and Consolas are not measured. A measurement is necessary.

The type scale has these sizes in CSS pixels:

- 11px: small labels in capital letters, tags, keyboard keys, and the numbers in rings.
- 12px: secondary text, counts, legends, and identifiers in lists.
- 13px: body text and controls.
- 15px and 17px: the project name, the description of a component, and small titles.
- 19px: the panel title.
- 22px: the question of the view.

Text in sentences is 12px or more. No text on the page is less than 11px.
The phone layout uses 14px and 15px for body text and controls.
Map text uses SVG units and changes size with the zoom. The smallest map text is 11 SVG units.

When the zoom is less than 100 percent, labels become larger (see Map and text).
The tags, the step numbers, and the line with the two ends in the step note use 13.6 SVG units.
This size is the largest card description size.
At Fit on a 1440 by 900 screen, the self map shows card names at 12px or more.
The other map text of the self map shows at 11px or more.
Only the container label OUTSIDE THE PACKAGE is smaller: its box gives room for 10.7px.

In a browser that can do it, the lines of a heading have almost the same length.
The last line of a paragraph does not contain only one short word.

## Sequences

Sequences shows one operation at a time. The toolbar starts with the label Sequence and the sequence button.
Whole route and Steps, the step controls, and End sequence follow.
The full-screen button at the end of the row opens full screen.

The sequence button shows the name of the current sequence and an arrow icon from the icon set.
It has the design of a selected segment: the card color, ink text, and the control radius.
It is not a native drop-down. The button opens the list of sequences under it.

The list has the surface color, the menu radius, and the panel width.
Each row of the list has the design of a row in the panel list.
It gives the small map of the regions, the name, the entry point, and the step count. The current sequence has the accent border.

The list uses the listbox pattern. The arrow keys, Home, and End move the focus.
A letter moves the focus to the next name that starts with that letter.
Enter, Space, or a click selects a sequence. Escape and Tab close the list.
A new sequence keeps Whole route or Steps and starts at step 1.

Whole route shows all the steps of the sequence on the map. Each line has the color of its flow kind
and the rest width. Each step has a number on its line.
The entry point component has a START tag. Cards that the sequence does not use have low contrast.
The route draws in step order.

Steps shows one step. The current step line has the emphasis width and the wider line under it.
The lines of earlier steps have the rest width and full opacity.
The lines of later steps have the rest width and 40 percent opacity.
The legend gives the flow kinds of the route, This step, and After.

The acting component has an ACTS tag.
A measurement component has a MEASURES tag. A note next to the line gives the step number, the artifact,
the two ends, and the step sentence.

The camera keeps the zoom. It moves only when the step is not in view. Then it moves only as far as necessary.

The panel gives the route in order, all sequences with a small map of their regions, and the entry point coverage.
Full screen shows the map and a step bar with the step number, the sentence, and Previous and Next.
The steps are an authored order. They do not record a run of the program.

## Changes

Changes compares two revisions on the map.
The page link `#changes` opens the Changes view. The address keeps `#changes` while the view is open.
The toolbar gives the base and the head revisions. Hold the B key or the Hold B button to show the map without change marks.

A component with changed source has a CHANGED tag. A component with only test changes has a TESTS tag.
A component that imports changed source has an IMPORTS tag.
A flow that must have a new source review has a vermilion dashed line. Other cards and lines have low contrast.
The marks show in a fixed order: the changed cards, the tagged cards, and then the flows.

The panel gives a summary, the changed components, the map changes, and the flows to examine.
It also gives the sequences with a changed step and the limits of the comparison.
Map changes compare the committed model at the merge base with the model of the page.
They have a group each for components, flows, sequences, and rules.

A row gives the item, its changed parts or the rule text,
and the word Added, Removed, or Changed in vermilion. A row for an item on the page selects it on the change map or starts the sequence.
A removed item has a dashed border and no action. A group shows ten rows and the quantity of the other rows.

A selected component with changed source shows its source changes and then its rules, because the change must keep them. The page does not show the judgement findings or the delta lines.
`systemap judgement` and the CI log give them to the maintainer.

## Live map

`systemap live` adds one script to each page that it supplies. The page that `systemap render` writes does not have this script.
Each version of the page has a version number. When the command has a newer version, the script keeps the view of the reader in the session storage of the browser.
Then it loads the page again.

The new page puts back the view (Map, Sequences, or Changes), the layer, the selected component or flow, and the sequence and its step.
It also puts back the camera of the map and of the change map. A camera at Fit stays at Fit for the new window size.
The script identifies a flow by its two components and its artifact, and a sequence by its identifier.
Thus a new flow or sequence in the model does not change the selection.
If the new page does not have the selected item, nothing is selected.
The page puts back the camera one animation frame after the selection, because the framing of the selection occurs in that frame.

An event with the version number of the page does not load the page again.
If the command cannot render a version, the page does not change. A notice at the bottom left gives the first line of the error.
The notice has the status role, so a screen reader reads it.
If the connection to the command breaks, the script closes it. The page does not load again and does not try to connect again.

## Selection and evidence

A selected component has an accent ring. Its flows show at full contrast. Other cards and lines have low contrast.
Structure shows no flow lines after a component selection.

A pointer or keyboard focus on a line shows a preview of that flow. The label of the line then has a thin outline.
A declared flow keeps its dash pattern during selection.
No more than one directional cue moves. The cue does not show a recorded run.

Escape closes the newest item first. The order is the Find dialog, the keyboard keys, the source panel of the commit,
full screen, the sequence, the selection, and then the panel.
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
When the page opens, the cards come in one time, row by row and from left to right, in 360 ms or less.
A theme change fades the colors in 240 ms.
The Find dialog fades in and moves 6px down in 160 ms.

No line has a glow. A wider line under the selected line and the current sequence line marks them:
the accent at 30 percent in Ink, the highlighter in Paper.

Reduce motion is a page setting. It is off on the first visit. When it is on, the page shows the final state with no motion.
The browser keeps the setting. The head script applies the kept setting before the page shows.

The system setting for reduced motion does not change the page. The maintainer made this decision:
the motion shows direction and order, and the page shows it to each reader until that reader stops it.

This decision has an accessibility cost. A reader with a vestibular disorder can set the system setting to stop motion.
On this page, that reader sees the motion until they set Reduce motion.
For this reason, Reduce motion is an icon in the header. The reader can find it on the first screen and set it with one click.

A figure outside the page has no page setting. A figure obeys the system setting.

The source modules are `page.py`, `page_assets.py`, `page_data.py`, `page_script.py`, `page_workspace.py`,
`page_guide.py`, `page_palette.py`, `page_groups.py`, `page_sequences.py`, `page_sequence_script.py`,
`page_present.py`, `page_changes.py`, `page_changes_map.py`, `page_changes_script.py`, `page_phone.py`,
`page_motion.py`, `page_mapview.py`, `page_icons.py`, and `page_font.py`.
The map source modules are `schematic.py`, `schematic_cards.py`, `schematic_change.py`, `schematic_style.py`, `schematic_script.py`, `schematic_labels.py`, and `schematic_relations.py`.
The build removes the comments, line breaks, and indentation from the page styles and scripts.
The browser measurements and test results are in `bench/jev/README.md`.
