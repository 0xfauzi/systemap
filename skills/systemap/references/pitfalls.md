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

## Positions that make routes cross

The check refuses a route through a card and across a foreign band, and
the router does its best in the gutters. Cards off the grid close the
corridors. Put every card on the grid (columns 190 apart, rows 92 apart),
put the parts that talk most next to each other, leave one empty column
where the long routes run, and move a card rather than accept a route that
snakes. `map routes: 0 edges through a card` is the line to reach.

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
