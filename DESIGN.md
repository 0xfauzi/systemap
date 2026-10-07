---
name: systemap
description: Authored system maps with evidence for directed relationships.
colors:
  primary: "#fafafa"
  dark-accent: "#fafafa"
  dark-bg: "#08090a"
  dark-surface: "#101014"
  dark-raised: "#19191d"
  dark-line: "#252529"
  dark-line-2: "#424249"
  dark-ink: "#fafafa"
  dark-ink-2: "#bcbcc4"
  dark-ink-3: "#9898a3"
  dark-steel: "#8fb0c4"
  dark-warn: "#d6b14a"
  dark-bad: "#d97b6c"
  light-accent: "#0a0a0a"
  light-bg: "#ffffff"
  light-surface: "#ffffff"
  light-raised: "#f4f4f4"
  light-line: "#e5e5e5"
  light-line-2: "#b8b8bd"
  light-ink: "#0a0a0a"
  light-ink-2: "#525252"
  light-ink-3: "#646464"
  light-steel: "#466c84"
  light-warn: "#7f641d"
  light-bad: "#b5412f"
  clay-accent: "#cf8b6b"
  clay-bg: "#111214"
  clay-surface: "#17181b"
  clay-raised: "#1e1f21"
  clay-line: "#292a2c"
  clay-line-2: "#4d4e52"
  clay-ink: "#fbfcfc"
  clay-ink-2: "#cdcecf"
  clay-ink-3: "#9a9b9d"
  clay-steel: "#82a7ba"
  clay-warn: "#c4a077"
  clay-bad: "#dda5a1"
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
    fontSize: "18px"
    fontWeight: 500
    lineHeight: 1.3
  code-title:
    fontFamily: 'ui-monospace,"SF Mono",SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace'
    fontSize: "19px"
    fontWeight: 500
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
    fontSize: "16px"
    fontWeight: 500
    lineHeight: 1.3
  phone-brand:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "15px"
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: "-0.03em"
  reference-title:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "17px"
    lineHeight: 1.3
  brand:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "15px"
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: "-0.03em"
  reading-title:
    fontFamily: 'ui-sans-serif,system-ui,-apple-system,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    fontSize: "18px"
    lineHeight: 1.3
rounded:
  layer-indicator: "1px"
  control: "6px"
  map-surface: "0px"
  plate: "10 SVG units"
  inspector-detail: "6px"
  standalone-panel: "8px"
spacing:
  desktop-margin: "0px"
  phone-margin: "0.8rem"
  pane-gap: "0px"
  inspector-padding: "1rem"
  section: "1rem"
  control-gap: "0.5rem"
components:
  button:
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.control}"
    padding: "0.4rem 0.7rem"
  button-selected:
    backgroundColor: "{colors.dark-raised}"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.control}"
  search:
    backgroundColor: "{colors.dark-surface}"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.control}"
    padding: "0.5rem 0.7rem"
  inspector:
    backgroundColor: "{colors.dark-bg}"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.map-surface}"
    padding: "{spacing.inspector-padding}"
    width: "300px"
  map-card:
    rounded: "{rounded.plate}"
  standalone-panel:
    backgroundColor: "{colors.dark-surface}"
    textColor: "{colors.dark-ink-2}"
    rounded: "{rounded.standalone-panel}"
    padding: "{spacing.section}"
---

# Design System: systemap

The page shows a software map with Components and Sequences navigation.
A component is a system part. A flow transmits an artifact between components.
A sequence shows authored operation steps. The page does not record execution.

## Appearance

