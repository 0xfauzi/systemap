# Layout: where the regions go, so the edges have somewhere to run

Placing the cards is the part of the draft that takes longest, and the
rule that governs it is not visible from the schema. It is this: an edge
may not cross a region it does not belong to. The router runs every flow
through the gutters between cards, and it treats a region the flow
neither starts nor ends in as a wall. When no corridor avoids every
foreign region, the route is drawn anyway and `systemap check` refuses
it (`route: A -> B crosses region X`). So the regions must leave
corridors, and the corridors must reach every pair of regions.

## The shapes that work

- **Regions never tile a container.** Leave a gap between every two
  regions: 48 units between region columns, 36 between region rows. The
  gap is where the edges between the regions run.
- **A 2xN grid of regions works for every pair.** With two region
  columns and any number of region rows, the vertical gap between the
  columns and the horizontal gaps between the rows form a cross (or a
  ladder): from any region, an edge can reach the corridor beside it and
  run along the corridors to any other region without entering a third.
  The starter model `init` writes is a 2x2 grid with these gaps already
  in place; rename the regions and keep the gaps.
- **More than two full-width bands does not.** Three regions stacked as
  full-width bands leave no corridor between the top band and the bottom
  one: every route between them must cross the middle band, and the check
  refuses it. Either narrow the middle band so a corridor runs past it,
  or turn the stack into two columns.
- **A container holding one region needs no gap**: the region is the
  container's inside. A container holding several needs the same gaps
  between them as the map does.

## Placing the cards

- Put the cards on the grid: columns 190 apart (150 card, 40 gutter),
  rows 92 apart (56 card, 36 gutter). A card off the grid closes the
  corridor beside it.
- The pitch is a starting value, not a rule. A dense region, one whose
  row gutters carry more labels than they have seats, raises its own row
  pitch (110, 130) and grows its box; the regions in one grid row need
  not share a height, and the corridors between regions stay where they
  were. When the check says `raise the row pitch of region X`, that is
  the region to open up; the rest keep the grid.
- Put the parts that talk most in adjacent regions, and within a region
  next to each other. An edge between neighbours is short and straight;
  an edge across the map bends around everything between.
- Leave one empty card column where the long routes run: a column of no
  cards down the middle of a region, or beside it, is the corridor the
  edges between the far ends of the map take. The check names every
  route through a card and every route across a foreign region; the fix
  is a card moved, never an edge dropped.
- Artifact labels sit on their edges. A label is a noun phrase of
  one to three words (`facts`, `the fix`, `package roots`), never a
  sentence. When a label cannot be seated the check says which fix
  applies, from the router's own seat counts: `gutter between the row of
  Orchestrator, Telemetry and the row of RosterClient (y 160 to 226)
  holds 3 of 3 seats: move a card or raise the row pitch of region
  orchestration` (the room across the gutter is used up; the gutter is
  named by the cards on either side and its coordinates, and the fix by
  the region it runs through) or `label is 41 units wider than its seat:
  shorten the artifact` (no run of the path is long enough for the
  words).

## Reading the picture without opening it

`systemap describe` prints what a look at the page would tell you: the
cards each region holds; every edge with its bends and length, worst
first, and the gutter its label sits in; every gutter, named by the cards
on either side of it and its coordinates (`between the row of A, B and
the row of C (y 160 to 226)`), with the seats used at its fullest point
of the seats it has (a seat is one label across the gutter, 13 units
with a 2-unit gap and 3 units clear of the cards); and
the cards and edges each reading lights. Run it after every check, and
open the page (`systemap serve`) only if you can. A gutter at its seat
count, an edge with five bends, a reading that lights two cards: each is
a thing to fix in the placement before the second pass.
