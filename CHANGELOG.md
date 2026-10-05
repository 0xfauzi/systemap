# Changelog

Release notes give behavior at the named version.
Historical command output and configuration identifiers keep their recorded text.
A component is a system part with module claims in the map.
A sequence is an ordered set of map steps.
An entry point starts work in the system.
A layer is a filtered view of the map.

## Unreleased

- All user interface text, command explanations, map prose, and documentation use the ASD-STE100 language policy.
  Agents must use Issue 9 for names, sequences, and all map updates.
  Coding-agent requests and cache keys contain the packaged policy.
  Historical evidence, commands, and schema identifiers keep their identities.

- Sequence framing uses the full map width after controls change.
  Selected component cards no longer clip at the right edge in the examined desktop and phone sequences.
  Arrow hover changes highlights without replacing the selected-relationship inspector.
  Sequence rows distinguish a missing display label from a missing source entry point.

- The TypeScript reader expands `${configDir}` at the start of `baseUrl`, `paths`, `rootDir`, or `outDir` values.
  The value becomes the folder of the top-level `tsconfig.json` throughout the `extends` chain.
  Previously, shared configurations such as `@sindresorhus/tsconfig` left `outDir` inside `node_modules`.
  Mapping a compiled package entry to source then needed guesses of `src/` or `source/`.
  Measurement against `tsc --showConfig` 7.0.2 showed that the variable applies only at the start of a value.

- With `rootDir` unset, the TypeScript reader no longer guesses `src/` or the repository root.
  It calculates the root as the project's `tsc` does, measured on 5.9.3, 6.0.3, and 7.0.2.
  TypeScript 5 uses the longest common folder of input files selected by `files`, `include`, and `exclude`.
  Version 6 and later use the `tsconfig.json` folder.
  `composite` uses that folder on every version.
  The reader finds the version in `node_modules/typescript`, then `package.json`.

  Without either, it tries both roots and maps a compiled target only when one fits and the other does not.

- Authored text follows the writing rules in `AGENTS.md`.
  Literal phrases replace metaphors, and terms have definitions at first use.
  Filtered views are now called layers in the page, `describe`, `figure`, and skill.
  Previously, some text used readings and some used layers, although only layers had a definition.
  The first line of `systemap suggest` now reads `a first grouping to revise, not the answer`.
  `README.md`, `docs/reference.md`, `docs/benchmarks.md`, `bench/jev/README.md`, `explain.py`, `page.py`, and the skill use the same rules.

  No check rule, judgement finding, or delta finding changed its identifier text.

- Each heading in `README.md` and `docs/reference.md` is a question answered by its section.
  Both pages give their scope and order before the details.

## 1.2.0 - 2026-09-20

This release adds commands that read the map: agent-written sequences, plan comparisons, and system history.
Finding explanations tell the reader what each finding means.
Two proposed features failed their experiments and were not implemented.
Their recorded measurements are in `bench/jev/README.md`.

- `delta` ends with components adjacent to the change.
  A flow connects each listed component to the component with most changes.
  This is context, not a claim about additional failures.
  Before implementation, measurement over 359 merged pull requests gave a median of 6 components and a 72% changed-component hit rate.
  Following the starting component's imports gave 20 components for 77%.
  No context prints when the starting component connects to more than a third of the map.

  This removes context for 18% of pull requests and decreases the hit rate by 3 points (`bench/jev/near.py`).

- `systemap journeys` writes one sequence for a group of entry points of one kind in a component.
  The sequence names the component in `starts`, which covers all its entry points.
  Coverage of Mealie uses two agent runs instead of sixty-five.
  Before integration, eight of nine groups across Mealie, paperless-ngx, and Poetry gave sequences accepted by the map.
  The acceptance rule was seven in ten (`bench/jev/group_journeys.py`).

- The `systemap history --by-card` experiment failed and the feature was not implemented.
  Each of the three fastest-growing components had to show a feature commit on at least three of four repositories.
  Two repositories passed.
  The aggregate showed work where a system grew, but found nothing useful where it did not (`bench/jev/by_card.py`).

- `systemap --help` gives one sentence per command.
  Full command behavior and options are in each command's `--help`.
  `docs/reference.md` now uses short command descriptions instead of one long table cell.

- A model module can import modules in its directory.
  Its directory is on the path during execution.
  Imported modules are removed afterwards so the next run reads disk content at execution.
  A map can keep sequences or region components in files adjacent to the model.
  systemap's own map uses this structure.

- `systemap history --since --every` samples one commit per window.
  It reads facts from Git, caches them, and uses component assignments in the selected map for each sample.
  Each window names changes and the commits that added new modules.
  Before implementation, a year of Mealie gave 25 samples in 29 seconds cold and less than a second warm.
  The time limit was five minutes.
  All five largest windows showed a change visible in their commits, against a required three (`bench/jev/history_eval.py`).

- `check`, `judgement`, `delta`, and `audit` add two explanation rows below the first finding of each kind.
  The rows give the consequence for the map and the necessary action.
  Finding text stays unchanged, so existing answers continue to work.
  Each kind has one explanation per report.
  `--brief` does not include the explanation rows.

- `systemap explain "<kind>"` gives the meaning, consequence, and action for one kind.
  Without a kind, it lists every kind that systemap prints.

- Pull-request comments give the same explanations once per kind in a details block below the findings.

- `AGENTS.md` gives systemap's writing rules and feature decision process.
  It specifies an acceptance number before implementation and a record of unsuccessful experiments.

- `systemap plan "<task>"` names components the work will probably change.
  It also gives their adjacent flows, sequences, and rules.
  `--check <id> --base <ref>` compares the plan with changed components and shows each changed component outside the plan.
  Over 80 recorded bug reports, the selected threshold covered 86% of components changed by fixes while naming 2.1 components.
  On a repository excluded from threshold selection, it covered 71% while naming 2.1.
  The acceptance rule was 70% coverage with at most 2 extra components (`bench/jev/plan_eval.py`).

- `systemap ripple` failed its experiment and was not implemented.
  The starting component owned the file with the most changes in a pull request.
  No map traversal found the request's other changed components within 10 points of import recall at half the list size.
  Five traversals were measured over 366 pull requests (`bench/jev/ripple.py`).

- `systemap journeys` writes a sequence for an entry point with no sequence start.
  The agent in `[agent] command` reads source from that entry point and gives components and a sentence for each step.
  systemap compares each step with the map.
  It rejects steps that name missing components or trace missing flows.
  Accepted sequences are written with `drafted=True`.
  `judgement` prints `drafted journey` until the mark is removed.

  Without a configured command, no agent runs and the command lists entry points without sequences.

- The first sequence proposal used imports alone.
  Its component overlap with manually written sequences was 0.28 against a required 0.60.
  The console-script module imported the full system.
  This proposal was not released.
  `bench/jev/propose.py` and `paths.py` keep the method and score calculation.

- `systemap extract` finds framework entry points.
  Routes include FastAPI, Flask, and Django `urlpatterns`.
  Commands include click, typer, cleo, and Django management commands.
  It also finds Celery tasks, Poetry scripts, and plugin hooks.
  Manual inspection found 29 entry points confirmed by source among 30 new records across seven maps.
  `judgement` asks for a sequence from each entry point.

  Four or more of one kind in a component become one grouped finding.

