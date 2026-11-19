"""The tools of the atlas page: Find, the theme control, Reduce motion and the keyboard keys.

The header of the atlas page (`atlas_header`) puts these tools at its right end. They give
the parity of docs/design/atlas.md ("Requirements of the product page") with the canvas page
(`canvas_header` and `page_canvas_details`):

- Find. The button opens the Find dialog (`atlas_find`). Ctrl K, Cmd K and / also open it.
- The theme control. Three buttons: Device, Light and Dark. Device follows the scheme of
  the device, also when the device changes it. Light and Dark keep the scheme in this browser
  with the key of the other pages (`page.SCHEME_KEY`). Device removes that key. The scheme
  script of the head (`page.head_start`) reads the same key before the first frame. The
  renderer reads the colors again when `data-theme` changes (`atlas_input`).
- Reduce motion. The button of `atlas_details`, with the key of the other pages
  (`page.MOTION_KEY`).
- Keyboard keys. The ? key and the button open a modal sheet with the keys of the page
  (`KEYS`, the sheet of `page_motion.keys_sheet`). Esc and its Close button close it, and
  the keyboard focus goes back to the element that had it.

On a screen of 720 px or less, the views fill the header. Then the tools are in one menu:
the Tools button opens it, and Esc or a click out of it closes it. In the menu, each tool
shows its name. On a touch screen, each tool is 44 x 44 px or more.

The markup has no style attribute and no inline event handler. Each button has its name as
its text. On a wide screen, the text of a button with an icon is visually hidden.
"""

from __future__ import annotations

import json

from systemap import page, page_motion
from systemap.page_icons import icon

# The keys of the atlas page, for the keyboard sheet.
KEYS: tuple[tuple[str, str], ...] = (
    ("Ctrl K", "Find a card, a flow, a sequence or an action"),
    ("Tab", "Move the keyboard focus through the cards and the lines of the map"),
    (
        "Enter",
        "Select the focused card, or keep the focused line lit. In the other views, do the "
        "same as a click on the focused item",
    ),
    (
        "Space",
        "In the Sequences diagram and in the States, Focus and History views, do the same as a "
        "click on the focused item",
    ),
    ("Shift Enter", "Go into the map of the focused card"),
    (
        "Esc",
        "Close the details, or go out one level. In the States, Focus and History views, "
        "remove the light",
    ),
    (
        "← ↑ → ↓",
        "In the Map view, move the map. In the States, Focus and History views, move the "
        "keyboard focus to a different item",
    ),
    ("← →", "In the Sequences view, go to the previous step or the next step"),
    (
        "Home",
        "In the States view, go to the first item. In the Focus view, go to the middle card. "
        "In the History view, go to the name of the row",
    ),
    (
        "End",
        "In the States view, go to the last item. In the History view, go to the last cell of "
        "the row",
    ),
    ("+ -", "Zoom in or out"),
    ("F", "Fit the current map"),
    ("?", "Show the keyboard keys"),
)

# The icon of the Device theme: a screen.
_DEVICE = (
    '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    '<path d="M2.75 3.25h10.5v7.5H2.75zM6 13.25h4M8 10.75v2.5"/></svg>'
)
_TOOLS = (
    '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    '<path d="M2.75 4.5h10.5M2.75 8h10.5M2.75 11.5h10.5"/></svg>'
)

THEMES = (
    ("device", "Device", _DEVICE),
    ("light", "Light", icon("sun")),
    ("dark", "Dark", icon("moon")),
)


def _button(id_: str, name: str, glyph: str, extra: str = "") -> str:
    return (
        f'<button type="button" class="tool" id="{id_}" title="{page.esc(name)}"{extra}>'
        f'{glyph}<span class="tl">{page.esc(name)}</span></button>'
    )


def html() -> str:
    """Give the tools of the header: Find, the Tools button for a phone, and the menu."""
    themes = "".join(
        f'<button type="button" class="tool" data-theme-pick="{key}" aria-pressed="false" '
        f'title="{name} theme">{glyph}<span class="tl">{name}</span></button>'
        for key, name, glyph in THEMES
    )
    return (
        '<button type="button" class="find" id="atlas-find" aria-haspopup="dialog" '
        'aria-expanded="false" aria-keyshortcuts="Control+K Meta+K /" title="Find (Ctrl K)">'
        f'{icon("search")}<span>Find</span><kbd data-mod-key aria-hidden="true">Ctrl K</kbd>'
        "</button>"
        + _button(
            "atlas-tools-open",
            "Tools",
            _TOOLS,
            ' aria-expanded="false" aria-controls="atlas-tools"',
        )
        + '<div class="tools" id="atlas-tools" role="group" aria-label="Tools">'
        + _button("atlas-find-menu", "Find", icon("search"), ' aria-haspopup="dialog"')
        + '<div class="themes" role="group" aria-label="Theme">'
        + themes
        + "</div>"
        + _button("atlas-motion", "Reduce motion", icon("motion"), ' aria-pressed="false"')
        + _button(
            "atlas-keys",
            "Keyboard keys",
            icon("help"),
            ' aria-haspopup="dialog" aria-keyshortcuts="?"',
        )
        + "</div>"
    )


