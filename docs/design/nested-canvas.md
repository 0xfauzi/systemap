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
| C4: axe-core 4.14.0 on the canvas page: the M11 tree, the map of 400 cards, the self-map and the fixture of `tests/test_nest_join.py`, at 1440 x 900 and 390 x 844 pixels, light and dark, at the top map and in a nested map, with no focus, with the focus on a link of the list and on a card | 0 serious or critical issues | PASS (S4 in `bench/jev/README.md`): 0 violations in 96 runs. axe-core cannot measure the contrast of a focused link of the hidden list. By hand, the contrast ratio is 14.34 (light) and 14.21 (dark). The job canvas-browser runs `tests/test_canvas_access.py` with axe-core 4.14.0. |
| C5: phone emulation in Playwright 1.63.0 Chromium, 390 x 844 pixels, `isMobile` and `hasTouch`, 3 device pixels for each pixel. The camera fit of each of the 50 maps of the M11 tree. | no horizontal scroll, and each target on the canvas 44 px or more in width and in height | PASS (acceptance 28 of `tests/test_canvas_browser.py`): at each of the 50 fits, the scroll width is 390 px and the scroll position is 0. The 294 targets at the fits (182 portals and 112 parts of the path) are 44 px or more in width and in height. The smallest is 44 x 44 px. The plate of the facts of a selected card is 44 px high. At the fits, no drawn portal covers a box of the maps, and the target of a portal goes into no card. |
| C2 and C3 again with the header and the layers (step 4, V1 in `bench/jev/README.md`): A/B with d8ac070 on a quiet host, the M11 shape (pan-fit, all-open, dive), 400 cards (pan-fit, dive) and 1,500 cards (pan-fit), with the layer data set, and for pan-fit also with a layer change during the move | p95 at most 35 ms at 4 times throttling and 17.5 ms at normal speed, the median of B at most one tick more than A, no more seam calls in a frame than drawn cards and flows, and C3 of the M11 tree at most 1.5 s | PASS: the largest p95 of B is 16.8 ms, the largest difference of the medians is +0.1 ms, and C3 of B is 93.8 ms or less at normal speed. |
| C4 and C5 again with the header (step 4, V1) | 0 serious or critical issues; no horizontal scroll and targets of 44 px or more | PASS: 0 violations in the 96 runs of A1 and in the runs with the focus on each header control. At 390 x 844 pixels, the scroll width is 390 px, and each header target is 44 x 44 px or more. Acceptance 17 and 28 of `tests/test_canvas_browser.py` pass with the top band of the header. |
| C1 with the change keys of the Changes view (step 4): the M11 tree with 819 changed modules and a changed `does` text in each map on level 3 | at most 2 MB raw | PASS (W1 in `bench/jev/README.md`): 1,127,222 bytes raw and 67,307 bytes after gzip -6. Without change data, the bytes are equal to the bytes of d8ac070 for the M11 tree and for the three-level tree of the tests. |
| C2 with the Changes view on (step 4): M11 shape, 400 cards and 1,500 cards with generated change keys, 4 times CPU throttling, A/B with the quiet gate | p95 at most 35 ms | PASS (W2 in `bench/jev/README.md`, measured with the stand-in seam before the merge of the parts): p95 16.7 to 16.8 ms in each quiet run of B. |
| Q1 (step 4, Sequences view): the bytes of the sequence data (`sq`) in the canvas data | a tree without sequences: the same bytes as d8ac070, and C1 stays at most 2 MB. The self-map: at most 20,000 bytes more. | PASS (`bench/jev/README.md`): the M11 tree has the same 731,865 bytes. The self-map (16 sequences, 69 steps) has 12,554 bytes more. The M11 tree with a sequence of 20 steps in each map has 796,797 bytes. |
| Q2 (step 4, Sequences view): C2 with a sequence shown, pan-fit and dive of the self-map and of the map of 400 cards with a sequence of 20 steps, in the Whole route and at step 10, A/B with the quiet gate | p95 at most 35 ms at 4 times throttling, and the median of B at most one tick more than A | PASS (`bench/jev/README.md`): the largest p95 of B is 16.8 ms. The largest difference of the medians is +0.1 ms. Two quiet runs of A and two of B. |
| C2 and C3 again after the merge of the four parts of step 4 (U1 in `bench/jev/README.md`): the scripts of the parts again (with the layers, in the Changes view, with a sequence shown), and the dive of the map of 400 cards for each tree of the merge | p95 at most 35 ms at 4 times throttling and 17.5 ms at normal speed, the median of B at most one tick more than A, and C3 at most 1.5 s | PASS: the largest p95 is 33.3 ms at 4 times throttling and 16.8 ms at normal speed. C3 of the M11 tree is 98.0 ms or less. The dive of the map of 400 cards has a p95 of one or two ticks from run to run in each tree, also in the part header-layers alone. The median of the merged tree is 16.8 ms. |
| S8: the Find dialog of step 4 (`page_canvas_find`), M11 shape (2,000 cards), A/B with the quiet gate against commit d8ac070 | page at most 32,000 bytes larger and the same data; making the results at most 50 ms at 1x; pan-fit p95 at most 35 ms at 4x after the dialog opens and closes, and at most 1 ms more than A | PASS: 22,317 bytes raw (6,773 after gzip -6) and the same data element; 0.9 to 3.8 ms for 3,952 results; p95 16.8 ms in A and in B. See `bench/jev/README.md`. |

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
| small: 15 px high or more | the name. From 15 px to 19 px of card height, the mark changes into a card and the name fades in. |
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
| 24 px to 75 px | 9 px |
| more than 75 px | 0.12 times the card height, 26 px or less |