- `systemap describe` ends with each sequence's steps, start, and evidence limits.
  It shows steps without import evidence as "on trust", unread agent drafts, and the number of covered entry points.
  The page gives the same information below each step.

- One function calculates entry-point coverage for `judgement`, `describe`, and `journeys`.
  A sequence covers an entry point through `starts`, or through its whole-word name as before.

- `Journey` can name its entry point with `starts="GET /recipes"`.
  `judgement` treats that entry point as covered.
  A `journey start` finding shows a name missing from the facts.

- With `TYPESAFE_API_KEY` set, `delta` automatically asks Jev about rewritten renames and unclaimed modules.
  It pairs modules renamed and rewritten together, then proposes an owner for each unclaimed module.
  `--no-jev` sends nothing.
  `--jev` requests Jev and gives a reason if it cannot run.
  Cost prints to stderr only when a question was asked.

- Without a key, `judgement` gives a stderr hint with the measured benefit of `audit`.
  `delta` gives its hint when a module was removed and another added.
  `[jev] enabled = false` disables hints and automatic Jev calls in delta.

- The skill first uses the Jev forms: `suggest --jev`, `audit` after `judgement`, `delta`, and `triage`.
  It uses the plain form if the key is unset or a Jev call fails.
  It tells the user that Jev was not used and gives the reason.

- `check` and `judgement` do not ask Jev.
  `suggest` keeps the optional `--jev` flag because it saved nothing in the first-map benchmark.

## 1.1.0 - not published

This release was prepared but replaced before tagging.
All changes below were released in 1.2.0.
They add an optional second opinion from Jev.
Every call must have `TYPESAFE_API_KEY`. No data is sent without it.
`check` and `judgement` never call Jev.

No dependency was added: `urllib` communicates with the HTTP API.

- `systemap audit` asks TypeSafe's Jev model five question kinds.
  It prints disagreements as `jev mis-fold`, `jev owner`, `jev sentence`, `jev flow`, or `jev governs`.
  Thresholds were selected on the five first maps in `bench/scratch`.
  `audit.py` gives each threshold and its measured result.
  `bench/jev` contains experiments, labels, answers, reports, and the earlier heuristic comparisons.
  Each kind was then measured on three maps excluded from threshold selection (`JEV_SET=holdout`).

  All results stayed within 10 points of development results except `jev flow`: 54% finding of incorrect flows compared with 66%.
  Thus, flow questions must have `--kind "jev flow"`.
  Repeated `--kind` flags select only the named kinds.
  Answers are in `[judgement] answered`.
  `audit` reads answers naming its findings. `judgement` ignores those answers.
  `--dry-run` counts questions and gives the outgoing data.

- `systemap triage "<issue>"` names the three components a fix will probably change.
  It gives their modules and map neighbours.

- `delta --jev` asks which new module replaces each disappeared module not paired by delta's rules.
  At confidence 0.8 or more, it prints the selection as a move.
  Across five repositories, it found 82 renames against delta's 66.
  Sixteen of its 17 additions were correct, with blind agent labels from commits (`bench/jev`).
  It also proposes an owner for each unclaimed module.
  `suggest --jev` groups modules from Jev's module-pair answers.

  It improved on one component per package on three of five development maps and was worse on two.
  The command gives that limit when it runs.
  On HTTPie, its first-map run took 54 turns, $3.61, and 5.5 minutes.
  The plain recipe took 46 turns, $3.43, and 4.8 minutes.
  There was one run each, so variation between runs was not measured.
  The option stays outside the recipe.

- `.systemap/jev-cache.json` caches answers by model, release date, state, and question.
  An unchanged map has no second-run cost.
  A new model release asks again.
  `[jev]` selects the model and cache.

- `typesafe_sdk` was added to the SDK list used by `model sdk` findings.

## 1.0.3

- The version badge uses PyPI instead of pypi and has a new address.
  GitHub's README image proxy had cached a missing-version image before publication.
  A purge did not remove it.
  The new address has no old cached copy and shows the version.

## 1.0.2

- The metadata changes `Development Status :: 3 - Alpha` to Production/Stable.
  That status agrees with the published 1.0 version.

- Badges read published metadata instead of copied values.
  Python versions and licence thus agree with `pyproject.toml`.

- The release workflow is `workflow.yml` and uses the `pypi` environment.
  This is the identity registered with PyPI's trusted publisher.
  This release is the first published by that workflow instead of manually.

## 1.0.1

- README images use full URLs so they show on PyPI.
  Repository-relative paths work on GitHub but not on PyPI's project page.
  A test rejects relative image paths because the same README is the repository front page and package description.

## 1.0.0

All roadmap gaps were implemented and exercised on repositories written by others.
The roadmap was deleted.
Its two acceptance numbers and measurements moved to `docs/benchmarks.md` adjacent to the result rows.

- A coding agent followed the skill to map six repositories fully.
  Four repositories were written by others.
  Each finished without intervention, with clean `systemap check` and `systemap judgement --strict` results.

- Two targets were missed and kept unchanged.
  Four of six first maps cost less than 0.15 dollars per module.
  The other two cost 0.159 and 0.177.
  Three maintenance runs cost 2.31, 4.39, and 2.50 dollars, taking 51, 63, and 46 turns.
  The maintenance target was 15 turns and 2 dollars.

- PyPI publication makes `uv tool install systemap` available.
  The workflow written by `init` can pin a released version.

## 0.12.1

- Paper text colours previously gave contrast ratios of 4.15 to 4.22 to 1 on raised surfaces.
  Those surfaces are chips, the note block, and the wheel centre.
  All twenty-one colours decreased approximately four per cent in lightness, with hue unchanged.
  Contrast now exceeds 4.60 on the raised surface, 4.99 on the ground, and 5.58 on the panel.

- A test rejects any readable colour below 4.5 to 1 on its lowest-contrast surface in every scheme.

## 0.12.0

The page adds three schemes and a header picker.
Previously, the light scheme needed configuration.
Theme tokens now control the page, so selection changes the root attributes without a redraw.

- Warm is the new default.
  It uses ink `#ece5d8`, a warm dark ground `#161310`, amber `#e5a84f`, and low-chroma layer hues.
  Graphite is the unchanged 0.11 dark table. Paper is the unchanged 0.11 light table.
  Each contains the same full token set.
  Every text token exceeds 4.5:1 against its ground under WCAG 2.

  `tests/test_theme.py` enforces measured ratios recorded in the commits.

- The Scheme select is in the header.
  All three tables are `:root[data-theme="..."]` blocks adjacent to the default table.
  A head script sets the root before first paint.
  It first selects the stored scheme. Without a stored scheme, it selects paper for a light system preference or the configured default.
  Selection changes the root, stores the choice in `localStorage` when permitted, and applies to nested maps.

  Refused storage does not change selection.
  The favicon and logo keep their colours.
  The Node driver's `theme` scenario has `--light`, `--stored NAME`, and `--no-storage`.
  Tests exercise nine load conditions.

- Every themed colour in the map SVG, panel, legend, controls, and scripts uses `var(--token)`.
  Values are defined only in root blocks.
  `theme.Palette` gives tokens for the page and literal values for exported figures.
  `systemap figure` and README images stayed byte-identical.
  Previously, SVG had 135 literal hex values and the legend had 14.
  Nested-map previews also use tokens.

