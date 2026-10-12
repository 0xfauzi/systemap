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
- give the maintainer a completion report: the check results, the recorded answers, the open questions, and the uncertain claims.

With `TYPESAFE_API_KEY`, the agent also uses `systemap suggest --jev` and `systemap audit`.
For a map that is already in use, the agent starts with [`systemap delta`](pull-requests-and-ci.html#systemap-delta).

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
| `command` | `systemap` | The command that starts systemap, for example `uv run systemap` or `uvx systemap`. The plugin adds `live --port 0 --json --no-watch` to it. |
| `autostart` | `false` | If true, the live map starts when a session starts in a systemap repository. The live map reads `map/model.py` without running its code, unless `SYSTEMAP_TRUST_MODEL_CODE=1` is in the environment of Claude Code. |

## Other agents

An agent that can read files and run commands can use the skill. Write the skill to the directory that your agent reads:

```sh
systemap skill --dir path/to/skills/systemap
```

Then give the agent the instruction from `init`.
The plugin works only in Claude Code. `systemap live` works with each agent and each browser.
`systemap journeys` can ask an agent for [draft sequences](reference.html#systemap-journeys-limit-n-dry-run) through `[agent] command`.

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
