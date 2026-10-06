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
button{background:transparent;border:1px solid var(--line-2);border-radius:4px;
min-height:36px;padding:.4rem .7rem}
button:hover,summary:hover{background:var(--raised);color:var(--ink)}
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
.bar{display:flex;align-items:center;gap:1.5rem;padding:.6rem 1.25rem;
border-bottom:1px solid var(--line);background:var(--surface)}
.brand{display:flex;align-items:center;gap:.6rem;font-size:18px;font-weight:600;
letter-spacing:-.03em;text-decoration:none;color:var(--ink)}
.brand svg{width:26px;height:26px;color:var(--accent)}
.project{min-width:0;flex:1}.project h1{font-size:15px;margin:0;font-weight:600}
.meta{font-size:11px;margin:.15rem 0 0;color:var(--ink-3)}
.header-links{display:flex;gap:1rem;font-size:12px}.header-links a{color:var(--ink-2)}
.snapshot{font-size:12px;color:var(--ink-3)}.snapshot p{margin:0}
.scheme{font-size:11px;color:var(--ink-2);display:flex;align-items:center;gap:.5rem}
select{max-width:100%;min-height:36px;padding:.3rem .5rem;border:1px solid var(--line-2);
border-radius:4px;background:var(--surface)}
.main{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:12px;
margin:0 1.25rem;align-items:start}
.map{min-width:0}.map-key{font-size:12px}.map-key p{max-width:72ch;font-size:13px}
.map-key>summary{min-height:30px;padding:.3rem 0}
.legend{display:flex;flex-wrap:wrap;gap:.8rem;font-size:12px;margin:.6rem 0;color:var(--ink-2)}
.lg{display:inline-flex;align-items:center;gap:.4rem}
.lg--solidline{width:22px;border-top:2px solid var(--ink-2)}
.lg--dashline{width:22px;border-top:2px dashed var(--ink-2)}
.controls{display:flex;align-items:center;flex-wrap:wrap;gap:.5rem .8rem}
.seg{display:flex;gap:2px;flex-wrap:wrap}.seg__b{display:flex;align-items:center;gap:.4rem;
font-size:12px;border-color:transparent;padding:.4rem .55rem;color:var(--ink-2)}
.seg__b i{width:12px;height:3px;background:var(--c,var(--ink-3));border-radius:1px}
.seg__b[aria-pressed="true"]{background:var(--surface);border-color:var(--line-2);color:var(--ink)}
.mobile-layer{display:none}.zoom{display:flex;align-items:center;gap:2px;font-size:11px}
.zoom button{padding:.3rem .5rem;min-width:36px}
.zoom button[aria-pressed="true"],.view-switch button[aria-pressed="true"]{
background:var(--raised);border-color:var(--accent);color:var(--ink)}
#zpct{font-family:var(--fm);min-width:3.5em;text-align:center;color:var(--ink-2)}
.view-switch{display:flex;gap:3px;margin-left:auto;font-size:12px}
.trace-controls{display:flex;align-items:center;flex-wrap:wrap;gap:.4rem;padding:.3rem 0}
.trace-controls select{min-width:0;flex:1;font-size:12px;max-width:42rem}
.trace-controls button{font-size:12px}.motion-control{display:flex;gap:.4rem;
align-items:center;font-size:12px;min-height:36px;white-space:nowrap}
#jcount{font-size:12px;font-family:var(--fm)}
.lstrip{font-size:13px;padding:.2rem 0 .3rem}.lstrip__l,.lstrip__s{display:none}
.lstrip__q{font-weight:500}.lstrip__row{display:flex;gap:.4rem;flex-wrap:wrap}
.lstrip__row button{font-size:12px}.lstrip__row i{font-style:normal;margin:0 .3rem}
.lstrip-members{display:none}.lstrip .on{border-color:var(--accent)}
.mapwrap{position:relative;background:var(--surface);border:1px solid var(--line-2);
border-radius:5px;overflow:hidden;
background-image:radial-gradient(var(--line) .7px,transparent .7px);background-size:18px 18px}
.stage{min-width:0;width:100%}#stage{height:calc(100vh - 220px);min-height:460px;max-height:1100px}
.stage svg,.stage #schematic,.stage #changemap{display:block;width:100%;height:100%}
.hint{font-size:12px;line-height:1.6;color:var(--ink-3);max-width:75ch}
.map-actions{display:flex;flex-wrap:wrap;gap:.5rem;margin:.8rem 0 1rem;font-size:12px}
.inspector{min-width:0;position:sticky;top:12px;margin-top:12px;max-height:calc(100vh - 24px);
overflow:auto;background:var(--surface);border:1px solid var(--line-2);border-radius:5px;
padding:1.1rem;scrollbar-width:thin;scrollbar-color:var(--line-2) var(--surface)}
.inspector h2{font-size:19px;font-weight:600;margin:.15rem 0 .7rem}
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
.strip{border-top:1px solid var(--line);padding-top:.5rem;margin-top:1rem;font-size:13px}
.strip summary{font-weight:600}.strip__n{font-family:var(--fm);margin-left:.3rem}
.strip__say{font-weight:400}.strip__meas,.strip__foot{font-size:12px!important}
.strip__meas.none,.draft{color:var(--warn)}
.reference{margin:1rem 1.25rem 2rem;max-width:110rem;display:grid;
grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:1.5rem 2rem}
.reference>section,.reference>details{min-width:0;
border-top:1px solid var(--line);
padding-top:.7rem}
.reference h2{font-size:17px;margin:.3rem 0 .6rem}.reference h3{font-size:13px}
.search input{width:100%;min-height:40px;border:1px solid var(--line-2);background:var(--surface);
border-radius:4px;padding:.5rem .7rem;caret-color:var(--accent)}
#search-help,.search-count{font-size:12px}
.ixgrid{display:grid;
grid-template-columns:repeat(2,minmax(0,1fr));
gap:1rem}
.region{font-size:12px;color:var(--ink-2);margin:1rem 0 .3rem}
.ix{display:grid;grid-template-columns:1fr auto;gap:.3rem;width:100%;text-align:left;
min-height:44px;padding:.7rem .5rem;margin:.3rem 0}
.ix__plain{grid-column:1/-1;font-size:13px;overflow-wrap:anywhere}.ix code{font-size:12px}
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
.foot{padding:1rem 1.25rem;border-top:1px solid var(--line);font-size:12px;color:var(--ink-2)}
@media(max-width:1050px){.main{grid-template-columns:minmax(0,1fr)}
.inspector{position:static;max-height:none;margin-top:0}.snapshot{display:none}
#stage{height:70vh;min-height:400px}.header-links{gap:.6rem}
.comparison-panes{grid-template-columns:minmax(0,1fr)}}
@media(max-width:640px){.bar{padding:.7rem .8rem;flex-wrap:wrap;gap:.5rem .8rem}
.brand{font-size:16px}.brand svg{width:22px;height:22px}.project h1{font-size:14px}
.meta{display:none}.header-links{order:3;flex:1;gap:.8rem}.scheme{font-size:12px}
.main{margin:0 .8rem;gap:12px}.seg{display:none}.mobile-layer{display:flex;gap:.5rem;
align-items:center;font-size:12px;flex:1}.controls{gap:.5rem}.view-switch{margin-left:0}
.trace-controls select{flex-basis:100%;width:100%}.trace-controls{gap:.3rem}
.zoom{flex-wrap:wrap}.reference{margin:1rem .8rem;grid-template-columns:minmax(0,1fr)}
#stage{height:auto;min-height:0}
button,select,input[type="search"],summary,.motion-control{min-height:44px}
button,.header-links a{min-width:44px}.header-links a{display:inline-flex;align-items:center;
min-height:44px}.ixgrid{grid-template-columns:minmax(0,1fr)}
.zoom button{min-width:44px}.map-key>summary{min-height:44px}
.submap{inset:.3rem}.submap__bar{padding:.5rem}.inspector{padding:1rem}
.foot{padding:1rem .8rem}.hint{font-size:12px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
html[data-reduce-motion="true"] *{transition:none!important;animation:none!important}
"""
