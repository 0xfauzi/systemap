# Map UI implementation and checks

The page generator no longer uses the rejected operations-first interface.
The replacement uses the refined prototype: an authored spatial map, compact
controls, and an inspector adjacent to the map. Text view gives a text alternative on
small screens. The production page is [docs/map/index.html](map/index.html).

The audit used main at `56716e9`, with the TypeScript merge included.
The implementation team examined each recommendation as a claim.
Previous source line numbers were not implementation instructions.

The final integration uses main at `c32dae9`.
It keeps the accuracy changes from main.
Source reviews use the source content and the authored claim.
Imports give structural evidence. Exact answers must have current
evidence. Explicit family policies stay visible as policies.

## Implemented behavior

A component contains modules that have one function.
A flow shows something that goes between components.
A layer selects the relationships that answer one question.
A sequence gives the steps of an authored operation.
The page's map-reading disclosure gives these terms.

The map keeps authored positions.
A selected relationship keeps its direction, artifact, layer, and evidence
through endpoint navigation. Declared relationships keep their declared label.
Structural evidence and source review keep their specified evidence states.
The inspector shows unresolved references and changed claims.
It also shows incoming and outgoing rows, source records, governing rules, and
recorded decisions.

Only the selected relationship has a moving cue.
Its solid route stays visible.
Each evidence state keeps its specified pattern.
System reduced motion and the page's Reduce control remove movement.
Other relationships keep their evidence patterns and readable labels.

Sequence state stays unchanged through inspection, Fit, Back, and header
navigation. At the end of a sequence, the prior selection and layer are active
again. Nested maps keep their parent context.
Focus goes back to the opening control.
The finder shows matches by component, function, or module.
It also shows an empty search result.

The page shows stored extraction provenance.
It does not claim knowledge of the working tree.
Source comparisons distinguish empty results, incorrect references, unknown
modules, and changes to public names.
Import connections do not show function-level reach.
The page keeps judgement finding identifiers.
Commands stay as terminal instructions.

The replacement has no runtime dependency or network fetch.
SVG components use flat fills.
The selected palettes and measured text contrast give the specified hierarchy.
The implementation does not include an isometric presentation or a different
control to share views. The component links operate correctly.
Malformed links show recovery feedback.

## Source responsibilities

| Responsibility | Source |
| --- | --- |
| Page composition, provenance, and review | `src/systemap/page.py` |
| Responsive layout and appearance | `src/systemap/page_assets.py` |
| Text view and viewport miniature | `src/systemap/page_atlas.py` |
| Source and comparison payload | `src/systemap/page_data.py` |
| Finder, sequences, nested maps, and details | `src/systemap/page_script.py` |
| SVG scene and metadata | `src/systemap/schematic.py` |
| Component geometry and styling | `src/systemap/schematic_cards.py`, `schematic_style.py` |
| Selection, directed flows, and focus | `src/systemap/schematic_relations.py` |
| Camera, framing, and serialized scene | `src/systemap/schematic_script.py` |
| Comparison error handling | `src/systemap/change.py`, `cli.py` |

`map/model.py` gives each new production module a component claim.
DESIGN.md and `.impeccable/design.json` record the implemented colors,
typography, and controls.

## Measured acceptance

The checks specified these acceptance limits before execution:

- Zero document overflow at widths of 390, 768, and 1440 pixels.

- Zero inspector overlap.

- A text contrast ratio of at least 4.5:1.

- Phone HTML controls of at least 44 pixels.

- A local performance threshold of 200 ms.

The sample-page size test keeps its 300 KiB limit.

Browser measurements found zero horizontal overflow at the specified widths and
the native 847-pixel viewport. The desktop inspector is 340 pixels wide.
The clearance between columns is 12 pixels.
At a viewport size of 1440 by 1000, the map starts 198.67 pixels from the top.

Phone reading selection scrolls the inspector into view and focuses its heading.
Visible phone HTML controls meet the 44-pixel target.
The fitted SVG gives an overview.
Text view gives the detailed alternative.

The rendered contrast probe examined 281 text records per theme.
The minimum ratios were 5.34:1 for Warm, 4.56:1 for Graphite, and 5.00:1 for
Paper. The probe includes selected components and warnings.
The local raw results are in
`output/playwright/ui-audit/rendered-contrast.json`.
The PR does not include these results.