- `[theme] scheme` selects `warm`, `graphite`, or `paper`.
  The 0.11 names `dark` and `light` select graphite and paper.
  A bare key overrides the default scheme. `[theme.paper]` overrides paper tokens.
  Unknown scheme names are rejected with the three available names, instead of silently using a default.

- `docs/screenshots/` contains `warm.png`, `graphite.png`, and `paper.png` at 1600 by 900.
  `scripts/screenshots.py` writes them through the page's load path, with storage set for each scheme.
  The tour uses warm.
  The workflow can run manually through `workflow_dispatch`.

## 0.11.2

Four page changes improve selection framing, nested-map access, counts, and source-commit information.

- Selection framing includes the selected component, its visible edges, and their other ends.
  All and Structure include every edge because Structure has no edges of its own.
  One layer table supplies dimming, tags, and framing.
  The rectangle is centred in the visible map area: the map box clipped to the window, excluding the drawer column.
  Geometry is measured on the next frame after drawer layout.
  The selected set no longer sits under the panel or below the visible area.

  A set larger than the area at minimum zoom is fitted fully, without cropping.
  Further zoom-out does nothing instead of increasing zoom.
  The frame follows window resizing during selection.
  Sequence steps and regions use the same framing.
  A selected wheel spoke shows its edge even in a layer that hides the edge.
  `tests/test_framing.py` runs the page under Node with stub viewport, drawer box, and path `getBBox` values.

  It independently calculates geometry from those values.
  For six components in every layer, centres agree within one unit and all selected components and edges fit.
  Tests use the sample and self-map at three window sizes.

- A component with a nested map has an inert Structure preview and an Open the map inside button.
  The preview is rendered into page data.
  The button, component double-click, or second Enter on the focused component opens an overlay.
  Its frame uses a relative path, compatible with Pages, `systemap serve`, and files.
  A `demo > Gateway` breadcrumb and close control show the nested map.
  Escape or the control closes the overlay and returns focus with selection kept.

  The nested page keeps its upward link for direct access.
  Check and screenshots use the same previews as refresh.
  Escape inside the frame belongs to the nested page.
  The parent overlay closes through its control or Escape with parent-page focus.

- Header and strip counts now agree.
  The header prints `15 components and 3 actors`.
  The strip counts the layer's code components and gives actors independently when present.
  Previously, the header excluded actors and the strip included them, giving 15 and 18 for the same map.

- The header uses `Facts from <sha>` instead of `Built at`.
  The SHA shows the tree read during extraction, before the commit that records the facts.
  The footer and `built_at_commit` schema reference give the same meaning.

## 0.11.1

`place` now searches region orders.
In two of four benchmark repositories, agents had written helpers to try orders with fewer bends and shorter routes.
Previously, `place` used model order without comparison.
ROADMAP gaps 4 and 6 give the four measured runs.

- `systemap place` tries all region orders when there are at most six regions.
  It includes every permutation within containers and every combination across containers, at most 720 orders.
  Above six, it starts with the region with the most flows.
  It then selects the region with most flows into placed regions.
  Pairwise swaps continue while they improve the score.
  Each full layout includes components and barycentre sweeps.

  An estimate uses minimum edge bends and Manhattan length.
  Facing components with no obstruction use a straight route.
  A clear L-shaped route uses an L. Other routes use a Z.
  Components and foreign regions are obstacles.
  The twelve best estimates and the listed order use the real router and label pass.

  Scores compare label collisions, foreign-region crossings, bends, and length, in that order.
  The lowest score wins.
  Ties use the first-listed order, preserving model order on equal scores.
  `--keep-order` skips the search and uses listed order.

- The two stages have measured costs.
  Routing one order costs 156 ms on the 144-module fixture and 215 ms on the self-map.
  Routing all 720 would take two minutes against a ten-second budget.
  The estimate costs 0.75 ms per order.
  Offline routing of all 720 found a minimum of 40 bends, compared with 43 in listed order.
  The estimate ranked that order second. Search found it in 2.2 seconds.

  On the five-region self-map (120 orders), search finds a minimum-bend order among all 120.
  It is ten percent longer than the shortest minimum-bend order.
  `tests/test_place.py` rejects fixture search times of ten seconds or more and recalculates the drawing score after placement.

- `place` prints the selected order and score after writing, and with `--print`.
  Recorded output is `region order: layout, contracts, gateway, orchestration, style, content; 40 bends, 7,909 units; 720 orders tried, 13 routed`.
  `describe` prints the same form with `; as written` or the search counts when placement was temporary.

- `schematic.geometry` supplies obstacles to both drawing and scoring.
  These include component boxes, headers, and empty container walls where labels cannot sit.
  The selected order is thus scored on the page's drawing.
  Page output is byte-identical to 0.11.0.
  The self-map adds three flows: Router and Schematic into Placer, and Placer into Describe.

- Skill step 2 and `references/layout.md` state that order is searched and printed.
  They prohibit a different order helper and give conditions for `--keep-order`.

- ROADMAP gap 6 measured four repositories, three written by others.
  All finished without intervention, with clean check and `judgement --strict` results.
  Logs contained zero systemap crashes or usage errors.
  Friction-item count was not measured because the harness used the user sentence without a friction-log instrument.
  The substitute measure was helper scripts: three on one repository, four on another, and none on the other two.
  Gap 4 compared four 0.9.0 first-map rows in `docs/benchmarks.md` with the unchanged 0.15 target.

  Three passed and one cost 0.159.

## 0.11.0

This release completes ROADMAP gap 7 except publication.
It exercises the package on three operating systems and plugin installation through the CLI workflow.
It also adds light-scheme inspection, keyboard script tests, a referenced cost table, and a thirty-second tour.
PyPI publication remains for the maintainer's 1.0 release with `scripts/publish.sh`.
Official marketplace submission is planned after 1.0.

- CI runs on Linux, macOS, and Windows with Python 3.11 and 3.13.
  Each runs the suite, `mypy --strict`, `ruff check`, and `ruff format --check`.
  Each platform also builds a wheel and installs it with pip into an empty virtual environment.
  That job copies the self-map adjacent to the checkout, without `.git` or source on the path, and without runtime uv.
  It runs `init`, `extract`, `refresh`, `check`, `judgement --strict`, `render --check`, and `describe`.
  Check follows refresh because an unrendered page is rejected.

  A copy without `.git` cannot reproduce the committed page's source-commit value.

- Every writer uses LF on every platform with `newline="\n"`.
  This includes pages, facts, figures, placement edits, skill files, and scaffolds.
  Pages thus render byte-identically across platforms and `render --check` compares written bytes.
  Printed and recorded paths use forward slashes through `Config.rel`, module `file` values, and the skill path.
  `.gitattributes` uses LF for text checkouts.
  The plugin skill-tree comparison now uses POSIX path keys.

  The `bench/run.sh` test skips Windows with a reason: Windows PATH `bash` is the WSL launcher.
  `git archive` in delta and the loopback server in serve needed no change and pass the Windows suite.

- The plugin job runs `claude plugin marketplace add ./`, installs `systemap@systemap`, and lists plugins in a different configuration directory.
  The list must show the plugin enabled.
  Login is not necessary for these commands, measured with empty `CLAUDE_CONFIG_DIR` on the pinned CLI locally and on the runner.
  Failure of any command fails the job.

