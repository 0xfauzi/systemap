# Coding agents

A coding agent writes the map with the systemap skill. The Claude Code plugin supplies the skill and a live map above the prompt.

Other agents can use the same skill files if they can read files and run commands.
The writing profile sets the writing rules for the map text.

## The skill

The skill is a directory with a `SKILL.md` file and nine reference files.
`systemap init` writes it to `.claude/skills/systemap/`.
`systemap skill` writes it again, for example after you install a new systemap version.

The instruction from `init` tells the agent to use the skill:

> Make a map of this repository with systemap. Obey the systemap skill and its writing rules.

The skill tells the agent to do these steps, and to mark each step when it is complete:

```text
- [ ] 1 extract: The facts are current.
- [ ] 2 draft: Each nonempty module has a component assignment. All components have positions.
- [ ] 3 check: The check has no failures. A `stale` finding can stay until step 5.
- [ ] 4 judgement: No judgement line or `jev` line stays without an action or an answer.
- [ ] 5 render: The page and figures are current, and you examined both figures.
- [ ] 6 source review: A complete source examination causes no model changes.
- [ ] 7 stop: The work agrees with each stop condition.
- [ ] 8 completion: The maintainer has the completion report.
```

The skill also tells the agent:

- to read `[writing] profile` before it writes a name or a sentence,
- to read the facts with `systemap facts`, not the full facts file,
- to write components and flows without positions, and then to run `systemap place`,
- to act on each `judgement` line, or to record an answer with a reason,
- to examine each module assignment, crossing import, declared flow, and entry point against the source in a second pass,
- not to record a digest without an examination of the source,
- not to complete the work while a check fails or `judgement --strict` does not exit 0.

At the end, the agent gives the maintainer a completion report:

```text
Check: <final systemap check result, with its coverage result>
Judgement: <final systemap judgement --strict result>
Audit: <final systemap audit result, or "Jev not available">
Procedure: <Jev or source examination, and each Jev failure>
Examined module assignments: <count>
Open questions: <each assignment that the maintainer must examine>
Recorded answers: <each answer in systemap.toml, with its reason>
Evidence limits: <each recorded extractor, source, or Jev limit>
Uncertainty: <each uncertain component assignment, source claim, or word under the writing profile>
Proposed rules: <each proposed invariant outside the invariant list>
```

With `TYPESAFE_API_KEY`, the skill also tells the agent to use `systemap suggest --jev` and `systemap audit`.
Without the key, the agent uses only the source examination procedure. The completion report tells which procedure it used.

For a map that is already in use, the skill tells the agent to start with `systemap delta --base REF`.
If `delta` identifies more than one third of the components, the agent does the full procedure again.
[Pull requests and CI](pull-requests-and-ci.html) gives the `delta` lines.

To read the skill, run `systemap skill --print`. The [reference](reference.html#systemap-skill-dir-path-print) gives the options.

## The Claude Code plugin

The systemap GitHub repository is also a Claude Code plugin marketplace. In Claude Code, type these two commands:

```text
/plugin marketplace add 0xfauzi/systemap
/plugin install systemap@systemap
```

The plugin supplies the skill and the live map. The live map runs the `systemap` command, so install systemap first.

## The live map in Claude Code

In a repository with `systemap.toml`, or with `[tool.systemap]` in `pyproject.toml`, the plugin shows one line above the prompt:

```text
map: not started · Start live map
```

The live map runs the code in `map/model.py` of the repository.
Start it only in a repository that you trust. [Trust and security](trust-and-security.html) tells what the model file can do.

To start the live map, select `Start live map`, or type `/map`.
The plugin then runs this command in the repository:

```sh
systemap live --port 0 --json --no-watch
```

After a turn that called a tool that can change files, the plugin asks `systemap live` to render the map again.
These tools are Edit, Write, MultiEdit, NotebookEdit, and Bash. A read-only Bash call does not count.
The line above the prompt then shows the state of the live map:

| Line | State |
|---|---|
| `map: rendering` | systemap renders the map now. |
| `map: live · 3 map updates · Open map · Show` | The map shows the current files. A map update is a `systemap delta` line that needs an action. |
| `map: not updated: ...` | systemap could not render the map. The text gives the first line of the error. The page keeps the last correct map. |
| `map: The command "systemap live" did not start: ...` | The command could not start. The line tells you to set the `command` option. |
| `map: The live map stopped: ...` | The process stopped. |

`Open map` opens the full page in a browser, at a `http://localhost` address.
`Show` and `/map` open a pane. In a terminal, the pane shows the map update lines and the link.
On other surfaces, the pane also shows the change figure.
If the figure has more than 131,072 characters, the pane shows the link and no figure.

In a directory without systemap configuration, the plugin shows nothing.
[The live map](live-map.html) tells what `systemap live` does.

## Plugin options

The plugin has two options. Set them with `/plugin configure systemap@systemap` or in `/config`.

| Option | Default | Meaning |
|---|---|---|
| `command` | `systemap` | The command that starts systemap, for example `uv run systemap` or `uvx systemap`. The plugin adds `live --port 0 --json --no-watch` to it. |
| `autostart` | `false` | If true, the live map starts when a session starts in a systemap repository. |

The plugin describes `autostart` with this sentence:
"The live map runs the Python code in map/model.py of that repository. Set true only if you trust each repository that you open."

## Other agents

The skill is Markdown text. An agent that can read files and run commands can use it.
Write the skill to the directory that your agent reads:

```sh
systemap skill --dir path/to/skills/systemap
```

Then give the agent the instruction from `init`.
The plugin and the live map line work only in Claude Code. `systemap live` works with each agent and each browser.

## Sequence drafts from an agent command

`systemap journeys` can ask a coding agent for draft sequences.
Set the command under `[agent]` in `systemap.toml`. The command reads the question from its standard input:

```toml
[agent]
command = "claude -p --output-format json"
```

Each question contains the language policy of the writing profile.
The command rejects a step that has no authored flow. It writes the accepted sequences with `drafted=True`.
`systemap judgement` prints a `drafted journey` finding until a person examines the sequence and removes the mark.
The [reference](reference.html#systemap-journeys-limit-n-dry-run) gives the options.

## The writing profile

The writing profile sets the writing rules for the map text that a person reads.
This text includes component names and descriptions, flow artifacts and sentences, layers, sequences, invariants, and the reasons of recorded answers.
Set the profile in `systemap.toml`. In `pyproject.toml`, use the `[tool.systemap.writing]` table.

```toml
[writing]
profile = "plain"
```

| Profile | Writing rules |
|---|---|
| `plain` | The common rules and the project glossary of the language policy. This is the default, and `init` writes it. |
| `asd-ste100` | The common rules, the glossary, and the full ASD-STE100 Issue 9 rules. These rules need the official ASD dictionary. |

The common rules limit the sentence length and require the active voice, literal words, and one term for each concept.
A person or a program can examine them without a dictionary.
Under `plain`, the agent must not say that the text obeys ASD-STE100.
Under `asd-ste100`, an agent without the official dictionary must tell the maintainer, and give no acceptance result.

The skill reads the profile. `systemap journeys` puts the policy of the profile in each agent question.
A different value gives a configuration error and exit code 2:

```text
$ systemap check
systemap: systemap.toml: writing.profile must be "plain" or "asd-ste100"
Correct systemap.toml or the model module. Then run the command again.
```

The profile does not change commands, schema keys, identifiers, or quoted source evidence.
This repository uses the `asd-ste100` profile for its map, its interface text, and its documentation.
The language policy is in the skill, at `references/language.md`.