Between two rows, the size changes at a constant rate. The fade from 15 px to 19 px of card height has the shape of the fade of the other texts (`cardShow` in `page_canvas_draw.py`). The name is not drawn below 7 px. In the same range of card height, the card changes from a mark into a card. Thus a name at the full alpha is on the card color, not on the mark color. On a map of 100 cards or more, the page uses the marks image (rule 3) only while the tallest card is less than 15 px high. The name has the inset of the card at its left and its right. When a name is wider than that space, the page cuts it and adds three dots. The text under the name starts 1.4 times the name size below the top of the name. Thus the name and that text do not overlap. At the fit of each map of the M11 tree on a screen of 1440 x 900 pixels, the cards are 19.2 px and 24.5 px high. Their names have 8.5 px and 9 px, at the full alpha (K1 in `bench/jev/README.md`, and acceptance 17 of `tests/test_canvas_browser.py`).

A text in more than one of these layouts, at the same place, is drawn one time. Thus the text that does not change keeps its alpha.

**Opening.** A card that opens a map changes into its frame over a range of screen widths. In the same range, the preview changes into the nested map. The positions are the same, so nothing jumps.

**Camera.**
- The wheel and the pinch zoom at the pointer. A drag pans.
- A double-click with a mouse goes into a card. On a touch screen, a tap selects a card, and a second tap goes into it (see "Access"). Esc goes out one level. F fits the current map.
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

**The header (step 4).** The page has one `header` element in front of `main` (`canvas_header.py`). It is over the top of the canvas, 48 px high, and 56 px high on a touch screen. It has the name of the project, the views, the layers and the Find button. The renderer keeps a top band of the header height free (`HEAD_H`): the path, the top row of the portals, the rings and the boundary flows are below it. The middle of a fit is at the same height as without the header when the frame of the map fits there. Else the frame moves down only as far as necessary. Thus the fits of the maps that are not as high as the free box do not change.
- The views are three buttons with `aria-pressed`. The script hides the button of a view that no part of the renderer registers.
- The layer control has one button for each layer of the union of the layers of all maps, then All. The layers of the top map come first, in the order of the linked page (`page.tab_layers`). The buttons are a toolbar: the arrow keys, Home and End move between them. When the buttons do not fit, a select shows in their place.
- In the Map view, a layer shows only its flows. A card that no flow of the layer touches and that is not a subject of the layer is quiet: it has the alpha 0.32, as on the linked page (`paint` in `schematic_relations.py`). The flags of each map are calculated one time for each layer.
- The page opens in the Map view with All. Thus it shows the same map as before step 4.
- A layer applies only in the Map view, as on the linked page. The layer control stays in the header in each view. A layer button in a different view goes to the Map view with that layer.
- A map that does not have a layer shows no flow for that layer, and each of its cards that is not a subject of the layer is quiet.
- The keys of the camera do not operate while the keyboard focus is in the header, in a text field, in a select, on a button or in a dialog.
- The live region gives each new view and layer, with the count of the flows that the current map shows. The label of the canvas gives the view and the layer when they are not Map and All.
- The URL hash does not hold the view. A live reload keeps only the hash. A view part of the hash is a decision for the maintainer.

