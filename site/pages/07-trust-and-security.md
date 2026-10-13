# Trust and security

This page tells what systemap reads, runs, sends, and writes.
Read it before you run systemap on a repository that another person controls.

## What systemap reads

systemap reads the source files under the package roots, the test files, `systemap.toml`, `pyproject.toml`, `package.json`, and `tsconfig.json`.
`delta`, `history`, `render --base`, and `live` also read committed files from Git.
Extraction parses the source files but does not import or run them.

The facts, the configuration, and the model can give file paths. A cloned repository can put any path in these files.
systemap reads such a file only if it is a regular file in the repository.
It refuses an absolute path, a path with a `..` part, and a symbolic link to a file that is not in the repository.
Extraction records a link to a file that is not in the repository as a module that did not parse.
A model file that is not in the repository gives a configuration error.

## What systemap runs

systemap reads the model, usually `map/model.py`, with a [reader that runs no code](reference.html#what-does-a-model-contain).
If the file needs code, the command stops and gives the file and the line.

- `SYSTEMAP_TRUST_MODEL_CODE=1` in the environment makes systemap run the model files as Python code.
  systemap does not read this value from a repository file. Set it only for code that you trust.
- [`systemap convert`](reference.html#systemap-convert) runs each refused model file one time with this value.
  Then it writes the file again with literal values only.
- The base models of `render --base`, `figure --base`, and `live` use the same reader.

systemap runs `git` with values from the model and from the command line.
A `source_review` value must be a 64-character hexadecimal digest before it goes to `git grep`.
A commit or a ref goes after `--end-of-options`. Thus a value that starts with `-` is not a Git option.

## The agent command

`systemap journeys` runs the command under `[agent] command` in `systemap.toml`, without a shell. No other command runs it.
A repository can set this command. Examine the value before you run `systemap journeys`.

## What systemap sends

A decision provider is a model API that answers the questions of `audit`, `suggest --decide`, `plan`, `triage`, and `delta --decide`.
Jev is the TypeSafe model at `https://api.typesafe.ai/v1`, and the default provider. `TYPESAFE_BASE_URL` selects a different server.
No question goes to Jev without `TYPESAFE_API_KEY`.
OpenAI Decisions is the second provider. A question goes to OpenAI only with `--provider openai` or `[decisions] provider = "openai"`, and with `OPENAI_API_KEY`.

A key alone does not make `delta` send questions. `delta` sends questions only with `--decide` or `[jev] enabled = true`.
`judgement` sends questions to Jev only with `--order-by-drift`.
`plan --check`, `delta --no-decide`, and `systemap decisions` send no question.

The questions contain module names, docstrings, public names, internal imports, component identifiers, sentences, invariants, and source lines at connections between components.
`--order-by-drift` also sends a diff or the text of the module files of each stale component.
`systemap audit --dry-run` shows this data. With a key, it gets the model list but sends no map data.

`systemap check` makes no network requests. `systemap judgement` makes no network requests without `--order-by-drift`.
The rendered page loads no files from other servers.

## The CI link job

In the workflow from `init`, only the `link` job has `pull-requests: write`. It runs only if:

- `systemap delta` wrote a comment, which needs `[delta] page_url`.
- The pull request comes from a branch of the same repository.

The code and the settings of a fork can change the comment text, so the `link` job does not run for a fork.
The other jobs have only `contents: read`. They check out the code without stored credentials.
Each action has a fixed commit.

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
Other programs on the computer can read the map and send `POST /refresh` to `systemap live`.

## What systemap writes

systemap writes the map files, the model files (`place` and `journeys`), and caches in `.systemap/`.
`init` and `skill` write the skill directory.
[Which command do you use?](reference.html#which-command-do-you-use) gives the files of each command.
