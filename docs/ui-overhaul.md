# Map UI implementation and verification

The rejected operations-first interface has been removed from the page
generator. The replacement follows the refined prototype: an authored spatial
map, compact task controls and a separate inspector. Reading view supplies a
text alternative on small screens. The generated production page is
[docs/map/index.html](map/index.html).

The audit was reassessed against main at `56716e9`, including the intervening
TypeScript merge. Recommendations were treated as claims to verify. Existing
source line numbers were not used as implementation instructions.

The final integration uses main at `c32dae9`. Its accuracy changes are preserved:
source reviews bind to source content and the exact authored claim, imports supply
structural evidence, and recorded exact answers require current evidence.
Explicit family policies remain visible as policies.

## Implemented behavior

A card represents a part whose modules do one job. A flow represents something
travelling between parts. A layer selects relationships that answer one
question. A journey describes an authored operation step by step. These terms
are defined in the page's map-reading disclosure.

The map preserves authored positions. Selecting a relationship keeps its exact
direction, artifact, layer and evidence through endpoint navigation. Declared
relationships remain labelled as declared. Structural evidence stays distinct
from source review. The inspector exposes unresolved references and changed
claims, alongside incoming and outgoing rows, source records, governing rules
and recorded decisions.

Only the selected relationship has a moving cue. Its solid route remains
visible, and evidence patterns remain distinct. System reduced motion and the
page's Reduce control both remove movement. Other relationships retain their
evidence patterns and readable labels.

Journey state survives inspection, Fit, Back and header navigation. Ending a
journey restores the prior selection and layer. Nested maps preserve their
parent context and return focus to the actual opening control. The finder
explains matches by part, purpose or module and reports an empty result.

The page describes stored extraction provenance rather than claiming that it
knows the current working tree. Source comparisons distinguish empty results,
invalid references, unknown modules and changes to public names. Import
connections do not claim function-level reach. Exact judgement finding text is
preserved. Commands remain terminal instructions.

The replacement has no runtime dependency or network fetch. SVG cards use flat
fills because the chosen palettes and measured text contrast already express
the required hierarchy. An isometric presentation and a separate view-sharing
control were not added. Existing part links work, and malformed links display
recovery feedback.

## Current source responsibilities

| Responsibility | Source |
| --- | --- |
| Page composition, provenance and review | `src/systemap/page.py` |
| Responsive layout and appearance | `src/systemap/page_assets.py` |
| Reading view and viewport miniature | `src/systemap/page_atlas.py` |
| Source and comparison payload | `src/systemap/page_data.py` |
| Finder, journeys, nested maps and details | `src/systemap/page_script.py` |
| SVG scene and metadata | `src/systemap/schematic.py` |
| Card geometry and styling | `src/systemap/schematic_cards.py`, `schematic_style.py` |
| Selection, exact flows and focus | `src/systemap/schematic_relations.py` |
| Camera, framing and serialized scene | `src/systemap/schematic_script.py` |
| Comparison failure handling | `src/systemap/change.py`, `cli.py` |

New production modules are assigned to cards in `map/model.py`. DESIGN.md and
`.impeccable/design.json` record the implemented colors, typography and controls.

## Measured acceptance

The checks required zero document overflow at 390, 768 and 1440 pixels wide,
zero inspector overlap, at least 4.5:1 text contrast, and 44-pixel HTML controls
on phones. The local performance experiment stated a 200 ms threshold before
running. The existing sample-page size test retains its 300 KiB limit.

Browser measurements found zero horizontal overflow at the tested widths and
the native 847-pixel viewport. The desktop inspector is 340 pixels wide with a
12-pixel gap. The map starts 198.67 pixels from the top at 1440 by 1000.
Phone reading selection scrolls the inspector into view and
focuses its heading. Visible phone HTML controls meet the 44-pixel target.
The fitted SVG is an overview; Reading view supplies the detailed alternative.

The rendered contrast probe inspected 281 text records per theme. Its lowest
ratios were 5.34:1 for Warm, 4.56:1 for Graphite and 5.00:1 for Paper. The probe
includes selected cards and warnings. Raw results are kept locally in
`output/playwright/ui-audit/rendered-contrast.json` and are excluded from the PR.

