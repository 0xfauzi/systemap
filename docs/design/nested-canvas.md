# The nested map canvas: the design

Status: a plan. The maintainer selected this direction on 2026-11-05 from three prototypes. It replaces the visual steps 6, 7 and 8 of `docs/design/nested-parts.md` (linked pages, the Map tree panel, and the search across pages). Steps 1 to 5 of that design stay as they are.

## The decision

The maintainer selected direction A with the portals of direction C:

- **One canvas for the full tree.** The reader goes deeper by zooming. A card that opens a map shows a preview of that map. When the card becomes large on the screen, the preview grows into the nested map.
- **Portals.** When a neighbour of the open map moves out of the screen, it stays at the screen edge as a portal, on its side. A click on a portal moves the camera to that neighbour.
- **Rings.** When the frame of an open map becomes larger than the screen, it stays at the screen edge as a ring. There is one ring for each level.
- **No control outside the map for depth.** Zoom, pan, depth and the path are on the canvas. The Map tree panel and the pages for each nested map go away.

The maintainer also gave these rules for the cards and the motion:

- A large card must not show empty space. It shows information. The amount of information grows with the card size on the screen: the name, the description, the facts (modules, flows in and out, review state), and then the lists of flows and modules.
- The depth transition must not jar. Each change follows the zoom continuously. Nothing appears at one time.

The prototype is `docs/design/nested-canvas-prototype.html`. Open it in a browser. It uses sample data and straight flow lines. It is a reference for the behavior, not code to ship.

## What is measured

Each value comes from a script whose acceptance value was written before the run.

| Item | Acceptance | Result |
|---|---|---|
| Frame time while zooming, prototype renderer, 50 maps and 2,000 cards, headless Chromium, 4-core Xeon at 2.1 GHz | p95 frame interval at most 16.7 ms | PASS: 240 frames in each of 3 runs, all at 16.7 ms. No frame was longer than 25 ms. |
| Size of one page with all 50 maps of the M11 tree, from the current pages (shared blocks one time) | at most 10 MB raw and 2 MB gzip | not known yet (the run is in progress) |
| C1: size of the canvas data (`canvas_data.text`) of the M11 tree, 50 maps | at most 2 MB raw | PASS: 731,326 bytes raw and 30,236 bytes after gzip -6. One build took 22 s. See `bench/jev/README.md`. |

These are not measured yet:
- the frame time on a slow device or with CPU throttling;
- the time from page load to an interactive map.

The steps below measure them.

## The data

One page has one data object for the tree. It holds no rendered SVG for the maps. For each map, it holds:

- the canvas size, the containers and the regions;
- each card: its ID, box, kind, layer, card text, `does` text, module names, assurance level and freshness, and the map that it opens;
- each flow: its source, target, artifact, kind, route points and label position. These come from the current router (`route.routed`), in the coordinates of that map. The page scales them into the card that opens the map. Thus the routes are the same right-angle routes as today.
- the boundary flows and their ports, from `nest_join` (step 4);
- the findings and the change records that the page shows today.

The module is `canvas_data.py`. The data is computed from the current model, facts and judgement. It adds no new facts.

## The renderer

The renderer is a script in the page (`page_canvas.py` gives it, under the current CSP digest rules). It draws SVG from the data at each frame. It draws only the elements on the screen.

**Level of detail.** This follows the screen size of each card:

| Screen size of a card | What it shows |
|---|---|
| very small | a mark in the layer color |
| small | the name |
| medium | the description and the fact row |
| large | the lists of flows and modules |
| a card that opens a map | the preview of the nested map, from the same layout |

**Opening.** A card that opens a map changes into its frame over a range of screen widths. In the same range, the preview changes into the nested map. The positions are the same, so nothing jumps.

**Camera.**
- The wheel and the pinch zoom at the pointer. A drag pans.
- A double-click or a tap goes into a card. Esc goes out one level. F fits the current map.
- A camera move changes the scale in log space. It goes out and back in when the two views are far apart.
- With `prefers-reduced-motion`, each camera move occurs at one time.

**Rings and portals.** They come from the camera position at each frame, as in the prototype. The portal of a neighbour that two levels connect takes the deepest connection. The boundary flow of the map that is open around the view is drawn one time, from its portal.

**The path.** The path is on the canvas at the top left. Each segment moves the camera to that level.

**Search.** Ctrl K stays. A result in a different map moves the camera to that card. The search index of step 8 is reused.

**Views.** Map, Sequences and Changes stay in the header, and so do the layers. They are views of the same canvas, not navigation. In the Changes view, a card that opens a map shows "changed inside" when a nested map changed (the roll-up of step 8).

**Links.**
- The URL hash holds the camera target, for example `#Gateway/Routes`. A link opens the canvas at that map.
- The pages of each nested map (`Gateway/index.html`) become small pages that go to the top page with that hash. Thus current links still work.

## Access

**Keyboard.**
- Tab moves through the cards of the current map in reading order.
- Enter goes into a card that opens a map.
- Esc goes out one level.
- The arrow keys pan, and + and - zoom.
- Focus is visible on the canvas.

**Screen readers.** A hidden list gives the tree: maps, cards, flows and the facts of each card. Each item is a link that moves the camera. The canvas has a label that gives the current path.

**Phone.**
- A pinch zooms, and a drag pans.
- A tap selects a card. A second tap on a card that opens a map goes into it.
- The current phone grid stays for the top map, until the canvas passes the phone measurements below.

## Steps

Each step is a pull request with the required checks of AGENTS.md, `/code-review` and `/simplify`.

1. **Data.** `canvas_data.py`, tests, and the measurement C1: the bytes of the canvas data for the M11 tree. Acceptance: at most 2 MB raw for 50 maps.
2. **Renderer behind a setting.** `[render] canvas = true` writes the canvas page in place of the linked pages. It covers level of detail, opening, the camera, rings, portals, the path, and the URL hash. Measurements:
   - C2: frame time with 4 times CPU throttling in Chromium. Acceptance: p95 at most 33 ms.
   - C3: load to an interactive map for 50 maps. Acceptance: at most 1.5 s.
3. **Access and phone.** Keyboard, the hidden tree list, and touch. Measurements:
   - C4: axe-core. Acceptance: 0 serious or critical issues.
   - C5: phone emulation at 390 x 844. Acceptance: no horizontal scroll, and targets of 44 px or more.
4. **Views.** Search across the canvas, the Changes roll-up on cards, and the layers.
5. **Default.** The canvas becomes the default. The linked pages become redirect pages, and the Map tree panel goes. Branches 6 to 8 of the nested-parts design close. Their tests for ports, badges, contrast and the search index move to the canvas.

## Open questions

- Text is drawn in SVG. Very long `does` texts need a line limit and an ellipsis. Is a limit of 4 lines correct?
- Is a map with more than 400 cards possible? It can be too large for one page. Measurement C1 decides if the data must load in parts.
- On a phone, is the canvas as good as the current grid for the top map? C5 and a test with a person decide.
