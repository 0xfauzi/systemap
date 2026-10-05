---
name: systemap
description: Authored system maps with evidence for directed relationships.
colors:
  primary: "#e5a84f"
  warm-bg: "#161310"
  warm-surface: "#1e1a15"
  warm-raised: "#27221a"
  warm-line: "#2e2820"
  warm-line-2: "#4a4237"
  warm-ink: "#ece5d8"
  warm-ink-2: "#c4b9a4"
  warm-ink-3: "#a2967f"
  warm-steel: "#82a7ba"
  warm-warn: "#d9b036"
  warm-bad: "#e26d5a"
  graphite-accent: "#e0a458"
  graphite-bg: "#121417"
  graphite-surface: "#181b1f"
  graphite-raised: "#1f2329"
  graphite-line: "#262b32"
  graphite-line-2: "#3a4149"
  graphite-ink: "#e6e4df"
  graphite-ink-2: "#b3b1aa"
  graphite-ink-3: "#868b93"
  graphite-steel: "#8fb0c4"
  graphite-warn: "#d6b14a"
  graphite-bad: "#d97b6c"
  paper-accent: "#905c1a"
  paper-bg: "#f4f2ee"
  paper-surface: "#ffffff"
  paper-raised: "#ebe9e4"
  paper-line: "#d9d6cf"
  paper-line-2: "#b9b5ac"
  paper-ink: "#1d2024"
  paper-ink-2: "#55534d"
  paper-ink-3: "#646870"
  paper-steel: "#466c84"
  paper-warn: "#7f641d"
  paper-bad: "#b5412f"
typography:
  body:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "14px"
    lineHeight: 1.5
  inspector-body:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "13px"
    lineHeight: 1.6
  inspector-title:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "19px"
    fontWeight: 600
    lineHeight: 1.3
  code-title:
    fontFamily: 'ui-monospace,"SF Mono",SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace'
    fontSize: "19px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.02em"
  label:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "12px"
    lineHeight: 1.5
  snapshot:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "12px"
    lineHeight: 1.5
  metadata:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "11px"
    lineHeight: 1.5
  project-title:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.3
  phone-brand:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "-0.03em"
  reference-title:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "17px"
    lineHeight: 1.3
  brand:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "-0.03em"
  reading-title:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "18px"
    lineHeight: 1.3
rounded:
  layer-indicator: "1px"
  control: "4px"
  map-surface: "5px"
  inspector-detail: "6px"
  standalone-panel: "8px"
spacing:
  desktop-margin: "1.25rem"
  phone-margin: "0.8rem"
  pane-gap: "12px"
  inspector-padding: "1.1rem"
  section: "1rem"
  control-gap: "0.5rem"
components:
  button:
    textColor: "{colors.warm-ink}"
    rounded: "{rounded.control}"
    padding: "0.4rem 0.7rem"
  button-selected:
    backgroundColor: "{colors.warm-raised}"
    textColor: "{colors.warm-ink}"
    rounded: "{rounded.control}"
  search:
    backgroundColor: "{colors.warm-surface}"
    textColor: "{colors.warm-ink}"
    rounded: "{rounded.control}"
    padding: "0.5rem 0.7rem"
  inspector:
    backgroundColor: "{colors.warm-surface}"
    textColor: "{colors.warm-ink}"
    rounded: "{rounded.map-surface}"
    padding: "{spacing.inspector-padding}"
    width: "340px"
  map-card:
    rounded: "{rounded.control}"
  standalone-panel:
    backgroundColor: "{colors.warm-surface}"
    textColor: "{colors.warm-ink-2}"
    rounded: "{rounded.standalone-panel}"
    padding: "{spacing.section}"
---

# Design System: systemap

## Overview

The authored spatial map is the main artifact. A component shows a system part.
A flow shows something that goes between parts.
The inspector shows a selected part or directed flow adjacent to the map.
Text view gives the same information as text.

The design uses refined prototype revision 5. It has compact controls, flat
surfaces, and visible part functions. The user rejected the operations-first
atlas layout. These specifications give the implemented design.
They do not give measurements of runtime performance or accessibility.

## Colors

Warm is the default scheme. Graphite is a cooler dark scheme.
Paper is a light scheme. On a first visit, the page uses a native light
preference. A stored appearance selection has precedence over that preference.
Each scheme has the same roles in [theme.py](src/systemap/theme.py):
background, surface, raised surface, borders, three text levels, accent,
measurement, warning, and error.