- Headless Chrome screenshots examine the light page, All and Control flow layers, a component drawer and spoke, a sequence step, index, and invariants.
  No readability defect was found, so tokens stayed unchanged.
  `docs/screenshots/light.png` and `dark.png` are 1600 by 900 and appear in README.
  `scripts/screenshots.py` writes both.

- Components are written in row order, left to right, so Tab follows reading order.
  Enter or Space opens a focused component's wheel.
  Escape closes it, restores the view, and returns focus.
  Left and right arrows cycle layers through All, or move sequence steps during a sequence.
  The sequence select keeps its own arrows.
  Focus rings use the scheme accent on components, spokes, and controls.

  Index buttons disable smooth scrolling with `prefers-reduced-motion`.
  That preference already disabled transitions and framing animation.
  Page hints give these controls.

- `tests/page_driver.js` loads a rendered page into a custom DOM without a library.
  It includes a tag parser, selector matcher, bubbling events, focus, animation frames, and a fake clock.
  It executes the page scripts, presses keys, and gives results.
  `tests/test_keyboard.py` examines layer arrows, Tab order, Enter, Escape, sequence controls, and immediate framing under reduced motion.
  Tests use the sample and committed self-map.
  They use Node when it is on PATH, as on every runner. Without Node, they skip with a reason.

- README states Python-only scope in its first paragraph.
  Cost links to the result table instead of copying rows.
  `docs/screenshots/tour.gif` is a thirty-second tour with twelve page states at two and a half seconds each.
  States include each layer, All, a component wheel, a spoke, sequence stepping, and a component in Control flow.
  Headless screenshots were combined with ffmpeg into a 1.7 MB GIF.
  Every state was operable headlessly.

## 0.10.1

The fourth headless run was the first with `place`.
It used the same repository as runs 1 to 3, systemap 0.8.0.
It finished without intervention, with clean check and `judgement --strict` 0.
This release addresses ten friction items and the measurement for ROADMAP gap 1.

- Run 4 had 21 check-and-refresh calls against a target of 11. Run 3 had 22.
  ROADMAP keeps the target and marks it missed.
  Calls to first clean layout were 2 and 3, with one refusal each.
  Work from first model write to that layout was 6 tool uses over 8 turns, then 5 over 7.
  Full costs were 168 turns and 17.30 dollars, then 232 turns and 25.49 dollars.

  Manual placement was already cheap by run 3, and `place` could not repeat full layout.
  The new placement acceptance claim is a clean layout from an unpositioned first draft with at most one refusal using `place --all`.
  It is to be measured on the next run.
  Gaps 3, 4, and 5 distinguish implemented work from unmeasured work.
  Gap 4 records 0.177 dollars per module against 0.15.

- `place --all` and `Component.pinned` permit repeated layout.
  Previously, all components had positions after first placement, so a later component needed manual edits when no slot was free.
  `pinned: bool = False` marks positions selected by a person.
  Plain `place` positions only components without positions and keeps the others.
  `place --all` places all unpinned components again.
  With no pins, it also changes boxes and canvas.

  The no-free-slots refusal names `place --all`.
  `describe` counts pins from the flag, for example `positions: 1 pinned, 17 placed`.
  The skill uses `place --all` after additions or removals. Layout.md gives pinning conditions.
  `Component.positioned` replaces the old `pinned` property. `Placement.kept` replaces `Placement.pinned`.

- Facts views show formatted records instead of JSON.
  `facts --module NAME` includes docstring, public names and kinds, re-export modules, imports, importers, external imports, and test count.
  It does not include test names.
  `--modules` adds each module docstring's first sentence before counts.
  `--docstrings` prints module and first sentence only. `--names NAME` gives public names and kinds.
  `--entry-points` adds targets so `python -m pkg` and `main()` can share one sequence.

  SKILL.md gives each view's contents.

- Two components can claim a shared module through symbol claims.
  They cannot have an import between them, so their flow previously stayed declared.
  The shared module now gives observed evidence, and the panel prints `observed: shared module`.
  layers.md gives this rule.

- The starter import has `# type: ignore[import-not-found, unused-ignore]` and an explanation.
  Without this ignore, strict mypy rejected repositories without a systemap dependency, the recommended installation structure.
  The second ignore prevents an unused-ignore error where systemap is installed.
  The package adds `py.typed`.
  `init` gives a mypy/deptry note with `[tool.deptry.per_rule_ignores]`, `DEP001 = ["systemap"]`, and `DEP003 = ["systemap"]`.
  pitfalls.md instructs the agent to run every repository CI command, not only pre-commit.

- Crossing-import findings group by ordered component pair and give a module count.
  For example, `crossing import: Page imports Model in 16 modules and no flow joins them` replaces per-import findings.
  `--verbose` lists imports below each finding.
  `--kind KIND` filters output, but the header and `--strict` count all open findings.
  `delta` matches answers to the grouped finding.
  Old `item` answers become stale.

  Answers must use `crossing`, `crossing_into`, `crossing_from`, or quote the new finding.
  second-pass.md gives all seven answer forms, the new finding, and both flags.

- pitfalls.md instructs the agent to keep scratch scripts outside the repository, for example `/tmp`.

- The anonymised fixture adds a pinned tool component with a symbol claim in its agent module and a tool flow.
  It exercises `place --all`, pinning, and shared-module evidence.
  Each decision above has a test.

## 0.10.0

ROADMAP gap 5 showed two limits: one map was difficult to use beyond sixty components, and checks assumed one canvas.
This release adds nested maps.

- `Component.map` names a model file relative to the parent model.
  Like other models, it exports `MODEL` and `MEANING`.
  Its components claim only the parent component's modules, each once.
  Symbol claims are permitted. Empty package markers are excluded as in coverage.
  Its actors are parent-map components adjacent to the parent component.

  This gives outside flows destinations without duplicate coverage claims.
  An actor cannot open a nested map.
  Missing files and files above the parent directory are rejected with exit 2.
  A nested identifier can be `Gateway/Routes`.

- `systemap.nest` loads the top map, then sub-maps depth-first in parent component order.
  Every model-reading command uses that tree.

- `check` applies every rule to every map.
  Nesting checks show extra, missing, and duplicate module claims, and actors missing from the parent map.
  Coverage applies only to the top map.
  Sub-map findings include a prefix such as `Gateway: map layout: clean ...`.
  Fixes name the sub-map file, and stale checks include every page.

- `refresh` and `render` write one page per map.
  The top page is `index.html`. Nested pages are `<card>/index.html` under the output directory.
  A nested-map component has a second-component mark on the page and figures, with a legend entry.
  Its panel prints `opens: Gateway (5 cards)` with a link.
  The header lists nested maps.

  A sub-page names its parent component, links upwards, and lists its own layers and sequences.

- `figure --map ID` selects a nested map. `[[figures]]` accepts `map`.
  `place` writes positions to every map file.
  `describe` prefixes sub-map output with its identifier.

- `judgement` runs on every map with sub-map prefixes.
  `item` answers quote the printed finding. Bulk forms cover every map.
  Entry-point and model SDK questions occur once, on the deepest claiming map, using sequences from every map.

- `delta` compares sub-maps over parent-component modules at each commit.
  A move or removal names the component and file on every map containing it.
  A new module without a sub-component claim shows the exact-parent-claim requirement.

