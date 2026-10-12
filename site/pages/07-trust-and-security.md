# Trust and security

This page tells what systemap reads, what it runs, what it sends over the network, and what it writes.
Read it before you run systemap on a repository that another person controls.

## What systemap reads

systemap reads the source files under the package roots, the test files, and the configuration files:
`systemap.toml`, `pyproject.toml`, `package.json`, and `tsconfig.json`.
For `delta`, `history`, `render --base`, and `live`, it also reads committed files from Git.

Extraction parses the source files. It does not import or run them.
Python source goes to the Python `ast` parser. TypeScript source goes to the tree-sitter parser.

## The model file runs as Python code

<!-- loader: update after the merge -->
The model, usually `map/model.py`, is a Python module. systemap loads it with the Python `exec` function.
Thus the code in the model file runs with your permissions. The modules that it imports from its directory also run.
Nested map files run in the same way.

Each command that reads the model runs this code.
These commands include `extract`, `facts`, `place`, `render`, `check`, `figure`, `refresh`, `judgement`, `delta`, `describe`, `history`, `live`, and the Jev commands.
`systemap init`, `systemap explain`, `systemap skill`, and `systemap serve` do not load the model.

With a comparison, `render --base`, `figure --base`, and `live` also load the committed model files of the merge base.
Thus they run the model code of that commit too.

Run systemap only in a repository that you trust, or in an isolated environment.
The same rule applies to the live map in Claude Code. [Coding agents](coding-agents.html#the-live-map-in-claude-code) tells when the plugin starts it.

## The agent command

`systemap journeys` runs the command under `[agent] command` in `systemap.toml`.
It sends the question on the standard input of the command. It does not use a shell.
A repository can set this command in its own `systemap.toml`. Examine the value before you run `systemap journeys`.
No other command runs it.

## Jev

Jev is the TypeSafe model for questions that imports and names cannot answer.
Without `TYPESAFE_API_KEY`, no question goes to Jev.
`systemap check` and `systemap judgement` make no network requests.

With the key, these commands can send questions to Jev:

| Command | When |
|---|---|
| `systemap audit` | Each run, except with `--dry-run`. |
| `systemap suggest --jev` | Each run. |
| `systemap plan "<task>"` | Each run. `plan --check` sends nothing. |
| `systemap triage` | Each run. |
| `systemap delta` | Each run, unless you use `--no-jev` or set `[jev] enabled = false`. |

The questions contain module names, docstrings, public names, internal imports, component identifiers, sentences, invariants, and source lines at connections between components.
`systemap audit --dry-run` shows the data that it would send.
With a key, the dry run gets the model list from the server, but it sends no map data.

The server is `https://api.typesafe.ai/v1`. The environment variable `TYPESAFE_BASE_URL` selects a different server.
Answers go into the cache `.systemap/jev-cache.json`.
Jev answers are suggestions for source examination. They are not evidence, and they do not change the `delta` lines or the exit code.

## The CI link job

The workflow from `init` has one job that can write to the pull request: the `link` job.
Only this job has the `pull-requests: write` permission.
It runs only if these two conditions are true:

- `systemap delta` wrote a comment. This occurs only with `[delta] page_url` in `systemap.toml`.
- The pull request comes from a branch of the same repository.

The `delta` job writes the comment text. That job runs the model code of the pull request.
The code and the settings of a pull request from a fork can thus change the comment text.
For this reason, the `link` job does not run for a pull request from a fork.

The other jobs have only the `contents: read` permission. They check out the code without stored credentials.
Each action in the workflow has a fixed commit, with its version in a comment.
[Pull requests and CI](pull-requests-and-ci.html) gives the jobs.

## The local servers

`systemap serve` and `systemap live` listen only on 127.0.0.1.
They answer only a request whose Host header is `127.0.0.1` or `localhost` with the server port:

```text
$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/
200
$ curl -s -o /dev/null -w "%{http_code}\n" -H "Host: evil.example:8765" http://127.0.0.1:8765/
403
```

Thus a web page that makes its own domain name point at 127.0.0.1 cannot read the map.
The servers have no other access control.
Other programs on the same computer can read the map, and they can send `POST /refresh` to `systemap live`.

## The page

The page that systemap renders contains its styles, its scripts, and its font. It loads no files from other servers.
A test of the renderer examines a sample page: its only URL is the SVG namespace.

The page keeps a few settings in the storage of your browser: the theme, Reduce motion, and the end of the first-visit guide.
The live map also keeps your view in the session storage before it loads a new version.

## What systemap writes

| Command | Files |
|---|---|
| `init` | `systemap.toml`, `map/model.py`, `docs/map/.gitkeep`, the workflow, and the skill directory. It keeps a configuration, model, or workflow file that exists. |
| `skill` | The skill directory. |
| `extract` | The facts file, `docs/map/map.json` by default. |
| `render` | The page of each map in the output directory. |
| `refresh` | The facts, the page of each map, and the configured figures. |
| `figure --out FILE` | One figure. |
| `place` | The positions in the model files. |
| `journeys` | The sequences in the model file, and the cache `.systemap/agent-cache.json`. |
| `delta --comment FILE` | The comment file, only with `[delta] page_url`. |
| `history`, `render --base`, `live` | Cached facts in `.systemap/facts/`. |
| Jev commands | `.systemap/jev-cache.json`. `plan` also writes `.systemap/plans/`. |
| `live` | A temporary directory that it deletes when it stops. |
