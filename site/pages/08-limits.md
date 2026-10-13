# Limits

A map without open findings agrees with the mechanical rules of systemap. It does not prove that each claim is correct.

## What it shows

- [`systemap check`](reference.html#what-does-systemap-check-reject): each module that is not an empty package marker has one component, or an ignore with a reason.
  Entry and interface names exist in the claimed modules. Routes and labels obey the layout rules. The facts, the page, and the figures are current.
- `systemap judgement --strict`: each possible map error has a map change or an answer with a reason. Each exact answer has the current evidence digest.
- `systemap rules`: no resolved import is against an import rule. If the facts possibly do not contain all imports of a rule module, the result is `unknown`.
- `systemap delta`: the component claims agree with the moved, added, and removed modules. Each changed component has a current source review.

## What it does not show

- The rules use names and imports, so a module in an incorrect component can pass them.
- An import does not show the direction of a flow or its artifact.
- A test reference does not show test coverage.
- A sequence is an authored order of steps, not a recorded run.
- No check proves the behavior of the program at run time.
- The map does not contain all function calls, or one component for each module.

Thus the skill tells the agent to examine the source in a [second pass](reference.html#what-does-the-second-pass-find).
The maintainer corrects the incorrect claims.

## Evidence is a record, not a proof

A current source review (`observed`) means that the stored source records and review digest agree with the current source and claim.
It does not show that the examination was correct, or that a program ran.

A digest (`source_sha256`, `review_digest`, `source_review`, or `evidence`) changes when its source or claim changes, and the finding opens again.
A person or an agent can record a current digest without a source examination. No program can find this.
`systemap decisions submit` makes sure that each citation refers to the current file. It cannot make sure that the agent read the cited lines correctly.

## Languages

- systemap reads only Python and TypeScript (`.ts`, `.tsx`, `.mts`, `.cts`).
  It does not read declaration files, such as `.d.ts`, or framework-specific routes.
- Syntax that systemap cannot parse, or a package target that it cannot map, gets an unknown record.
  `check` does not reject the map for it. `judgement --strict` accepts it only after a correction or an accepted answer.
  A parser can refuse correct source. Thus each result that reads such a module is not known, not a pass.
- The [Jev measurements](reference.html#what-questions-does-jev-answer) and the [OpenAI measurements](reference.html#which-decision-provider-answers-the-questions) used Python repositories only.
  No TypeScript row set is available. Thus `decision flow` is not a default question of `audit`.
- If a module did not parse, its `unresolved_imports` value is not known. An import rule for that module gives `unknown`, not `pass`.

## Size limits

- About forty components on one map. Above this, each layer can contain almost all components. Use a [nested map](reference.html#what-do-you-do-above-forty-components).
- 131,072 characters for a change figure in the Claude Code pane. The pane shows a larger figure as a link to the page.
