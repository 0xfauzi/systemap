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
   The full drawing at full resolution does not replace the last moving frame at one time. The page draws each moving frame on a second canvas over the page canvas. When the camera stops, it draws the full drawing one time on the page canvas, under the last moving frame. Then the second canvas fades out in 160 ms or more: each frame only changes its opacity, and the browser blends the two canvases. No frame copies a canvas. A version that copied the last moving frame had one long frame more than the earlier renderer after each stop at 4 times throttling (attempt 3 of S3 in `bench/jev/README.md`). Thus the text that the moving frame hid, the full drawing that replaces the images of rule 3, and the full resolution all fade in together. During this fade, nothing on the page canvas changes. A camera change stops the fade. Then the next moving frame continues from the alphas of the text and of the images that the screen shows, but at half resolution.
3. **Large maps.** When the cards of a map are marks only (a map of 400 to 1,500 cards when it is far away), draw the marks of that map into an image one time for each zoom step, and use that image at each frame. The 1,500-card map fails without this.
   While the camera moves, draw a large open map with no nested map and no port from images of the full map. Make one image for each half step of zoom, at 1.41 times the moving resolution, with at most 2 million pixels. Thus the frame never shows an image larger than its pixels, and the names stay clear. Make each image in slices, in the free time of the moving frames. Between two steps, draw the lower image and the higher image over it, with an opacity that follows the zoom. Thus each fade of the level of detail follows the zoom. Until the two images are complete, draw the map as usual.
   The change between the usual drawing and the images fades in time. The maintainer decided this on 2026-11-06: keep the images, and add fades so that nothing appears at one time. The image layer of the map has an alpha from 0 to 1. The alpha goes to 1 while the camera moves and an image of the current step is complete. It goes to 0 when the zoom goes out of the range of the images. While the alpha is between 0 and 1, the frame draws the usual drawing and the images over it. A frame with the two drawings is the most expensive frame of a large map. Thus the alpha of the layer changes by 1 in 80 ms or more, and by 0.2 or less in one frame. At 60 frames each second, a fade takes 5 frames or more. A fade out uses the last images. When the camera stops, the fade of rule 2 removes the images.
   Above the highest step with an image of 2 million pixels or less, the image of that step stays for an eighth of a step more of zoom. Over that part of the zoom, the alpha of the layer goes from 1 to 0, and it follows the zoom. In that part, the image has 0.92 to 1 pixel for each pixel of the moving frame. Thus the fade occurs where the usual drawing is necessary also without the images. While the zoom stays in that part, each frame draws the two drawings. Thus a slow zoom gives more such frames than a fast zoom. In the 400-card dive of `canvas_frames.py`, the fade has 4 or 5 frames in each direction (R1 in `bench/jev/README.md`). In an exploration run without this part, the zoom out of the 400-card map had a fade in of 5 frames after the images were ready. Each of these frames had the usual drawing and the image, and each took more than one tick at 4 times throttling.
   In the layer, each image has a weight that goes to its part: 1 - t for the lower image and t for the higher image, where t follows the zoom between the two steps. When only one of the two images is complete, that image has all of the layer. Thus an image that becomes complete fades in. The higher image of a step becomes the lower image of the next step with no change. While the zoom goes in, the images also fade in over the marks image, in the last quarter step of zoom before the marks end. There a frame costs less than a frame of the usual drawing. In the other frames of marks, the page draws only the marks image.
   The text in an image can show more characters than the usual drawing. The fade makes this difference gradual, but it does not remove it.
   Only the map that asked last keeps its images, at most 4. The marks images of all maps have at most 16 million pixels together. When an image is necessary and there is no space, the marks images of the maps that the last two frames did not draw are removed first. A change of the device pixel ratio makes the images again.