The independent visual inspection found a camera defect.
The SVG's CSS rectangle included unused space outside its drawable viewBox.
A regression experiment found four incorrect cases before the correction.
Framing uses the intersection of the visible area and the native viewBox.
The inspection also found snapshot provenance text that was too small.
The font size changed from 10 to 12 pixels.

The reviewer opened the corrected captures and accepted the two corrections.
The two endpoints, their system functions, the selected route, and its artifact label stay
visible on desktop and tablet. The corrected tablet capture is 768 by 1024.
All nine drawable-area regression cases meet their acceptance rules.
This decision applies to those corrections.
It is not a full accessibility certification.

## Local performance experiment

The probe compares the generator at `56716e9` with the replacement on the same
inputs. A larger recorded fixture has 27 components and 144 module records.
Each completed case uses five reloads and five keyboard selections.
The times are medians in milliseconds.
The sizes are uncompressed HTML bytes.

| Case | Load | Selection | Bytes |
| --- | ---: | ---: | ---: |
| Committed generator, self map | 30.0 | 4.3 | 195056 |
| Replacement, self map | 29.8 | 4.8 | 382533 |
| Committed generator, larger fixture | 24.6 | 3.5 | 181265 |
| Replacement, larger fixture | 28.4 | 4.2 | 312359 |


All completed local observations were less than the recorded threshold.
The maximum replacement load was 33.3 ms.
The maximum selection time was 5.5 ms.
These results do not show a speed improvement.
The larger page loads more slowly, and the output is larger.

The initial pointer experiment did not complete because the target moved.
The completed keyboard experiment is not field Interaction to Next Paint.
That metric measures responsiveness across real visits.
See the [metric definition](https://web.dev/articles/inp).

These observations came before the final framing corrections, provenance-font
corrections, and integration with main.
Local inputs, scripts, and results are in `output/playwright/ui-audit/`.
The PR does not include these files.
The 300 KiB sample-page limit does not apply to the larger self-map.

## Checks and limits

Regression tests include these cases:

- Directed flows and reverse-direction flows.

- Layer reading sets and focus restoration.

- Nested maps and sequence state.

- Unknown source records and comparison details.

- Drawable-area framing.

Browser captures include desktop, tablet, phone map, phone reading, and the
native app viewport. The local captures are in `output/playwright/ui-audit/`.
The PR does not include them.

The final integration run completed with 540 successful tests and one skipped
test. Mypy found no issues in 53 source files.
Pre-commit checks include staged changes and tracked files.
Refresh completed. Check found all 53 modules mapped and routes with no
geometry findings. Strict judgement had no open findings and seven answered
findings. Extraction and rendering checks found the output current.

Three independent agents examined the main integration, flow evidence, and
recorded single-module reasons. They found that an audit-family policy can
crash the page's mechanical review. The page accepts only recognized
mechanical family kinds. Regression cases compare accepted reasons, open
findings, and review notices with the CLI's decisions.

The team renewed source reviews only for examined claims.
The obsolete single-module answer for Page was removed after the module split.
The modules have different responsibilities.

The first CI run completed all Linux and macOS test jobs and all six
installation jobs. The two Windows test jobs found fixture errors.
CRLF newlines caused a difference between a raw-byte hash and the extractor's
normalized source hash. The default text encoding did not write Unicode HTML.
The fixtures specify LF newlines and UTF-8.
All ten tests in the affected files completed successfully on the local machine.

New helpers meet the cognitive-complexity limit.
The page builder changed from 45 to 17.
The SVG renderer stays at 156.
The two functions did not increase in complexity.
New Python files have fewer than 800 lines.
The cyclomatic-complexity ratchet accepts the changes.

The design detector gives palette, compact-heading, and map-inset
advisories. These items follow the selected design.
Its stroke-width warning concerns SVG styling.
The independent reviewer did not request changes to those items.

Native browser zoom, text enlargement, spoken screen-reader operation, and
physical touch are unverified. The examined interactions produced no browser
warning or error logs. This does not show the results of a full audit of unsuccessful requests.
The automated checks and captures show the tested behavior.
They do not give results for every device or assistive technology.