- `suggest` reads the tree for maps with components.
  Above forty components, it proposes the largest components for nested maps.
  A component above ten modules is shown on any map.

- `schema.md` documents `map`. `layout.md` gives nested-map conditions and construction.
  `pitfalls.md` adds the sixty-component limit. `second-pass.md` applies its pass to every map.
  The loop stays unchanged.

- Tests use a top map with two nested maps.
  They cover exact claims, actors, single coverage counts, pages, links, `figure --map`, and sub-map placement.
  They also cover judgement/describe prefixes, delta names, and suggest output.
  The self-map is not nested because its 18 components are below the threshold.

## 0.9.0

ROADMAP gaps 3 and 4 added a maintenance process and repeatable cost measurements.
Previously, maintenance had no documented process and cost had only two manual measurements on one repository.

`systemap delta --base REF [--head REF]` adds these behaviors:

- Facts come from two Git commits through `git archive` into temporary directories, followed by extraction.
  They never come from the working copy.
  The base is the refs' merge base, excluding changes caused only by base-branch progression.
  Comparison uses the on-disk map's component assignments.
  Moves first use the same content. Without a content match, they use the same public names.

  Additions and removals name their components. Unclaimed additions show lost coverage.
  Entry and interface names missing since the base use the check's interface rule.
  New boundary-crossing imports show missing flows and missing `[judgement]` answers.
  Flows with base import evidence but no evidence for the stored source snapshot are also shown.

- Each finding names a fix under `needs a person` or `changed, nothing to do`.
  Exit 0 means no person is needed. Exit 1 means action is needed.
  The last line gives the next command.
  A component needing a module rename or removal is not also asked about public names.
  A new path in the map counts as a claim of its previous path at the base, giving one pending-rename finding.

  Reports affecting more than approximately a third of components show that scope.

- `--format markdown` gives a pull-request comment with a marker and both finding groups.
  It embeds the committed full-map figure at the head through a blob URL with `?raw=true`.
  This follows GitHub's image guidance. GitHub removes `data:` URIs.
  The change map depends on the base and is not committed.
  The comment gives its drawing command.

- Unknown refs are rejected with exit 2 and a fix.

The maintenance process adds these instructions and gates:

- SKILL.md adds "When the code changed" and `references/maintenance.md`.
  The process is `delta --base <the base branch>`, necessary finding fixes, `refresh`, then `check && judgement --strict`.
  It prohibits redrawing a map for a small change.
  Above approximately a third of components, it states the scope and uses the full loop.
  The agent instruction is "The code changed. Update the map with systemap: follow the systemap skill's maintenance path, with base <ref>."
  The budget is 15 turns.

- Step budgets are extract 2, draft 10, place/check 15, judgement 10, and second pass 20.
  These are reported overrun budgets, not limits.
  SKILL.md's ceiling increases from 200 to 230 lines.

- The generated workflow adds a pull-request delta job.
  It runs `delta --base <base sha> --head <head sha> --format markdown`, with both SHAs in environment variables.
  It creates or updates one comment found through its marker with `gh api`.
  It rejects the run while a finding needs a person's action.
  Top-level permission is `contents: read`. Only this job has `pull-requests: write`, with a reason.

  Every action is pinned to a commit, and zizmor is clean.
  A fork's read-only token changes comment publication to a warning.
  The repository workflow has the same job.

The benchmark harness adds these measurements:

- `bench/run.sh <repo-url-or-path> <first-map|maintenance> [--ref REF] [--base REF] [--from SPEC] [--model NAME] [--max-turns N]` accepts paths or URLs.
  It makes a worktree for a path or clone for a URL under `bench/scratch/`.
  It installs systemap into a different tool directory from this checkout version's release tag, unless `--from` overrides the source.
  It runs `systemap init` and the documented sentence, with `--base` for maintenance.
  The headless agent uses acceptEdits and the recipe's tools: Skill, Read, Edit, Write, Glob, Grep, TodoWrite, and Bash.
  Permitted Bash commands are systemap, uv, uvx, python3, git, ls, cat, grep, rg, find, head, tail, sed, wc, and mkdir.

  A streamed JSON session goes to a log.
  Afterwards, it runs `check`, `judgement --strict`, and module counting.
  `bench/summary.py` adds a row to `bench/results.jsonl`.
  The row contains model, turns, minutes, dollars, finish/cutoff state, and if the first call was the required systemap skill.
  Values come from the session and result event. Missing values are null, without estimates.

- `bench/table.py` renders one row per repository/mode from `bench/results.jsonl` into `docs/benchmarks.md`.
  Rows name model and systemap version. First-map rows include dollars per module.
  A test compares the committed file with that render.
  At this release, the table is empty because no harness measurements exist.
  README Cost shows that table as the measurement source.

- Tests cover synthetic stream-JSON parsing, the table, script usage, recipe, workflow text, and every delta finding in a synthetic two-commit repository.

The shared interface and self-map also change:

- `interface_problem` supplies both check findings and delta's two-commit comparison.

- ChangeDetector claims the delta module.
  The self-map adds the interface-rule flow from Check, rewrites the refactor sequence as maintenance, and answers the new crossing import.

## 0.8.0

ROADMAP gaps 1 and 2 change both model and check.
They add automatic layout and flow evidence.

`systemap place` adds these behaviors:

- It deterministically gives a first position to every unpositioned component using only the standard library.
  Regions use a two-column container grid in model order.
  `references/layout.md` specifies 48 units between region columns and 36 between rows.
  Component columns are 190 apart and rows 92 apart, with three rows before a second column.
  Barycentre sweeps place connected parts together.
  Region boxes follow component counts. Container boxes follow regions.

  Actors use an adjacent column, aligned with their connected parts.

- Schema `x` and `y` become optional.
  A component with both values is pinned and never moved.
  With any pin, boxes and canvas stay unchanged and unpinned components use free slots in their boxes.
  Without pins, the full model is placed.
  Check rejects missing positions until placement writes them.
  Other check behavior stays unchanged.

- Placement edits only `x=`, `y=`, `box=` tuples, and canvas values in the model file.
  Other bytes stay unchanged.
  `--print` gives values without writing.
  The model is read back and compared after writing.

- With all positions removed, the anonymised 144-module fixture gets a clean geometry check without manual moves in approximately a millisecond.
  The test rejects times of ten seconds or more.
  Repeated placement changes nothing, pins stay fixed, and the position-stripped self-map also becomes clean.

- The starter has no positions or position tables.
  The skill drafts components and flows, runs `place`, then checks.
  `describe` gives pinned and temporary-placement counts.
  layout.md keeps decisions about component regions, region order, pins, and `describe` output.

Every flow gains calculated evidence:

- At render and check time, facts determine evidence without an authored state.
  `observed` means an import connects component modules in either direction.
  `external` means an actor endpoint. Without import evidence or an actor, the state is `declared`.
  Declared edges are dashed on pages, figures, and wheels.
  Panels print `declared: no import behind it`, `observed: an import joins them`, or `external: outside the code`.

  The legend gives the dash meaning.

- `judgement` prints `declared flow: A -> B (artifact): no import joins them; find the evidence, name the mechanism in the sentence, or remove it`.
  Bulk answers accept `kind = "declared flow"`.
  second-pass.md examines this kind after crossing imports.

