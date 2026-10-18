# Pull requests and CI

The workflow from `systemap init` compares the map with the source in CI. On a pull request, `systemap delta` gives the map changes.

## The workflow from init

`systemap init` writes `.github/workflows/systemap.yml` with three jobs:

| Job | When it runs | What it does |
|---|---|---|
| `systemap` | Each push to `main` and each pull request | Runs `extract --check`, `check`, `judgement --strict`, and `render --check`. |
| `delta` | Each pull request | Runs `delta` from the base commit to the head commit. Writes the architecture summary to the job summary. |
| `comment` | Each pull request from a branch of the same repository | Posts or changes one comment with the architecture summary. |

The workflow runs `uvx --from "systemap==<version>"` with the version that wrote the file.
It does not set `TYPESAFE_API_KEY` or `OPENAI_API_KEY`, and it does not give `--decide`. Thus no question goes to a decision provider.
When you install a new systemap version, change the version in the workflow file.

## Advisory and strict

The variable `SYSTEMAP_CI` in the workflow sets what a map finding does.
`systemap init` writes `advisory`. `systemap init --strict-ci` writes `strict`. You can change the value later.

| Exit code of a systemap step | `advisory` | `strict` |
|---|---|---|
| `0` | The step passes. | The step passes. |
| `1`: a map finding | A warning annotation. The job passes. | An error annotation. The job fails. |
| `2` or more: systemap cannot run | The job fails. | The job fails. |

## systemap delta

`systemap delta --base REF` compares the facts at the merge base of `REF` and `HEAD` with the facts at `HEAD`.
It uses the committed files at the two commits and the model on disk.

In the [Get started](getting-started.html) project, a branch added a module and renamed another one.
These are the first lines of the output:

```text
$ systemap delta --base main
delta: main (5e0837b) -> HEAD (3e4b6a9): 1 module changed, 1 added, 0 removed, 1 moved. 2 of 3 components specified
The map needs an update (4):
  moved: shop.store -> shop.storage (same content). OrderFiles specifies shop.store in implemented_by. Change this claim to shop.storage in map/model.py
```

The exit code is 1 while the map needs an update.
After the agent did the four actions, the exit code was 0.

