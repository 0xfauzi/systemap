# Accuracy findings and recommendations without Jev

Consolidated on 2026-09-27 from this conversation's ownership experiments,
Python review, and TypeScript review. This file contains all 32 finding IDs,
measurements, review-time dispositions, recommendations, failed approaches,
and acceptance criteria. Earlier reports remain historical records.

## Implementation follow-up (2026-09-28)

The targeted Python and TypeScript contracts now pass. The self-map has exact
journey coverage for every non-alias entry point and source-reviewed claims
for all 58 internal flows. `systemap judgement --brief --strict` reports no
open, stale, or pending items, with eight exact single-module answers. These
results supersede the review-time status lines below for implemented defects.

F23 remains an evaluation limit. `bench/jev/review_accuracy_v2.py` now freezes
source and facts together, verifies their hashes, randomizes blind ownership
cases, requires independently recorded labels and card alignment, and scores
a recorded workflow's ownership. An offline Mealie run under Python 3.12
built 437 nonempty-module cases from 460 extracted records; 23 records were
empty package markers. One nested map is recorded but not scored. The offline
checks do not supply the independent labels or a fresh workflow run. The
original pilot still missed its preset false-challenge bar.

## PR review corrections (2026-10-02)

The ten findings from the review of PR #15 are now covered by regression
contracts. The corrections address these observed failures:

| Review ID | Corrected behavior | Verification |
|---|---|---|
| R1 | TypeScript facts remain current after relocating an identical checkout. | Equal provenance and zero freshness drift across two directories; changed settings still invalidate facts. |
| R2 | Recorded card reviews survive supported Python interpreter changes. | Canonical syntax hashes match for all 45 source modules under Python 3.11 and 3.13; comments preserve hashes and body edits change them. |
| R3 | Existing positional Journey constructors preserve their drafted flag. | A fifth positional boolean leaves covers empty and coverage checks complete without crashing. |
| R4 | Full workflow evaluation uses a separate input without reference ownership. | Input preparation retains source and tests, excludes maps and case packets, and rejects changed or unbound manifests. |
| R5 | Added and removed wildcard-owned modules reopen card review. | Membership changes require a decision until a current review is recorded. |
| R6 | A reviewed flow losing its source citation reopens delta even if its import remains. | Both structural and declared fallback states require a decision. |
| R7 | Overlapping rootDirs follow the compiler's most specific root. | TypeScript 5.9.3 oracle cases match, including explicit input files. |
| R8 | TypeScript namespace and class fingerprints exclude callable bodies and static blocks. | Body edits preserve public surface; signature and public value edits change it. |
| R9 | A later journey file write failure restores earlier model files. | Staging and replacement failures preserve original bytes and modes; failed restoration retains and names the original backup. |
| R10 | Frozen working trees support tracked file deletions. | Deletions before capture are accepted; deletions during capture are rejected. |

Final verification: 501 tests passed with one expected syntax-version skip
under Python 3.11, and all 502 passed under Python 3.13. Mypy and pre-commit
passed. The self-map covers 45 of 45 modules with zero open strict judgements.
Facts format 4 invalidates historical caches created before the portability fix.

Workflow input validation checks the recorded files. External runs still need
filesystem isolation, and explicitly selected configuration files need review
before exposure. No independent semantic ownership score is claimed. Journey
write recovery handles reported I/O failures; process termination and concurrent
model edits remain outside that transaction contract.

## Contents

