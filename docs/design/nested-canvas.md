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
| C1: size of the canvas data (`canvas_data.text`) of the M11 tree, 50 maps | at most 2 MB raw | PASS after PR #152 (3 runs): 732,502 bytes raw and 30,256 bytes after gzip -6. One build takes 1.9 to 2.1 s. Before PR #152, one build took 22 s for 731,326 bytes. The key `fp` of the nested-flow ports (7afa36f) added the 1,176 bytes. See `bench/jev/README.md`. |
| C2: frame time of the canvas page of step 2, half resolution while the camera moves, 4 times CPU throttling: M11 tree (pan, all top cards with previews, dive), 400 cards (pan, dive), 1,500 cards (pan). No GPU: Chromium paints in software. | p95 at most 35 ms (two 60 Hz ticks, 33.3 ms, plus 5 percent) | PASS in run 2: p95 16.7 to 16.8 ms, and 33.3 ms for the dive of the 400-card map. Run 1 failed the dive (p95 550 ms): long dashed paths of the maps above the view. After the change for the deep zoom, the dive of the 400-card map has p95 of one tick (16.7 or 16.8 ms) in 17 of 17 runs. See `bench/jev/README.md`. |
| C2 at normal CPU speed, same scenarios | p95 at most 17.5 ms | PASS in run 2: p95 16.7 to 16.8 ms. |
| C3: load to an interactive map, M11 tree, 50 maps | at most 1.5 s at normal CPU speed | PASS: 76 ms (264 ms with 4 times throttling). The time of `canvas_data.build` is not included. |

The frame time on a real slow device is not measured yet. The `?hud` readout of the canvas page shows it on a device.

## Performance

The maintainer asked for care with the speed of the canvas when many elements are on the screen. The prototype was measured in the views that show the most cards. Each value below comes from a script whose acceptance value was written before the run. The host is headless Chromium on a 4-core Xeon at 2.1 GHz with no GPU. Thus the browser paints in software, and the values are worse than on a usual laptop or phone. That difference is not measured.

Acceptance for each view: p95 frame interval at most 16.7 ms at normal CPU speed, and at most 35 ms with 4 times CPU throttling. The maintainer set the second limit to two 60 Hz ticks (33.3 ms) plus 5 percent, because the timer of the ticks has a small error.

| Renderer | 50 maps, all top cards open | 400 cards, pan | 1,500 cards, pan | 50 maps, 4 times throttling |
|---|---|---|---|---|
| SVG elements made again at each frame | 33 ms | 67 ms | 100 ms | 67 to 100 ms |
| `<canvas>` 2D | 17 ms | 33 ms | 50 ms | 67 to 133 ms |
| `<canvas>`, half resolution while the camera moves | 17 ms | 17 ms | 33 ms | 33 to 50 ms |

A CPU profile of the canvas renderer with 4 times throttling gave these shares: stroke 32 %, text 30 %, fill 18 %, and the scene code less than 5 %. One path for each style (batching) did not change the result. Thus the cost is the area of pixels that the browser paints, not the number of calls.

These are the rules for the renderer of step 2:

1. **Draw on a `<canvas>`.** Do not make SVG elements at each frame. The hidden tree list gives access for keyboards and screen readers.
2. **Resolution.** Use half resolution while the camera moves. Draw at full resolution 150 ms after the camera stops.
3. **Large maps.** When the cards of a map are marks only (a map of 400 to 1,500 cards when it is far away), draw the marks of that map into an image one time for each zoom step, and use that image at each frame. The 1,500-card map fails without this.
   While the camera moves, draw a large open map with no nested map and no port from images of the full map. Make one image for each half step of zoom, at 1.41 times the moving resolution, with at most 2 million pixels. Thus the frame never shows an image larger than its pixels, and the names stay clear. Make each image in slices, in the free time of the moving frames. Between two steps, draw the lower image and the higher image over it, with an opacity that follows the zoom. Thus each fade of the level of detail follows the zoom. Until the two images are complete, draw the map as usual.
   The change between the usual drawing and the images is a visible change at one time: in the frame after the two images are complete, and when the camera stops. The text in an image can also show more characters than the usual drawing. The rule "Nothing appears at one time" does not permit this change, so the maintainer must accept it or remove it. A fade between the two drawings needs the two drawings in the same frames, and that removes the gain of the images.
   Only the map that asked last keeps its images, at most 4. The marks images of all maps have at most 16 million pixels together. When an image is necessary and there is no space, the marks images of the maps that the last two frames did not draw are removed first. A change of the device pixel ratio makes the images again.