- `[flows] observed_by = ["subprocess", "queue", ...]` names non-import connection mechanisms.
  A whole-word, case-insensitive mechanism in the flow sentence or artifact makes that flow observed and solid.
  The panel prints `observed by: queue`.

- On the self-map, two flows were initially declared.
  The facts file connects extractor to schematic through `observed_by = ["facts file"]` and its sentence.
  The CLI connects the change map to the page through a configuration answer.

Other changes:

- The generated workflow pins `uvx --from "git+https://github.com/0xfauzi/systemap@v<version>"` before PyPI publication.
  Version 1.0 will use PyPI.

- The self-map adds Placer, makes Model the owner of evidence, and changes invariant 5 to "written once by systemap place or by hand".

- Five plain words and one container `sub` in the fixture exceeded 0.7.0 text limits and were shortened.
  Two low containers moved clear of headers.
  The manually placed fixture now passes geometry checks.

## 0.7.0

A third headless run mapped a real repository using the skill and found twenty-one items.
It finished without intervention, with clean check and answered judgement results.
Each item has a fix and test.
The anonymised fixture adds interface and re-export cases.

Schema-reference defects are corrected:

- The panel now prints `interface` as the component signature, `entry` as `entry: name (module)`, and `note` as a caution.
  A note gives the component a top-corner dot on the page and figures.
  schema.md gives each field's display location.

- Interface leading identifiers must exist in component modules, including re-exports.
  The token ends at `(`, `.`, `->`, or whitespace. Both identifiers in `Class.method` are examined.
  Rejection gives the closest defined name.
  Sixteen of twenty-one interface lines in a real map were incorrect under the earlier unchecked behavior.
  `interface` stays optional.

- Refresh now states `already current: the page matches the model's rendered fields and the facts`.

Check defects are corrected:

- Component text must fit without truncation.
  Names fit approximately 20 characters. Component, agent, and tool CamelCase names can wrap over two lines.
  Plain words fit approximately 26 characters per available line.
  Rejection gives the limit, such as `actor cards fit about 26 characters on one line; this one has 34`.
  The drawing no longer adds ellipses.

- Duplicate invariant numbers are rejected with both rules.

- An `__init__` without public names or imports is an empty package marker.
  Extraction lists it once, and coverage excludes it.
  Ignores naming only such markers are rejected as unnecessary.
  Nine files previously needed nine ignores.
  The reference documents `module = "pkg.sub.*"`.
  Coverage prints `144 of 144 modules mapped, 5 of them ignored with a reason, 9 of them empty package markers`.

Facts gain these views and fields:

- `systemap facts` reads one formatted view at a time.
  `--modules` gives names, public names, imports, and tests. Other views are `--module NAME`, `--entry-points`, `--external`, and `--imports NAME`.
  Skill step 1 uses these views instead of the 451 KB JSON for a 144-module tree.
  pitfalls.md gives the same instruction.

- A package `__init__` records imported names from its own modules in `names`.
  It includes `reexport_of` and the defining module's kind.
  `entry` and `interface` accept re-exports.
  Facts format becomes 2. `extract --check` marks older files stale.

- Extraction summary uses documented `functions`, `classes`, `errors`, and `tests` field names.
  schema.md maps those words.

Judgement and layout change:

- `crossing_into = "Card"` covers incoming crossing imports. `crossing_from = "Card"` covers outgoing ones.
  `crossing` accepts two or more IDs and covers each pair.
  Each form has an example.

- Every loop round runs `systemap check && systemap judgement --strict`.
  Dropping an edge for layout can reopen findings, which judgement then finds in that round.

- `describe` and label diagnosis show gutters by neighbours and coordinates.
  Example output is `between the row of Orchestrator, Telemetry and the row of RosterClient (y 160 to 226)`.

- layout.md treats pitch as a starting value.
  Dense regions can increase row pitch, and regions in one grid row can have different heights.
  Diagnosis prints `raise the row pitch of region X`.

- The skill targets three to ten modules per component, or N/10 to N/3 components for N modules.
  Judgement findings show groups above and below useful sizes.
  `systemap suggest` gives package/import-based groups as a starting proposal, not the final answer.

Agentic behavior changes:

- `Component.calls_model` marks a single-shot model call site.
  Context and tool flows accept an agent or a `calls_model` component at the agent end.
  Context and Tools layers show these flows. Agents shows only agents.
  The flag answers `model sdk` findings and is listed with the four outcomes in second-pass.md.

- `entry` is optional for `store` and `context` kinds.
  The panel prints `entry: none (a namespace)`.

Documentation and scaffold changes:

- schema.md and duplicate-pair errors specify one flow per ordered pair.
  The author must select the relevant artifact or use a different reverse-direction flow.

- The starter uses only `# ruff: noqa: E501`.
  Every schema name is imported and used, so F401 and RUF100 do not fire.
  `# fmt: off` and `# fmt: on` protect position tables, with a reason.

- The second pass rereads newcomer documents once: README, AGENTS.md, CLAUDE.md, docs index, or first-level docs/.
  It stops when new rules apply only to parts outside the tree.

- SKILL.md step 4 lists each answer form and constraint independently.
  A table gives all seven finding kinds, assignment-error meaning, and actions.

- SKILL.md instructs the agent to extract if `systemap.toml` exists but facts do not.
  schema.md documents `state`, where `built` is the only displayed value, and defines wheel counts.

The self-map adds correct interface lines and a Scaffold note.
FactsExtractor claims `facts`. Judgement claims `suggest`.
Plain words now fit component boxes.

## 0.6.0

A second new agent mapped a real repository from the sentence printed by `init`.
It found ten items, all different from the first run's twenty-two.
Repository pre-commit hooks found three more.
Each item has a fix and test.

Layout used a third of session turns, so its instructions change:

- `references/layout.md` is linked from the draft step.
  Edges cannot cross foreign regions, so region boxes cannot fill a container without corridors.
  A 2xN grid connects every pair through crossing corridors. More than two full-width bands does not.
  Region-column gaps are 48 units and row gaps are 36.
  Frequently connected parts use adjacent regions. Long routes get an empty component column.

- The starter uses a 2x2 region grid with corridors.
  It is ruff-formatted at 88 and 100 columns and imports every schema name, including `Layer`.
  A test fills all four corners and routes every pair cleanly.

- Label collisions give fixes from router seat counts.
  Examples are `gutter between rows 2 and 3 holds 3 of 3 seats: move a card or widen the row pitch`.
  Another is `label is 41 units wider than its seat: shorten the artifact`.
  Artifact labels must be noun phrases of one to three words, not sentences.
  The second gutter seat moves from 51 to 53 units to give two seats per side.

- `systemap describe` gives information an agent would obtain by looking at the picture.
  It gives components per region, edge bends and lengths worst-first, label gutters, gutter seat usage, and components/edges per layer.
  The render step runs it and opens the page when possible.

Judgement changes:

- `ignored:` lines do not print because they are not questions.
  The coverage reason is their answer.

- Bulk answers use one `[judgement] answered` table per reason.
  `crossing = ["A", "B"]` covers both directions. `kind = "single module"` covers that kind.
  `module_sdk = "google.adk"` covers that SDK import.
  `item` and `items` stay available.
  An answer without a matching finding is printed as stale under its original form.
  `references/second-pass.md` gives all forms and examples.