Thin borders, plain controls, and projected plates use the styles from
[Hairline](https://github.com/lucasmarkes/hairline).
The application has its own navigation and layout.
Dark and Light use black, white, and gray surfaces.
Clay uses the terracotta accent from [0xfauzi.com](https://0xfauzi.com).
A first visit uses the device theme. A saved selection replaces that theme.
The Theme menu contains Dark, Light, and Clay. Warm, Graphite, and Paper are not available.

The three themes have the same CSS tokens in `theme.py`.
Accent shows selection and acting components. Steel shows measurement components.
Layer colors identify flow types. Stroke patterns identify evidence states.
External components have dashed borders.

Color is not the only indication of meaning.

## Navigation and layout

The title bar contains the project name, map counts, Reference, and Theme.
The application symbol is a link to the map.
The page has no introduction above the application controls.

On desktops, a 260px navigation panel contains Components and Sequences.
Components contains the search field and component list.
Sequences contains the operation list and step counts.
`Reference` contains review records, rules, commands, `Read the map`, and `Reduce motion`.

The map toolbar contains the layer menu, zoom controls, and Flat, Isometric, and Text view.
A component or flow selection shows a 300px inspector next to the map.
The inspector shows the selected item, its connections, and source evidence.
The map uses the available viewport height.

At widths of 1050px or less, navigation uses 230px.
The inspector follows the map in the document.

At widths of 640px or less, Components and Sequences stay above the map.
Their lists open on selection and close after a component or sequence selection.
Close list gives keyboard focus to the selected navigation control.

The layer control becomes a native selector. Zoom controls use a second row.
Phone controls have a minimum height of 44px.

On phones, Previous and Next control the current sequence step.
The sequence list supplies the operation selection. The diagram is before the step sentence and source information.
Desktop users can see the step list.

An active sequence shows Previous, Next, and End sequence above the map.
A horizontal step list shows each flow and the current step.
The current step sentence shows above the map.
Its disclosure contains measurement components and evidence.
Go to sequence restores the current step after component inspection.
End sequence restores the previous selection, layer, and camera position.

## Projection and text

Flat is the initial view. Isometric changes the same component and flow geometry.
The change ends after 480ms at the specified projection matrix.
A projection control can replace the destination during the change.
With reduced motion, the change occurs immediately.
Projection changes keep the selected item and sequence step.

Saved camera positions contain their projection for restoration in the correct plane.

Component names stay horizontal in the two views.
Displayed names and descriptions use 12 CSS pixels after the camera transform.
When description text overlaps a different component, the map shows component names.
When names overlap, the map shows region names and component counts.

Region labels move apart and stay in the map width.
Region summaries give component, flow, and source module counts from the current model and recorded source data.
A region flow count includes each flow with an endpoint in that region.
Components without a region use a different summary group.
Select a region to read its components at a larger scale.

At a small scale, a selection shows its components with horizontal text.
An active sequence shows its components and flow, with component descriptions when the map has sufficient space.
The other components stay in the model and navigation list.

The inspector and Text view contain full descriptions and source evidence.

Isometric depth shows sequence roles.
Acting components have plates 18 CSS pixels above their initial position.
Measurement components have plates 10 CSS pixels above their initial position.
The text moves with the plate.

An inspection moves its selected plate 6 CSS pixels above its initial position.
The initial border stays at its initial position. Reduced motion keeps these component positions.

The map footer gives the meaning of the plate height for an active sequence.
The isometric diagram names the acting and measurement components in its legend.
Projection changes keep the current step participants in the diagram viewport.

The information below the diagram gives source module counts, entry point counts, and related sequences.
A component selection gives its function. A flow selection gives its artifact, direction, and evidence state.
The information uses model claims and recorded source data without a table for one repository.

System sans fonts show controls and descriptions.
System monospace fonts show identifiers, paths, commands, and finding lines.
The page loads no font files. The title bar uses a 16px project title.
Source paths can use multiple lines. Recorded identifiers keep their full text.

Document figures keep the authored coordinate plane and full card text.

## Selection and evidence

Structure shows no flow lines after component selection.
Other layers show connected flow lines for the selected component.
A selected flow or sequence step shows its flow line.
A pointer or keyboard focus can show a flow preview.
The inspector keeps all connections across layers.

The map shows flow labels only for a selected flow or preview.
A declared flow keeps its dash pattern during selection.
No more than one directional cue moves. Each cycle ends after 1.8 seconds.
The cue does not show recorded execution.
`Reduce motion` stops this cue and all camera animation.

Text view keeps the selected component, flow, and sequence step.
A nested map opens in a dialog above an inert background.
The dialog restores keyboard focus to its opening control when it closes.
Finding identifiers, authored claims, and evidence states keep their meaning.
Source records show missing evidence without a different claim.

The source modules are `page.py`, `page_assets.py`, `page_workspace.py`,
`page_atlas.py`, `schematic_style.py`, `schematic_script.py`, and `schematic_relations.py`.
The browser measurements and test results are in `bench/jev/README.md`.