- [Priorities and scope](#recommended-priorities)
- [Measurements and limits](#measurements-and-their-limits)
- [All 32 findings](#complete-finding-register)
- [Implementation sequence and acceptance gates](#implementation-sequence-and-acceptance-gates)
- [Approaches not supported by the evidence](#approaches-not-supported-by-the-evidence)
- [Validation and open questions](#validation-coverage-and-unresolved-questions)
- [Reproduction and evidence](#reproduction-and-evidence-locations)

## Recommended priorities

Fix source accounting, API diffs, and evidence invalidation first. Then improve
journey identity and review the behavior each journey describes. Compiler facts
can replace several TypeScript resolution heuristics. A person or the user's
configured coding agent can review purpose and behavior without Jev.

The highest-priority TypeScript findings are F9, F10, F27, and F29. Earlier
journey, evidence, and cache findings remain open. The latest review verdict
was **Block on P1 findings**. No production accuracy fixes were implemented by
these reviews. Part of F11 was fixed by the intervening codebase update.

Earlier README and skill changes ask for every module's ownership to be reviewed
against source, including modules with no heuristic warning. Those changes remain
in the main working tree. Their end-to-end effectiveness has not been measured.

### Terms and status

A **card** groups modules by their intended job. A **flow** claims a relationship
between cards. A **journey** describes an ordered scenario through the system.
An **entry point** is a place where a scenario can start. **Facts** are extracted
source information. A **surface diff** compares public APIs between versions.
An experimental **contract** states an expected behavior before its measurement.

P1 identifies a serious accuracy or workflow failure. P2 identifies a narrower
reproduced defect or supported-use gap. A **design limit** means deliberate
behavior weakens an accuracy claim. F23 is an evaluation limitation.

The disposition in each finding describes its reviewed snapshot. The
implementation follow-up above reports the later working tree. Findings apply
to these frozen snapshots, not unspecified later code:

| Review | Revision | Scope |
|---|---|---|
| Python and shared behavior | `83aabb818069b62c3cce16dea34dcb3d4a0ebda7` | Earlier uncommitted ownership instructions and pilot; targeted contracts, Python census, rename replay. |
| TypeScript and shared behavior | `56716e947cd94ad3c0b26f2937bbbfbd9b0484fc` | Earlier-case replay; TypeScript contracts, compiler comparison, CLI and packaging checks. |

The main checkout was still at the first revision during consolidation. The
TypeScript review used a separate checkout. Source links below identify the
reviewed revisions. Consolidation changes documentation only and does not rerun
the experiments or establish a new current-code verdict.

## Measurements and their limits

The measurements answer different questions. There is no measured overall
map-accuracy percentage in this conversation.

### Python extraction and rename replay

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

### Package-neighbor ownership rule

`heuristic_owner.py` tested one addition: flag a module when at least two
other modules in its package belong to another card and none belong to its
current card. It uses the existing owner samples and places each sampled
module in a neighbouring wrong card. The bar in the script's docstring was
at least 50% of planted errors caught and at most 3% of unchanged owners
flagged, on both development and holdout maps.

| map set | rule | planted errors caught | unchanged owners flagged |
|---|---|---:|---:|
| development | current | 61/195 | 2/195 |
| development | with package evidence | 116/195 | 21/195 |
| holdout | current | 32/96 | 1/96 |
| holdout | with package evidence | 52/96 | 23/96 |

The addition missed the false-alarm bar on both sets, so it is not shipped.
Two cards can legitimately split one package by purpose. These labels are
finished maps rather than independent checks of every module's purpose, so
they measure agreement with those maps and detection of planted mistakes.
For a Jev-free map, the skill now asks the agent to review every assignment
against the code instead of treating unflagged modules as verified.

### Source-reading ownership pilot

The subsequent accuracy review found mixed snapshots in five systemap cases:
their source differs from the cached facts supplied alongside it. It also
found a fixed condition order: four planted cases, then four unchanged
cases, in every repository batch. The counts below remain the recorded
pilot results; these limitations need correction before an end-to-end
accuracy claim. See F23 in the full review.

In this pilot, code review found 24 more of the 32 planted mismatches than
the word rule: 32 rather than 8. It challenged one more of the 32 unchanged
assignments: 2 rather than 1. The run tests one code-reading judgement per
module, not the full mapping procedure.

`review_accuracy.py` sampled eight modules from each of the five development
and three holdout maps. Four kept their card; four were placed in another card
in the same region. One module appeared once. The reviewer was Claude Opus
5.5 with no tools or Jev: it saw the full source file, module facts, and the
descriptions of nearby cards, but no card's module list or reference owner.
The script selected files of at most 25,000 characters with a neighbouring
card, so these figures do not cover larger files or isolated cards.

The bar in the script's docstring was to catch at least 60% of planted wrong
assignments, challenge at most 5% of unchanged assignments, and beat the word
rule's planted-error recall on both sets. "Reference card chosen" counts
planted cases where the reviewer named the module's card in the finished map
as the better one. The results were:

| set | planted caught | reference card chosen | unchanged challenged | word rule caught | word rule challenged |
|---|---:|---:|---:|---:|---:|
| development | 20/20 | 19/20 | 1/20 | 5/20 | 1/20 |
| holdout | 12/12 | 12/12 | 1/12 | 3/12 | 0/12 |
| combined | 32/32 | 31/32 | 2/32 | 8/32 | 1/32 |

On planted mismatches, code review caught 100% versus the word rule's 25%,
an improvement of 75 percentage points. It named the reference card in 31
of 32 planted cases; the word rule does not name a replacement card. On
unchanged assignments, code review challenged 6.25% versus 3.125%, an
increase of 3.125 points. It therefore missed the preset 5% challenge bar.
Its binary decisions agreed with the finished maps on 62 of 64 cases
(96.9%), versus 39 of 64 (60.9%) for the word rule: 23 more agreements,
or 36 percentage points. This is agreement on a balanced synthetic sample,
not the error rate of a real map.

The two challenges name plausible placement errors: `poetry.config.source`
defines a source entry for `pyproject.toml`, while ProjectLoader explicitly
owns the project's sources; `praxis.reports.commitment_rollup` assembles the
weekly masthead payload, while Digest owns that presentation. One replacement
differs from the reference for `kstrl.tui.home_data`: the reviewer chose RunViews,
while the finished map puts the home board's data under Dashboard. These
are unresolved semantic labels, so the finished map cannot establish whether
the two challenges are false alarms or corrections. A maintainer must label
them before a stronger accuracy claim is possible.

The first kstrl call returned fenced JSON, which the scorer rejected and did
not count. The same prompt was retried, and the parser was changed to accept
the code fence without changing any judgement. The scored answers and their
prompt hashes are in `results/review-accuracy.json` and
`results/holdout/review-accuracy.json`. The eight scored calls reported $1.88;
the failed and diagnostic calls were not included in that cost.

### Results after TypeScript support

The earlier 37-case experiment was rerun unchanged against the new source.

| Measure | Earlier revision | Current revision | Interpretation |
|---|---:|---:|---|
| Existing project tests | 376 passed in the previous run | 400 passed in this run | The test suite grew; this is not a measured map-accuracy improvement. |
| Earlier targeted contracts met | 4 / 37 | 5 / 37 | One formerly failing case now passes. |
| Earlier targeted contracts failing | 33 / 37 | 32 / 37 | Most earlier counterexamples remain. |
| Unparsable changed module | Report raised `KeyError` | Report retains the unparsed module | A concrete repair to part of F11. |

TypeScript also retains syntax failures as module records with explicit unknowns.
The Python path still silently omits unparsable files. TypeScript constructor
signature changes are detected in the new controls; the old Python constructor
case still fails. These are language-specific differences, not a single overall
accuracy score.

The new TypeScript experiment has **32 contracts: 5 controls pass and 27
challenges fail**. It deliberately selects difficult inputs. Its failure
fraction is not an estimate of how often users receive wrong maps. Some
challenges test proposed evidence guarantees, which are identified below as
design limits rather than implementation regressions.

[Earlier-contract replay](bench/jev/results/no-jev-accuracy-review.json).
[TypeScript contracts and actual results](bench/jev/results/typescript-accuracy-review.json).

### TypeScript dependency retention

The compiler comparison used pinned Hono, Ky, and Zod revisions already named
by the project's TypeScript benchmark. It inspected 372 extracted modules.
A dependency was eligible when TypeScript 5.9.3 resolved its literal import
to another module in that extracted inventory.

The table measures **dependency occurrences whose correct target is present
in the full facts graph**. Multiple imports can refer to the same graph edge.

| Repository | Extracted modules | Eligible occurrences | Correct target present | Missing | Target retained |
|---|---:|---:|---:|---:|---:|
| Hono | 187 | 579 | 530 | 49 | 91.5% |
| Ky | 51 | 93 | 93 | 0 | 100.0% |
| Zod | 134 | 499 | 465 | 34 | 93.2% |
| Total | 372 | 1,171 | 1,088 | 83 | 92.9% |

All 83 missing occurrences are in 12 source files with parser warnings: eight
files in Hono and four in Zod. For example, Hono's `src/context.ts` loses its
imports when a generic call signature fails to parse. Zod's
`v4/classic/schemas.ts` loses imports when the grammar rejects `out` variance
syntax. These are explicit unknowns, not silent confident answers.

In isolation, the resolver finds the correct target for all 1,171 eligible
occurrences. The loss happens when full-file parsing rejects the source and
the adapter returns an empty import list. This separates a grammar-coverage
problem in these repositories from the wrong-target cases in the focused probes.

There were 1,224 literal import occurrences overall. The measurement excluded
52 that the compiler could not resolve and one whose target was outside the
extracted inventory. Npm dependencies were not installed. Compiler diagnostics
and systemap unknowns are retained in the results. This measures neither
external dependency accuracy nor false-positive rates over all possible edges.
It does not evaluate ownership, flow direction, prose, or journey behavior.

No TypeScript comparison exists for the old revision, which lacked this adapter.
The 92.9% result is therefore a current baseline, not a before/after gain.

[Corpus results, exact revisions, and missing dependencies](bench/jev/results/typescript-import-census.json).
[Reproduction script](bench/jev/typescript_import_census.py).

## Complete finding register

### F1. [P1] Keep unreadable and unparsable files in the inventory

**Latest status:** Open for Python; TypeScript improves inventory preservation. Python parse failure still omits its module. TypeScript retains a warned module, but its imports are unavailable when whole-file parsing fails.

`collect_module` returns `None` for a parse failure, and `build` skips the file. A new, unclaimed invalid file can therefore vanish before coverage is calculated. An existing explicit claim may expose the omission later, but that does not account for all files. The source inventory and the parsed facts need separate counts.

This occurred in the real Mealie snapshot: it requires Python 3.12, while this workspace runs Python 3.11. Files including `repository_generic.py`, the authentication provider, and route controller helpers disappeared. Switching the experiment to the installed Python 3.12 recovered all 15 files. Python's AST grammar depends on its release. [Python AST documentation](https://docs.python.org/3/library/ast.html).

**Change:** Record a file with `parse_error` or `unsupported_syntax`, including path, line, and parser version. Refuse a completeness claim while any discovered file remains unresolved. Select or require a parser compatible with the target project. Do not execute the application to discover its modules.

**Acceptance:** Every discovered file is parsed, explicitly excluded with a reason, or reported unresolved. Zero silent omissions in the challenge suite. All 460 Mealie files are accounted for under either interpreter.

Source: [extract.py:372](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L372), [extract.py:704](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L704). Reproduction: `parse_failure_inventory`; both census JSON files.

### F2. [P1] Recheck descriptions when implementation behavior changes

**Latest status:** Open. Two body-changed cards still produce zero named decisions and “nothing to decide”. Direct change highlighting is a passing control.

The maintenance path says to act only on delta lines needing a decision. Delta produces no such line when function bodies change without changing imports or deleting entry names. Its full-review threshold counts cards named by those lines, rather than all cards whose code changed.

The reproduction changes behavior in both cards of a two-card model. Delta reports two changed modules, zero cards named, and “the map already covers this change.” The full-review trigger remains false. Refreshing the facts then removes source-staleness warnings without checking the card descriptions, flow sentences, journeys, or invariants. The change overlay does highlight these cards; the omission is specifically in the maintenance decision path.

**Change:** Build the review set from changed source and its claimed cards. Include the affected descriptions, flows, journeys, and invariants. A body edit should request a review, not assert that a claim is false. Compute the broad-change threshold from that set. An AST fingerprint can avoid treating comments and formatting as behavioral changes.

**Acceptance:** The behavior-changing fixture names both affected cards and requests review. All affected claims remain pending until reviewed against the new source. A formatting-only control produces no semantic-change claim.

Source: [delta.py:507](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/delta.py#L507), [Delta.named](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/delta.py#L218), [maintenance instructions](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/skill/references/maintenance.md#L20). Reproduction: `body_change_review`.

### F3. [P1] Invalidate journey answers when the code changes

**Latest status:** Open. Editing source still reuses the cached journey answer: one transport call, one cache hit.

The agent cache hashes the command, question, and context. Journey context contains file paths and the map's descriptions, but no source hashes. Editing the entry function while keeping those descriptions unchanged reuses the previous answer. Updating the facts' module hash does not help because that hash is absent from the context.

The injected transport was called once across two different source versions. The second journey came from the cache. No real agent was run.

**Change:** Include a digest of the source snapshot the agent can read. A digest of all mapped source files is a simple correct first implementation; narrowing dependencies can follow measurement. Include the effective agent/model configuration when available. A commit alone does not identify uncommitted source.

**Acceptance:** Identical inputs reuse the answer. Every changed source dependency in the regression fixtures causes a fresh review. An unknown dependency set cannot produce a “reviewed against current code” claim.

Source: [agent.py:55](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/agent.py#L55), [journeys.py:143](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/journeys.py#L143). Reproduction: `journey_cache_source_freshness`.

### F4. [P1] Revisit recorded reasons when their evidence changes

**Latest status:** Open. Replacing an imported dependency without changing the crossing count leaves the old answer applicable.

An exact answered crossing line identifies the card pair and number of importing modules. It does not identify the imported symbols or source. Replacing a type import with a behavioral import leaves that line unchanged, so an old reason saying “only an annotation type is imported” still suppresses it. Broad answers can also cover future imports that the author never reviewed.

**Change:** Separate standing policies from decisions about observed code. Attach an evidence digest to a decision and reopen it when its imports or supporting source change. Keep broad policies explicit and show how many new instances they cover. Preserve existing line identifiers; add evidence alongside them.

**Acceptance:** Replacing the fixture's `Type` import with `send` requests renewed review. An unchanged instance keeps its answer. A policy applying to new instances is visibly distinguished from a prior review of those instances.

Source: [judgement.py:617](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/judgement.py#L617), [delta.py:436](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/delta.py#L436). Reproduction: `answer_dependency_freshness`.

### F5. [P1] Design limit: Give entry points stable identities and explicit coverage

**Latest status:** Open, design limit. Incidental words and non-unique entry labels still satisfy journey coverage. Empty journeys still validate.

Journey coverage currently accepts a matching word anywhere in a journey. A label containing “main” covers a `main()` entry. A `starts="GET /read"` value covers that route name in multiple modules. Starting at a card covers every entry kind on the card, so a grouped HTTP journey also covers a background task. An empty journey can satisfy these conditions.

These are deliberate compatibility and grouping rules, not accidental string matching. They still overstate what was reviewed. The real census found 18 name-collision groups. One Mealie group contains 23 modules exposing the local route `GET /{item_id}`.

**Change:** Identify entries by kind, module, target, and local name. Keep the displayed name separate. Grouped journeys should list the entries or declare a kind-specific, reviewed group. Newly discovered entries must not become covered automatically. Treat legacy word matches as migration candidates requiring confirmation.

**Acceptance:** Zero cross-module, incidental-word, or cross-kind coverage in the fixtures. Zero empty walks counted as reviewed coverage. Existing journeys migrate without silently claiming new entries.

Source: [judgement.py:277](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/judgement.py#L277). Reproductions: `entry_identity_collision`, `incidental_word_coverage`, `crowd_kind_scope`, `empty_journey_validation`.

### F6. [P1] Serialize generated journey text safely before writing the model

**Latest status:** Open. A quoted sentence still generates invalid Python in the journey writer.

Journey source is assembled by inserting text inside double quotes. An ordinary sentence such as `A sends the "value" to B.` produces invalid Python. The writer overwrites the model without compiling the complete proposed source first. This prevents later map commands from loading the model.

**Change:** Serialize all string values as Python literals, construct the proposed complete source, validate it, then replace the file atomically. Use syntax-aware insertion or verify the insertion target. The current text anchor can also match text that is not the intended tuple.

**Acceptance:** Quotes, backslashes, Unicode, and newlines round-trip exactly. Zero invalid model writes. On any validation failure, the existing model remains byte-for-byte unchanged.

Source: [journeys.py:260](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/journeys.py#L260), [jev_cli.py:281](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/jev_cli.py#L281). Reproduction: `journey_string_roundtrip`.

### F7. [P2] Refuse an invalid journey as a whole

**Latest status:** Open. A partially invalid journey still retains its valid step instead of rejecting the proposed journey as a whole.

If one returned step is valid and another names an invalid edge, the parser drops the invalid step and still returns a journey. The CLI writes that shortened walk and prints the problem. The warning is visible, but the stored artifact is a different walk from the answer. Existing tests explicitly expect partial acceptance.

**Change:** Return a rejected draft whenever any step fails validation. Preserve the original answer and diagnostics for correction. Validate field types and required text before constructing steps. Keep the draft marker for semantic review after structural validation.

**Acceptance:** Zero partial writes from malformed or invalid answers. The valid control is preserved exactly. Do not add an edge-adjacency rule: the earlier continuity experiment rejected legitimate branching journeys.

Source: [journeys.py:188](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/journeys.py#L188). Reproduction: `partial_journey_rejection`.

### F8. [P1] Design limit: Separate structural evidence from a verified flow claim

**Latest status:** Open, design limit; expanded to TypeScript. A mechanism word in prose still yields “observed”. A type-only import also yields “observed: an import joins them” for an authored data flow.

An internal flow can become “observed by: queue” solely because its sentence contains a configured word. The reproduction obtains that state with no facts at all. An import between cards, or a shared module, also establishes proximity but does not verify the flow's direction, artifact, or sentence. Existing tests document these classifications.

The eight maps contain four flows promoted by a mechanism word. There are also 341 `TYPE_CHECKING` blocks in the source census. This does not mean their flows are wrong; it means runtime behavior cannot be inferred from every syntactic import. Python explicitly defines `TYPE_CHECKING` as false at runtime. [Python typing documentation](https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING).

**Change:** Represent the evidence as “import present,” “shared module,” “mechanism declared,” “source reviewed,” or “execution observed.” A reviewed semantic flow should cite the call, registration, write/read pair, or other supporting source. Record direction and artifact separately. Preserve the existing finding text where it is an identifier.

**Acceptance:** Zero word-only flows described as observed. Every source-reviewed flow has references that resolve at the reviewed snapshot. Existing import facts remain available without being promoted to verified behavior.

Source: [evidence.py:116](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/evidence.py#L116). Reproduction: `prose_as_observation`.

### F9. [P1] TypeScript API changes disappear from surface diffs

**Open, expanded from the earlier public-surface finding.** An interface property
changing from `id: string` to `id: number` produces empty added, removed, and
changed buckets. The same happens for a type alias, enum value, public class
field, generic arrow-function constraint, and an overload signature. Public
objects and local or remote re-exports can disappear without a surface removal.

The adapter stores interfaces, aliases, and enums as class records whose
fingerprint contains only methods. Other exported names exist in `names` but
never enter the diff's four buckets. Overloads overwrite each other in the
name-to-signature dictionary. The map can identify the directly changed file
while omitting the changed contract carried between cards.

There is a second identity mismatch: a named default function is imported as
`default`, but its changed signature is recorded under its local name. The
integration fixture highlights the API and its caller, yet reports no changed
artifact on the connection.

Fix direction: represent exported API identities and their definitions before
projecting them into display buckets. Preserve properties, aliases, enum
members, generic constraints, overload sets, object exports, and re-export
bindings. Use the exported name consistently for imported artifacts.
Acceptance: every supplied API-change case must report the change or explicit
uncertainty. The default-function case must identify the changed artifact.

Evidence: `interface_property`, `type_alias`, `enum_value`,
`public_class_field`, `generic_constraint`, `local_export_signature`,
`local_export_removed`, `named_reexport_removed`, `overload_changed`,
`object_removed`, `default_export_change_wire`.
[Type records](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_surface.py#L106),
[diff fingerprints](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/change.py#L84),
[default export renaming](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_surface.py#L430).

**Python scope retained:** Constructor parameters, annotated class fields, public objects, and re-export changes can leave every surface-change bucket empty. A public function under a module-level condition can be omitted. A package initializer executing private registration can be treated as an empty marker. These Python cases remain open. TypeScript detects its constructor-signature control, so that result differs by language.

### F10. [P1] Configuration can change the graph while freshness checks pass

**Open, expanded from the earlier freshness finding.** Changing only a
`tsconfig.json` alias changes the module imported by a source file. A fresh
extraction records the new edge, but `extract.drift` returns no difference.
The command-level reproduction runs `refresh`, changes the alias, then runs
`extract --check`. Both commands exit zero. The latter says that the map is
current.

Freshness compares source hashes, entry labels, and total test counts. It does
not compare import targets or fingerprint the configuration used to derive them.
Commands reading the stored facts can therefore continue to draw and judge
the old graph. The old same-count test and script-target cases also still fail.

Fix direction: compare the derived facts that readers use, or fingerprint all
extraction inputs and invalidate their outputs. Include inherited configuration,
parser/extractor version, and relevant package metadata.
Acceptance: both alias-change probes must invalidate the stored map, while an
unchanged rebuild remains current.

Evidence: `config_dependency_freshness`, `config_freshness_cli`.
[Freshness comparison](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/extract.py#L1096),
[CLI gate](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/cli.py#L188).

### F11. [P2] Failed comparisons become empty results or crashes

**Latest status:** Partially fixed. Unparsable changes no longer crash. An invalid comparison ref still produces `has_change=False`.

**Observation at the earlier revision:** `change.compute` returns `has_change=False` for a nonexistent base ref. An owned source file that cannot parse reaches `deltas[m]` and raises `KeyError`.

**Recommendation and acceptance:** Resolve refs with explicit errors. Propagate an unavailable surface as unknown, retaining structural change information. Both fixtures must report the failure without claiming no change or crashing. [change.py:154](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/change.py#L154).

### F12. [P2] An explicit head uses the working tree's graph

**Latest status:** Open. An explicit historical head still gives different reach when supplied working-tree facts.

**Observation at the earlier revision:** The CLI supplies current stored facts while `change.compute` reads source diffs from the requested head. In the fixture, card B imports changed card A at the requested head; B disappears from adjacent reach when the working tree has since removed the import.

**Recommendation and acceptance:** Extract the graph at the compared head, with base facts where removed dependencies matter. The result must be identical regardless of checkout state. [cli.py:260](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/cli.py#L260), [change.py:278](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/change.py#L278).

### F13. [P2] Historical facts are cached by commit alone

**Latest status:** Open. Reusing a commit cache after changing the configured module prefix still returns the old names.

**Observation at the earlier revision:** Changing the configured import prefix returns the old cached module names for the same commit. A fresh extraction returns different names. Extractor and interpreter changes are also absent from the key.

**Recommendation and acceptance:** Key by commit, extraction configuration, extractor schema, and parser version. Declare whether historical roots or today's scope is being compared. A configuration change must match a fresh extraction. [history.py:33](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/history.py#L33), [delta.py:134](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/delta.py#L134).

### F14. [P2] Design limit: Common names assert a move

**Latest status:** Open, design limit. Unrelated removed and added modules exposing only `run` are still asserted to be a move.

**Observation at the earlier revision:** An unrelated removed email module and added billing module, both exposing `run`, are paired as a move. Delta tells the maintainer to rename the ownership claim.

**Recommendation and acceptance:** Keep uncertain pairings as candidates for source review, with ambiguity and alternatives. Unique exact content can be stronger evidence. Do not replace all rules with exact matching: the replay failed its acceptance bar. [moves.py:94](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/moves.py#L94).

### F15. [P2] Symbol cards disappear from change attribution

**Latest status:** Open. A changed symbol card is still absent from the overlay while its module card is present.

**Observation at the earlier revision:** A card claiming `pkg.a:run` is not highlighted when `run` changes, while the card claiming `pkg.a` is highlighted. The module matcher intentionally excludes symbol claims, but the overlay never adds symbol attribution.

**Recommendation and acceptance:** Diff qualified symbols and project them onto symbol cards. If symbol attribution is unavailable, show the card as potentially affected rather than untouched. The supplied symbol card must appear. [change.py:233](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/change.py#L233), [model.py:646](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/model.py#L646).

### F16. [P2] Decorator spelling substitutes for framework identity

**Latest status:** Open. An imported Click decorator is missed; an unrelated local `get` decorator is called a route.

**Observation at the earlier revision:** `from click import command; @command()` is missed. A locally defined `cache.get('/key')` decorator is asserted to be an HTTP route.

**Recommendation and acceptance:** Resolve imported decorator names and known framework bindings; report unresolved registrations as candidates. Both fixtures must be classified correctly. Click supports direct decorator use. [ways_in.py:65](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/ways_in.py#L65), [Click API](https://click.palletsprojects.com/en/stable/api/#click.command).

### F17. [P2] Dotted package roots lose internal imports

**Latest status:** Open for Python. A dotted Python package prefix still loses an internal import. The TypeScript scoped-package control passes in the existing suite.

**Observation at the earlier revision:** A configured prefix `ns.pkg` is compared with the first segment `ns`. `from ns.pkg.b import run` is not recorded as an internal use. Configuration accepts dotted names.

**Recommendation and acceptance:** Match full package prefixes on segment boundaries. Absolute and relative imports in a dotted root must remain internal. [extract.py:401](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L401).

### F18. [P2] Nested journey coverage is inconsistent

**Latest status:** Open. A parent's explicit child start still fails to satisfy the child's journey-coverage check.

**Observation at the earlier revision:** A parent journey explicitly starting at a child's route still produces a child “has no journey” line. The tree shares journey prose but not explicit starts. Journey generation also gathers only from the top map.

**Recommendation and acceptance:** Share structured coverage records across the tree and generate on the owning map. The parent-start fixture must not produce a false missing-journey line; add a command-level nested-generation fixture. [judgement.py:571](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/judgement.py#L571), [jev_cli.py:243](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/jev_cli.py#L243).

### F19. [P2] A module function validates a nonexistent class method

**Latest status:** Open. A module function still validates a nonexistent method of a named class.

**Observation at the earlier revision:** `Item.run()` passes interface validation when `Item` has no method and `run` is an unrelated module-level function.

**Recommendation and acceptance:** Resolve a member against the named class or an explicit module re-export. Do not accept another public name as a class member. Reject the supplied fixture while retaining valid re-exported-module interfaces. [check.py:555](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/check.py#L555).

### F20. [P2] Test identities collapse

**Latest status:** Open. Test identities still collapse by unqualified name. TypeScript adds separate early-cap and modifier problems, F31 and F32.

**Observation at the earlier revision:** Two test classes each defining `test_value` are counted as one test. All tests in a file are also attributed to every module the file imports, so this is file association, not verified behavioral coverage.

**Recommendation and acceptance:** Qualify test IDs by file, class, and function. Label the association precisely; use optional execution coverage only when behavioral evidence is required. The fixture must count both tests. [extract.py:525](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L525), [extract.py:754](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/extract.py#L754).

### F21. [P2] Historical card growth includes renames

**Latest status:** Open. A pure rename still appears as growth under today's explicit card path.

**Observation at the earlier revision:** With today's card claiming only `pkg.c`, a pure rename from `pkg.a` to `pkg.c` produces card growth of +1 while total modules remain unchanged. The history report says a moved module still counts under its card, but no historical identity mapping is applied.

**Recommendation and acceptance:** Either resolve reviewed module lineage or describe these as counts matched by today's paths, with unmatched historical modules shown. A pure rename must not be presented as semantic growth. [trend.py:82](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/trend.py#L82), [trend.py:117](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/trend.py#L117).

### F22. [P2] Nested delta turns a pending rename into a deletion

**Latest status:** Open. Parent delta reports a rename while the child reports removal of the same module.

**Observation at the earlier revision:** When the parent and child explicitly claim the old module name, an exact-content rename is correctly reported on the parent but reported as a removal inside it. The child is told to drop its claim.

**Recommendation and acceptance:** Apply the inferred name mapping before restricting the child's head facts, as the base side already applies its mapping. Both levels must report the same move and retain the child's ownership. [delta.py:569](https://github.com/0xfauzi/systemap/blob/83aabb818069b62c3cce16dea34dcb3d4a0ebda7/src/systemap/delta.py#L569). Reproduction: `nested_pending_move`.

### F23. Evaluation limitation: interpret the ownership pilot correctly

**Latest status:** The pilot limitations remain. An offline replacement harness
now prepares matched snapshots, blind cases, independent-label validation, and
full-workflow ownership scoring. No independent labels or fresh workflow scores
are recorded yet.

The earlier pilot recorded a useful result: on its 32 planted assignments, the coding agent challenged all 32 and the word rule challenged 8. On 32 unchanged assignments, the agent challenged 2 and the word rule challenged 1. That is 24 additional planted errors detected, with one additional challenge to the reference assignments. The agent restored the exact reference owner on 31 of the 32 planted cases.

Those counts do not establish whole-map accuracy. This review found additional limitations in the benchmark:

1. **Mixed source snapshots:** five of the eight systemap cases contain source whose hash differs from the cached facts used alongside it. The affected modules are `describe`, `scaffold`, `audit`, `suggest`, and `jev`. Their current source still matches the captured prompt source. The mismatch is between that source and the older facts.
2. **Predictable condition order:** every repository batch presents four planted cases followed by four unchanged cases. The answerer was not told that pattern, so leakage is not proven. Randomize the condition order to remove the opportunity.
3. **Restricted alternatives:** every case includes the reference owner among only two to five cards. That is easier than discovering an appropriate owner among all cards, or deciding that the map needs a new card.
4. **Selected short modules:** files over 25,000 characters and modules without a nearby alternative are excluded. Large orchestration modules are not represented.
5. **Reference maps are not adjudicated truth:** plausible boundary disagreements were scored as errors. Obtain source-based labels and retain an ambiguous category.
6. **No end-to-end comparison:** the benchmark judges isolated assignments with supplied source. It does not test whether the actual skill finds every module, reads enough code, fixes the model correctly, or preserves accurate journeys and invariants.
7. **The acceptance bar was missed:** unchanged assignments were challenged in 2/32 cases, or 6.25%, above the preset 5% maximum. The benchmark should not be cited as passing that gate.

Source: [review_accuracy.py:52](bench/jev/review_accuracy.py#L52), [review_accuracy.py:106](bench/jev/review_accuracy.py#L106). Evidence: `pilot` sections of the census results.

Before using the pilot to justify a default behavior, rebuild a versioned dataset from one source snapshot per repository. Score the real workflow against a fresh, independently adjudicated set. Keep the current results as a pilot record. Do not silently replace or relabel them after seeing the answers.

The TypeScript benchmark also has a limit: recording a name or unknown for each export does not establish that its API definition is correct. Attributing a test file to a module does not verify its test totals or behavioral coverage.

### F24. [P2] Dotted paths can resolve to a different file

**Latest status:** Open, new in the TypeScript review.

With both `foo.bar.ts` and `foo.ts`, importing `./foo.bar.js` resolves to `foo.bar.ts` in the compiler and `foo.ts` in systemap. There is no unknown warning.

**Recommendation and acceptance:** Replace recognized script extensions without deleting another suffix. The dotted-file probe must match the compiler. Also use the same resolver for test attribution.

Source: [Path candidates](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript.py#L121)

### F25. [P2] Alias precedence differs from TypeScript

**Latest status:** Open, new in the TypeScript review.

A broad alias listed first wins over a more specific matching alias. A normalized module name can also win before an explicit alias is considered. Both fixtures select the wrong existing module.

**Recommendation and acceptance:** Use compiler resolution rules, including exact matches and wildcard specificity. Both alias probes must match the compiler regardless of JSON property order.

Source: [Early name match](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript.py#L130), [alias ordering](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_config.py#L434)

### F26. [P2] Valid dependencies are omitted without uncertainty

**Latest status:** Open, new in the TypeScript review.

Literal dynamic imports and `import x = require("./value")` yield no dependency. A relative import resolved through `rootDirs` is also absent. All three targets resolve in the compiler.

**Recommendation and acceptance:** Record these syntax forms and resolution options, or mark their dependency evidence unavailable. Every supplied dependency must be retained or specifically reported as unresolved.

Source: [Import visitor](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript.py#L245), [resolver](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript.py#L173)

### F27. [P1] Re-export chains lose function kinds and entry points

**New.** A valid `index -> a -> middle -> z` re-export chain exposes a function
according to TypeScript 5.9.3, with no compiler diagnostics. systemap leaves the
index's name classified as `reexport` and produces no public entry point.

Named exports are resolved once, in module order. A source that has not yet
been resolved supplies its intermediate kind. No later pass repairs consumers.
Journey discovery depends on the resulting entry list, so a public way into a
library can disappear before journey coverage is checked.

Fix direction: resolve export bindings through their defining symbols with
cycle handling. Preserve aliases and default names while doing so.
Acceptance: the supplied chain must expose `run` as a function and entry point;
renaming files to change traversal order must not change that result.

Evidence: `reexport_chain`.
[Single-pass binding resolution](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/extract.py#L542),
[entry filtering](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript.py#L583).

### F28. [P2] The inferred TypeScript 5 emit root omits imported inputs

**Latest status:** Open, new in the TypeScript review.

A file under `src` imports a file under `shared`, outside `include: ["src"]`. The compiler's common source directory is the repository. systemap instead accepts `out/cli.js` and rejects the actual `out/src/cli.js` target.

**Recommendation and acceptance:** Derive the emit root from the complete compiler program, including transitive imports. The fixture must map only the correct bin target.

Source: [Input selection](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_config.py#L341), [root computation](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_config.py#L410)

### F29. [P1] Generated TypeScript CI omits the required parser extra

**New.** `scaffold.files(..., language="typescript")` generates five tool
invocations using `systemap==1.2.0`, with no `[typescript]` extra. The reviewed
package declares the parser dependencies only in that extra. A clean isolated
installation of this checkout without extras raises
`ConfigError: TypeScript support is not installed; install systemap[typescript]`.

The development environment hides this because the dev dependency group includes
the parsers. The default generated workflow cannot provide the promised
TypeScript freshness and judgement gates in a clean environment.

Fix direction: generate the dependency specification from the selected language.
Acceptance: every TypeScript workflow invocation requests its required extra,
and extraction succeeds in a clean environment containing only that specification.
The isolated check used the reviewed local package, not a claim about the contents
of an independently published release.

Evidence: `typescript_ci_extra` and the isolated installation command in the
run log.
[Workflow commands](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/scaffold.py#L269),
[workflow generation](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/scaffold.py#L396),
[optional dependencies](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/pyproject.toml#L13).

### F30. [P2] JavaScript private methods enter the public API

**Latest status:** Open, new in the TypeScript review.

`#hidden()` is recorded beside `public visible()`. Only textual access modifiers are filtered.

**Recommendation and acceptance:** Exclude private identifiers as well as private/protected modifiers. The public-method fixture must contain only `visible`.

Source: [Method collection](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_surface.py#L93)

### F31. [P2] Display truncation changes test totals

**Latest status:** Open, new in the TypeScript review.

Thirty distinct tests in one file are reported as 25 total tests because the names are truncated before aggregation.

**Recommendation and acceptance:** Count all qualified tests, then cap only the displayed sample. The fixture must report 30 total and at most 25 displayed.

Source: [Early cap](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript.py#L85)

### F32. [P2] Common test modifiers disappear

**Latest status:** Open, new in the TypeScript review.

A file containing `test.only`, `it.concurrent`, and ordinary `test` retains only the ordinary test name.

**Recommendation and acceptance:** Recognize supported test-call chains and retain execution modifiers separately. All three literal names must be retained.

Source: [Test scanner](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_surface.py#L502)

## Implementation sequence and acceptance gates

### First: Make deterministic results dependable

Fix F1, F6, F9 through F13, F15, F17, F19, F20, F22, and F24 through F32. For F11, retain the repaired crash case and fix the remaining invalid-ref behavior. These changes improve inventory, identity, extraction, serialization, and snapshot consistency. They require no model judgement. Preserve unknowns when a static answer cannot be established.

Before each implementation, move the relevant reproductions into regression tests with explicit expected outcomes. The acceptance number is 100% for the relevant deterministic contracts and controls, with zero silent omissions or invalid writes. Run the repository gates and mapping commands. The challenge suite's total is not a product score.

### TypeScript-specific work in the deterministic phase

#### Use compiler facts

The compiler oracle already resolves the adversarial import cases and reads
the source files that triggered the 83 missing dependency occurrences. This
supports prototyping a compiler-backed extraction provider. It does not yet
prove the performance or deployment characteristics of a production provider.

The provider should return file identities, resolved imports, export bindings,
public declarations, diagnostics, and configuration provenance. systemap should
then project those facts into cards and diffs. This removes custom resolution
rules and makes unsupported syntax explicit. Retain the existing lightweight
provider only with a clearly recorded provider identity and coverage limits.

Acceptance before implementation: recover all 83 eligible missing occurrences,
introduce zero wrong targets on the current corpus, and pass every focused
resolver case. Measure extraction latency and memory on the full seven-repository
benchmark before selecting a production approach or a latency limit. No latency
claim for the proposed provider has been established by this review.

#### Make API diffs use one complete exported representation

A class-shaped record cannot represent every TypeScript contract. Compare
public declarations and bindings first, then summarize the differences for the
map. Include a symbol's exported identity, fields, generic parameters, overloads,
and type/value role. Preserve unresolved definitions rather than equating them.

Acceptance: all F9 fixtures, including default-export connection attribution,
must become informative. Unchanged bodies and formatting-only changes need
controls so broader extraction does not create spurious API-change claims.

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

### Preserve coverage and review uncertainty

Review every claimed module, including those with no judgement line. Compare
source and public declarations with the card's purpose. If neither the current
card nor an alternative fits, revise the cards. Record unresolved alternatives
and source evidence. A package, word, or import match does not establish purpose.

Preserve command finding text where it serves as an identifier. Add evidence
and explanations alongside it. After production changes, name new modules in
map cards and run `uv run pytest`, `uv run pre-commit run --all-files`,
`systemap refresh`, `systemap check`, and `systemap judgement`. Tests must use
injected or recorded responses, with no real Jev or coding-agent calls.

## Approaches not supported by the evidence

- **Replacing all rename inference with exact hashes:** the new replay reduced Git disagreements but lost 52 correctly paired reference renames. Keep uncertain suggestions reviewable instead.
- **Generating journeys by walking module imports:** the earlier experiment achieved median card overlap of 0.28 against its 0.60 target. Imports do not specify scenario execution.
- **Rejecting journeys because consecutive edges do not join:** the earlier review found 30 flagged steps and no real problems. Journeys can branch and return.
- **Adding package-neighbor votes to ownership as a default:** the preceding experiment increased unchanged-assignment challenges to 21/195 on development and 23/96 on holdout. It failed its preset bar.
- **Treating one more LLM opinion as verified truth:** a second opinion can help find problems, but it needs source evidence and evaluation. The current pilot does not prove an overall accuracy rate.

The earlier failed experiments remain in [the benchmark log](bench/jev/README.md).

### Additional TypeScript concerns that were rejected or narrowed

Module-ID collisions now raise `ConfigError`, so silent overwriting is not a
current defect. The documented adapter scope is `.ts` and `.tsx`; omission of
`.mts` and `.cts` was not reported as a violation of that scope.

Conflicting star exports produce compiler error TS2308 in the probe. That result
is retained as an uncertainty case, not a separate blocker: complete compiler
semantic validation is not promised. The valid `rootDirs` dependency remains
under F26 because its absence is silent.

Type-only imports establish source dependencies, not runtime movement. See the
[TypeScript module reference](https://www.typescriptlang.org/docs/handbook/modules/reference.html).
Compiler input selection is documented under [exclude](https://www.typescriptlang.org/tsconfig/exclude.html).
The modifier forms in F32 appear in the [Vitest test API](https://vitest.dev/api/test).

## Validation, coverage, and unresolved questions

### Python review

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

### TypeScript review

| Area | State | Evidence and remaining limit |
|---|---|---|
| TypeScript/TSX extraction, config, resolution, re-exports | Finding | Read the new adapters and their callers; compiler-checked fixtures and three pinned repositories. Nested project references, installed workspace packages, and every compiler option were not exhaustively validated. |
| Public APIs, diffs, test attribution, historical comparisons | Finding | Surface fixtures, temporary Git histories, earlier replay, and existing tests. No new long-history TypeScript rename benchmark. |
| Facts freshness and CI packaging | Finding | Command-level alias mutation and clean package installation; inspected generated workflow commands. No GitHub Actions run was dispatched. |
| Ownership, coverage, evidence, journeys, nesting, answers | Finding | Earlier contracts replayed; unchanged shared code verified; added type-only-flow and barrel-entry interactions. No live agent output evaluation. |
| Schema, skill copies, optional dependency handling | Reviewed | Existing tests, pre-commit, and strict type checking pass. No changes to their shipped files. |
| Figures and page integration | Finding | Traced facts and change objects into consumers; existing rendering tests pass. No new visual browser review. |
| New benchmark quality | Reviewed with limits | Compiler is the separate reference for resolution. Compared actual full facts, not only isolated resolver calls. Sampling is purposeful, dependencies uninstalled, and counts are not semantic truth labels. |
| Production semantic accuracy and compiler-provider latency | Not covered | No independent map/journey truth set or production provider exists in this review. These need measurements before a broader accuracy or speed claim. |

Validation completed:

- `uv run pytest -q`: **400 passed**.
- `uv run pre-commit run --all-files`: **passed** for tracked files.
- `uv run mypy src/systemap`: **passed**, 40 source files.
- Earlier-contract replay: **5/37 met**, including all four controls.
- New TypeScript contracts: **5/32 met**, all five controls.
- New Python review scripts: direct Ruff and complexity checks, since untracked
  files are outside the ordinary all-files hook selection.
- Node syntax check for the compiler oracle.

The audit used separate **local** review and critic passes, not independent
reviewers. All reported P1s are coordinator-reproduced. The critic retained
F9, F10, F27, and F29 after checking their consumers and controls. It rejected
module-ID overwrite as a current defect because collisions now raise
`ConfigError`. It also rejected unsupported `.mts/.cts` files as a violation
of the documented `.ts/.tsx` scope.

Conflicting star exports remain a measured uncertainty case, not a separate
blocking finding: the fixture itself has compiler error TS2308, and systemap
does not promise complete compiler semantic validation. Missing `rootDirs`
support is retained under F26 because the valid dependency is silently absent.
No unresolved blocking candidate remains.

The final integration challenge followed three paths: export identity into
connection diffs, configuration changes into the CLI freshness gate, and
language selection into generated CI installation. Each produced a reproduced
finding already included above. The reviewed production snapshot remained
unchanged.

## Reproduction and evidence locations

All substantive findings and results are included above. Raw fixtures, answers,
and source fingerprints are linked below. Source links use the reviewed Git
revisions. They support the findings in this file.

### Python experiments in the main checkout

The scripts contain their acceptance criteria. They use temporary repositories or read existing benchmark snapshots; no Jev request or real coding-agent call is made.

```sh
uv run python bench/jev/accuracy_review.py
uv run python bench/jev/accuracy_census.py
PYTHONPATH=src uv run --no-project --python 3.12 bench/jev/accuracy_census.py bench/jev/results/no-jev-accuracy-census-py312.json.gz
PYTHONPATH=src uv run --no-project --python 3.12 bench/jev/accuracy_moves.py
```

The first attempt at the rename replay used Python 3.11 and failed because a historical Mealie module was omitted by that parser. It produced no score. The recorded replay explicitly uses Python 3.12; this is a change of interpreter with a stated reason, not a silent retry.

Artifacts:

- [Targeted cases and observed outcomes](bench/jev/results/no-jev-accuracy-review.json), including SHA-256 hashes of the reviewed production modules.
- [Python 3.11 census](bench/jev/results/no-jev-accuracy-census.json.gz).
- [Python 3.12 census](bench/jev/results/no-jev-accuracy-census-py312.json.gz).
- [Rename comparison](bench/jev/results/no-jev-accuracy-moves.json).

### TypeScript experiments in the review checkout

Run from this review checkout using `uv`. Supply the path to an installed
TypeScript 5.9.3 `lib/typescript.js` for the compiler comparisons.

```sh
uv run python bench/jev/accuracy_review.py
uv run python bench/jev/typescript_accuracy_review.py /path/to/typescript/lib/typescript.js
uv run python bench/jev/typescript_import_census.py /path/to/pinned/checkouts /path/to/typescript/lib/typescript.js
```

The census expects `hono`, `ky`, and `zod` directories and checks their exact
commits before extraction. The JSON records source fingerprints or repository
revisions, compiler information, expected outcomes, and actual results.
The scripts create temporary fixtures and do not modify production source.

TypeScript review revision: `56716e947cd94ad3c0b26f2937bbbfbd9b0484fc`.

The review scripts and results are included in this checkout as part of the
implementation. The earlier ownership pilot did call a coding agent; the later
deterministic review scripts did not. The original results are not relabelled.

## Decision before claiming improvement

Preserve the frozen results, failed cases, and missed acceptance bars. Write the
next acceptance criteria before implementation. Compare paired outcomes on the
same source snapshots and validate a fresh independently labelled holdout.
Report missing facts, unsupported confident claims, and abstentions separately.

The evidence supplies concrete failures and tests for repairing them without
Jev. Overall semantic map accuracy, journey correctness, production compiler
latency, and the required evaluation sample size still need measurement.

## Implementation verification, 2026-09-28

The review above records the original state and remains the baseline evidence.
The implementation now passes all 37 Python and all 32 TypeScript targeted
contracts. The pinned Hono, Ky and Zod dependency census matches 1,171 of
1,171 compiler-resolved targets in the extracted inventory, with zero wrong
targets. The repository suite passes 463 tests, and all pre-commit hooks pass.

F23 remains an evaluation limitation. Its ownership pilot missed the preset
false-challenge bar and has no independently adjudicated end-to-end labels.
It is not used to justify a default policy change. The new entry and flow
review rules deliberately reopen legacy map claims until current source is
reviewed and exact identities or citations are recorded. The original result
files remain unchanged; the current counts above were measured by rerunning
the scripts in memory against the implementation.
