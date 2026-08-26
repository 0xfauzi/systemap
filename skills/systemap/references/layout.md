# Layout: what is still yours to decide

`systemap place` places every card that has no `x` and `y` and keeps
every card that has them; `systemap place --all` lays every card out
again and keeps only the cards marked `pinned=True`. Write the components
and the flows without positions, run `place`, then run the check; after
adding or removing a card, run `place --all`. What it does, so that you
do not do it by hand:

- Regions go on a two-column grid inside their container, in the order
  the model lists them, with the corridors the router needs already
  there: 48 units between the region columns, 36 between the region
  rows. An edge may not cross a region it does not belong to, and on
  this grid every pair of regions is joined by a corridor.
- Cards go on the grid inside their region, columns 190 apart and rows
  92 apart, three deep before the region takes a second column. A
  region's box follows its card count and a container's box its
  regions. An actor, or any card in a container and no region, stands
  in a column beside the regions, level with the cards it talks to.
- The cards of a region are ordered by a few barycentre sweeps over the
  flows, so the parts that talk sit together.
- The positions are written into `map/model.py` in place, as the values
  of `x` and `y`, and the boxes and the canvas with them; nothing else in
  the file changes. `systemap place --print` prints them instead.

The check decides, as before. `place` is deterministic: the same model
always gets the same positions, and a second run changes nothing. When
`place` says a region has no free slot for a new card, run `place
--all`: the boxes were sized for the cards the region had.

## What you decide

- **Which region a card is in.** A region is a phase, a concern or a
  team; the parts that talk most belong in one region or in adjacent
  ones. This is the placement decision that carries meaning, and
  `place` never makes it.
- **The order of the regions.** The model's order is the grid's order,
  two regions per row, left to right and then down. List the regions in
  the order a reader would walk them, and put regions that talk most
  side by side or one above the other.
- **When to pin a card.** A card marked `pinned=True` (with its `x`
  and `y`) is one a person placed on purpose: `place --all` keeps it
  where it is and lays the other cards out around it, in the free
  slots of the boxes as written; with no pinned card, `place --all`
  lays the boxes and the canvas out again too. Pin a card when the
  check names a route through it and moving it is the fix, or when its
  place must say something the grid does not. A position without the
  flag is `place`'s own: `place` keeps it, `place --all` may move it.
- **The artifact labels.** A label is a noun phrase of one to three
  words (`facts`, `the fix`, `package roots`), never a sentence. When a
  label cannot be seated the check says which fix applies, from the
  router's own seat counts: `gutter between the row of A, B and the row
  of C (y 160 to 226) holds 3 of 3 seats: move a card or raise the row
  pitch of region X` (the room across the gutter is used up: pin a card
  elsewhere, or give that region's cards positions 110 or 130 apart and
  grow its box), or `label is 41 units wider than its seat: shorten the
  artifact` (no run of the path is long enough for the words).

## When to open a map inside a card

One canvas holds about forty cards; past that the readings stop being
readings and no placement leaves a corridor. `systemap suggest` says
when a map is past forty and names the cards with the most modules as
the candidates; a card whose modules exceed ten is a candidate on any
map. To open one:

- Give the card `map="gateway.py"`: a path relative to the model file.
- Write that module like any model, exporting `MODEL` and `MEANING`,
  with no positions: its cards claim exactly the modules the card
  claims, each once, and nothing else (a symbol claim is allowed); its
  actors are the cards around the card on the map above, by their ids,
  so the edges that leave the card land on them.
- Run the loop as before. `systemap place` places every map; `systemap
  check` runs every rule on every map and the nesting rule between
  them, and refuses any difference with the modules named, a sub-map's
  lines prefixed by its id (`Gateway: `); `refresh` writes one page per
  map (`docs/map/Gateway/index.html`, linked from the card's panel and
  back); `figure --map Gateway` draws one; `describe` and `judgement`
  prefix their lines the same way; `delta` names a moved module's card
  on every map it is drawn on, and the map's file.

The top map keeps the card, its flows and its sentences: the map inside
is a closer look, not a replacement. A map inside a map is opened the
same way; its id is `Gateway/Routes`.

## Reading the picture without opening it

`systemap describe` prints what a look at the page would tell you: how
many cards are pinned (the flag), how many `place` wrote, and how many
it positioned for the look only; the
cards each region holds; every edge with its bends and length, worst
first, and the gutter its label sits in; every gutter, named by the cards
on either side of it and its coordinates (`between the row of A, B and
the row of C (y 160 to 226)`), with the seats used at its fullest point
of the seats it has (a seat is one label across the gutter, 13 units
with a 2-unit gap and 3 units clear of the cards); how many edges are
observed, external and declared; and the cards and edges each reading
lights. Run it after every check, and open the page (`systemap serve`)
only if you can. A gutter at its seat count, an edge with five bends, a
reading that lights two cards: each is a thing to fix (a card in another
region, the regions reordered, a card pinned) before the second pass.