4. **Less work at each frame.**
   - Draw only the cards on the screen. Use an index of the card boxes for each map.
   - Do not draw text below 7 px.
   - Keep the wrapped text of each card for each count of columns. A column is half of the font size, so the lines do not change with the size.
   - After the font loads, set each font that the drawing uses and measure the words of each card. Do this in the idle time of the page.
   - While the camera moves, a card with a name below 10 px shows only its name. While the name grows from 10 px to 12 px, the text under the name fades in. With the name size of 2026-11-06, this occurs from 83 px to 100 px of card height, as before that decision. Text is the largest cost of a moving frame. This rule also fades in time (the decision of 2026-11-06). When the camera starts to move, the text under the name fades out. When the camera stops, it fades in.
   - Each of these fades changes an alpha by 1 in 160 ms or more, and by 0.2 or less in one frame. The fade of the image layer of rule 3 changes an alpha by 1 in 80 ms or more. With reduced motion, each alpha changes at one time, as each camera move does. The browser test (acceptance 13 of `tests/test_canvas_browser.py`) records the alpha of each layer in each frame. The measurements of these fades are S1 to S4 in `bench/jev/README.md`. On a quiet host, commit 0b547b7 had a p95 of two ticks for the dive of the 400-card map at 4 times throttling in each run. The cause was the frames with the usual drawing and the images in the fade above the highest image step. With the shorter and faster fade of rule 3, the p95 was one tick in 4 of 4 runs (R1 and R2 in `bench/jev/README.md`).
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
| very small: less than 15 px high | a mark in the layer color |
| small: 15 px high or more | the name. The name fades in from 15 px to 19 px of card height. |
| medium | the description and the fact row |
| large | the lists of flows and modules |
| a card that opens a map | the preview of the nested map, from the same layout |

Each change of the level of detail follows the zoom continuously (`page_canvas_text.py`):
- A name, a flow label and the name of a box fade in from the size at which the page starts to draw them.
- A new line of a text, a new row of a list, the fact row and the lists fade in with the space that they get. The text under them moves with that space.
- The count of columns of a text does not change while its font size follows the zoom. When the font size stays at a limit, the count of columns changes, and the lines of the two counts fade into each other.
- The lists change from one column to two columns with a fade.
- The description has 4 lines or less.

**The size of the name.** The maintainer decided this on 2026-11-06: on each map, a card 20 px to 32 px high has a larger name, of about 9 px for a card 24 px high. The name size follows the card height continuously (`titleRaw` in `page_canvas_text.py`):

| Card height | Name size |
|---|---|
| 15 px | 6.75 px. The name starts to fade in. |
| 19 px | 8.5 px. The name has the full alpha. |
| 24 px | 9 px |
| 24 px to 75 px | 9 px |
| more than 75 px | 0.12 times the card height, 26 px or less |

Between two rows, the size changes at a constant rate. The fade from 15 px to 19 px of card height has the shape of the fade of the other texts (`sizeFade`). The name is not drawn below 7 px. The card changes from a mark into a card from 16 px to 28 px of height. Thus the name of a small card can be on the mark color. The name has the inset of the card at its left and its right. When a name is wider than that space, the page cuts it and adds three dots. The text under the name starts 1.4 times the name size below the top of the name. Thus the name and that text do not overlap. At the fit of each map of the M11 tree on a screen of 1440 x 900 pixels, the cards are 19.2 px and 24.5 px high. Their names have 8.5 px and 9 px, at the full alpha (K1 in `bench/jev/README.md`, and acceptance 17 of `tests/test_canvas_browser.py`).

A text in more than one of these layouts, at the same place, is drawn one time. Thus the text that does not change keeps its alpha.

**Opening.** A card that opens a map changes into its frame over a range of screen widths. In the same range, the preview changes into the nested map. The positions are the same, so nothing jumps.

**Camera.**
- The wheel and the pinch zoom at the pointer. A drag pans.
- A double-click or a tap goes into a card. Esc goes out one level. F fits the current map.
- A camera move changes the scale in log space. It goes out and back in when the two views are far apart.
- With `prefers-reduced-motion`, each camera move occurs at one time.

