# Improving map accuracy without Jev

Reviewed on 2026-09-26 at commit `83aabb818069b62c3cce16dea34dcb3d4a0ebda7`, including the uncommitted ownership-review instructions and pilot from the preceding work.

**The largest opportunities are reliable extraction, correct change detection, and evidence attached to claims.** Several failures happen before a model is asked to judge anything. Fixing them would improve both a fully offline workflow and a workflow using the user's preferred coding agent.

I recommend fixing the silent omissions and stale conclusions first. Then make the existing `[agent]` interface support a review grounded in source references. Jev is not required for either step. A purely deterministic implementation can establish syntax, identity, and freshness. It cannot establish that an architectural description captures the system's purpose.

This review changes no production implementation. It adds reproducible experiments and records their results. The earlier skill changes remain in the working tree.

## What was measured

The measurements answer different questions. They must not be combined into one accuracy percentage.

| Measurement | Result | What the result establishes |
|---|---|---|
| Existing suite | 376 tests passed | Existing regression expectations hold. Several expectations explicitly permit the behaviors discussed below. |
| Targeted challenge suite | 33 gaps reproduced; 4 controls passed | The listed failure modes exist. The cases were chosen to expose problems, so 4/37 is not an accuracy estimate. |
| Source census | 1,381 Python files across eight mapped repositories | The review includes actual syntax and map structures outside this repository. |
| Mealie extraction under Python 3.11 | 445 of 460 files parsed | Fifteen files silently disappear from the extracted inventory. |
| Same Mealie extraction under Python 3.12 | 460 of 460 files parsed | Matching the project's grammar restores 15 files, a 3.26 percentage-point increase in parsed-file coverage. Five flows regain import evidence. |
| Rename replay, current rules | 65 correct pairs; 4 disagreements with Git; 21 reference renames not correctly paired | Current rules recognize edited moves that exact-content matching misses. |
| Rename replay, unique exact content only | 13 correct pairs; 0 disagreements; 73 reference renames not paired | Removing the name rules loses 52 correct pairs. It failed the preset bar of fewer disagreements without losing correct pairs. |