**The seam of the views (step 4).** The other view parts (Sequences, Changes and the search) use this contract of `page_canvas_view.py`:
- `VIEW` is `{mode, layer, epoch}`. The mode is "map", "sequences" or "changes". The epoch grows by 1 at each change. The marks image and the map images of a large map have the epoch in their key.
- `setView(mode, layer)` sets the view, as the header does. `systemapCanvas.setView` and `systemapCanvas.viewState` give it to the tests. A view part can test with `setView` before its header button shows.
- A view part registers `VIEWS[mode] = {card, flow, over, enter, leave, frame, band, facts, say}`. Each function is optional.
- `card(c)` gives null for the usual card, or `{a, ring, tag, back, note}`. `a` is the alpha of the card. `ring` is null or `{c, w, d}`: a line 3 px outside the card, with a color (a theme token or a color), a width and an optional dash. `tag` is null or `{s, c, t, o}`: a plate with a short text at the top right of the card, with a fill color, an optional text color and an optional outline `{c, d}`. `back` is null or `{c, w}`: a line around the back card of a card that opens a map. `note` has the keys of `tag`: a plate on the lower edge of the back card, at the right. A tag and a note fade in with the width of the card, from the width of their plate.
- `flow(f)` gives null for the usual flow, or `{a, color}`. A color of null is the layer color. `f.map` is the map of the flow.
- `over(m, a, ox, oy, alpha)` draws after the cards of map m, for example a route. `alpha` includes the fade of the view.
- `frame()` occurs at the start of each frame. `band(fresh)` gives the height of a bar of the view under the header (the toolbar of the Sequences view). The top band of the screen is the header and each bar, multiplied by the fade of its view (`headBand`).
- `facts(c)` and `say(m)` give the words of the current view for a card in the list of the tree and for a map in the live region and the list (`viewFacts`, `viewSay`). After a change of the mode, the script writes the list of the tree again when one of the two modes has `facts`.
- `enter(from)` and `leave(to)` occur at a change of the mode. `viewTouch()` tells the seam that the values of a view part changed without `setView`, for example at a new step of a sequence.
- The drawing calls the seam only for the cards and the flows that a frame draws (`viewCard`, `viewFlow`). A value fades: it changes by 0.2 or less in one frame, and by 1 in 160 ms or more from the input. A mark fades out, and then the new mark fades in. With reduced motion, a value changes in one frame. The marks image of a large map fades from the old view to the new view (`viewMarks`).

**The Sequences view (step 4).** `canvas_sequences.py` adds the key `sq` to each map that has sequences. A tree without sequences has the same canvas data as before. `page_canvas_sequences.py` registers `VIEWS.sequences` only when a map has sequences. Else the header hides the Sequences button.
- A toolbar under the header has the words of the linked page: the sequence chooser, Whole route and Steps, Start at step 1, Previous, Next and End sequence. It shows only in the Sequences view, and it fades in and out in 160 ms. The top band of the screen grows with the toolbar (`band`), so the path, the portals and the fit stay below it.
- The chooser opens a listbox: the sequences of the current map first, then one group for each other map. The arrow keys, Home, End and a letter move the focus. Enter or Space selects, Escape closes the list and gives the focus back to the chooser, and Tab closes it.
- A choice moves the camera to the fit of the map of the sequence. There, the route flows keep their layer colors, and the flows of the later steps have the alpha 0.4. The other cards have the alpha 0.32, and the other flows 0.16. Each step has its number at the label of its flow. The first card has the tag START. In the Steps mode, the current flow is wider, and its cards have the tags ACTS and MEASURES.
- Previous and Next move the camera to the two cards of the flow of the step, or to its acting components. The camera does not move when the cards are in the free box with their names. The live region gives "Step k of n:" and the sentence of the step.
- The layer filter does not apply in this view.

