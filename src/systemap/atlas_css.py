"""The styles of the atlas page: the color tokens, the header, the headline and the controls.

The atlas page (`atlas_page`) has one style element. The styles come from the design study
(docs/design/atlas/study-head.html), changed to the requirements of the product page in
docs/design/atlas.md:

- The page uses the embedded Inter font of the product (`page_font`) and a system mono
  font. It loads no font from a font host. The headings use Inter with a small negative
  letter spacing, in place of the Inter Tight font of the study.
- The light tokens are on `:root`. The dark tokens apply with `data-theme="dark"`, and
  with the dark scheme of the device when the page has no light `data-theme`.
- The canvas fills the window under the header. The parts that do not zoom (the header,
  the headline, the zoom control, the key and the note) are HTML over the canvas.
- On a screen of 720 px or less, the headline is smaller and has no counts, and the note
  and the key do not show.
- `--fs` and `--fm` give the two fonts to the renderer script (`atlas_scene`).
- `--change` is the color of the change marks (`atlas_marks`). `--focus` is the color of
  the focus rings, of the keyboard focus lines and of the lit cell of the History view: the
  brand color of the study in the dark scheme, and a darker tone of it in the light scheme,
  so that these marks have a contrast of 3 or more on the ground
  (tests/test_atlas_contrast.py). `--brand` is only for the mark of the brand and for the
  dot of a new module in the History view.
"""

from __future__ import annotations

LIGHT = (
    "--bg:#F1EFEC;--map:#F4F2EF;--surface:#FCFAF7;--card:#FFFEFC;--line:#E2DFDA;--line-2:#CFCBC5;"
    "--ink:#1D1B17;--ink-2:#524F4A;--ink-3:#716C65;--wire:#A9A49C;--tint:rgba(29,27,23,.028);"
    "--data:#0B6B58;--control:#B4483F;--judge:#7A5C00;--context:#4F5BD5;--tool:#96600A;"
    "--brand:#F2B33D;--halo:rgba(242,179,61,.38);--shade:rgba(29,27,23,.06);--change:#9C2F86;--focus:#8A5A00;"
    "--shadow:0 1px 0 rgba(29,27,23,.04),0 12px 32px -18px rgba(29,27,23,.28);color-scheme:light"
)
DARK = (
    "--bg:#0F0E0C;--map:#12110F;--surface:#161411;--card:#1C1A17;--line:#27241F;--line-2:#3A362F;"
    "--ink:#F1EDE4;--ink-2:#BEB8AC;--ink-3:#8F887B;--wire:#5E5A52;--tint:rgba(241,237,228,.035);"
    "--data:#3CC4A6;--control:#E0776B;--judge:#D6B24A;--context:#9AA4FF;--tool:#E0A44A;"
    "--brand:#FCB442;--halo:rgba(252,180,66,.32);--shade:rgba(0,0,0,.35);--change:#E27BD0;--focus:#FCB442;"
    "--shadow:0 1px 0 rgba(0,0,0,.4),0 14px 36px -18px rgba(0,0,0,.8);color-scheme:dark"
)