`systemap explain "<kind>"` gives the meaning and the action of a line kind.
The [reference](reference.html#systemap-delta-base-ref-head-ref-comment-file-pr-n-decide-no-decide) gives the options.

`delta` sends questions to a decision provider only with `--decide` or `[jev] enabled = true`. A key alone sends no request.
The answers are suggestions under their own heading. They do not change the delta lines or the exit code.

## Changes that the upgrade from 1.2.0 makes in CI

These changes can change the result of a CI job after you install 2.0.0:

- The workflow from 1.2.0 uses `systemap delta --format markdown`, which 2.0.0 does not have. [Upgrade a workflow from 1.2.0](#upgrade-a-workflow-from-1-2-0) gives the steps.
- systemap reads the model file as data. A model file that needs code stops each command. Run `SYSTEMAP_TRUST_MODEL_CODE=1 systemap convert` one time.
- The facts format is 12. A facts file of an earlier format is stale, so `extract --check` and `check` exit 1. Run `systemap refresh`, and commit the facts file.
- Each exact answer that is not for a `crossing import` line is pending one time. `judgement` prints the new digest. Examine the source again, and write the digest in `evidence`.
- The `jev ...` finding kinds are now `decision ...` kinds. Some `unknown surface` and `entry point` lines have a new form. The earlier names and lines give a warning for one release.
- `judgement --strict` exits 1 for a model without components. `judgement --json` has schema version 3.
- A configured cache path, `out_dir`, or `model` that is absolute or has a `..` part is a configuration error.
- With `[judgement] require_reviews = true`, a component without a `source_review` digest is a finding, and `judgement --strict` exits 1.
- An import rule with the result `fail` makes `check` and `refresh` exit 1.
- A flow from a component to itself is a `check` error.
- A source module or a test file that the parser cannot read does not make `check` exit 1. `check` gives it as not known, with its cause.
- A component `source_review` digest that is not current is a `stale source review` finding, and `judgement --strict` exits 1.
- A configuration file or a `package.json` file that is not a regular file in the repository gives a configuration error.

[CHANGELOG.md](../../CHANGELOG.md) gives each change and its steps.

## The Changes view

`systemap render --base REF` writes a page with a revision comparison.
A link that ends in `#changes` opens the Changes view. [Read the map](reading-the-map.html#changes) tells what it shows.

Do not commit this page into the output directory, because `systemap render --check` finds it stale.
Publish the page of each pull request at a different place, or use [the live map](live-map.html) on your computer.

## The architecture summary

The architecture summary tells the reviewer of a pull request the effect of the change on the architecture.
`systemap delta --comment FILE` writes it to `FILE`. The summary has these parts:

- **Contract**: the invariants and the import rules that the change added, removed, or changed. Accept or reject each contract change in the review.
- **Map**: the components, the flows, and the sequences that the change added, removed, or changed.
- **Rules**: the result of each import rule at the head commit.
- **Map update**: the number of delta lines with a necessary action. This row shows only if a map update is necessary.

Each row of an item gives the assurance level of its claim at the head commit, and the freshness of the record behind the level.
A removed item, an actor, and a sequence have no level.
Each part gives a maximum of 5 rows, and then the count of the other rows.

In the two-component fixture of the systemap tests, a change added an import rule, a reason, a flow artifact, and a module without a component.
This is the summary of that change:

```text
<!-- systemap delta -->
**Architecture**

- **Contract:** 1 changed invariant, 1 added import rule. Accept or reject each contract change in this review.
  - changed invariant `1` (reason): unknown, source review missing
  - added import rule `no-back`: established from facts
- **Map:** 1 changed flow
  - changed flow `Reader` -> `Writer`, `parsed request` (artifact): unknown, flow review missing
- **Rules:** 1 passed, 0 failed, 0 unknown
- **Map update:** necessary for 1 line. The log of the delta job gives the action for each line.

Levels: established = the facts show the claim. examined = an agent or a person examined the cited source. unknown = no fact or review shows the claim.
```

If the change has no effect on the contract or the map, and no rule has the result `fail`, the summary is one line:

```text
**Architecture:** no change to the contract or the map. Rules: 1 passed, 0 failed, 0 unknown.
```

The `comment` job posts the summary as one comment, and changes the same comment after each push.
It runs only for a pull request from a branch of the same repository. [Trust and security](trust-and-security.html#the-ci-comment-job) tells why.
For a pull request from a fork, read the summary in the job summary of the `delta` job.

## The link to the Changes view

If your repository publishes the map page of each pull request, set its URL in `systemap.toml`:

```toml
[delta]
page_url = "https://example.org/pr-{number}/"
```

The [reference](reference.html#what-can-you-configure) gives the rules for the URL.
Then the comment also has a link to the Changes view of the page, and `--comment FILE` must have `--pr N`:

```text
[Open the Changes view of the map](https://example.org/pr-7/#changes)
```

systemap does not publish the page.

## Upgrade a workflow from 1.2.0

A workflow from `systemap init` 1.2.0 or earlier runs `systemap delta --format markdown`.
Version 2.0.0 does not have this option, so the delta job fails with exit code 2:

```text
$ systemap delta --base main --format markdown
usage: systemap [-h] [--version] [--root ROOT] command ...
systemap: error: unrecognized arguments: --format markdown
```

`init` does not change a workflow file that exists. To get the new workflow:

1. Remove `.github/workflows/systemap.yml`.
2. Run `systemap init`. It keeps your configuration and your model.
3. If you changed the old workflow, compare it with the new file.

The new workflow is advisory. For a workflow that fails on a map finding, run `systemap init --strict-ci` in step 2.