The rename replay covers 33 historical commits and 86 Git-labelled renames in Mealie, Paperless, Poetry, and Rich. Git labels are a similarity-based reference, not independent semantic truth. The sample contains commits selected for renames, so it does not establish precision on arbitrary delete/add commits. [Git documents the similarity threshold used by rename detection](https://git-scm.com/docs/git-diff#Documentation/git-diff.txt--Mltngt).

The census found 480 public classes with constructors and 966 public classes with annotated fields under Python 3.12. Those are exposure counts for the API limitations below, not counts of incorrect maps. It also found 18 groups of entry points sharing a kind and name across different modules. Thirty-four of the 36 existing journeys have no explicit `starts` value, so changing coverage semantics needs a migration.

## Findings that should be addressed first

P1 means a priority for the next accuracy work because a result can appear complete or current while relevant information is missing. P2 means a concrete defect or supported-use gap with a narrower trigger. A finding marked “design limit” describes deliberate current behavior that weakens the accuracy claim.

### F1. P1: Keep unreadable and unparsable files in the inventory

`collect_module` returns `None` for a parse failure, and `build` skips the file. A new, unclaimed invalid file can therefore vanish before coverage is calculated. An existing explicit claim may expose the omission later, but that does not account for all files. The source inventory and the parsed facts need separate counts.

This occurred in the real Mealie snapshot: it requires Python 3.12, while this workspace runs Python 3.11. Files including `repository_generic.py`, the authentication provider, and route controller helpers disappeared. Switching the experiment to the installed Python 3.12 recovered all 15 files. Python's AST grammar depends on its release. [Python AST documentation](https://docs.python.org/3/library/ast.html).

**Change:** Record a file with `parse_error` or `unsupported_syntax`, including path, line, and parser version. Refuse a completeness claim while any discovered file remains unresolved. Select or require a parser compatible with the target project. Do not execute the application to discover its modules.

**Acceptance:** Every discovered file is parsed, explicitly excluded with a reason, or reported unresolved. Zero silent omissions in the challenge suite. All 460 Mealie files are accounted for under either interpreter.

Source: [extract.py:372](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L372), [extract.py:704](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L704). Reproduction: `parse_failure_inventory`; both census JSON files.

### F2. P1: Recheck descriptions when implementation behavior changes

The maintenance path says to act only on delta lines needing a decision. Delta produces no such line when function bodies change without changing imports or deleting entry names. Its full-review threshold counts cards named by those lines, rather than all cards whose code changed.

The reproduction changes behavior in both cards of a two-card model. Delta reports two changed modules, zero cards named, and “the map already covers this change.” The full-review trigger remains false. Refreshing the facts then removes source-staleness warnings without checking the card descriptions, flow sentences, journeys, or invariants. The change overlay does highlight these cards; the omission is specifically in the maintenance decision path.

**Change:** Build the review set from changed source and its claimed cards. Include the affected descriptions, flows, journeys, and invariants. A body edit should request a review, not assert that a claim is false. Compute the broad-change threshold from that set. An AST fingerprint can avoid treating comments and formatting as behavioral changes.

**Acceptance:** The behavior-changing fixture names both affected cards and requests review. All affected claims remain pending until reviewed against the new source. A formatting-only control produces no semantic-change claim.

Source: [delta.py:507](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/delta.py#L507), [Delta.named](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/delta.py#L218), [maintenance instructions](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/skill/references/maintenance.md#L20). Reproduction: `body_change_review`.

### F3. P1: Invalidate journey answers when the code changes

The agent cache hashes the command, question, and context. Journey context contains file paths and the map's descriptions, but no source hashes. Editing the entry function while keeping those descriptions unchanged reuses the previous answer. Updating the facts' module hash does not help because that hash is absent from the context.

The injected transport was called once across two different source versions. The second journey came from the cache. No real agent was run.

**Change:** Include a digest of the source snapshot the agent can read. A digest of all mapped source files is a simple correct first implementation; narrowing dependencies can follow measurement. Include the effective agent/model configuration when available. A commit alone does not identify uncommitted source.

**Acceptance:** Identical inputs reuse the answer. Every changed source dependency in the regression fixtures causes a fresh review. An unknown dependency set cannot produce a “reviewed against current code” claim.

Source: [agent.py:55](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/agent.py#L55), [journeys.py:143](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/journeys.py#L143). Reproduction: `journey_cache_source_freshness`.

### F4. P1: Revisit recorded reasons when their evidence changes

An exact answered crossing line identifies the card pair and number of importing modules. It does not identify the imported symbols or source. Replacing a type import with a behavioral import leaves that line unchanged, so an old reason saying “only an annotation type is imported” still suppresses it. Broad answers can also cover future imports that the author never reviewed.

**Change:** Separate standing policies from decisions about observed code. Attach an evidence digest to a decision and reopen it when its imports or supporting source change. Keep broad policies explicit and show how many new instances they cover. Preserve existing line identifiers; add evidence alongside them.

**Acceptance:** Replacing the fixture's `Type` import with `send` requests renewed review. An unchanged instance keeps its answer. A policy applying to new instances is visibly distinguished from a prior review of those instances.

Source: [judgement.py:617](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/judgement.py#L617), [delta.py:436](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/delta.py#L436). Reproduction: `answer_dependency_freshness`.

### F5. P1, design limit: Give entry points stable identities and explicit coverage

Journey coverage currently accepts a matching word anywhere in a journey. A label containing “main” covers a `main()` entry. A `starts="GET /read"` value covers that route name in multiple modules. Starting at a card covers every entry kind on the card, so a grouped HTTP journey also covers a background task. An empty journey can satisfy these conditions.

These are deliberate compatibility and grouping rules, not accidental string matching. They still overstate what was reviewed. The real census found 18 name-collision groups. One Mealie group contains 23 modules exposing the local route `GET /{item_id}`.

**Change:** Identify entries by kind, module, target, and local name. Keep the displayed name separate. Grouped journeys should list the entries or declare a kind-specific, reviewed group. Newly discovered entries must not become covered automatically. Treat legacy word matches as migration candidates requiring confirmation.

**Acceptance:** Zero cross-module, incidental-word, or cross-kind coverage in the fixtures. Zero empty walks counted as reviewed coverage. Existing journeys migrate without silently claiming new entries.

Source: [judgement.py:277](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/judgement.py#L277). Reproductions: `entry_identity_collision`, `incidental_word_coverage`, `crowd_kind_scope`, `empty_journey_validation`.

### F6. P1: Serialize generated journey text safely before writing the model

Journey source is assembled by inserting text inside double quotes. An ordinary sentence such as `A sends the "value" to B.` produces invalid Python. The writer overwrites the model without compiling the complete proposed source first. This prevents later map commands from loading the model.

**Change:** Serialize all string values as Python literals, construct the proposed complete source, validate it, then replace the file atomically. Use syntax-aware insertion or verify the insertion target. The current text anchor can also match text that is not the intended tuple.

**Acceptance:** Quotes, backslashes, Unicode, and newlines round-trip exactly. Zero invalid model writes. On any validation failure, the existing model remains byte-for-byte unchanged.

Source: [journeys.py:260](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/journeys.py#L260), [jev_cli.py:281](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/jev_cli.py#L281). Reproduction: `journey_string_roundtrip`.

### F7. P2: Refuse an invalid journey as a whole

If one returned step is valid and another names an invalid edge, the parser drops the invalid step and still returns a journey. The CLI writes that shortened walk and prints the problem. The warning is visible, but the stored artifact is a different walk from the answer. Existing tests explicitly expect partial acceptance.

**Change:** Return a rejected draft whenever any step fails validation. Preserve the original answer and diagnostics for correction. Validate field types and required text before constructing steps. Keep the draft marker for semantic review after structural validation.

**Acceptance:** Zero partial writes from malformed or invalid answers. The valid control is preserved exactly. Do not add an edge-adjacency rule: the earlier continuity experiment rejected legitimate branching journeys.

Source: [journeys.py:188](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/journeys.py#L188). Reproduction: `partial_journey_rejection`.

### F8. P1, design limit: Separate structural evidence from a verified flow claim

An internal flow can become “observed by: queue” solely because its sentence contains a configured word. The reproduction obtains that state with no facts at all. An import between cards, or a shared module, also establishes proximity but does not verify the flow's direction, artifact, or sentence. Existing tests document these classifications.

The eight maps contain four flows promoted by a mechanism word. There are also 341 `TYPE_CHECKING` blocks in the source census. This does not mean their flows are wrong; it means runtime behavior cannot be inferred from every syntactic import. Python explicitly defines `TYPE_CHECKING` as false at runtime. [Python typing documentation](https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING).

**Change:** Represent the evidence as “import present,” “shared module,” “mechanism declared,” “source reviewed,” or “execution observed.” A reviewed semantic flow should cite the call, registration, write/read pair, or other supporting source. Record direction and artifact separately. Preserve the existing finding text where it is an identifier.

**Acceptance:** Zero word-only flows described as observed. Every source-reviewed flow has references that resolve at the reviewed snapshot. Existing import facts remain available without being promoted to verified behavior.

Source: [evidence.py:116](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/evidence.py#L116). Reproduction: `prose_as_observation`.

## Further implementation gaps

The following findings are narrower, but affect the same facts and views. Each has an executable reproduction unless the row explicitly identifies a benchmark audit.

| ID | Priority and finding | Confirmed trigger and outcome | Smallest useful direction and acceptance |
|---|---|---|---|
| F9 | P2: Incomplete public API representation | Constructor parameters, annotated class fields, public objects, and re-export changes can leave every surface-change bucket empty. A public function under a module-level condition is omitted. An `__init__` executing a private registration function is classified as an empty marker. | Extend the shared surface representation to supported constructs, retaining conditions and provenance. Classify executable package initialization separately. Detect every supplied API-change fixture; do not invent runtime exports for unresolved branches. [extract.py:227](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L227), [change.py:110](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/change.py#L110). |
| F10 | P2: Incomplete freshness comparison | Replacing a test with a different name at the same count produces no drift. Changing a console script's target without changing its displayed name also produces no drift. | Compare full semantic entry records and qualified test identities. Fingerprint the extraction inputs and version. Both fixtures must report stale facts. [extract.py:785](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L785). |
| F11 | P2: Failed comparisons become empty results or crashes | `change.compute` returns `has_change=False` for a nonexistent base ref. An owned source file that cannot parse reaches `deltas[m]` and raises `KeyError`. | Resolve refs with explicit errors. Propagate an unavailable surface as unknown, retaining structural change information. Both fixtures must report the failure without claiming no change or crashing. [change.py:154](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/change.py#L154). |
| F12 | P2: An explicit head uses the working tree's graph | The CLI supplies current stored facts while `change.compute` reads source diffs from the requested head. In the fixture, card B imports changed card A at the requested head; B disappears from adjacent reach when the working tree has since removed the import. | Extract the graph at the compared head, with base facts where removed dependencies matter. The result must be identical regardless of checkout state. [cli.py:260](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/cli.py#L260), [change.py:278](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/change.py#L278). |
| F13 | P2: Historical facts are cached by commit alone | Changing the configured import prefix returns the old cached module names for the same commit. A fresh extraction returns different names. Extractor and interpreter changes are also absent from the key. | Key by commit, extraction configuration, extractor schema, and parser version. Declare whether historical roots or today's scope is being compared. A configuration change must match a fresh extraction. [history.py:33](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/history.py#L33), [delta.py:134](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/delta.py#L134). |
| F14 | P2, design limit: Common names assert a move | An unrelated removed email module and added billing module, both exposing `run`, are paired as a move. Delta tells the maintainer to rename the ownership claim. | Keep uncertain pairings as candidates for source review, with ambiguity and alternatives. Unique exact content can be stronger evidence. Do not replace all rules with exact matching: the replay failed its acceptance bar. [moves.py:94](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/moves.py#L94). |
| F15 | P2: Symbol cards disappear from change attribution | A card claiming `pkg.a:run` is not highlighted when `run` changes, while the card claiming `pkg.a` is highlighted. The module matcher intentionally excludes symbol claims, but the overlay never adds symbol attribution. | Diff qualified symbols and project them onto symbol cards. If symbol attribution is unavailable, show the card as potentially affected rather than untouched. The supplied symbol card must appear. [change.py:233](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/change.py#L233), [model.py:646](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/model.py#L646). |
| F16 | P2: Decorator spelling substitutes for framework identity | `from click import command; @command()` is missed. A locally defined `cache.get('/key')` decorator is asserted to be an HTTP route. | Resolve imported decorator names and known framework bindings; report unresolved registrations as candidates. Both fixtures must be classified correctly. Click supports direct decorator use. [ways_in.py:65](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/ways_in.py#L65), [Click API](https://click.palletsprojects.com/en/stable/api/#click.command). |
| F17 | P2: Dotted package roots lose internal imports | A configured prefix `ns.pkg` is compared with the first segment `ns`. `from ns.pkg.b import run` is not recorded as an internal use. Configuration accepts dotted names. | Match full package prefixes on segment boundaries. Absolute and relative imports in a dotted root must remain internal. [extract.py:401](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L401). |
| F18 | P2: Nested journey coverage is inconsistent | A parent journey explicitly starting at a child's route still produces a child “has no journey” line. The tree shares journey prose but not explicit starts. Journey generation also gathers only from the top map. | Share structured coverage records across the tree and generate on the owning map. The parent-start fixture must not produce a false missing-journey line; add a command-level nested-generation fixture. [judgement.py:571](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/judgement.py#L571), [jev_cli.py:243](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/jev_cli.py#L243). |
| F19 | P2: A module function validates a nonexistent class method | `Item.run()` passes interface validation when `Item` has no method and `run` is an unrelated module-level function. | Resolve a member against the named class or an explicit module re-export. Do not accept another public name as a class member. Reject the supplied fixture while retaining valid re-exported-module interfaces. [check.py:555](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/check.py#L555). |
| F20 | P2: Test identities collapse | Two test classes each defining `test_value` are counted as one test. All tests in a file are also attributed to every module the file imports, so this is file association, not verified behavioral coverage. | Qualify test IDs by file, class, and function. Label the association precisely; use optional execution coverage only when behavioral evidence is required. The fixture must count both tests. [extract.py:525](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L525), [extract.py:754](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L754). |
| F21 | P2: Historical card growth includes renames | With today's card claiming only `pkg.c`, a pure rename from `pkg.a` to `pkg.c` produces card growth of +1 while total modules remain unchanged. The history report says a moved module still counts under its card, but no historical identity mapping is applied. | Either resolve reviewed module lineage or describe these as counts matched by today's paths, with unmatched historical modules shown. A pure rename must not be presented as semantic growth. [trend.py:82](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/trend.py#L82), [trend.py:117](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/trend.py#L117). |
| F22 | P2: Nested delta turns a pending rename into a deletion | When the parent and child explicitly claim the old module name, an exact-content rename is correctly reported on the parent but reported as a removal inside it. The child is told to drop its claim. | Apply the inferred name mapping before restricting the child's head facts, as the base side already applies its mapping. Both levels must report the same move and retain the child's ownership. [delta.py:569](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/delta.py#L569). Reproduction: `nested_pending_move`. |

## F23. Correct the interpretation of the previous ownership benchmark

The earlier pilot recorded a useful result: on its 32 planted assignments, the coding agent challenged all 32 and the word rule challenged 8. On 32 unchanged assignments, the agent challenged 2 and the word rule challenged 1. That is 24 additional planted errors detected, with one additional challenge to the reference assignments. The agent restored the exact reference owner on 31 of the 32 planted cases.

Those counts do not establish whole-map accuracy. This review found additional limitations in the benchmark:

1. **Mixed source snapshots:** five of the eight systemap cases contain source whose hash differs from the cached facts used alongside it. The affected modules are `describe`, `scaffold`, `audit`, `suggest`, and `jev`. Their current source still matches the captured prompt source. The mismatch is between that source and the older facts.
2. **Predictable condition order:** every repository batch presents four planted cases followed by four unchanged cases. The answerer was not told that pattern, so leakage is not proven. Randomize the condition order to remove the opportunity.
3. **Restricted alternatives:** every case includes the reference owner among only two to five cards. That is easier than discovering an appropriate owner among all cards, or deciding that the map needs a new card.
4. **Selected short modules:** files over 25,000 characters and modules without a nearby alternative are excluded. Large orchestration modules are not represented.
5. **Reference maps are not adjudicated truth:** plausible boundary disagreements were scored as errors. Obtain source-based labels and retain an ambiguous category.
6. **No end-to-end comparison:** the benchmark judges isolated assignments with supplied source. It does not test whether the actual skill finds every module, reads enough code, fixes the model correctly, or preserves accurate journeys and invariants.
7. **The acceptance bar was missed:** unchanged assignments were challenged in 2/32 cases, or 6.25%, above the preset 5% maximum. The benchmark should not be cited as passing that gate.

Source: [review_accuracy.py:52](review_accuracy.py#L52), [review_accuracy.py:106](review_accuracy.py#L106). Evidence: `pilot` sections of the census results.

Before using the pilot to justify a default behavior, rebuild a versioned dataset from one source snapshot per repository. Score the real workflow against a fresh, independently adjudicated set. Keep the current results as a pilot record. Do not silently replace or relabel them after seeing the answers.

## A Jev-free implementation plan

### First: Make deterministic results dependable

Fix F1, F6, F9 through F13, F15, F17, F19, F20, and F22. These changes improve inventory, identity, extraction, serialization, and snapshot consistency. They require no model judgement. Preserve unknowns when a static answer cannot be established.

Before each implementation, move the relevant reproductions into regression tests with explicit expected outcomes. The acceptance number is 100% for the relevant deterministic contracts and controls, with zero silent omissions or invalid writes. Run the repository gates and mapping commands. The challenge suite's total is not a product score.

### Second: Make review status follow the evidence

Fix F2 through F5 and F8. A review record should identify the claim, source snapshot, supporting symbols or registrations, result, and unresolved alternatives. A source span can move without changing meaning, so store a symbol and content digest as well as its displayed path and line.

Use the existing configured agent command to review the claims that require judgement. Supply the source, the affected claims, and the evidence records. Require a structured response containing supporting references and one of: supported, contradicted, or unresolved. Validate that references exist and that the proposed edits still satisfy model checks. Reference validation proves that a citation resolves; it does not prove that the citation supports the claim.

If no agent is configured, print the same review packet for a person to handle. Do not substitute keyword agreement for semantic review or mark unresolved claims as current. This makes the workflow useful without Jev and explicit when it needs a reader.

### Third: Review journeys as scenarios, including branches and outcomes

Fix F7 and F18 alongside structured coverage. For each important entry, record the scenario, initial conditions, main outcome, meaningful failure paths, and relevant source references. Ask the reviewer to trace calls and registrations from that entry. A list of existing map edges is insufficient evidence because the map being reviewed may already be wrong.

For grouped entries, review representatives from distinct implementations and record which entries share the scenario. A fixed first sample can miss a different handler later in the group. Keep routes, commands, and background tasks separate unless source review establishes a shared scenario.

Optional execution traces can confirm the path of a specific test or scenario. They should carry the inputs and environment they observed. A trace cannot establish that an unexecuted branch does not exist. Static evidence and execution evidence should remain distinguishable.

### Fourth: Evaluate semantic improvement on claims, not reassuring totals

An end-to-end evaluation should compare the old and proposed workflows on the same frozen repository snapshots. Preserve development cases for tuning and keep a fresh holdout for the final decision. The previously examined holdout is no longer untouched for future tuning.

Measure these separately:

| Claim type | What to score |
|---|---|
| Inventory and ownership | Files accounted for; correct owners; omitted modules; ambiguous boundaries; review coverage. |
| Flows | Supported endpoints, direction, artifact, and sentence; omitted required relationships; unsupported confident claims. |
| Diffs | True affected claims found; false review requests; edits incorrectly reported as no change; snapshot consistency. |
| Journeys | Correct entry identity, supported steps, scenario outcome, relevant branch coverage, unsupported steps. |
| Invariants | Source of the rule, continued validity, correct governed cards, stale or missing references. |
| Workflow | Incorrect edits introduced, unresolved claims retained, review time, agent calls, and repeat-run stability. |

Report paired before/after counts, percentage-point changes, denominators, and uncertainty. Report abstentions separately so a workflow cannot appear more precise by refusing every hard case. Do not use a map's existing card assignment as the sole truth label for the change being evaluated.

The acceptance rule for a semantic pilot should be written before running it: improve detected true errors without increasing incorrect confident claims on the adjudicated comparison, and pass all deterministic contracts. The attainable production rate and required sample size still need measurement. The current evidence does not justify promising a particular overall accuracy percentage.

## Changes the evidence does not support

- **Replacing all rename inference with exact hashes:** the new replay reduced Git disagreements but lost 52 correctly paired reference renames. Keep uncertain suggestions reviewable instead.
- **Generating journeys by walking module imports:** the earlier experiment achieved median card overlap of 0.28 against its 0.60 target. Imports do not specify scenario execution.
- **Rejecting journeys because consecutive edges do not join:** the earlier review found 30 flagged steps and no real problems. Journeys can branch and return.
- **Adding package-neighbor votes to ownership as a default:** the preceding experiment increased unchanged-assignment challenges to 21/195 on development and 23/96 on holdout. It failed its preset bar.
- **Treating one more LLM opinion as verified truth:** a second opinion can help find problems, but it needs source evidence and evaluation. The current pilot does not prove an overall accuracy rate.

The earlier failed experiments remain in [the benchmark log](README.md).

## Coverage and review limits

| Review area | Status and evidence |
|---|---|
| Source inventory, imports, public surface, entry discovery, tests | Reviewed with fixtures and a census of eight repositories. F1, F9, F10, F16, F17, F20. |
| Ownership, coverage, symbols, interface checks, nesting | Reviewed in model/check/evidence code and fixtures. F5, F8, F15, F18, F19. Purpose-based ownership still needs independent labels. |
| Diff computation, moves, historical facts, trends | Reviewed with temporary Git histories and a 33-commit replay. F2, F11 through F14, F21, F22. |
| Journeys, agent context/cache, writing, confirmed reasons | Reviewed through parser and CLI write paths with an injected transport. F3 through F7, F18. No real agent was called. |
| Figure/page fidelity | Traced the shared evidence and change objects into renderers; existing rendering, routing, and UI tests passed. No new browser visual audit was performed. |
| Invariants | Reviewed schema validation and skill instructions. Checks validate governed IDs, not the truth or freshness of the rule. Future source-backed review must cover both. |
| Benchmark integrity | Audited construction, ordering, inputs, labels, scoring, and recorded output. F23. No new semantic truth set was created. |

A separate local critic pass challenged the findings against existing tests and caller behavior. It was not an independent reviewer. That pass retained the documented caveats: import evidence does not itself claim execution; partial journey rejection prints a warning; the overlay sees body edits even though maintenance does not; and Git disagreements are not automatically semantic errors.

Other candidate concerns were rejected or narrowed. Duplicate ordered flows already fail model validation. General graph continuity was not proposed because the previous experiment disproved that rule's usefulness. The source census counts syntax exposure, not incorrect claims. This review does not claim exhaustive semantic verification of every existing card or journey.

An additional scan found no package initializer in these eight snapshots that was classified as an empty marker while containing a direct top-level call expression. The executable-marker finding is therefore a demonstrated synthetic edge case, not a measured current defect in those maps.

Repository validation passed: `uv run pytest -q` (376 tests), `uv run pre-commit run --all-files`, and explicit pre-commit checks of the new artifacts. Direct complexity checks also passed after simplifying two census functions. `systemap refresh` found the map current; `systemap check` reported 35 of 35 modules mapped with clean layout; `systemap judgement --strict` reported nothing pending and 18 answered lines. Those results validate the current repository contracts, not the semantic accuracy of every map claim.

## Reproduce the measurements

The scripts contain their acceptance criteria. They use temporary repositories or read existing benchmark snapshots; no Jev request or real coding-agent call is made.

```sh
uv run python bench/jev/accuracy_review.py
uv run python bench/jev/accuracy_census.py
PYTHONPATH=src uv run --no-project --python 3.12 bench/jev/accuracy_census.py bench/jev/results/no-jev-accuracy-census-py312.json.gz
PYTHONPATH=src uv run --no-project --python 3.12 bench/jev/accuracy_moves.py
```

The first attempt at the rename replay used Python 3.11 and failed because a historical Mealie module was omitted by that parser. It produced no score. The recorded replay explicitly uses Python 3.12; this is a change of interpreter with a stated reason, not a silent retry.

Artifacts:

- [Targeted cases and observed outcomes](results/no-jev-accuracy-review.json), including SHA-256 hashes of the reviewed production modules.
- [Python 3.11 census](results/no-jev-accuracy-census.json.gz).
- [Python 3.12 census](results/no-jev-accuracy-census-py312.json.gz).
- [Rename comparison](results/no-jev-accuracy-moves.json).

The next implementation should start with source accounting and stale conclusions. Those changes remove demonstrated causes of inaccurate maps. A dependable overall accuracy percentage requires the end-to-end, independently labelled evaluation described above.