The independent visual review found a camera defect: the SVG's CSS rectangle
included unused space outside its drawable viewBox. A regression experiment
failed four cases before the fix. Framing now intersects the visible area with
the native viewBox. The review also found undersized snapshot provenance; its
font size increased from 10 to 12 pixels.

The reviewer opened the corrected captures and accepted both fixes. Both
endpoints, their purposes, the selected route and its artifact label remain
visible on desktop and tablet. The corrected tablet capture is 768 by 1024.
All nine drawable-area regression cases pass. The verdict applies to these
corrections, not a complete accessibility certification.

## Local performance experiment

The probe compares the generator at `56716e9` with the replacement using identical
inputs. A larger recorded fixture has 27 cards and 144 module records.
Each completed case uses five reloads and five keyboard selections. Times below
are medians in milliseconds; sizes are uncompressed HTML bytes.

| Case | Load | Selection | Bytes |
| --- | ---: | ---: | ---: |
| Committed generator, self map | 30.0 | 4.3 | 195056 |
| Replacement, self map | 29.8 | 4.8 | 382533 |
| Committed generator, larger fixture | 24.6 | 3.5 | 181265 |
| Replacement, larger fixture | 28.4 | 4.2 | 312359 |

All completed local observations were below the stated threshold. The largest
observed replacement load was 33.3 ms; selection was 5.5 ms. These results do
not establish a speed improvement: the larger page loads more slowly and the
output grows. The initial pointer experiment failed on a moving target and was
incomplete. The completed keyboard experiment is not field Interaction to Next
Paint, which measures responsiveness across real visits. See the
[metric definition](https://web.dev/articles/inp).

These observations precede the final framing, provenance-font corrections and
integration with main. The raw inputs, scripts and results are kept locally in
`output/playwright/ui-audit/` and are excluded from the PR.
The sample-page size gate does not impose a 300 KiB limit on the richer self map.

## Verification and limits

Regression tests cover exact and reverse-direction flows, layer reading sets,
focus restoration, nested maps, journey state, unknown source records,
comparison details and drawable-area framing. Browser captures cover desktop,
tablet, phone map, phone reading and the native app viewport. They are saved in
`output/playwright/ui-audit/` locally and are excluded from the PR.

The final integration run passed 540 tests with one skipped, and mypy across
53 source files. Pre-commit checks cover the staged changes and tracked files.
Refresh completed, check reported all 53 modules mapped with clean routes, and
strict judgement reported nothing to confirm with seven answered findings.
Extraction and rendering checks confirmed the generated output is current.

Three independent agents reviewed the main integration, flow evidence and
recorded single-module reasons. Their review found an audit-family policy could
crash the page's mechanical review. The page now accepts only recognized
mechanical family kinds. Regression cases compare its accepted reasons, open
findings and review notices with the CLI's decisions. Source reviews were renewed
only for the checked claims; the obsolete single-module answer for Page was
removed after its modules were split by responsibility.

The first CI run passed the Linux and macOS test jobs and all six installation
jobs. Both Windows test jobs exposed fixture defaults: CRLF newlines made a
raw-byte hash assertion differ from the extractor's normalized source hash, and
the default text encoding could not write Unicode HTML. The fixtures now specify
LF newlines and UTF-8. All ten tests in the two affected files passed locally.

New helpers stay within the cognitive-complexity limit. The existing
page builder improves from 45 to 17; the existing SVG renderer remains at 156.
Those existing functions were not increased. New Python files remain below
800 lines, and the cyclomatic-complexity ratchet passes.

The design detector's remaining palette, compact-heading and map-inset
advisories reflect the selected direction. Its stroke-width warning concerns
SVG styling. The independent reviewer did not request changes for those items.

Native browser zoom, text enlargement, spoken screen-reader use and physical
touch remain unverified. Checked interactions produced no browser warning or
error logs, but this is not a complete failed-request audit. The automated
checks and supplied captures establish the tested behavior. They do not certify
every device or assistive technology.