SHEET = page_motion.keys_sheet(KEYS)

# The sheet of the linked page and its tokens: `--raised` is the tint of the atlas page,
# and `--accent` is the color of the focus ring.
CSS = (
    page_motion.KEYS_CSS
    + """
.pal,.keys{--raised:var(--tint);--card-line:var(--line-2);--accent:var(--focus)}
.keys__close,.keys__box{font-family:var(--fs)}
.bar__end .tl{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.find{display:flex;align-items:center;gap:8px;height:30px;margin-right:6px;padding:0 6px 0 9px;border:1px solid var(--line);
border-radius:8px;background:var(--map);color:var(--ink-3);font-weight:500}
.find:hover{color:var(--ink);border-color:var(--line-2)}
.find kbd{font:500 10.5px/16px var(--fm);color:var(--ink-3);border:1px solid var(--line);border-radius:4px;padding:0 5px}
.tools{display:flex;align-items:center;gap:4px}
.themes{display:flex;gap:0;padding:1px;margin-right:4px;border:1px solid var(--line);border-radius:9px;background:var(--map)}
.themes .tool{width:28px;height:28px;border-radius:7px}
.themes .tool[aria-pressed="true"]{background:var(--surface);color:var(--ink);box-shadow:0 1px 2px var(--shade)}
#atlas-tools-open,#atlas-find-menu{display:none}
@media (max-width:720px){
.find{display:none}
#atlas-tools-open{display:grid}
.tools[data-open] #atlas-find-menu{display:flex}
.tools{display:none}
.tools[data-open]{position:fixed;top:52px;right:8px;z-index:6;display:flex;flex-direction:column;align-items:stretch;gap:4px;
width:min(260px,calc(100% - 16px));box-sizing:border-box;padding:8px;border:1px solid var(--line-2);border-radius:12px;
background:var(--surface);box-shadow:var(--shadow)}
.tools[data-open] .tl{position:static;width:auto;height:auto;overflow:visible;clip-path:none}
.tools[data-open] .tool{display:flex;align-items:center;gap:10px;width:auto;height:40px;padding:0 10px;color:var(--ink-2)}
.tools[data-open] .themes{margin:0 0 4px;padding:2px}
.tools[data-open] .themes .tool{flex:1 1 0;justify-content:center;gap:6px;height:36px;padding:0 4px}
}
@media (pointer:coarse){.tool,.find{min-width:44px;min-height:44px}
.tools[data-open] .tool,.tools[data-open] .themes .tool{height:44px}}
"""
)

