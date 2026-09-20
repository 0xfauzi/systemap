# Working on systemap

systemap helps one person keep an accurate view of a system that is larger
than what they can hold in their head. Everything here serves that: the map
is the artefact, the commands are how it stays true, and the words are how a
reader learns what the map is telling them.

## How the words are written

systemap talks to someone who is learning the system, not to someone who
already knows it. That means:

- **The line says what was found. The rows under it teach.** Every line a
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
- **Say the thing, not a picture of it.** "A parameter worth varying", not
  "a dial worth turning". A metaphor carries meanings nobody chose.
- **No emoji. No em dashes.** A hyphen, a colon or a full stop.
- **Short sentences.** A line a reader has to re-read has failed.

When a new kind of line is added, add its entry to `explain.py`: a test
refuses a kind with no lesson.

## How a feature is decided

- **Measure before building.** State the acceptance number first, in the
  experiment's own docstring, then run it. `bench/jev/README.md` holds every
  run, including the ones that failed.
- **A feature that fails its gate does not ship.** It is recorded, with its
  numbers and the reason it failed, so nobody builds it twice by accident.
  `systemap ripple` and the import-derived journey paths are both there.
- **Never invent a number.** If it has not been measured, say so.
- **No silent substitution.** If a command cannot do what was asked, it says
  so and exits; it does not do something else quietly.

## The gates that run here

`uv run pytest`, `uv run pre-commit run --all-files`. Between them they hold:
ruff, mypy, cognitive complexity at 15 for anything this commit adds or
worsens, cyclomatic complexity that never grows, no file past 800 lines,
`SKILL.md` at 240 lines, no em dashes, and the three copies of the skill
directory identical. No test sends anything to Jev or runs an agent: both are
injected, and recorded answers are replayed.

The map maps itself. After changing the source, run `systemap refresh`,
`systemap check` and `systemap judgement`, and claim any new module.