- The fourth model SDK outcome is a deliberate single model call outside the repository's definition of an agent.
  Repository definitions take precedence over the SDK prompt.
  Built-in SDK names match import prefixes.
  `[facts] model_sdks` can remove a built-in name with `"-google.adk"`.
  Removal of an unlisted name is rejected.

- `systemap judgement --strict` exits 1 for unanswered findings.
  The generated CI workflow runs it after check.

Symbol claims become available:

- `implemented_by` accepts `"pkg.mod:name"` for a part inside another component's module, such as an agent's tool.
  Symbol claims do not count in module coverage and do not conflict with module claims.
  Entry checks reject missing modules, undefined symbols, and symbols in unclaimed modules.
  `references/layers.md` gives the example.

Command and documentation changes:

- The skill accepts `systemap` or `uv run systemap` after tool installation.
  It selects the form that answers `systemap --version`.

- Extraction summary shows its counts as change-detector facts, which do not appear on the map.

- Model-load `NameError` and `ImportError` failures give one fix line and exit 2 without a traceback.
  The form is `map/model.py failed to import: ...; add the missing name to the import from systemap`.

- Coverage prints `140 of 144 modules mapped, 4 ignored with a reason`, agreeing with the extraction total.

- `figure --out` is relative to `out_dir`, as `[[figures]] out` is.
  Absolute paths stay absolute.

- Model source is compiled and executed directly.
  The previous import loader could reuse stale bytecode after a same-size edit within one second.

Repository-hook changes:

- Facts use no indentation, sorted keys, one module record per line, and no per-symbol docstrings.
  On the same trees, the 17-module self-map decreased from 87 KB to 59 KB.
  A 111-module tree decreased from 428 KB to 304 KB.
  The 144-module session tree was 635 KB but unavailable for another measurement.
  Its approximately 450 KB prediction used the measured ratio, not a new measurement.
  That prediction was below the 500 KB hook, so the symbol table was not split.

- The generated workflow pins every action to a commit with its version.
  It declares `permissions: contents: read` and sets checkout `persist-credentials: false`.
  Zizmor gives no findings, and tests enforce all three properties.

- `references/pitfalls.md` instructs the agent to format `map/model.py` before check and keep scratch scripts outside the repository root.

The self-map adds `Describe` and uses bulk judgement answers.

## 0.5.0

A new agent mapped a real repository with only README instructions and found twenty-two defects.
Each has a fix and test.

Judgement changes:

- `possible mis-fold` previously compared component ID with the final module-path segment, giving 112 findings on 27 components.
  It now compares dotted-path words with component ID, `does`, plain word, and `interface`.
  It applies only to multi-module components when the module's package contains none of the other modules and is not one of them.
  `tests/fixture_workspace.py` has two packages, 144 modules, 27 components, and four agents.
  Its findings decrease from 112 to 0.

- `[judgement] answered` records each `item` or `items` answer with its reason in `systemap.toml`.
  Answered findings are hidden and counted in the header.
  Answers for missing findings are stale. Answers without reasons are configuration errors.
  Skill step 4 and hand-back instructions show these repository records as the answers.

- The new finding is `model sdk: module X imports <sdk> and its component P is not an agent`.
  A built-in SDK/framework list extended by `[facts] model_sdks` supplies the agentic-layer prompt.

- `note: ... sits on a shorter segment` is removed from clean check output because it was not a rule.

Facts change:

- Module records add `external` for third-party dotted imports and `names` for public module-level names.
  Kinds are function, class, error, constant, and object.
  `entry` accepts any public name, including `app` and `root_agent`.

- `tests_dir` accepts one directory or a list.
  Without configuration, extraction reads every root-relative directory named `tests` or `test`.
  Facts record `tests_dirs`.
  If no test imports a module, the summary states that result and names searched directories.

- Package roots are found under each `[tool.uv.workspace]` member.
  If none exist, the error lists all directories with `__init__.py` up to four levels deep.

- `name` defaults to `[project] name`, then the main Git checkout's directory name, then the directory name.
  Worktrees use the main checkout for the Git default.

- `extract.FIELDS` defines every written facts field.
  `references/schema.md` is rendered from that table.
  A test compares the reference and build output with the table.

Check changes:

- `wheel of X: label Y leaves the drawing` is removed because wheel size follows labels.
  Wheel checks prevent centre/label overlap.

- A label collision names both labels by artifact and edge.
  Collisions in the 2-unit gap no longer give an empty list.

- Container and region headers join label checks.
  `sub` can wrap over two lines but is rejected beyond that.
  Labels wider than their boxes and headers touching components are also rejected.

- `refresh` checks written output and exits 1 on failure.

- `--root` is accepted before or after the subcommand.

`init` changes:

- It configures bare `figures/structure.svg` and `figures/system.svg` instead of `system.html`.

- The starter has no components or TOML ignore.
  Check gives only "the model has no components yet; see the skill".

- Skill output is one line: "wrote .claude/skills/systemap/ (SKILL.md and 6 references)".

- The workflow runs `uvx --from "systemap==<the version that wrote it>" systemap ...` without a project dependency.
  PyPI publication is necessary but has not happened at this release. README states that limit.

- The starter opens with `# ruff: noqa: E501` and an explanation.
  Every rendered file ends with a newline.

Skill and README changes:

- The draft reads repository README, AGENTS.md, CLAUDE.md, and docs/.

- `systemap serve [--port 8765]` serves output over loopback HTTP and prints the URL.
  At this release, documentation states that page scripts do not run from `file://` and instructs use of serve.

- The second pass uses bulk answers, examines model SDK findings, and examines `figures/structure.svg` then `figures/system.svg`.

Agentic rendering changes:

- Context highlights context components, Tools highlights tools, and Agents highlights agents.
  Single-layer figures use layer-coloured subject strokes and dim components untouched by that layer's edges.
  The page uses the same strokes and dimming.

The self-map is rendered again with new facts fields.
Its top row moves clear of the region header caught by the new rule.
Its sixteen remaining judgement findings are answered in `systemap.toml`.

## 0.4.1

A single-layer figure lets a document show one map question without every arrow.

- `systemap figure --layer ID` draws only the selected layer's edges.
  Kind layers use their flows. Derived layers use the page's derived edges.
  `structure` has none. `system` uses boundary-crossing edges in its layer colour.
  All components stay present, the legend uses only that layer, and title/caption give its question.
  Unknown IDs exit 2 with available layers.

- `[[figures]]` adds optional `layer`.
  Refresh writes and check compares these figures as usual.

- `systemap.model.reading` selects layer edges through `edge_in_layer` and subjects through `subject_of_layer`.
  Browser scripts read `_meta.readings` and each layer's `derived` field from detail JSON instead of recalculating selection.
  Thus, page and figure use one selection rule.
  Every generated SVG adds a `<title>`.

- The self-map adds `figures/structure.svg` and `figures/control.svg` adjacent to `figures/system.svg`.
  README opens with Structure and then Control flow.
  It no longer embeds all layers together.

## 0.4.0

The map shows current implementation in standard layers.
A second pass improves the first draft.

Breaking removals:

- `Component.tracker`, `planned`, and `partial` build states are removed.
  The change also removes ghost rendering, Today / End toggle, figure end-state checkbox, planned legend, tracker chips, and panel issue links.
  `build_state` gives only `built`.
  Missing modules or entries fail the `entry` check.
  Findings include "X names module Y which is not in the facts", "X names entry Z which none of its modules defines", and "X names no module".
  The `tracker` rule is removed.

