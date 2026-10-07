"""Styles for the map, inspector and source records."""

CSS = r"""
{ROOT}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{scroll-padding-top:1rem}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--fs);
font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
::selection{background:var(--accent);color:var(--bg)}
button,input,select{font:inherit;color:inherit;accent-color:var(--accent)}
button,summary{cursor:pointer}
button{background:var(--surface);border:1px solid var(--line);border-radius:6px;
min-height:36px;padding:.4rem .7rem;
transition:background-color .16s ease-out,border-color .16s ease-out,color .16s ease-out}
button:hover,summary:hover{background:var(--raised);color:var(--ink)}
button:hover{border-color:var(--line-2)}
button:disabled{color:var(--ink-3);cursor:default;border-color:var(--line)}
:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
a{color:var(--accent);text-underline-offset:3px}
code{font-family:var(--fm);font-size:.9em;overflow-wrap:anywhere}
p{margin:.6rem 0;color:var(--ink-2);overflow-wrap:anywhere}
h1,h2,h3,h4{line-height:1.3;overflow-wrap:anywhere}
summary{min-height:36px;padding:.45rem 0;color:var(--ink-2)}
.sr-only{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0,0,0,0)}
.skip{position:fixed;left:1rem;top:-5rem;z-index:30;background:var(--surface);padding:1rem}
.skip:focus{top:1rem}
.bar{display:flex;align-items:center;gap:1.2rem;padding:.8rem 1.2rem;
border-bottom:1px solid var(--line);background:var(--bg);min-height:76px}
.brand{display:flex;align-items:center;gap:0;font-size:0;font-weight:500;
letter-spacing:-.03em;text-decoration:none;color:var(--ink)}
.brand svg{width:18px;height:18px;color:var(--accent)}
.project{min-width:0;flex:1}.project-name{font-size:16px;color:var(--ink);margin:0;font-weight:500}
.meta{font:11px var(--fm);margin:.2rem 0 0;color:var(--ink-3)}
.header-links{display:flex;gap:1rem;font-size:12px}
.header-links a{color:var(--ink-2);text-decoration:none}
.header-links a:hover{color:var(--ink);text-decoration:underline}
.snapshot{display:none}
.theme-menu,.layer-menu{position:relative;font-size:12px}
.theme-menu>summary,.layer-menu>summary{list-style:none;border:1px solid var(--line);
border-radius:6px;padding:.45rem .8rem;min-height:36px}
.theme-menu>div,.layer-menu>.seg{position:absolute;top:calc(100% + 6px);z-index:15;
background:var(--surface);padding:6px;border:1px solid var(--line-2);border-radius:8px;
min-width:170px;box-shadow:0 8px 28px color-mix(in srgb,var(--bg) 60%,transparent)}
.theme-menu>div{right:0;display:grid;gap:3px}
[data-scheme]{display:flex;align-items:center;gap:10px;border:0;text-align:left;background:none}
[data-scheme] i{width:12px;height:12px;border:1px solid var(--line-2);border-radius:50%}
[data-scheme][aria-pressed="true"]{background:var(--raised)}
select{max-width:100%;min-height:36px;padding:.3rem .5rem;border:1px solid var(--line);
border-radius:6px;background:var(--surface)}
select:hover{border-color:var(--line-2)}
.main{display:grid;grid-template-columns:260px minmax(0,1fr) 300px;gap:0;align-items:start}
.main:has(.drawer[hidden]):has(#review-detail[hidden]){grid-template-columns:260px minmax(0,1fr)}
.sidebar{height:calc(100svh - 76px);position:sticky;top:0;border-right:1px solid var(--line);
display:flex;flex-direction:column;min-width:0;background:var(--surface)}
.browser-tabs{display:flex;padding:.75rem .65rem .5rem;gap:3px;border-bottom:1px solid var(--line)}
.browser-tabs button{flex:1;font-size:12px;border:0;background:none;padding:.4rem}
.browser-tabs [aria-pressed="true"]{background:var(--raised);color:var(--ink)}
.browser-tabs span{font:10px var(--fm);color:var(--ink-3);margin-left:3px}
.browser-content{overflow:auto;padding:.8rem .75rem 1rem;min-height:0}
.browser-close{display:none}
.map{min-width:0;height:calc(100svh - 76px);display:flex;flex-direction:column}
.map>*{flex-shrink:0}.map:has(.atlas:not([hidden])){height:auto}
.map-key{font-size:12px}.map-key p{max-width:72ch;font-size:13px}
.map-key{margin:0 0 .7rem}.map-key>summary{min-height:36px;padding:.5rem 0;text-align:center}
.legend{display:flex;flex-wrap:wrap;gap:.8rem;font-size:12px;margin:.6rem 0;color:var(--ink-2)}
.lg{display:inline-flex;align-items:center;gap:.4rem}
.lg--solidline{width:22px;border-top:2px solid var(--ink-2)}
.lg--dashline{width:22px;border-top:2px dashed var(--ink-2)}
.controls{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;
gap:.5rem;padding:.7rem 1rem;border-bottom:1px solid var(--line)}
.seg{display:flex;flex-direction:column;gap:4px;padding:0;background:none;
border:0;border-radius:8px}
.seg__b{display:flex;align-items:center;gap:.4rem;background:transparent;text-align:left;
font-size:12px;border-color:transparent;padding:.4rem .55rem;color:var(--ink-2)}
.seg__b i{width:4px;height:4px;background:var(--c,var(--ink-3));border-radius:50%}
.seg__b[aria-pressed="true"]{background:var(--raised);border-color:transparent;color:var(--ink)}
.mobile-layer{display:none}.zoom{display:flex;align-items:center;gap:2px;font-size:11px}
body[data-view="reading"] .zoom{display:none}
.zoom button{padding:.3rem .5rem;min-width:36px;background:transparent}
.zoom button[aria-pressed="true"],.view-switch button[aria-pressed="true"]{
background:var(--surface);border-color:var(--line-2);color:var(--ink)}
#zpct{font-family:var(--fm);min-width:3.5em;text-align:center;color:var(--ink-2)}
.view-switch{display:flex;gap:3px;font-size:12px;
padding:0;border:0;border-radius:8px;background:none}
.view-switch button{background:transparent;border-color:transparent}
.trace-controls{display:flex;align-items:center;flex-wrap:wrap;gap:.4rem;padding:.6rem 1rem;
border-bottom:1px solid var(--line)}
body:not([data-sequence="true"]) .trace-controls{display:none}
.sequence-toggle{font-size:12px;background:none;border-color:transparent;color:var(--ink-2)}
.trace-controls select{min-width:0;flex:1;font-size:12px;max-width:42rem}
.trace-controls button{font-size:12px}.motion-control{display:flex;gap:.4rem;
align-items:center;font-size:12px;min-height:36px;white-space:nowrap}
#jcount{font-size:12px;font-family:var(--fm)}
.lstrip{font-size:12px;text-align:left;padding:.7rem 1rem;color:var(--ink-2)}
.lstrip__l,.lstrip__s{display:none}
.lstrip__q{font-weight:500}.lstrip__row{display:flex;gap:.4rem;overflow:auto;white-space:nowrap}
.lstrip__row button{font-size:12px}.lstrip__row i{font-style:normal;margin:0 .3rem}
.lstrip-members{display:none}.lstrip .on{border-color:var(--accent)}
.mapwrap{position:relative;background:var(--bg);border:0;overflow:hidden}
.map-roles{position:absolute;top:.8rem;left:1rem;right:1rem;z-index:2;
display:flex;flex-wrap:wrap;gap:.35rem .9rem;font-size:12px;pointer-events:none}
.map-roles span{background:var(--bg);padding:.3rem .5rem;border:1px solid var(--line);
border-radius:4px;color:var(--ink-2)}
.map-roles .acting{border-top:2px solid var(--accent)}
.map-roles .measurement{border-top:2px solid var(--steel)}
.map-context{border-top:1px solid var(--line);padding:.7rem 1rem;background:var(--surface)}
.map-context h3{font-size:13px;font-weight:500;margin:0 0 .25rem}
.map-context p{font-size:12px;max-width:85ch;margin:.3rem 0}
.map-context dl{display:flex;flex-wrap:wrap;gap:.5rem 1.5rem;margin:0;font-size:12px}
.map-context dl>div{display:flex;gap:.4rem;align-items:baseline}
.map-context dt{color:var(--ink-2)}.map-context dd{margin:0;font-family:var(--fm)}
.map-context .context-evidence{color:var(--ink-2);font-size:12px}
.spatial-map{flex:1;min-height:420px}.mapwrap{height:100%}
.stage{min-width:0;width:100%}#stage{height:100%;min-height:420px}
.stage svg,.stage #schematic,.stage #changemap{display:block;width:100%;height:100%}
.hint{font-size:11px;line-height:1.6;color:var(--ink-3);max-width:75ch;
margin:.6rem auto;text-align:center;padding:0 1rem}
.map-actions{display:flex;justify-content:center;flex-wrap:wrap;gap:.5rem;
margin:.8rem 0 1rem;font-size:12px}
.inspector{min-width:0;position:sticky;top:0;max-height:calc(100svh - 76px);
overflow:auto;background:var(--surface);border-left:1px solid var(--line);padding:1rem}
.inspector:has(.drawer[hidden]):has(#review-detail[hidden]){display:none}
.inspector h2{font-size:18px;font-weight:500;margin:.15rem 0 .7rem}
.inspector p{font-size:13px;line-height:1.6;max-width:72ch}
.text-action{display:block;text-align:left;font-size:12px;margin:.5rem 0}
.drawer__x{font-size:12px;margin:0 0 .8rem}
.systemap-panel.on{padding:0;margin:0;background:none;border:0;box-shadow:none}
.systemap-f__plain{font-size:14px!important;line-height:1.5!important}
.systemap-f__kind{display:block;margin-top:.3rem}.systemap-f__iface{overflow-wrap:anywhere}
.systemap-f__say,.systemap-f__evidence{font-size:13px!important;line-height:1.6!important}
.systemap-f__chips{margin-top:.8rem}
.source-section{border-top:1px solid var(--line);padding-top:1rem;margin-top:1rem}
.source-section h3{font-size:13px;margin:0 0 .5rem}
.connection{display:block;width:100%;text-align:left;padding:.7rem .5rem;margin:.4rem 0}
.connection__route{display:flex;align-items:baseline;flex-wrap:wrap;gap:.35rem;font-size:12px}
.connection__say{display:block;color:var(--ink-2);font-size:13px;line-height:1.6;margin:.3rem 0}
.connection__evidence{font-size:12px;color:var(--ink-2)}
.connection[data-evidence="declared"] .connection__evidence{color:var(--warn)}
.module-record{font-size:13px}.module-record p{font-size:12px}.file{font-family:var(--fm)}
.rule-row{display:flex;gap:.6rem;margin:.7rem 0;font-size:13px;line-height:1.6}
.rule-row b{font-family:var(--fm);color:var(--accent)}
.strip{border-top:1px solid var(--line);padding:.6rem 1rem;margin:0;font-size:13px}
.strip>summary{cursor:pointer}.strip__say{margin:.3rem 0 0;max-width:72ch}
.strip summary{font-weight:600}.strip__n{font-family:var(--fm);margin-left:.3rem}
.strip__say{font-weight:400}.strip__meas,.strip__foot{font-size:12px!important}
.strip__meas.none,.draft{color:var(--warn)}
.reference{margin:0;display:grid;gap:1rem}
body:not([data-mode="review"]) .reference{display:none}
.reference>section,.reference>details{min-width:0;
border-top:1px solid var(--line);
padding-top:.7rem}
.reference h2{font-size:17px;margin:.3rem 0 .6rem}.reference h3{font-size:13px}
.search input{width:100%;min-height:40px;border:1px solid var(--line);background:var(--surface);
border-radius:6px;padding:.5rem .7rem;caret-color:var(--accent)}
.search input:hover{border-color:var(--line-2)}
#search-help,.search-count{font-size:12px}
.ixgrid{display:grid;gap:.7rem}
.region{font-size:12px;color:var(--ink-2);margin:1rem 0 .3rem}
.ix{display:flex;flex-direction:column;gap:.25rem;width:100%;text-align:left;
min-height:44px;padding:.8rem .5rem;margin:0;border-color:transparent;
border-bottom-color:var(--line);border-radius:0;background:transparent}
.ix__plain{font-size:12px;color:var(--ink-2);overflow-wrap:anywhere}
.ix code{font-size:13px;order:-1}
.ix[aria-current="true"]{background:var(--raised);border-color:var(--accent)}
.chip{font-size:11px;color:var(--ink-2)}.chip--built{display:none}
.journey-choice,.review-choice{display:block;width:100%;text-align:left;margin:.4rem 0;
padding:.75rem;font-size:13px;overflow-wrap:anywhere}
.journey-choice small,.review-choice small{display:block;
color:var(--ink-2);
margin:.3rem 0;
font-size:12px}
.journey-choice[aria-pressed="true"],.review-choice[aria-pressed="true"]{border-color:var(--accent);
background:var(--raised)}
.review-count{font-size:13px}.review-count span{margin-left:1rem}
.review-filters{display:flex;gap:.4rem;margin:.7rem 0}.review-filters [aria-pressed="true"]{
background:var(--raised);border-color:var(--accent)}
.review-line{font-family:var(--fm);font-size:12px;overflow-wrap:anywhere;padding:.7rem 0}
.review-cards{display:flex;gap:.4rem;flex-wrap:wrap;font-size:12px}.review-reason{color:var(--ink)}
.rules{padding-left:1.5rem}
.rules li{margin:.8rem 0;
font-size:13px}
.rules li::marker{color:var(--accent)}
.governs{display:block;margin:.4rem 0}.gv{font-size:12px;margin:.2rem}
.command{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.3rem;padding:.8rem 0;
border-bottom:1px solid var(--line);font-size:13px}
.command b,.command p{grid-column:1/-1}.command p{margin:0 0 .4rem}
.command button{font-size:12px}.command code{align-self:center;overflow-wrap:anywhere}
.change-view{grid-column:1/-1}.change-view h2{font-size:18px}
.comparison-panes{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:12px}
.change-view .stage{height:480px;border:1px solid var(--line)}
#change-panel{padding:1rem;min-width:0;overflow-wrap:anywhere}
#change-panel.on{border:1px solid var(--line-2)}
.submap{position:fixed;inset:1rem;z-index:20;background:var(--bg);border:1px solid var(--line-2);
display:flex;
flex-direction:column;
box-shadow:0 8px 60px color-mix(in srgb,var(--bg) 80%,transparent)}
.submap__bar{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.75rem;
border-bottom:1px solid var(--line)}
.submap__crumb{font-size:13px;
overflow-wrap:anywhere;
min-width:0}
.submap__frame{flex:1;width:100%;border:0;background:var(--bg)}body.submap-open{overflow:hidden}
.foot{margin:auto;padding:1rem;border-top:1px solid var(--line);
font-size:11px;line-height:1.7;color:var(--ink-3)}
@media(max-width:1050px){.main{grid-template-columns:230px minmax(0,1fr)}
.main:has(.drawer[hidden]):has(#review-detail[hidden]){grid-template-columns:230px minmax(0,1fr)}
.inspector{position:static;max-height:none;margin-top:0;border-left:0;
border-top:1px solid var(--line);padding:1rem;grid-column:2}
.comparison-panes{grid-template-columns:minmax(0,1fr)}}
@media(max-width:640px){.bar{padding:.6rem .8rem;gap:.6rem;min-height:76px}
.brand{font-size:15px}.brand svg{width:18px;height:18px}.project-name{font-size:12px}
.brand{font-size:0;gap:0}.project-name{font-size:14px}.meta{font-size:10px}
.reference-toggle{font-size:11px;padding:.3rem .5rem}
.theme-menu>summary{font-size:11px;padding:.3rem .5rem}
.main,.main:has(.drawer[hidden]):has(#review-detail[hidden]){display:block}
.sidebar{height:auto;position:sticky;top:0;z-index:10;border:0;border-bottom:1px solid var(--line)}
.browser-tabs{padding:.4rem .6rem;border:0}.browser-content{display:none;max-height:50svh}
body[data-browse="true"] .browser-content{display:block;border-top:1px solid var(--line)}
.browser-close{display:block;margin:0 0 .6rem auto;font-size:12px}
.layer-menu{display:none}.mobile-layer{display:flex;gap:.5rem;
align-items:center;font-size:12px;flex:1}.controls{gap:.5rem;padding:.6rem .8rem}
.view-switch{margin-left:0}.view-switch button{font-size:12px;padding:.3rem .55rem}
.mobile-layer{flex:0 1 auto;font-size:0;gap:0}.mobile-layer select{font-size:12px}
.zoom [data-zoom="actual"]{display:none}
.trace-controls select,.trace-controls>label{display:none}.trace-controls{gap:.3rem}
body[data-sequence="true"] .lstrip__row{display:none}
body[data-sequence="true"] .lstrip{padding:.4rem .8rem}
.map{height:auto}.spatial-map{flex:none;min-height:0}
.spatial-map,.atlas{order:1}.strip{order:2}.map-context{order:3}
.map>.hint,.map>#linkstatus{order:4}
.zoom{order:3;width:100%;justify-content:flex-end}.reference{margin:0}
#stage{height:calc(100svh - 295px);min-height:300px}
body[data-sequence="true"] #stage{height:calc(100svh - 380px)}
button,select,input[type="search"],summary,.motion-control{min-height:44px}
button,.header-links a{min-width:44px}.header-links a{display:inline-flex;align-items:center;
min-height:44px}.ixgrid{grid-template-columns:minmax(0,1fr)}
.zoom button{min-width:44px}.map-key>summary{min-height:44px}
.submap{inset:.3rem}.submap__bar{padding:.5rem}.inspector{padding:1rem}
.foot{padding:1rem .8rem}.hint{font-size:12px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
html[data-reduce-motion="true"] *{transition:none!important;animation:none!important}
"""
