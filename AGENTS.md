# Working on systemap

systemap helps one person keep an accurate view of a system larger than they
can remember in full. Everything here serves that: the map is the artefact,
the commands keep it matching the code, and the words are how a reader learns
what the map says.

## How should the words be written?

systemap talks to someone who is learning the system, not to someone who
already knows it. That means:

- **The line reports the finding. The rows under it explain it.** Every line a
  command prints is also an identifier: the maintainer quotes it in
  `[judgement] answered`, and some are read back by code. Never change a
  line's text to make it friendlier. Add to it instead, in `explain.py`,
  where each kind of line has three sentences: what it means, why it matters
  to your view of the system, and what to do. `--brief` leaves them out.
- **The reason comes before the instruction.** "A card is a promise that its
  modules do one job; move the module to the card whose job it serves" reads
  as teaching. "Move the module" reads as a rule.
- **Define a term the first time it is used.** A journey, a card, a flow, a
  way in: each of these is ordinary English being used precisely, and a
  reader who guesses wrong stays wrong for the rest of the page.
- **Use the literal words.** Write "a parameter worth varying", not "a dial
  worth turning". A metaphor carries meanings the writer did not choose and
  cannot control, and it makes the reader do the decoding.
- **No emoji. No em dashes.** A hyphen, a colon or a full stop.
- **Short sentences.** A line a reader has to re-read has failed.

A reader needs the explanation as much as the finding, so when a new kind of
line is added, add its entry to `explain.py`. A test fails when a kind of line
has no entry there.

## How is a feature decided?

- **A number chosen after the run is chosen to pass, so state it first.**
  Write the acceptance number in the experiment's own docstring, then run it.
  `bench/jev/README.md` records every run, including the ones that failed.
- **Work nobody records is work someone repeats, so a feature that misses its
  number is written down rather than shipped.** Record the numbers and the
  reason it failed. `systemap ripple` and the import-derived journey paths are
  both there.
- **Never invent a number.** If it has not been measured, say so.
- **A wrong answer costs more than no answer, so never substitute one.** If a
  command cannot do what was asked, it says so and exits, rather than doing
  something else without saying.

## Which gates must pass?

`uv run pytest`, `uv run pre-commit run --all-files`. Between them they
enforce: ruff, mypy, cognitive complexity at 15 for anything this commit adds
or worsens, cyclomatic complexity that never grows, no file past 800 lines,
`SKILL.md` at 240 lines, no em dashes, and the three copies of the skill
directory identical.

Jev is the TypeSafe model systemap asks for the judgement calls the facts
cannot settle. No test sends anything to Jev, and no test runs a coding
agent. Both are injected, and recorded answers are replayed, so the suite
costs nothing and cannot fail because a service was slow.

This repository is mapped with systemap. After changing the source, run
`systemap refresh`, `systemap check` and `systemap judgement`, and name any
new module in a card.
