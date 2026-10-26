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

`systemap journeys` runs the command under `[agent] command` in `systemap.toml`. No other command runs it.
systemap does not give the command to a shell. The command can start a shell, for example `sh -c '...'`.
A cloned repository can set this command. The command operates with your user permissions in the repository directory.

- systemap starts the command only if the environment of `systemap journeys` sets `SYSTEMAP_TRUST_AGENT_COMMAND=1`.
  systemap does not read this value from a repository file. Only the value `1` gives the permission.
- Without this value, `systemap journeys` starts no program. It stops with exit 1 and names the value.
  It does not give the output for a repository without an agent.
- `systemap journeys --dry-run` starts no program. It needs no value.
  If the environment does not set the value, the dry run tells you that a run needs the value.
- `SYSTEMAP_TRUST_MODEL_CODE=1` does not give this permission. The two permissions are separate.

Examine the agent command before you set the value. If you trust the repository, set the value. If you do not trust the repository, do not set the value.
Set the value for one command only, for example `SYSTEMAP_TRUST_AGENT_COMMAND=1 systemap journeys`.
Do not export the value in a shell profile, a CI environment, or a shared environment.
The value is not specific to one repository. Thus an exported value permits the agent command of each repository.
systemap does not remove environment variables from the agent process.
A coding agent program needs its own keys, for example `OPENAI_API_KEY` for `codex`.
Thus the agent command can read each key in your environment, for example `GH_TOKEN` or `TYPESAFE_API_KEY`.
The question to the agent contains map text and source facts. The agent command can send this question to a model API.

## What systemap sends

Only the six commands in the table send data on the network.
Each of these commands sends questions to a decision provider: a model API that gives typed answers.
A command sends no data if it has no question, or if the key of its provider is not set.

There are two decision providers:

- Jev is the TypeSafe model at `https://api.typesafe.ai/v1`, and the default provider. `TYPESAFE_BASE_URL` selects a different server. Each Jev request must have `TYPESAFE_API_KEY`.
- OpenAI Decisions is at `https://api.openai.com/v1/decisions`. A request goes to OpenAI only with `OPENAI_API_KEY`, and with `--provider openai` or `[decisions] provider = "openai"`. A key alone does not select OpenAI.

| Command | Provider | Condition | Data in the questions |
|---|---|---|---|
| `audit` | The selected provider. | The key of that provider. | Module names, docstrings, public names, internal imports, component IDs and sentences, invariants, flow sentences, and source lines at connections between components. |
| `delta` | The selected provider. | `--decide`, or `[jev] enabled = true` without `--no-decide`. Also the key of that provider. | The names, files, docstrings, public names, and internal imports of removed modules, added modules, and modules without a component. Also the component IDs and sentences. |
| `suggest --decide` | Jev only. With OpenAI, the command sends no data. | `TYPESAFE_API_KEY`. | The names, docstrings, public names, and internal imports of two modules for each question. |
| `triage TEXT` | Jev only. With OpenAI, the command sends no data. | `TYPESAFE_API_KEY`. | The system name, the first 2,000 characters of the issue text, and the component IDs and sentences. |
| `plan "<task>"` | Jev only. With OpenAI, the command sends no data. | `TYPESAFE_API_KEY`. | The system name, the first 2,000 characters of the task text, and the component IDs and sentences. |
| `judgement --order-by-drift` | Jev only. With OpenAI selected, the command sends no data and gives the cause: no measured drift result. | `TYPESAFE_API_KEY` and one or more open `stale source review` lines. | For each stale component: its sentences, flows, sequences, and invariants, and a diff or the text of its module files, to 12,000 characters. |

Before the questions, each Jev command reads the Jev model list. This request sends only the key.
The model list request also occurs when the Jev cache has all the answers. A cached answer does not go to the provider again.

`systemap audit --dry-run` lists the types of data that `audit` sends. With Jev and `TYPESAFE_API_KEY`, it reads the model list but sends no map data. With OpenAI, it sends no request.

All other commands send no data on the network.
These commands include `check`, `refresh`, `render`, `review`, `decisions`, `plan --check`, and `judgement` without `--order-by-drift`.
`journeys` sends no data, but [the agent command](#the-agent-command) can send its question to a model API.
`serve` and `live` answer only requests on 127.0.0.1 ([The local servers](#the-local-servers)).
The rendered page loads no files from other servers.

## The CI comment job

In the workflow from `init`, only the `comment` job has `pull-requests: write`. It runs only if:

- `systemap delta` wrote the summary comment.
- The pull request comes from a branch of the same repository.

The code and the settings of a fork can change the comment text. Thus the `comment` job does not run for a fork.
The token of a fork pull request also cannot write a comment.
For each pull request, the `delta` job writes the summary to its job summary. That job has only `contents: read`.
The workflow does not use `pull_request_target`, because that event gives a write token to the workflow for the code of a fork.
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