CSS = (
    ":root{"
    + LIGHT
    + ';--fs:"systemap Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;'
    "--fm:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
    '@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){' + DARK + "}}"
    ':root[data-theme="dark"]{'
    + DARK
    + "}"
    + """
html,body{margin:0;height:100%;overflow:hidden}
body{background:var(--map);color:var(--ink);font:13px/1.45 var(--fs);-webkit-font-smoothing:antialiased}
button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px;border-radius:6px}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.bar{position:fixed;left:0;right:0;top:0;z-index:2;display:flex;align-items:stretch;gap:20px;height:48px;
box-sizing:border-box;background:var(--surface);border-bottom:1px solid var(--line);
padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));min-width:0}
.brand{display:flex;align-items:center;gap:9px;margin:0;font:600 14px/1 var(--fs);letter-spacing:-.01em;flex:none}
.brand svg{display:block}
.brand .mark{fill:var(--brand)}
.tabs{display:flex;align-items:stretch;gap:2px;overflow-x:auto;scrollbar-width:none;min-width:0}
.tabs::-webkit-scrollbar{display:none}
.tab{position:relative;padding:0 11px;color:var(--ink-3);font-weight:500;white-space:nowrap;transition:color .16s}
.tab:hover{color:var(--ink)}
.tab[aria-selected="true"]{color:var(--ink)}
.tab[aria-selected="true"]::after{content:"";position:absolute;left:11px;right:11px;bottom:-1px;height:2px;background:var(--ink);border-radius:2px 2px 0 0}
.tab i{font:500 10.5px/1 var(--fm);font-style:normal;color:var(--ink-3);margin-left:6px;font-variant-numeric:tabular-nums}
.views{display:flex;align-self:center;padding:2px;border:1px solid var(--line);border-radius:9px;background:var(--map);flex:none}
.views button{height:26px;padding:0 11px;border-radius:7px;color:var(--ink-3);font-weight:500;transition:color .16s,background .16s,box-shadow .16s}
.views button:hover{color:var(--ink)}
.views button[aria-pressed="true"]{background:var(--surface);color:var(--ink);box-shadow:0 1px 2px rgba(29,27,23,.12)}
#canvas{position:fixed;inset:0;width:100%;height:100%;display:block;touch-action:none;outline:none;cursor:grab}
#canvas.over{cursor:pointer}
#canvas.drag{cursor:grabbing}
#canvas:focus-visible{box-shadow:inset 0 0 0 2px var(--focus)}
#still{position:fixed;inset:0;width:100%;height:100%;display:block;pointer-events:none}
#still[hidden]{display:none}
.ask{position:fixed;top:70px;left:max(24px,env(safe-area-inset-left,0px));right:24px;pointer-events:none;max-width:560px;z-index:1}
.ask__k{font:500 10.5px/1 var(--fm);letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);display:flex;gap:7px;align-items:center;flex-wrap:wrap}
.ask__k button{pointer-events:auto;font:inherit;letter-spacing:inherit;text-transform:inherit;color:var(--ink-3);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line-2)}
.ask__k button:hover{color:var(--ink)}
.ask__k b{font-weight:500;color:var(--ink)}
.ask__q{margin:9px 0 0;font:600 23px/1.18 var(--fs);letter-spacing:-.022em;text-wrap:balance}
.ask__n{margin-top:8px;color:var(--ink-3);font-size:12px;font-variant-numeric:tabular-nums}
.ask.beside{max-width:290px;top:78px}
.ask::before{content:"";position:absolute;inset:-22px -40px -26px -40px;z-index:-1;background:radial-gradient(closest-side,var(--map) 62%,transparent);opacity:.92}
.ask>*{transition:opacity .18s,transform .18s}
.ask.swap>*{opacity:0;transform:translateY(3px)}
.zoom{position:fixed;left:max(20px,env(safe-area-inset-left,0px));bottom:max(20px,env(safe-area-inset-bottom,0px));display:flex;align-items:center;gap:2px;
color:var(--ink-3);font:500 11px/1 var(--fm);font-variant-numeric:tabular-nums;z-index:1}
.zoom button{width:28px;height:28px;border-radius:7px;display:grid;place-items:center;color:var(--ink-2);font:400 17px/1 var(--fs)}
.zoom button:hover{background:var(--tint);color:var(--ink)}
.zoom span{min-width:38px;text-align:center}
.key{position:fixed;right:max(20px,env(safe-area-inset-right,0px));bottom:max(24px,env(safe-area-inset-bottom,0px));display:flex;gap:14px;color:var(--ink-3);font-size:11.5px;z-index:1}
.key i{display:inline-block;width:14px;height:2px;border-radius:2px;margin-right:6px;vertical-align:3px;background:var(--k)}
.note{position:fixed;left:max(24px,env(safe-area-inset-left,0px));bottom:64px;margin:0;font-size:11.5px;color:var(--ink-3);max-width:230px;line-height:1.5;z-index:1}
@media (max-width:720px){
.bar{gap:12px}.brand span,.note,.key{display:none}
.ask{top:62px}.ask__q{font-size:19px}.ask__n{display:none}
.views button{padding:0 7px}
.tabs{position:fixed;top:48px;left:0;right:0;height:38px;box-sizing:border-box;background:var(--surface);border-bottom:1px solid var(--line);
padding:0 max(5px,env(safe-area-inset-left,0px))}
body[data-mode="map"] .ask{top:100px}
}
@media (max-width:400px){.views button{padding:0 6px;font-size:12.5px}}
@media (pointer:coarse){.zoom button{width:44px;height:44px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
:root[data-reduce-motion="true"] *{transition:none!important;animation:none!important}
"""
)