Accent shows selection, focus, and the part that acts in a sequence step.
Steel shows the part that measures that step.
Layer hues show a question about the system.
The tables in `theme.py` contain the layer hues.
A selected relationship uses accent. Its inspector keeps the layer name.

Kind marks use shapes to show agents, tools, and context components.
A stroke pattern shows the evidence state.
Thus, color is not the only indication of meaning.

## Typography

System sans fonts show explanations and controls.
System monospace fonts show identifiers, paths, commands, and finding lines.
The page loads no font files.
Inspector text uses the `inspector-body` role.
Part functions and code titles use different text roles.

The `snapshot` and `metadata` roles show compact header text.
The project title has a different role.
The brand text is smaller on phones.
Reference and reading titles show sections below the map and in reading
view. These roles do not specify one size sequence for all headings.

The SVG uses 11 units for text and 11.5 units for part identifiers before the
map transform. These values do not show the physical text size at Fit.
Text view gives the same parts and flows at text size.
Keep full identifiers. Show long source paths on more than one line.

## Layout

The desktop layout has a flexible map column and a fixed inspector column
(340px). The clearance between columns is 12px.
The inspector stays in the viewport and scrolls independently.
The map height is `calc(100vh - 220px)`.
Its minimum is 460px. Its maximum is 1100px.

A disclosure above the controls gives the map terms.
The compact controls select layers, views, and sequences.
Reference material is below the map.

At widths of 1050px or less, the inspector is below the map and has no sticky
position. The map height is 70vh, with a minimum of 400px.
At widths of 640px or less, a native layer selector replaces the segmented
buttons. The map uses its authored aspect ratio.
Reference and reading sections use single columns.

Phone controls have a minimum height of 44px.
Zoom buttons also have a minimum width of 44px.

## Elevation & Depth

The map and inspector use different backgrounds and thin borders for separation.
The map has a dot grid with an interval of 18px.
Selection adds an accent border and an inner vertical mark.
A nested map opens in a dialog above an inert background.
Only that dialog has a broad shadow.
The sidecar records the specified shadow value.

## Shapes

Controls and spatial components use the `control` radius.
Map and inspector surfaces use the `map-surface` radius.
Inspector notes and endpoint buttons use the `inspector-detail` radius.
Layer hue indicators use the `layer-indicator` radius.
A standalone figure panel uses the `standalone-panel` radius.

A nested-map component has a second card behind it, with an offset of 3 SVG units.
Outside actors keep dashed borders.

## Components

Layer buttons have a text label and hue indicator.
The pressed state adds a surface fill and border.
Hover adds a raised fill.
Keyboard focus has a visible accent outline.
The phone selector gives the same layer state.

The Fit control shows the full map.
Its miniature shows authored part positions and the visible area.
Sequence controls move through the authored sequence.
Back to sequence shows the selected step after an inspection.
End restores the selection and view from before the sequence.

Flow labels and inspector choices select one directed relationship.
The inspector first shows the artifact, endpoints, layer, evidence, and
explanation. Source details come after these fields.
Declared flows keep their dashes during selection.
No more than one directional cue moves.
Its cycle is 1.8 seconds.

Native reduced motion or the page preference stops motion and transitions.
Static selection and evidence marks stay visible.

Search shows why a part matched.
Part choices keep their plain function text.
Connected parts and source records use disclosures.
Part notes stay visible before these disclosures.
Nested maps keep the opening control for focus restoration.
Text view keeps the selected part, flow, and sequence.

## Design rules

- Keep authored positions when you change the layer or view.

- Keep a part's function readable during relationship inspection.

- Do not change finding identifiers.

- Show authored claims and facts in different fields.

- Keep selection, evidence, and sequence roles clear without motion.

- Do not use the rejected operations-first atlas layout.

- Do not suggest that a directional animation records execution.

- Do not hide missing evidence.

- Do not change a declared flow to observed evidence.

The implementation sources are [page_assets.py](src/systemap/page_assets.py),
[schematic_style.py](src/systemap/schematic_style.py),
[schematic_cards.py](src/systemap/schematic_cards.py),
[schematic_script.py](src/systemap/schematic_script.py), and
[page_atlas.py](src/systemap/page_atlas.py).
When those sources change, update these specifications.