4. **Less work at each frame.**
   - Draw only the cards on the screen. Use an index of the card boxes for each map.
   - Do not draw text below 7 px.
   - Keep the wrapped text of each card for each count of columns. A column is half of the font size, so the lines do not change with the size.
   - After the font loads, set each font that the drawing uses and measure the words of each card. Do this in the idle time of the page.
   - While the camera moves, a card with a name below 10 px shows only its name. While the name grows from 10 px to 12 px, the text under the name fades in. Text is the largest cost of a moving frame. It is a visible change: when the camera stops, the text under the name comes back at one time. The rule "Nothing appears at one time" does not permit this change, so the maintainer must accept it or remove it.
   - Read the theme colors one time, and again only when the theme changes.
5. **A performance test in CI.** A Playwright test uses the scenarios of `bench/jev` (the M11 tree, a 400-card map, and a 1,500-card map) with 4 times CPU throttling. It fails when a p95 value is more than its limit. A frame-rate display (`?hud`) lets a person measure on a real device.

The data side must also be fast. The first canvas data build took 22 s for 50 maps. A profile found two causes outside the canvas code:
- `model.claimed` compared each pattern with each module. This was 20 million comparisons.
- `judgement_evidence.names` compiled one regular expression for each judgement line and each module.

PR #152 replaces both with indexes that give the same output bytes. On the M11 tree, `check` goes from 69.6 s to 9.8 s, and `judgement` from 571.9 s to 6.0 s (`bench/jev/README.md`). After that PR merged, C1 was measured again in 3 runs: one build of the canvas data for 50 maps takes 1.9 to 2.1 s, not 22 s.

## The data

One page has one data object for the tree. It holds no rendered SVG for the maps. For each map, it holds:

- the canvas size, the containers and the regions;
- each card: its ID, box, kind, layer, card text, `does` text, module names, assurance level and freshness, and the map that it opens;
- each flow: its source, target, artifact, kind, route points and label position. These come from the current router (`route.routed`), in the coordinates of that map. The page scales them into the card that opens the map. Thus the routes are the same right-angle routes as today.
- the boundary flows and their ports, from `nest_join` (step 4);
- the findings and the change records that the page shows today.

The module is `canvas_data.py`. The data is computed from the current model, facts and judgement. It adds no new facts.

## The renderer

The renderer is a script in the page (`page_canvas.py` gives it, under the current CSP digest rules). It paints the data on a `<canvas>` element with the 2D API, and it follows the rules of the section "Performance". It does not make SVG elements at each frame.

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

**Rings and portals.** They come from the camera position at each frame, as in the prototype. The portal of a neighbour that two levels connect takes the deepest connection. The boundary flow of the map that is open around the view is drawn one time, from its portal. A boundary flow fades in and out with the camera. It fades out before a card, a text or a portal gets to it, because it must not cross them (`page_canvas_fade.py`, F1 in `bench/jev/README.md`).

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
   - C2: frame time with 4 times CPU throttling in Chromium. Acceptance: p95 at most 35 ms. The maintainer set this limit to two 60 Hz ticks (33.3 ms) plus 5 percent, because the timer of the ticks has a small error.
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
- A boundary flow can still change by more than 0.25 between two frames (F1 in `bench/jev/README.md` passes only for the camera moves of the test). The two rules conflict when a box gets to a line quickly: a line must not cross a box, and nothing appears or goes at one time. These are the known causes:
  - The cap of a value has no rate limit when it goes down. A box that starts to move quickly near a line, from rest, makes the value go down at once.
  - A path that a portal blocks becomes not possible in one frame. Then its value goes to 0 at once.
  - The line keeps its path until that path is not possible or much longer. Thus the same camera move gives a different result after a different earlier move.
- A portal appears and goes at one time when the chain changes. A fade of the portals in time was tried. With it, F1 failed (0.287 in one frame), because the speed of a box in `boxCap` does not include the change of the weight of a portal. When the weight of the frame before was added, F1 failed with 0.432. A fix needs a decision about the two rules above.