**Rings and portals.** They come from the camera position at each frame, as in the prototype. The portal of a neighbour that two levels connect takes the deepest connection. The boundary flow of the map that is open around the view is drawn one time, from its portal. A boundary flow fades in and out with the camera (`page_canvas_fade.py`). The maintainer decided on 2026-11-06 that a boundary flow is under the cards, their texts and the portals, as the routes of a map are. A card that moves onto a line covers it while the line fades. A line is never drawn over a card. The page draws the lines into a layer with the resolution of the canvas of the frame. While the camera moves, that is the second canvas at half resolution. A line that fades out because the chain changed keeps its end on the portal of the same neighbour, also when that portal moves or fades out. The line uses a clear path when one is possible. When a box comes onto that path, the line fades out by time, by 0.2 or less in each frame. Then it fades in on a different clear path, if there is one (F1 and F4 in `bench/jev/README.md`). A portal fades in and out by time, also when the chain changes. A neighbour has a portal only when no part of its card is on the screen. The camera position does not give a part of the alpha. Thus, when the camera stops, each portal is fully shown or it fades out fully (H1 in `bench/jev/README.md`). Its alpha changes by 1 in 400 ms or more, and by 0.0425 or less in one frame. A portal that the chain removes stays at its side or in its row, with no boundary flow, until it has faded out. A portal is drawn only with this alpha, also over a card. The gap between two portals on the same edge also grows and becomes smaller by time. Thus a portal does not jump when a different portal comes or goes (F5 in `bench/jev/README.md`). A portal also keeps off the cards, the flow label plates and the texts of the maps on the screen. When such a box is at the place of a portal, the portal moves to the nearest open place: along its edge, or 34 px or less into the screen. Of the open places, it selects the place nearest to its place in the last frame. Thus it does not go from one side of a box to the other side while the camera moves. When no place is open, the portal stays at its place. While the camera moves, this move changes by 3.4 px or less in one frame. While the place of the portal does not move, the step is a quarter of the distance to the target, and 3.4 px or more, thus the move slows down near its target. It also does not make a move of the portal of more than 16 px in one frame. When the camera moves the place of the portal by 16 px or more in one frame (a fast camera move, a jump of the camera or a change of the screen size), this move changes by that distance or less. Thus the move does not stay from an earlier view, and the portal does not slide for a long time after the camera stops. While the move goes step by step, the portal does not go over a different portal, and it stays in the range of its edge. With reduced motion, it occurs at one time (G1, G2 and J1 in `bench/jev/README.md`).

**The path.** The path is on the canvas at the top left. Each segment moves the camera to that level. When the path is wider than the screen, the widest names become shorter, with "...".

**The fit and the screen bands.** The fit of a map (F, Esc, the path, a link with a hash) puts the frame of the map in the free box of the screen. The free box is the screen less these bands:
- At the top: the path and the top row of the portals.
- At the bottom: the bottom row of the portals and the help line.
- At the left and the right: a band for the portals, only when the widest portal fits in 12 % of the screen width. On a narrow screen, all portals are in the top row or the bottom row.

The fit has a margin of 4 % of the screen at each side. Thus the frame of a wide map fills 92 % of the width of a phone screen. The bands do not change with the level, the camera or the help line. Thus, after a change of the screen size, a camera at the fit of the open map fits that map again.

**The help line.** The help line has one line on a plate at the bottom left, below the bottom row of the portals. On a touch screen, it gives the touch inputs. Else it gives the longest text that fits the screen width. The plate keeps the text clear above the cards.

**The names of the boxes.** In a map that has a nested map or a port, the name of a container or a region stays 14 px from the left screen edge when its box starts at the left of the screen. The name stays in its box. Thus the screen edge does not cut the name when the camera is deep in the map. A map with no nested map and no port can be drawn from images while the camera moves. Thus its names do not move in this way, and they do not jump when the camera stops.

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
