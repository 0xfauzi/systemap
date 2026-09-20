# Journeys and invariants: extracted, not invented

Both are optional in the schema; a model without them renders without the
journey selector or the invariant list. Both are extracted from what the
repository already states, and both cite where.

## Journeys come from entry points

`systemap extract` records every place a run can start, under
`entry_points` in the facts file:

- console scripts from `[project.scripts]` in `pyproject.toml`, Poetry's
  `[tool.poetry.scripts]`, and the plugin hooks under `[project.entry-points]`
- `__main__` modules
- `main` functions
- argparse subcommands, where `add_parser("name", ...)` is written with a
  literal name
- the public functions of the package root
- routes a framework registers: `@app.get("/x")` and its relatives, Flask's
  `@app.route`, and Django's `urlpatterns`
- commands: click and typer's `@cli.command()`, cleo's command classes, and
  Django's `management/commands/*`
- background tasks: `@shared_task` and `@app.task`

Write one journey per entry point that matters, tracing the components it
passes through: the actor that starts it, the component that takes the
input, each hand-off, and where the result lands. Each `Step` names what
acts, what measures (or `()`), the flow it traces, and one sentence. Name
the way in in `starts`, exactly as `systemap facts --entry-points`
prints its name (`starts="GET /recipes"`): that is how `systemap
judgement` knows the way in has a journey. Naming it in the label or a
step's sentence as a whole word still counts, for maps written before
`starts` existed. A console script's `main` and a `__main__` that imports
it count as the script.

A card that takes a crowd of ways in of one kind, a hundred routes or a
dozen subcommands, gets one journey for the crowd rather than one each:
name the card in `starts` (`starts="HttpApi"`), and every way in that
card claims counts as walked. `systemap judgement` asks about a crowd as
one line for the same reason.

`systemap journeys` writes one for you, when `[agent] command` names a
coding agent: the agent reads the code from that way in, or from two or
three of a crowd, and answers with the walk, and systemap refuses a step
that traces a flow the map does not draw or names a card that is not
there. What it writes is marked
`drafted=True` and prints as a `drafted journey` judgement line. Read each
step against the code, fix what is wrong, then remove the mark. A drafted
journey nobody has read is not knowledge of the system.

Not every entry point matters. A debugging hook, a public function that
only tests call, a subcommand that prints a version: leave those without
a journey and answer the judgement line in `[judgement] answered` saying
so. An entry point you cannot explain is a finding for the maintainer,
not a journey to invent.

In an agentic system, one journey per agent's turn is expected: what
enters the window, what the model returns, what the agent invokes, what it
writes back.

## Invariants come from stated rules

An invariant is a rule the repository states about itself. Sources, in
order of trust:

1. Rules stated in the repository's own words: its README, AGENTS.md,
   CLAUDE.md, docs/. Cite the file and the heading: `(README, Principles)`.
2. Guard clauses that raise: a function that refuses an input and says
   why. Cite the file and line: `(pkg/ledger.py:42)`.
3. Assertions in the code, cited the same way.
4. Tests whose names encode a rule: `test_every_record_is_written_once`.
   Cite the test file.

Each `Invariant` carries the rule in the repository's own words where it
can, the citation in the text, and the ids of the components it directly
governs. A rule the repository did not state is not an invariant; it is a
proposal, and belongs in your hand-back note to the maintainer.

## The check, and what it cannot see

The check refuses a journey step that traces a flow the model does not
have or names an unknown id, and an invariant governing an unknown id. It
cannot see whether a journey is the walk a reader needs, or whether an
invariant is true. `systemap judgement` prints "entry point X has no
journey" for every entry point no journey mentions; the second pass reads
every rule the documents state and asks whether the model carries it.