- `issue_url` is removed and rejected as an unknown key.

- `Meaning.layers` no longer declares standard layers.
  Reserved IDs are `structure`, `system`, `data`, `control`, `agents`, `context`, `tools`, and `all`.
  Custom use of a reserved ID fails meaning checks.
  `layers`, `layer_of_kind`, and `relations` become optional.

- Unknown flow kinds missing from standard kinds and `flow_kinds` fail placement checks with available kinds.

- `theme.resolve`, `schematic.layer_rows`, `check.run`, and `schematic.render` change signatures.
  Theme resolution uses `systemap.all_layers(model, meaning)`.
  `layer_rows` accepts the model, and `issue_url` arguments are removed.

- Theme constants become `GRAPHITE`, `INK`, `AMBER`, `STEEL`, `PAPER`, and `INK_ON_PAPER`.
  `TEAL`, `PANEL`, `SLATE`, and `MUTED` are removed.
  Scheme `layers` tables name every standard layer. `[theme.layers]` overrides by ID.

Additions:

- Structure and System context are derived without author definitions.
  Structure shows positioned components without edges.
  System context shows actors and boundary-crossing edges, with internal edges dimmed.
  Standard `data` and `control` kinds add Data flow and Control flow with their own verbs.
  Page order is Structure, System context, Data flow, Control flow, custom layers, then All.
  Structure is the initial view.

- `Component.kind` adds `agent`, `tool`, and `context`.
  Standard `context` flows enter agent context windows. `tool` flows invoke tools.
  Agents, Context, and Tools layers appear only with an agent.
  Check rejects context/tool flows without an agent at the agent end.
  Component marks come from theme `marks`: ring, notch, and dotted, without a colour distinction.
  The legend names them.

- Facts `entry_points` include console scripts, `__main__` modules, `main` functions, literal argparse subcommands, and public package-root functions.
  Facts drift checks compare them.

- Judgement adds "entry point X has no journey" and "crossing import: module A (component P) imports module B (component Q) and no flow joins P and Q".
  Thin-layer findings include standard kind layers.

- The palette uses cool graphite, muted amber, and low-chroma layer hues.
  Every light-scheme text hue is measured above 4.5:1.
  The supplied accent `#a8722a` measured 3.68:1 and is shown in the palette commit.

- The skill becomes a directory.
  SKILL.md has 129 lines for use conditions, loop, model contents, commands, hand-back, rules, and reference index.
  References are `schema.md`, `example.md`, `layers.md`, `journeys-and-invariants.md`, `second-pass.md`, and `pitfalls.md`.
  `skill` and `init` install the full directory and remove obsolete references.
  A test compares plugin and package trees.

- The self-map uses standard kinds and one sequence per entry point.
  Invariants cite README, a guard clause, and a test.
  All judgement findings are answered in the commit.

## 0.3.0

A coding agent writes the map, check rejects incomplete or stale output, and a person examines judgement findings.

- `assets/` adds a logo mark and hero image.
  Default colours use ink ground, panel surfaces, paper text, amber selection, and teal for connected parts.
  `scheme = "light"` under `[theme]` selects a derived light scheme.
  Token names stay unchanged, so existing overrides work.

- The primary instructions are `systemap/skill/SKILL.md` in the package.
  `init` installs them by default. `skill` reinstalls them. `--print` writes to stdout.
  They include the full schema, a worked example of each part, step commands, and hand-back instructions.
  A test runs the real check on the example.
  `init --no-ci` does not include the workflow and ends with the agent instruction.

- `systemap judgement` prints maintainer questions from model and facts.
  They concern single-module components, module/component name disagreement, flows without sentences, thin layers, and ignored modules with reasons.
  It is a report with exit 0, not a gate.

- Check adds `entry`, `tracker`, and `stale` rules.
  Entry checks defined names. Tracker checks the building item for planned components.
  Stale compares facts with extraction, page with rendering, and configured figures with generation in one command.
  Each failure gives its fix under the rule.
  Refresh no longer says "already current" when check fails.

- An `out` ending in `.svg` writes a bare drawing on its ground for image embedding.

- The repository maps itself through `map/model.py` and `docs/map/`, with page and README figure.
  `docs/index.html` and `docs/.nojekyll` serve GitHub Pages.
  The generated workflow also runs on this repository.

- README adds the hero, agent/script rationale, quick start, check-rule table, one-screen model, commands, and configuration.

- The repository is a Claude Code plugin and marketplace.
  Files are `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and `skills/systemap/SKILL.md`.
  A test keeps the skill byte-identical to the package file and checks manifest/package versions.
  Installation uses `/plugin marketplace add 0xfauzi/systemap` then `/plugin install systemap@systemap`.
  Skill front matter adds `license` and `compatibility`. The description gives trigger phrases.

  Workflow validation checks both manifests and the skill in strict mode.

## 0.2.0

- Breaking: the package uses the term "map".
  Defaults become `model = "map/model.py"` and `out_dir = "docs/map"`. Facts stay in `map.json`.
  Init writes those model/output paths, and README, scaffold, and workflow use "map".
  Projects using earlier defaults must configure `model` and `out_dir` to keep their paths.

- `systemap check` rejects incomplete coverage.
  Every facts module must have one component `implemented_by` claim, without duplicates.
  Unmapped and duplicate claims print individually with exit 1.
  Success prints `coverage: N/N modules mapped`.
  Optional `[coverage] ignore = [{ module = "pkg.mod", reason = "..." }]` gives justified exclusions.
  Missing reasons are configuration errors with exit 2.

  Ignores for missing modules are shown. Missing facts fail closed.

- An `implemented_by` package with `.*` claims that package and all descendants.
  Build state, drift, change map, and coverage use this same convention.

- `systemap skill [--dir PATH]` writes SKILL.md, by default under `.claude/skills/systemap/`.
  The skill drafts the model in order and gives the maintainer judgement decisions to confirm.
  README distinguishes mechanical extraction, agent drafts, person inspection, and incomplete-map rejection.

- The example project is removed. Tests keep their sample system.
  A later release will use the self-map as the package example.

## 0.1.0

The first release ports an earlier repository tool, replacing project literals with configuration.
The original map is byte-identical inside the SVG view group.

- Frozen schema dataclasses are `Container`, `Region`, `Component`, `Flow`, `Invariant`, `Journey`, `Step`, `Layer`, `Model`, and `Meaning`.
  `build_state` derives built, partial, or planned from facts.
  `Model.layout_problems` and `meaning_problems` examine the model.

- Configuration uses `systemap.toml` or `[tool.systemap]` in `pyproject.toml`.
  Package roots are found unless configured. Unknown keys are rejected.

- The engine includes `ast` extraction, orthogonal component-grid routes, label placement, SVG scene and interaction script, page, change map, lesson figures, and layout checks.

- The default theme is neutral dark.
  Every token can be overridden. Layer colours use ID-specific values or ordered palette values.

- CLI commands are `init`, `extract`, `render`, `check`, `figure`, and `refresh`.
  Exit codes are 0 for current, 1 for stale/failed, and 2 for configuration errors.

- `examples/` contains a full model of one project.
