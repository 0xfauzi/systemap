# Accuracy review after TypeScript support

Reviewed revision: `56716e947cd94ad3c0b26f2937bbbfbd9b0484fc`.
Previous review: `83aabb818069b62c3cce16dea34dcb3d4a0ebda7`.
Completed: 2026-09-27.

## Findings that need attention first

TypeScript support adds useful extraction and explicit parser warnings. It does
not resolve the earlier problems with journey evidence, review freshness, or
semantic change detection. The most important new failures are incomplete API
diffs, stale dependency graphs after configuration changes, lost entry points
through re-exports, and a generated CI workflow that omits its parser dependency.

**Review result: findings present. Verdict: Block on the P1 findings below.**
This is a review of the current codebase, including affected existing behavior.
It is not a claim that every finding was introduced by the TypeScript changes.
No production source was changed. No Jev request or coding agent was run.

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

## Other confirmed TypeScript findings

These findings affect narrower inputs. Each has an executed counterexample.

| ID | Finding and observed result | Fix direction and acceptance | Source |
|---|---|---|---|
| F24 | **[P2] Dotted paths can resolve to a different file.** With both `foo.bar.ts` and `foo.ts`, importing `./foo.bar.js` resolves to `foo.bar.ts` in the compiler and `foo.ts` in systemap. There is no unknown warning. | Replace recognized script extensions without deleting another suffix. The dotted-file probe must match the compiler. Also use the same resolver for test attribution. | [Path candidates](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript.py#L121) |
| F25 | **[P2] Alias precedence differs from TypeScript.** A broad alias listed first wins over a more specific matching alias. A normalized module name can also win before an explicit alias is considered. Both fixtures select the wrong existing module. | Use compiler resolution rules, including exact matches and wildcard specificity. Both alias probes must match the compiler regardless of JSON property order. | [Early name match](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript.py#L130), [alias ordering](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_config.py#L434) |
| F26 | **[P2] Valid dependencies are omitted without uncertainty.** Literal dynamic imports and `import x = require("./value")` yield no dependency. A relative import resolved through `rootDirs` is also absent. All three targets resolve in the compiler. | Record these syntax forms and resolution options, or mark their dependency evidence unavailable. Every supplied dependency must be retained or specifically reported as unresolved. | [Import visitor](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript.py#L245), [resolver](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript.py#L173) |
| F28 | **[P2] The inferred TypeScript 5 emit root omits imported inputs.** A file under `src` imports a file under `shared`, outside `include: ["src"]`. The compiler's common source directory is the repository. systemap instead accepts `out/cli.js` and rejects the actual `out/src/cli.js` target. | Derive the emit root from the complete compiler program, including transitive imports. The fixture must map only the correct bin target. | [Input selection](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_config.py#L341), [root computation](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_config.py#L410) |
| F30 | **[P2] JavaScript private methods enter the public API.** `#hidden()` is recorded beside `public visible()`. Only textual access modifiers are filtered. | Exclude private identifiers as well as private/protected modifiers. The public-method fixture must contain only `visible`. | [Method collection](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_surface.py#L93) |
| F31 | **[P2] Display truncation changes test totals.** Thirty distinct tests in one file are reported as 25 total tests because the names are truncated before aggregation. | Count all qualified tests, then cap only the displayed sample. The fixture must report 30 total and at most 25 displayed. | [Early cap](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript.py#L85) |
| F32 | **[P2] Common test modifiers disappear.** A file containing `test.only`, `it.concurrent`, and ordinary `test` retains only the ordinary test name. | Recognize supported test-call chains and retain execution modifiers separately. All three literal names must be retained. | [Test scanner](https://github.com/0xfauzi/systemap/blob/56716e947cd94ad3c0b26f2937bbbfbd9b0484fc/src/systemap/typescript_surface.py#L502) |

The compiler independently confirmed the import targets in F24, F25, F26, and
F28. TypeScript documents its [module resolution rules](https://www.typescriptlang.org/docs/handbook/modules/reference.html)
and that [imports can add files outside the configured include/exclude selection](https://www.typescriptlang.org/tsconfig/exclude.html).
The test modifier forms are documented in the [Vitest test API](https://vitest.dev/api/test).

## What improved since the earlier review?

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

[Earlier-contract replay](results/no-jev-accuracy-review.json).
[TypeScript contracts and actual results](results/typescript-accuracy-review.json).

## What the real-repository measurement says

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

[Corpus results, exact revisions, and missing dependencies](results/typescript-import-census.json).
[Reproduction script](typescript_import_census.py).

## Status of the earlier findings

Stable IDs refer to the [earlier report](ACCURACY_REVIEW.md).
The shared journey, evidence, delta, history, move, and model implementations
are unchanged between the two reviewed revisions. Their old counterexamples
were replayed against the current implementation.

| ID | Current disposition | Latest evidence |
|---|---|---|
| F1 | Open for Python; TypeScript improves inventory preservation | Python parse failure still omits its module. TypeScript retains a warned module, but its imports are unavailable when whole-file parsing fails. |
| F2 | Open | Two body-changed cards still produce zero named decisions and “nothing to decide”. Direct change highlighting is a passing control. |
| F3 | Open | Editing source still reuses the cached journey answer: one transport call, one cache hit. |
| F4 | Open | Replacing an imported dependency without changing the crossing count leaves the old answer applicable. |
| F5 | Open, design limit | Incidental words and non-unique entry labels still satisfy journey coverage. Empty journeys still validate. |
| F6 | Open | A quoted sentence still generates invalid Python in the journey writer. |
| F7 | Open | A partially invalid journey still retains its valid step instead of rejecting the proposed journey as a whole. |
| F8 | Open, design limit; expanded to TypeScript | A mechanism word in prose still yields “observed”. A type-only import also yields “observed: an import joins them” for an authored data flow. |
| F9 | Open; raised to P1 for the TypeScript cases | Common TypeScript contracts produce empty API diffs. See the first finding. |
| F10 | Open; raised to P1 for configuration-driven graph changes | Alias changes can leave the CLI freshness gate green. Same-count tests and script target changes still evade it. |
| F11 | Partially fixed | Unparsable changes no longer crash. An invalid comparison ref still produces `has_change=False`. |
| F12 | Open | An explicit historical head still gives different reach when supplied working-tree facts. |
| F13 | Open | Reusing a commit cache after changing the configured module prefix still returns the old names. |
| F14 | Open, design limit | Unrelated removed and added modules exposing only `run` are still asserted to be a move. |
| F15 | Open | A changed symbol card is still absent from the overlay while its module card is present. |
| F16 | Open | An imported Click decorator is missed; an unrelated local `get` decorator is called a route. |
| F17 | Open for Python | A dotted Python package prefix still loses an internal import. The TypeScript scoped-package control passes in the existing suite. |
| F18 | Open | A parent's explicit child start still fails to satisfy the child's journey-coverage check. |
| F19 | Open | A module function still validates a nonexistent method of a named class. |
| F20 | Open | Test identities still collapse by unqualified name. TypeScript adds separate early-cap and modifier problems, F31 and F32. |
| F21 | Open | A pure rename still appears as growth under today's explicit card path. |
| F22 | Open | Parent delta reports a rename while the child reports removal of the same module. |
| F23 | Evaluation limitation remains | The previous ownership pilot was not rerun. Its labels and experiment construction do not establish production semantic accuracy. The new TypeScript benchmark also measures export accounting and file attribution, not correctness of API definitions or journeys. |

F8 is a distinction the product must preserve. Type-only imports are erased
from emitted JavaScript, as the [TypeScript module reference](https://www.typescriptlang.org/docs/handbook/modules/reference.html)
specifies. They establish a source-level type dependency. They do not establish
that a runtime flow carries the named artifact in the drawn direction.

## How to improve accuracy without Jev

The next work should separate facts that a language tool can determine from
claims about system purpose. Both can improve, but they need different evidence.

### Use the compiler for TypeScript facts

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

### Make API diffs use one complete exported representation

A class-shaped record cannot represent every TypeScript contract. Compare
public declarations and bindings first, then summarize the differences for the
map. Include a symbol's exported identity, fields, generic parameters, overloads,
and type/value role. Preserve unresolved definitions rather than equating them.

Acceptance: all F9 fixtures, including default-export connection attribution,
must become informative. Unchanged bodies and formatting-only changes need
controls so broader extraction does not create spurious API-change claims.

### Invalidate maps and reviews when their evidence changes

An answer is reusable only while its inputs are the same. Apply this rule to
stored facts, historical snapshots, journey answers, and recorded judgements.
Use the relevant source and configuration fingerprints. Scope invalidation to
the evidence each answer actually used.

Acceptance: the old source-change, same-count dependency, historical-config,
and new alias-change cases must all invalidate the relevant result. A repeated
request over identical evidence must still reuse the cache.

### Give journeys explicit evidence and coverage

A journey is an ordered account of one scenario through the system.
The existing checks verify some structural references, but do not establish
that its steps, direction, conditions, and outcome match execution.

Use stable entry identities: module, exported symbol or registration, and entry
kind. Track which entry and scenario each journey covers. Separate “declared by
the map”, “supported by imports”, and “observed during execution”. A type
dependency or prose keyword must not upgrade a behavioral claim.

Validate a generated journey as a whole and serialize it with Python's literal
escaping before writing. Include source revisions in its review state.
Optional test traces can support an executed scenario, but cannot prove every
path. No Jev dependency is needed for those mechanisms.

Acceptance: the earlier journey identity, nesting, invalid-step, string
round-trip, and cache cases must pass. Evaluate behavioral accuracy on
independently reviewed scenarios, including failure and alternative paths.
This review has not measured that semantic accuracy.

## Review coverage and limits

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

## Reproduce the review

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

The practical next step is to repair fact extraction and invalidation, then
measure journey claims separately. The current measurements identify exact
failures to remove; they do not justify a percentage for overall map accuracy.
