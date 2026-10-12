# Pull requests and CI

The workflow from `systemap init` compares the map with the source in CI. On a pull request, `systemap delta` gives the map changes.

The workflow runs on each push to `main` and on each pull request.
Each `delta` line gives a map change and the necessary action.
By default, a map finding gives a warning, and the job passes.

## The workflow from init

`systemap init` writes `.github/workflows/systemap.yml`. It has three jobs:

| Job | When it runs | What it does |
|---|---|---|
| `systemap` | Each push to `main` and each pull request. | Runs `extract --check`, `check`, `judgement --strict`, and `render --check`. |
| `delta` | Each pull request. | Runs `delta` from the base commit to the head commit of the pull request. |
| `link` | A pull request, if `delta` wrote a comment. | Posts or changes one comment with a link to the Changes view. |

The workflow runs the released package with `uvx --from "systemap==<version>"`.
The version is the version that wrote the file, so your project needs no dependency on systemap.
When you install a new systemap version, change the version in the workflow file.

The `systemap` and `delta` jobs have only the `contents: read` permission. They check out the code without stored credentials.
The `link` job checks out no code. It is the only job with the `pull-requests: write` permission.

## Advisory and strict

The variable `SYSTEMAP_CI` in the workflow sets what a map finding does:

```yaml
env:
  # advisory: a map finding gives a warning. strict: a map finding makes the job fail.
  SYSTEMAP_CI: advisory
```

| Exit code of a systemap step | `advisory` | `strict` |
|---|---|---|
| `0` | The step passes. | The step passes. |
| `1`: a map finding | A warning annotation. The job passes. | An error annotation. The job fails. |
| `2` or more: systemap cannot run | The job fails. | The job fails. |

`systemap init` writes `advisory`. `systemap init --strict-ci` writes `strict`.
You can change the value in the workflow file later.
If the workflow file exists, `init` does not change it.

## systemap delta

`systemap delta --base REF` compares the facts at the merge base of `REF` and `HEAD` with the facts at `HEAD`.
It reads the committed files at the two commits, and it uses the model on disk.
Each line gives a map change and its necessary action.

In the example project of [Get started](getting-started.html), a branch added a module and renamed another one:

```text
$ systemap delta --base main
delta: main (5e0837b) -> HEAD (3e4b6a9): 1 module changed, 1 added, 0 removed, 1 moved. 2 of 3 components specified
The map needs an update (4):
  moved: shop.store -> shop.storage (same content). OrderFiles specifies shop.store in implemented_by. Change this claim to shop.storage in map/model.py
      why: A component with the previous path no longer contains the module.
      do:  Change the module claim to the new name. Or put the module in the component for its task at this snapshot.
  added: shop.discounts, No component has a claim for it. Add it to a component implemented_by in map/model.py, or give a reason to ignore it in [coverage]
      why: Without a component for the module, the map omits part of the system.
      do:  Add the module to the component for its task, or give a reason to ignore it in `[coverage]`.
  source review: CommandLine has changed code in shop.cli. Compare its description, flows, sequences, and invariants with the new source.
      why: Imports and public signatures do not give all behavior changes. The component description and related claims can now be incorrect.
      do:  Read the changed source. Correct the claims. Then record the `source_review` digest as the maintenance guide specifies.
  source review: OrderFiles has changed code in shop.store. Compare its description, flows, sequences, and invariants with the new source.
next to the change:
  CommandLine has the most changed modules. It has flows to 3 of the 3 components, so the list gives no useful context.
The change includes more than one third of the components. Use the full skill maintenance procedure.
Do the action in each line under "The map needs an update". Then run systemap refresh && systemap check && systemap judgement --strict
```

The exit code is 1 while the map needs an update.
The agent changed the claims in `map/model.py`, examined the changed source, and recorded the `source_review` digests.
Then the same command gave exit code 0:

```text
$ systemap delta --base main --brief
delta: main (5e0837b) -> HEAD (5920aaf): 1 module changed, 1 added, 0 removed, 1 moved. 2 of 3 components specified
No action is necessary for these changes (2):
  moved: shop.store -> shop.storage (same content), with a claim in OrderFiles
  added: shop.discounts, with a claim in Orders
next to the change:
  CommandLine has the most changed modules. It has flows to 3 of the 3 components, so the list gives no useful context.
The change includes more than one third of the components. Use the full skill maintenance procedure.
The map is current. Run systemap refresh to write the facts and the page again.
```

Other line kinds include `removed`, `entry vanished`, `interface vanished`, `new crossing import`, and `evidence lost`.
`systemap explain "<kind>"` gives the meaning and the action of each kind.
The [reference](reference.html#systemap-delta-base-ref-head-ref-comment-file-pr-n-jev-no-jev) gives all options.

With `TYPESAFE_API_KEY` set, `delta` also asks Jev for possible module moves. `--no-jev` sends nothing.
Jev answers do not change the delta lines or the exit code. The workflow from `init` does not set the key.

## The Changes view

`systemap render --base REF` writes a page with a revision comparison.
A link to the page that ends in `#changes` opens the Changes view.
[Read the map](reading-the-map.html#changes) tells what the view shows.

The Changes panel lists the map changes.
It compares the committed model at the merge base with the model on disk.

Do not commit this page into the output directory.
The checks compare the committed page with a page without a comparison, so the page is stale for them:

```text
$ systemap render --base main
The command wrote docs/map/index.html (398 KB)
$ systemap render --check
docs/map/index.html is stale: it differs from the rendered output.
run: systemap refresh
```

Publish the page of each pull request at a different place, or use [the live map](live-map.html) on your computer.

## The link comment

CI writes no comment by default.
If your repository publishes the map page of each pull request, set its URL in `systemap.toml`:

```toml
[delta]
page_url = "https://example.org/pr-{number}/"
```

The URL must start with `https://` or `http://` and contain `{number}`. It must not contain `#` or a space.
The pull request number replaces `{number}`.
With this value, `systemap delta --comment FILE --pr N` writes the comment to `FILE`:

```text
<!-- systemap delta -->
[Open the Changes view of the map](https://example.org/pr-7/#changes)

A map update is necessary (4 lines). The log of the delta job gives the action for each line.
```

Without `page_url`, the command writes no file. The comment does not change the delta lines or the exit code.
systemap does not publish the page. Your repository must publish it at that URL.

The `link` job posts the comment, and changes the same comment after each push.
It runs only for a pull request from a branch of the same repository.
The delta job runs the code of the pull request, and the code and the settings of a fork can change the comment text.
[Trust and security](trust-and-security.html#the-ci-link-job) gives the details.

## Upgrade a workflow from 1.2.0

A workflow from `systemap init` 1.2.0 or earlier runs `systemap delta --format markdown`.
Version 2.0.0 removed this option.
The workflow uses the version in its file.
If you change that version to 2.0.0 or later, `systemap delta` stops with exit code 2, and the delta job fails:

```text
$ systemap delta --base main --format markdown
usage: systemap [-h] [--version] [--root ROOT] command ...
systemap: error: unrecognized arguments: --format markdown
```

`init` does not change a workflow file that exists. To get the new workflow, do these steps:

1. Remove `.github/workflows/systemap.yml`.
2. Run `systemap init`. It keeps your configuration and your model, and it writes the skill directory again.
3. If you changed the old workflow, compare it with the new file.

Use the same steps to get the advisory mode in a workflow from 2.0.0.
In that workflow, each map finding makes the job fail.
