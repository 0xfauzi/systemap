# Pull requests and CI

The workflow from `systemap init` compares the map with the source in CI. On a pull request, `systemap delta` gives the map changes.

## The workflow from init

`systemap init` writes `.github/workflows/systemap.yml` with three jobs:

| Job | When it runs | What it does |
|---|---|---|
| `systemap` | Each push to `main` and each pull request | Runs `extract --check`, `check`, `judgement --strict`, and `render --check`. |
| `delta` | Each pull request | Runs `delta` from the base commit to the head commit. |
| `link` | If `delta` wrote a comment | Posts or changes one comment with a link to the Changes view. |

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

## Changes that the upgrade to 3.1.0 makes in CI

These changes can change the result of a CI job after you install 3.1.0:

- The facts format is 7. A facts file of an earlier format is stale, so `extract --check` and `check` exit 1. Run `systemap refresh`, and commit the facts file.
- Each exact answer that is not for a `crossing import` line is pending one time. `judgement` prints the new digest. Examine the source again, and write the digest in `evidence`.
- The `jev ...` finding kinds are now `decision ...` kinds. The previous names give a warning for one release.
- With `[judgement] require_reviews = true`, a component without a `source_review` digest is a finding, and `judgement --strict` exits 1.
- An import rule with the result `fail` makes `check` exit 1.

[CHANGELOG.md](../../CHANGELOG.md) gives each change and its steps.

## The Changes view

`systemap render --base REF` writes a page with a revision comparison.
A link that ends in `#changes` opens the Changes view. [Read the map](reading-the-map.html#changes) tells what it shows.

Do not commit this page into the output directory, because `systemap render --check` finds it stale.
Publish the page of each pull request at a different place, or use [the live map](live-map.html) on your computer.

## The link comment

If your repository publishes the map page of each pull request, set its URL in `systemap.toml`:

```toml
[delta]
page_url = "https://example.org/pr-{number}/"
```

The [reference](reference.html#what-can-you-configure) gives the rules for the URL.
Then `systemap delta --comment FILE --pr N` writes the comment to `FILE`:

```text
<!-- systemap delta -->
[Open the Changes view of the map](https://example.org/pr-7/#changes)

A map update is necessary (4 lines). The log of the delta job gives the action for each line.
```

systemap does not publish the page.
The `link` job posts the comment, and changes the same comment after each push.
It runs only for a pull request from a branch of the same repository. [Trust and security](trust-and-security.html#the-ci-link-job) tells why.

## Upgrade a workflow from 1.2.0

A workflow from `systemap init` 1.2.0 or earlier runs `systemap delta --format markdown`.
Version 2.0.0 removed this option, so with 2.0.0 or later the delta job fails with exit code 2:

```text
$ systemap delta --base main --format markdown
usage: systemap [-h] [--version] [--root ROOT] command ...
systemap: error: unrecognized arguments: --format markdown
```

`init` does not change a workflow file that exists. To get the new workflow:

1. Remove `.github/workflows/systemap.yml`.
2. Run `systemap init`. It keeps your configuration and your model.
3. If you changed the old workflow, compare it with the new file.

In a workflow from 2.0.0, each map finding makes the job fail. For the advisory mode, do the same steps.
