# Coding agents

A coding agent writes the map with the systemap skill. The Claude Code plugin supplies the skill and a live map above the prompt.

## The skill

`systemap init` writes the skill to `.claude/skills/systemap/`.
After you install a new systemap version, run `systemap skill` to write it again.
To read the skill, run `systemap skill --print`.
Give the agent the instruction from `init`:

> Make a map of this repository with systemap. Obey the systemap skill and its writing rules.

The skill tells the agent to:

- read `[writing] profile` before it writes a name or a sentence,
- write the components and flows without positions, and then run `systemap place`,
- act on each `judgement` line, or record an answer with a reason,
- continue until no check fails and `judgement --strict` exits 0,
- examine the module assignments, crossing imports, declared flows, and entry points against the source in a second pass,
- record each source review with `systemap review` or `systemap decisions`, and not by a change of the model file,
- give the maintainer a completion report: the check results, the recorded answers, the open questions, and the uncertain claims.

With `TYPESAFE_API_KEY`, the agent also uses `systemap suggest --decide` and `systemap audit`.
`--decide` replaces `--jev`, which stays for one release.
For a map that is already in use, the agent starts with [`systemap delta`](pull-requests-and-ci.html#systemap-delta).

## Source reviews and verdicts

A source review is a recorded examination of the source that supports a claim.
`systemap review ID` writes the current `source_review` digest of one component. `systemap review --flow ID` writes the `review_digest` of one flow.
The command writes one target for each call, because the agent must examine each claim.

`systemap decisions` gives the open claims to the agent in its current session, with no request to a model:

1. `systemap decisions pending --json` gives each decision request with its claim and its source files.
2. The agent examines the source. Then it writes a verdict for each request: `supported`, `contradicted`, or `insufficient_evidence`.
3. `systemap decisions submit FILE` examines each citation: the file, the line span, and the SHA-256 digest of the current file.
4. The command records each `supported` verdict as a review digest or as an exact answer.

After one `insufficient_evidence` verdict, the decision request becomes unknown.
After 3 `contradicted` verdicts for one target, it also becomes unknown. `[decisions] max_contradicted` sets this limit.
The agent gives each unknown decision request to the maintainer. An unknown request does not show that the claim is correct.
The [reference](reference.html#systemap-decisions-pending-submit-file-status) gives the fields of each request and verdict.

## The Claude Code plugin

[Install systemap](getting-started.html#install-systemap) first, because the plugin runs the `systemap` command.
Then, in Claude Code, type:

```text
/plugin marketplace add 0xfauzi/systemap
/plugin install systemap@systemap
```

## The live map in Claude Code

In a repository with `systemap.toml`, or with `[tool.systemap]` in `pyproject.toml`, the plugin shows one line above the prompt:

```text
map: not started · Start live map
```

To start the [live map](live-map.html), select `Start live map`, or type `/map`.
The plugin runs `systemap live --port 0 --json --no-watch` in the repository.
The live map reads `map/model.py` without running its code, unless `SYSTEMAP_TRUST_MODEL_CODE=1` is in the environment of Claude Code.
If the `command` option runs code of the repository, the code of the repository can run when the live map starts.

After a turn that called Edit, Write, MultiEdit, NotebookEdit, or Bash, the plugin asks `systemap live` to render the map again.
A read-only Bash call does not count. The line then shows the state:

| Line | State |
|---|---|
| `map: live · 3 map updates · Open map · Show` | The map shows the current files. A map update is a `systemap delta` line with a necessary action. |
| `map: not updated: ...` | systemap could not render the map. The page keeps the last correct map. |
| `map: The command "systemap live" did not start: ...` | Set the `command` option. |
| `map: The live map stopped: ...` | The process stopped. |

`Open map` opens the page in a browser.
`Show` and `/map` open a pane with the map update lines and the link. Outside a terminal, the pane also shows the change figure.

## Plugin options

Set the options with `/plugin configure systemap@systemap` or in `/config`.

| Option | Default | Meaning |
|---|---|---|
| `command` | `systemap` | The command that starts systemap, for example `systemap` or `uvx systemap`. The plugin adds `live --port 0 --json --no-watch` to it. Do not use `uv run systemap`. That command builds the project of the repository, and the build can run code of the repository. |
| `autostart` | `false` | If true, the live map starts when a session starts in a systemap repository. The live map reads `map/model.py` without running its code, unless `SYSTEMAP_TRUST_MODEL_CODE=1` is in the environment of Claude Code. If the `command` option runs code of the repository, the code of the repository can run when the live map starts. |

## Other agents

An agent that can read files and run commands can use the skill. Write the skill to the directory that your agent reads:

```sh
systemap skill --dir path/to/skills/systemap
```

Then give the agent the instruction from `init`.
The plugin works only in Claude Code. `systemap live` works with each agent and each browser.
`systemap journeys` can ask an agent for [draft sequences](reference.html#systemap-journeys-limit-n-dry-run) through `[agent] command`.
The configuration in the repository gives this command. Thus systemap starts it only if the environment sets `SYSTEMAP_TRUST_AGENT_COMMAND=1` ([The agent command](trust-and-security.html#the-agent-command)).
A coding agent must not set this value itself. The maintainer sets it after an examination of the command.

## The writing profile

The writing profile sets the rules for the map text that a person reads.
The skill gives the rules in `references/language.md`. Set the profile in `systemap.toml`:

```toml
[writing]
profile = "plain"
```

| Profile | Writing rules |
|---|---|
| `plain` | The common rules (sentence length, active voice, literal words, one term for each concept) and the project glossary. This is the default. |
| `asd-ste100` | The common rules, the glossary, and the full ASD-STE100 Issue 9 rules. These rules need the official ASD dictionary. Without it, the agent tells the maintainer and gives no acceptance result. |