TOOLS = r"""
// ---- the tools of the header (atlas_tools) ---------------------------------------------
var THEME_BTNS = Array.prototype.slice.call(document.querySelectorAll('[data-theme-pick]')), THEME_PICK = 'device';
var DEVICE_LIGHT = window.matchMedia ? matchMedia('(prefers-color-scheme: light)') : null;
var THEME_NAMES = {device: 'Device', light: 'Light', dark: 'Dark'};
// The scheme of the device, with the rule of the scheme script of the head.
function deviceScheme() { return DEVICE_LIGHT && DEVICE_LIGHT.matches ? 'light' : 'dark'; }
function themeShow() { THEME_BTNS.forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-theme-pick') === THEME_PICK)); }); }
// Set the theme `pick`: 'device', 'light' or 'dark'. With no storage, the page does not keep it.
function themeSet(pick, quiet) {
  if (!THEME_NAMES[pick]) return false;
  THEME_PICK = pick;
  try { if (pick === 'device') localStorage.removeItem(SCHEME_KEY); else localStorage.setItem(SCHEME_KEY, pick); } catch (e) { /* no storage */ }
  var s = pick === 'device' ? deviceScheme() : pick;
  if (document.documentElement.getAttribute('data-theme') !== s) document.documentElement.setAttribute('data-theme', s);
  themeShow();
  if (!quiet) say('Theme: ' + THEME_NAMES[pick] + '.');
  return true;
}
(function () {
  var s = null;
  try { s = localStorage.getItem(SCHEME_KEY); } catch (e) { /* no storage */ }
  THEME_PICK = s === 'light' || s === 'dark' ? s : 'device';
  themeShow();
})();
THEME_BTNS.forEach(function (b) { b.addEventListener('click', function () { themeSet(b.getAttribute('data-theme-pick')); }); });
if (DEVICE_LIGHT && DEVICE_LIGHT.addEventListener) DEVICE_LIGHT.addEventListener('change', function () { if (THEME_PICK === 'device') themeSet('device', true); });

// ---- the Tools menu of a phone ------------------------------------------------------------
var TOOLS_EL = document.getElementById('atlas-tools'), TOOLS_BTN = document.getElementById('atlas-tools-open');
function toolsShow(on) {
  if (!TOOLS_EL || !TOOLS_BTN) return;
  if (on) TOOLS_EL.setAttribute('data-open', ''); else TOOLS_EL.removeAttribute('data-open');
  TOOLS_BTN.setAttribute('aria-expanded', String(on));
}
function toolsOpen() { return !!TOOLS_EL && TOOLS_EL.hasAttribute('data-open'); }
if (TOOLS_BTN && TOOLS_EL) {
  TOOLS_BTN.addEventListener('click', function () {
    toolsShow(!toolsOpen());
    if (toolsOpen()) { var b = TOOLS_EL.querySelector('button'); if (b) b.focus(); }
  });
  TOOLS_EL.addEventListener('keydown', function (e) { if (e.key === 'Escape' && toolsOpen()) { e.preventDefault(); e.stopPropagation(); toolsShow(false); TOOLS_BTN.focus(); } });
  document.addEventListener('pointerdown', function (e) { if (toolsOpen() && !TOOLS_EL.contains(e.target) && !TOOLS_BTN.contains(e.target)) toolsShow(false); });
  window.addEventListener('resize', function () { if (toolsOpen() && W > WIDE) toolsShow(false); });
}

// ---- the keyboard sheet: ? opens it, Esc closes it -----------------------------------------
var KEYS_EL = document.getElementById('keys'), KEYS_CLOSE = KEYS_EL && KEYS_EL.querySelector('[data-keys-close]'), KEYS_FROM = null;
function typingIn(t) { return !!(t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName || ''))); }
function findShown() { var p = document.getElementById('palette'); return !!p && !p.hidden; }
function keysShown() { return !!KEYS_EL && !KEYS_EL.hidden; }
function keysOpen(from) {
  if (!KEYS_EL || keysShown() || findShown()) return;
  KEYS_FROM = from || document.activeElement;
  toolsShow(false);
  KEYS_EL.hidden = false;
  if (KEYS_CLOSE) KEYS_CLOSE.focus();
}
function keysClose() {
  if (!keysShown()) return;
  KEYS_EL.hidden = true;
  var back = KEYS_FROM;
  KEYS_FROM = null;
  if (back && back.focus && back.isConnected && back.getClientRects().length) back.focus({preventScroll: true});
  else if (TOOLS_BTN && TOOLS_BTN.offsetParent) TOOLS_BTN.focus(); else cv.focus({preventScroll: true});
}
if (KEYS_EL) {
  if (KEYS_CLOSE) KEYS_CLOSE.addEventListener('click', keysClose);
  KEYS_EL.addEventListener('click', function (e) { if (e.target === KEYS_EL) keysClose(); });
}
var FIND_MENU = document.getElementById('atlas-find-menu');
if (FIND_MENU) FIND_MENU.addEventListener('click', function () { toolsShow(false); if (TOOLS_BTN) TOOLS_BTN.focus(); if (FIND) FIND.show(); });
var KEYS_BTN = document.getElementById('atlas-keys');
if (KEYS_BTN) KEYS_BTN.addEventListener('click', function () { keysOpen(toolsOpen() ? TOOLS_BTN : KEYS_BTN); });
// The sheet is modal: the keys of the page do not operate under it.
window.addEventListener('keydown', function (e) {
  if (keysShown()) {
    if (e.key === 'Escape') { e.preventDefault(); keysClose(); }
    else if (e.key === 'Tab') { e.preventDefault(); if (KEYS_CLOSE) KEYS_CLOSE.focus(); }
    e.stopImmediatePropagation();
    return;
  }
  if (e.key !== '?' || e.ctrlKey || e.metaKey || e.altKey || typingIn(e.target) || findShown()) return;
  e.preventDefault(); e.stopImmediatePropagation(); keysOpen();
}, true);
// The state of the tools for the tests.
function toolsState() {
  return {theme: THEME_PICK, scheme: document.documentElement.getAttribute('data-theme'), menu: toolsOpen(), keys: keysShown(), find: findShown(),
    motion: document.documentElement.getAttribute('data-reduce-motion')};
}
"""

TOOLS = TOOLS.replace("SCHEME_KEY", json.dumps(page.SCHEME_KEY))
