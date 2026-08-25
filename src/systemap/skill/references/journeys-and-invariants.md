# Journeys and invariants: extracted, not invented

Both are optional in the schema; a model without them renders without the
journey selector or the invariant list. Both are extracted from what the
repository already states, and both cite where.

## Journeys come from entry points

`systemap extract` records every place a run can start, under
`entry_points` in the facts file:

- console scripts from `[project.scripts]` in `pyproject.toml`
- `__main__` modules
- `main` functions
- argparse subcommands, where `add_parser("name", ...)` is written with a
  literal name
- the public functions of the package root

Write one journey per entry point that matters, tracing the components it
passes through: the actor that starts it, the component that takes the
input, each hand-off, and where the result lands. Each `Step` names what
acts, what measures (or `()`), the flow it traces, and one sentence. Name
the entry point in the journey's label or a step's sentence, as a whole
word (`pkg init`, `render`, `main`): that is how `systemap judgement`
knows the entry point has a journey. A console script's `main` and a
`__main__` that imports it count as the script.

Not every entry point matters. A debugging hook, a public function that
only tests call, a subcommand that prints a version: leave those without
a journey and answer the judgement line by saying so. An entry point you
cannot explain is a finding for the maintainer, not a journey to invent.

In an agentic system, one journey per agent's turn is expected: what
enters the window, what the model returns, what the agent invokes, what it
writes back.

## Invariants come from stated rules

An invariant is a rule the repository states about itself. Sources, in
order of trust:

1. Rules stated in the README and the design documents. Cite the file and
   the heading: `(README, Principles)`.
2. Guard clauses that raise: a function that refuses an input and says
   why. Cite the file and line: `(pkg/ledger.py:42)`.
3. Assertions in the code, cited the same way.
4. Tests whose names encode a rule: `test_every_record_is_written_once`.
   Cite the test file.

Each `Invariant` carries the rule in the repository's own words where it
can, the citation in the text, and the ids of the components it directly
governs. A rule the repository did not state is not an invariant; it is a
proposal, and belongs in your list for the maintainer.

## The check, and what it cannot see

The check refuses a journey step that traces a flow the model does not
have or names an unknown id, and an invariant governing an unknown id. It
cannot see whether a journey is the walk a reader needs, or whether an
invariant is true. `systemap judgement` prints "entry point X has no
journey" for every entry point no journey mentions; the second pass reads
every rule the documents state and asks whether the model carries it.