**The Changes view (step 4).** `canvas_changes.py` adds the change keys `cm`, `cl`, `cr` and `ci` to each map with a revision comparison: the change marks of the cards, the lost flows, the roll-up record and the cards that open a changed map. The roll-up (`Rollup`, `records`, `counted`) is copied from `page_rollup.py` of the branch `claude/nested-step-8`, which was not merged. `page_canvas_changes.py` registers `VIEWS.changes` on the seam. The values of each card and flow are constant, so the part makes them one time.
- A card with changed source has a ring of 2 px in the change color and the filled tag CHANGED. A card with only changed tests has a ring of 1.2 px and the outlined tag TESTS. A card that imports changed source has a dashed ring of 1.2 px and the tag IMPORTS with a dashed outline.
- The other end of a lost flow has the alpha 0.6. Each other card has the alpha 0.32. A marked card and a card that is "changed inside" keep the alpha 1. A card that opens a map goes to the alpha 1 as it opens.
- Only the lost flows show, in the change color with the dash of their evidence.
- A card that opens a map with a change in it or below it (the roll-up) has a second outline on its back card and the note "changed inside".
- When the roll-up of a map is not known, the map has `cr = {e: reason}`, and no card of it is "changed inside".
- A page without a revision comparison shows the text and the command of the linked page (`page_changes.empty`) in the Changes view, with a Copy button of 44 px or more.
- In the Changes view, the list of the tree gives the change words of each card, and the live region gives the change words of each map.

**The search (step 4).** `page_canvas_find.py` gives the Find dialog. It uses the dialog of the linked page (`page_palette.html` and `page_palette.CSS`) with no change. The match code, the list code and the ranking of step 8 are public constants of `page_palette.py` (`MATCH`, `LIST`, and `_RANK` with the text of the branch `claude/nested-step-8`). The script of the linked page has the same bytes as before.
- Ctrl K, Cmd K, / and the Find button of the header open the dialog. The dialog stops each key, so the camera keys do not operate while it is open.
- The results come from the canvas data when the dialog opens. Thus the data does not grow. The groups are: Views and Layers, the Components and Flows of the current map, Sequences and Steps, Actions (Fit the current map, Go to the top map), and Other maps with the hint "in" and the map name.
- Enter on a card of a different map writes the hash of the card, moves the camera to the card, and selects it when the flight ends. The live region gives the selected card and its map. A card that opens a map moves the camera into that map, and a flow moves the camera to its two cards.
- A result of the Views, Layers or Sequences group sets the view on the seam.

**Links.**
- The URL hash holds the camera target, for example `#Gateway/Routes`. A link opens the canvas at that map.
- The pages of each nested map (`Gateway/index.html`) become small pages that go to the top page with that hash. Thus current links still work.

## Access

**Keyboard.**
- Tab moves through the cards of the current map in reading order.
- Enter goes into a card that opens a map.
- Enter on a card that opens no map selects it. This is the same selection as a tap on a touch screen (`select` in `page_canvas_touch.py`). The focus ring is 7 px outside the card, so it does not cover the line of the selection.
- Esc goes out one level. When the canvas has the keyboard focus, the focus then goes to the card that opens the map that the camera comes from. The live region gives the new map and that card in one text.
- The focused card keeps the keyboard focus only while it is in the current map or it is open. Thus the card loses the keyboard focus when its map closes, for example after a zoom out, and when a zoom goes into the map of a different card. Tab, the ring and the live region use this one rule.
- Tab during the flight that Enter starts does not stop the flight. When the open map changes, the live region gives the card only in the text of the new map.
- The arrow keys pan, and + and - zoom.
- Focus is visible on the canvas.

**Screen readers.** A hidden list gives the tree: maps, cards, flows and the facts of each card. Each item is a link that moves the camera. The canvas has a label that gives the current path. The script writes the list after the first frame is on the screen, so the list does not make C3 longer. The canvas, its help text, the list and the live region are in one `main` landmark.

**Phone.**
- A pinch zooms, and a drag pans.
- A tap selects a card. A second tap on a card that opens a map goes into it.
- The current phone grid stays for the top map, until the canvas passes the phone measurements below.

