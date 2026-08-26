# Pitfalls seen on first drafts

Each of these has appeared in a first draft. Read before drafting; read
again when `systemap judgement` runs long.

## A module is not a component

One card per module is a dependency graph with prose on it. A component is
something a reader would point at and name: "the part that reads input",
"the ledger". It usually holds several modules; a module that does two
things belongs with the one it is for. The judgement line `single module`
asks about every card that claims one module. Some are right (a small
system has small parts); a map where every line is `single module` was
grouped by file.

## Reading the facts file whole

The facts file is hundreds of kilobytes on a real tree, and reading it
fills the context with JSON that answers nothing. Read it through
`systemap facts` instead: `--modules` for the list with each module's
first sentence, `--docstrings` for the sentences alone, `--module NAME`
for one record rendered, `--names NAME` for its public names with their
kinds, `--entry-points` with their targets, `--external`, and `--imports
NAME` for the edges around one module. The JSON is for the tools; the
views are for you, and none of them prints a test's name.

## Counting

"Handles 14 modules", "guarded by 40 tests", "the largest part": none of
this belongs in `does`, `plain`, a sentence or a journey. The map explains
what the system does, not how much of it there is. The facts file keeps the
counts for the change detector.

## A flow with no artifact

`Flow("A", "B", "uses", "data")` names nothing. The artifact is what moves:
a request, a record, a file, a call. If nothing can be named, ask whether
the flow exists, and whether it is control rather than data.

## Edges without a sentence

The check refuses a flow with no sentence in `relations`, but not a
sentence that says nothing. "A sends data to B" is the artifact restated.
Read from the source side, say what A is to B: "The reader hands the
parser one request at a time; the parser never goes back to the source."

## Grouping by directory instead of by purpose

`pkg/util/` is not a component. Neither is `pkg/models/` when its modules
serve different parts. Group by what a reader would name; then a crossing
import line in the judgement tells you where the directory and the purpose
disagree.

## Placing the cards by hand

A third of a first map's turns once went on positions: a card off the
grid closing a corridor, regions tiling their container, a route that
snakes. Leave `x` and `y` out and run `systemap place`; it lays the
regions out with the corridors and puts every card on the grid, the
parts that talk together; after adding or removing a card, run `systemap
place --all`, which lays every card out again and keeps only the pinned
ones. Pin a card (`pinned=True`, with its `x` and `y`) only when the
check names a fix that is a card moved. `references/layout.md` says what
is still yours to decide; `systemap describe` says what the picture looks
like. `map routes: 0 edges through a card` is the line to reach.

## A map past forty cards

Sixty cards on one canvas is a poster, not a map: every reading lights
everything, and no placement leaves a corridor. When `systemap suggest`
says a map is past forty cards, or a card holds more than ten modules,
open a map inside that card (`map=` on the card; `references/layout.md`
says how) instead of squeezing the grid. The card stays on the top map
with its flows; the map inside claims exactly the card's modules and
nothing else, and the check refuses any difference with the modules
named.

## A flow the code does not back

An edge inferred from a document, or from what the parts ought to do, is
a claim the facts do not make. Every flow carries an evidence state, and
a flow no import joins is `declared`: it draws dashed and the judgement
lists it. Find the import (often a module in the wrong card), name the
mechanism in the sentence when the parts are joined by a subprocess, a
queue or a file and list it under `[flows] observed_by`, or remove the
edge. A map where a quarter of the edges are dashed was drawn from the
README, not from the tree.

## Inventing an entry

The entry must be a public function or class the claimed modules define,
copied from the facts file. A name that sounds right and is not there is
refused by the check; a name that is there but is not the way in (a
helper, a dataclass) passes the check and misleads the reader. Pick the one
a caller uses.

## Layers that are not readings

A layer answers a question a reader asks. A layer with one edge, or one
that mirrors a directory, is not a reading. The standard layers (Structure,
System context, Data flow, Control flow) are derived; add one of your own
only when the repository's vocabulary has it.

## Journeys that skip

A journey that jumps from one side of the map to the other between steps
is missing a step, or the model is missing an edge. Every step traces a
flow the model has; if the walk needs an edge that is not there, the edge
is the finding.

## Invariants that are proposals

"The writer should never read the input" is not an invariant unless the
repository says so. Cite the source in the text. What the repository does
not state goes in your list for the maintainer.

## Answers that live in a chat

An answer to a judgement line written in a message is gone by the next
run; the line comes back and is answered again. Answers go in
`[judgement] answered` in `systemap.toml`, where the next run suppresses
the line and counts it, and where the maintainer reads them.

## A long list answered one line at a time

Two hundred `single module` lines on a two-hundred-module repository do
not need two hundred tables. One table with `items = [...]` and one
reason answers every line the reason covers. Group by reason, not by
line; a line whose reason differs gets its own table.

## Scratch scripts in the repository root

A helper written to count something the tool did not print (`.answers.py`,
`.routes.py`) ends up committed beside the model. `systemap describe`
prints the geometry, the bulk answer forms cover a list, and the label
line names its fix; when a script is still needed, write it outside the
repository (for example /tmp), never in the repository root, and delete
it before the hand-back.

## The generated files and the repository's own gates

Run the repository's formatter on `map/model.py` before the check, and
then every CI command the repository runs, not only pre-commit: its type
checker, its dependency checker, its linter, on the map's files. The
facts file is compact for a large-file hook and the workflow is pinned
for a workflow linter, but a gate the repository adds is the repository's
rule. Two are known: `mypy --strict` cannot find `systemap` in a
repository that does not depend on it (the recommended shape), which the
`# type: ignore[import-not-found]` on the starter's import line answers;
`deptry` reports the same import (DEP001, DEP003), which the pyproject
lines `systemap init` prints answer. A hand-back that says the hooks
passed has not said CI will.
