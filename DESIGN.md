---
name: systemap
description: Authored system maps with exact relationship evidence.
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

The authored spatial map is the main artefact. A card represents a part of the
system. A flow names something passed between parts. The inspector explains a
selected part or exact flow beside the map. Reading view presents the same
information as text.

The selected direction follows refined prototype revision 5. It uses compact
controls, flat surfaces and visible card purposes. The user rejected the former
operations-first atlas layout. These specifications describe the implementation;
they do not certify runtime performance or accessibility.

## Colors

Warm is the default scheme. Graphite provides a cooler dark scheme. Paper
provides a light scheme. A first visit follows a native light preference;
a stored appearance choice takes precedence. Each scheme has the same roles in
[theme.py](src/systemap/theme.py): background, surface, raised surface, borders,
three text levels, accent, measurement, warning and error.

Accent identifies selection, focus and the part acting in a journey step.
Steel identifies the part measuring that step. Layer hues identify a question
about the system. Layer hues come from the tables in `theme.py`. A selected
relationship uses accent while its inspector retains the layer name. Kind
marks distinguish agents, tools and context cards by shape. Evidence also has
a stroke pattern, so meaning does not depend on colour alone.

## Typography

System sans fonts carry explanations and controls. System monospace fonts carry
identifiers, paths, commands and finding lines. The page loads no font files.
Inspector prose uses the `inspector-body` role. Part purposes remain separate
from code titles.

The `snapshot` and `metadata` roles describe the current compact header text.
The project title has its own role. Brand text becomes smaller on phones.
Reference and reading titles identify sections below the map and in reading
view. These are component roles, not a size progression for every heading.

The SVG uses text at 11 units and part identifiers at 11.5 units before the map
transform. Those values do not guarantee a readable physical size when the
whole map is fitted. Reading view supplies the same parts and flows at text
size. Keep identifiers intact and allow long source paths to wrap.

## Layout

Desktop uses a flexible map column and a fixed inspector column (340px), with a
gap (12px). The inspector sticks within the viewport and scrolls independently.
The map height is `calc(100vh - 220px)`, bounded by a minimum (460px) and maximum
(1100px). Definitions are a disclosure above compact layer, view and journey
controls. Reference material follows the map.

At widths up to 1050px, the inspector moves below the map and loses its sticky
position. The map uses a viewport-relative height (70vh), with a minimum
(400px). At widths up to 640px, a native layer selector replaces segmented
buttons. The map follows its authored aspect ratio. Reference and reading
columns become single columns. Phone controls have a minimum height (44px).
Zoom buttons also have a minimum width (44px).

## Elevation & Depth

The map and inspector use background differences and thin borders for
separation. The map has a faint dot grid with a repeat interval (18px).
Selection adds an accent border and an inner vertical mark. A nested map opens
in a dialog above an inert background. That dialog alone uses a broad shadow;
its exact value is recorded in the sidecar.

## Shapes

Controls and spatial cards use the `control` radius. Map and inspector surfaces
use the `map-surface` radius. Inspector notes and endpoint buttons use the
`inspector-detail` radius. Layer hue indicators use the `layer-indicator` radius.
A panel accompanying a standalone figure uses the `standalone-panel` radius.
Cards that contain a nested map have a second card offset behind them (3 SVG
units). Outside actors retain dashed borders.

## Components

Layer buttons combine a text label and hue indicator. Pressed state adds a
surface fill and border. Hover adds a raised fill. Keyboard focus has a visible
accent outline. The phone selector exposes the same layer state.

The Fit control restores the complete map view. Its miniature shows authored
part positions and the visible area. Journey controls advance an authored
sequence. Back to journey restores the current step after inspection. End
restores the selection and view that preceded the journey.

Flow labels and inspector choices select one exact directed relationship.
The inspector shows the artifact, endpoints, layer, evidence and explanation
before source details. Declared flows retain dashes during selection. At most
one directional cue moves. Its cycle is 1.8 seconds. Native reduced motion or
the page preference disables motion and transitions while retaining static
selection and evidence marks.

Search reports why a part matched. Part choices retain their plain purpose.
Connected parts and source records use disclosures. Part notes remain visible
before those disclosures. Nested maps preserve the opening control for focus
restoration. Reading view retains the selected part, flow and journey.

## Do's and Don'ts

- Do preserve authored positions when switching layers or reading views.
- Do keep a part's purpose readable while inspecting its relationships.
- Do preserve exact finding lines and distinguish authored claims from facts.
- Do keep selection, evidence and journey roles distinguishable without motion.
- Don't restore the rejected operations-first atlas composition.
- Don't imply that directional animation records an execution.
- Don't hide missing evidence or convert a declared flow to observed evidence.

The implementation sources are [page_assets.py](src/systemap/page_assets.py),
[schematic_style.py](src/systemap/schematic_style.py),
[schematic_cards.py](src/systemap/schematic_cards.py),
[schematic_script.py](src/systemap/schematic_script.py) and
[page_atlas.py](src/systemap/page_atlas.py). Update these specifications when
those sources change.