The touch part of the renderer (`page_canvas_touch.py`) does these steps:
- A tap with a finger or a pen selects the card under it. The page draws a line around the selected card. When there is space above or below the card, it also draws a plate with the name and the facts of the card. A tap on that plate is a second tap on the card.
- A second tap on the selected card goes into it when it opens a map. A second tap on a card that opens no map keeps the selection.
- A tap on empty space removes the selection. A tap on an open card is a tap on empty space, because its map is on the screen.
- The selection fades in and out. Its alpha changes by 1 in 160 ms or more, and by 0.2 or less in one frame. With reduced motion, it changes at one time. A frame draws only the selected card and the cards that fade out. Thus the work of a frame does not grow with the count of cards.
- A double-click with a mouse goes into a card, as before. Two fast taps are not a double-click: the first tap selects the card, and the second tap goes into it.
- A gesture with two fingers is not a tap. After a pinch, the finger that stays down moves the map.

On a touch screen (`pointer: coarse`), each target on the canvas is 44 x 44 px or more:
- A part of the path is 44 px high and 44 px wide or more. The top row of the portals is 8 px lower, below the larger path. The bottom band of the fit is also 8 px larger. Thus the fit puts the middle of a map at the same height as on a screen with no touch.
- A portal has the drawing of 34 px height as before. Its target is 44 px high. In the top row and in the bottom row, the added 10 px are between the drawing and the screen edge. At the left and the right, the target has 5 px above and 5 px below the drawing. The gap between two portals is 10 px. Thus two targets do not overlap. In a trial with a drawing of 44 px height, each of the 182 portals at the fits of the M11 tree on the phone screen covered a card of the map above, because no open place was near.
- The plate of the facts of a selected card is 44 px high.
- The help line is not a target.

**The decision for the phone grid.** C5 passes (see "What is measured"). Thus the canvas meets the phone measurements of this design, and the top map can use the canvas on a phone. The phone grid goes in step 5, when the canvas becomes the default. These items are not measured yet: the frame time on a real phone (the `?hud` readout), and a test with a person (the last open question).

## Steps

Each step is a pull request with the required checks of AGENTS.md, `/code-review` and `/simplify`.

1. **Data.** `canvas_data.py`, tests, and the measurement C1: the bytes of the canvas data for the M11 tree. Acceptance: at most 2 MB raw for 50 maps.
2. **Renderer behind a setting.** `[render] canvas = true` writes the canvas page in place of the linked pages. It covers level of detail, opening, the camera, rings, portals, the path, and the URL hash. Measurements:
   - C2: frame time with 4 times CPU throttling in Chromium. Acceptance: p95 at most 35 ms. The maintainer set this limit to two 60 Hz ticks (33.3 ms) plus 5 percent, because the timer of the ticks has a small error.
   - C3: load to an interactive map for 50 maps. Acceptance: at most 1.5 s.
3. **Access and phone.** Keyboard, the hidden tree list, and touch. Measurements:
   - C4: axe-core. Acceptance: 0 serious or critical issues.
   - C5: phone emulation at 390 x 844. Acceptance: no horizontal scroll, and targets of 44 px or more.
4. **Views.** Search across the canvas, the Changes roll-up on cards, and the layers. Done on the branch `claude/canvas-views`: the header, the layers and the seam of the views, the Sequences view, the Changes view and the search. The parts were made in parallel and merged on the seam of the header part. The Changes part first had a stand-in seam. At the merge, its marks became values of the seam (`ring`, `tag`, `back` and `note`), and its words became `facts` and `say`.
5. **Default.** The canvas becomes the default. The linked pages become redirect pages, and the Map tree panel goes. Branches 6 to 8 of the nested-parts design close. Their tests for ports, badges, contrast and the search index move to the canvas.

## Open questions

- Text is drawn in SVG. Very long `does` texts need a line limit and an ellipsis. Is a limit of 4 lines correct?
- Is a map with more than 400 cards possible? It can be too large for one page. Measurement C1 decides if the data must load in parts.
- On a phone, is the canvas as good as the current grid for the top map? C5 passes (see "The decision for the phone grid"). A test with a person is necessary.
