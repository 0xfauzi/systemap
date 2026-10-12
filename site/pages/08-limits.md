# Limits

A map without open findings agrees with the mechanical rules of systemap. It does not prove that each claim is correct.

A clean map does not prove that each component assignment, flow direction, or artifact is correct.
This page tells what the checks show, what they do not show, and the measured limits.

## What a clean map shows

| Command | What a clean result shows |
|---|---|
| `systemap check` | Each module that is not an empty package marker has one component, or an ignore with a reason. Entry and interface names exist in the claimed modules. Routes and labels obey the layout rules. The facts, the page, and the figures are current. |
| `systemap judgement --strict` | Each possible map error has a change in the map, or an answer with a reason. Each exact answer has the current evidence digest. |
| `systemap delta` | The component claims agree with the moved, added, and removed modules. Each changed component has a current source review. |

## What a clean map does not show

- The rules use names and imports. A module in an incorrect component can pass all of them.
- An import does not show the direction of a flow or its artifact.
- A test reference does not show test coverage.
- A sequence is an authored order of steps. It does not record a run of the program.
- No check proves the behavior of the program at run time.
- A program cannot show that the map text obeys the writing rules. It can count words and find contractions and em dashes.

For these reasons, the skill tells the agent to examine the source in a second pass.
The maintainer reads the completion report and corrects the claims that are not correct.

## Evidence is a record, not a proof

"Current source review" means that a person or an agent recorded source records and a review digest for the flow.
These records still agree with the current source and the current claim.
The words do not mean that the examination was correct, and they do not mean that a program ran.

`observed` is the stored identifier of this evidence state. [Concepts](concepts.html#evidence-states) gives all the states.

## The review digests

systemap uses digests to find changes in recorded evidence:

- the `source_sha256` value in each source record of a flow,
- the `review_digest` of a flow,
- the `source_review` digest of a component,
- the `evidence` digest of an exact answer.

When the source or the claim changes, the digest changes, and the finding opens again.
A digest identifies the recorded source and claims. It does not show that the claim is correct.
A person or an agent can record a current digest without an examination of the source.
The skill forbids this, but no program can find it.

## Languages

systemap reads Python and TypeScript. The TypeScript reader reads `.ts`, `.tsx`, `.mts`, and `.cts` modules.
It does not read declaration files, such as `.d.ts`.
It does not read framework-specific TypeScript routes.
systemap reads no other languages.

When the parser cannot read some syntax or map a package target, the facts get an explicit unknown record.
`systemap check` prints these records but does not reject the map for them.
`systemap judgement --strict` accepts each unknown record only after a correction or an accepted answer.

The Jev measurements in `bench/jev` used Python repositories only. No TypeScript result was measured.
The [reference](reference.html#what-questions-does-jev-answer) gives the measured results and their limits.

## Size limits

| Limit | Value | Effect |
|---|---|---|
| Components on one map | About forty | Above this number, each layer can contain almost all components. A component can open a nested map. |
| Figure in the Claude Code pane | 131,072 characters | A larger change figure does not show in the pane. The pane shows the link to the page. |
| Page of the sample map in the tests | 329,728 bytes (322 KiB) | A test of the renderer keeps this page smaller. |

The page size test applies to one sample map in the tests of systemap. It is not a limit on your map.
The page of the systemap map in `docs/map/` is larger than this value.
The test value includes 300 KiB, the embedded font subset of 18,452 bytes, and 4,076 bytes of more space.

`systemap suggest` shows maps above forty components and the components that can become nested maps.
The [reference](reference.html#what-do-you-do-above-forty-components) tells how a nested map works.

On the systemap repository, one render of the live map takes about 7 to 8 seconds.
[The live map](live-map.html#update-time) gives the measurements.

## The map is authored

A person or an agent writes the model. Extraction gives the facts, but it does not make the components or the flows.
The map contains authored and examined flows. It does not contain all function calls, or one component for each module.
systemap is not a UML tool. It uses one picture and one layout, with components, flows, and sequences.
