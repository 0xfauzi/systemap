# Component positions and routes

`systemap place` writes positions for components without `x` and `y`.
It keeps existing positions.
After component additions or removals, use `systemap place --all`.
That command keeps only positions with `pinned=True`.
Then run `systemap check && systemap judgement --strict`.

## Automatic placement

Regions use a two-column grid inside their container.
The grid keeps corridors between region boxes: 48 units between columns and 36 units between rows.
A route must not cross an unrelated region.
The corridors connect all region pairs.

For up to six regions, the command examines every region order.
For more regions, it uses a greedy initial order and pairwise swaps.
The initial estimate uses minimum bends and route length.
The router examines the best twelve estimates and the original model order.
The final score compares label collisions, unrelated-region crossings, bends, and length, in that order.
The lowest score wins. An equal score keeps the earlier order.
Use `--keep-order` when the grid must keep the model's region order.

Component columns are 190 units apart. Rows are 92 units apart.
After three rows, the region uses another column.
Region size depends on its components. Container size depends on its regions.
Actors and components without a region use a column beside the regions.
Their vertical positions depend on connected components.
Barycenter sweeps put components with many flows near one another.

Placement changes positions, boxes, and canvas dimensions in the model file.
It does not change component functions or flow claims.
Use `--print` to show positions without file changes.
The same model gives the same positions. A second placement changes nothing.
If a region has no free position, use `systemap place --all`.

## Placement decisions

Select each component's region by system function, phase, or team.
Keep components with many flows in the same or adjacent regions.
Automatic placement does not select the region assignment.

The region list also determines document order and the search tie-breaker.
Select an order that helps a reader learn the system.
Use `--keep-order` only when that grid order is necessary.
A forced order can have more route bends than the selected search result.

Use `pinned=True` for a position that must stay fixed.
With pinned components, placement uses free positions in the existing boxes.
Without pinned components, `--all` can change boxes and the canvas.
A position without the flag can move during `--all`.

Use ASD-STE100 artifact noun phrases of one to three words.
If a label has no free position in a gutter, move a component or increase row spacing.
If a label is wider than its route segment, shorten the artifact without a change to its meaning.
Use the actual dimensions printed by the checker.
Do not select spacing from an invented measurement.

## Nested maps

The suggestion threshold is forty components for a map or more than ten modules for one component.
These are tool thresholds, not a readability guarantee.
For a suggested nested map:

1. Set `map="gateway.py"` on the parent component.
   The path is relative to the parent model file.
2. Write `MODEL` and `MEANING` in that module without positions.
   Assign exactly the parent's modules or source symbols to its internal components.
   Do not include unrelated source claims.
3. Use the parent map's adjacent component identifiers for the nested map actors.
4. Run the normal mapping loop for every map.

`systemap place` and `systemap check` examine every nested map.
The nesting check rejects differences in source coverage.
Nested findings have a map prefix, for example `Gateway: `.
`refresh` writes `docs/map/Gateway/index.html` with parent and child links.
`figure --map Gateway` makes its figure.
`describe`, `judgement`, and `delta` also identify the applicable map.
The parent component and its flows stay on the parent map.
A further nested map can have an identifier such as `Gateway/Routes`.

## Read the layout measurements

`systemap describe` shows these measurements:

- Pinned, stored, and automatically displayed positions.
- Components in each region.
- Bends and length for each route, with the worst routes first.
- Label gutters and their occupied positions.
- Flow evidence states and layer contents.

A gutter label position uses 13 units, a 2-unit gap, and 3 units of component clearance.
The command gives actual gutter coordinates and occupancy.
Examine full gutters, routes with many bends, isolated regions, and empty layers.
Use `systemap serve` to examine the page when a browser is available.
