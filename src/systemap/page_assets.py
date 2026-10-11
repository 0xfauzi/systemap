"""Styles for the page shell: header, map frame, reading panel and records."""

CSS = r"""
{ROOT}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{scroll-padding-top:1rem}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--fs);
font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased;min-height:100svh}
::selection{background:var(--hl);color:var(--ink)}
button,input,select{font:inherit;color:inherit;accent-color:var(--accent)}
button,summary{cursor:pointer}
button{background:transparent;border:1px solid var(--line-2);border-radius:6px;
min-height:32px;padding:0 12px;color:var(--ink-2);
transition:background-color .16s ease-out,border-color .16s ease-out,color .16s ease-out}
button:hover{background:var(--raised);color:var(--ink)}
button:disabled{color:var(--ink-3);cursor:default;opacity:.6}
button:disabled:hover{background:transparent}
:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
a{color:var(--ink);text-underline-offset:3px}
code,kbd{font-family:var(--fm);font-size:.92em;overflow-wrap:anywhere}
p{margin:.6rem 0;color:var(--ink-2);overflow-wrap:anywhere}
h1,h2,h3,h4{line-height:1.3;overflow-wrap:anywhere}
summary{min-height:32px;padding:.4rem 0;color:var(--ink-2)}
.sr-only{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);
white-space:nowrap}
.skip{position:fixed;left:1rem;top:-5rem;z-index:30;background:var(--surface);padding:1rem}
.skip:focus{top:1rem}

/* ---- header: one row ---------------------------------------------------- */
.bar{height:52px;display:flex;align-items:center;gap:18px;padding:0 20px;position:relative;
z-index:12;
border-bottom:1px solid var(--line);background:var(--surface)}
.brand{display:flex;align-items:center;color:var(--ink);text-decoration:none;flex:none;
margin-right:-8px}
.mark{width:22px;height:22px;display:block}
.mark__path{fill:none;stroke:var(--ink);stroke-width:44;stroke-linecap:round;stroke-linejoin:round}
.mark__dot{fill:var(--brand)}
.project{display:flex;align-items:baseline;gap:18px;min-width:0;flex:none}
.project-name{margin:0;font:600 15px/1 var(--fs);letter-spacing:-.02em;color:var(--ink);
white-space:nowrap}
.crumb{font:13px var(--fs);color:var(--ink-2);text-decoration:none}.crumb:hover{color:var(--ink)}
.crumb__sep{color:var(--ink-3);margin:0 -4px}
.snap{font:12px/1 var(--fm);color:var(--ink-3);white-space:nowrap}.snap code{font-size:12px}
.views{display:flex;gap:2px;margin-left:10px}
.views button{height:32px;padding:0 14px;border-color:transparent;font-size:13px;color:var(--ink-2);
display:flex;align-items:center;gap:8px}
.views button[aria-pressed="true"]{border-color:var(--line-2);background:var(--raised);
color:var(--ink);
font-weight:500}
.views__dot{width:6px;height:6px;border-radius:50%;background:var(--change);display:inline-block}
.bar__space{flex:1}
.find{display:flex;align-items:center;gap:8px;height:32px;width:200px;padding:0 6px 0 10px;
border:1px solid var(--line-2);border-radius:6px;background:var(--map)}
.find:focus-within{border-color:var(--ink-3)}
.find label{font-size:12px;color:var(--ink-3)}
.find input{flex:1;min-width:0;height:28px;border:0;background:transparent;color:var(--ink);
font-size:13px;outline:none;padding:0}
.find input::placeholder{color:var(--ink-3);opacity:0;transition:opacity .16s}
.find:focus-within input::placeholder{opacity:1}
.find input::-webkit-search-cancel-button{display:none}
.find kbd{font-size:11px;color:var(--ink-3);border:1px solid var(--line-2);border-radius:4px;
padding:0 5px;line-height:16px}
.find:focus-within kbd{visibility:hidden}
.find__results{position:fixed;z-index:20;top:46px;right:96px;width:360px;
max-height:min(70svh,560px);
overflow:auto;padding:12px;border:1px solid var(--line-2);border-radius:10px;
background:var(--surface);
box-shadow:0 14px 40px color-mix(in srgb,#000 40%,transparent)}
:root[data-theme="light"] .find__results{box-shadow:0 14px 40px color-mix(in srgb,#5a4a2a 18%,
  transparent)}
.find__results #search-help{margin:0 0 4px;font-size:12px;color:var(--ink-3)}
.find__results .search-count{margin:0 0 8px;font:12px var(--fm);color:var(--ink-3)}
.find__results .region{margin:12px 0 4px;font:600 11px/16px var(--fm);letter-spacing:.08em;
color:var(--ink-3);text-transform:uppercase}
.ixgrid{display:flex;flex-direction:column}
.ix{display:grid;grid-template-columns:minmax(0,1fr);gap:1px;width:100%;text-align:left;
min-height:40px;
padding:6px 8px;margin:0;border:0;border-radius:6px;background:transparent}
.ix code{order:-1;font:600 13px/18px var(--fm);color:var(--ink)}
.ix__plain{font:12px/16px var(--fs);color:var(--ink-3)}
.ix:hover,.ix:focus-visible,.ix[aria-current="true"]{background:var(--raised)}
.ix .chip{display:none}.ix__match{font:11px/15px var(--fs);color:var(--ink-3)}
#searchempty{font-size:13px;color:var(--ink-2)}
#read-toggle[aria-pressed="true"]{background:var(--raised);color:var(--ink);
  border-color:var(--ink-3)}
.more{position:relative;flex:none}
.more>summary{list-style:none;width:32px;height:32px;min-height:32px;padding:0;display:flex;
align-items:center;justify-content:center;border:1px solid var(--line-2);border-radius:6px;
color:var(--ink-2);font-size:16px}
.more>summary::-webkit-details-marker{display:none}
.more[open]>summary,.more>summary:hover{background:var(--raised);color:var(--ink)}
.more__menu{position:absolute;right:0;top:calc(100% + 8px);z-index:20;width:220px;padding:6px;
display:flex;flex-direction:column;gap:2px;border:1px solid var(--line-2);border-radius:10px;
background:var(--surface);box-shadow:0 14px 40px color-mix(in srgb,#000 40%,transparent)}
:root[data-theme="light"] .more__menu{box-shadow:0 14px 40px color-mix(in srgb,#5a4a2a 18%,
  transparent)}
.more__menu>button,.more__menu [data-scheme]{width:100%;justify-content:flex-start;text-align:left;
border-color:transparent;font-size:13px;color:var(--ink);display:flex;align-items:center;gap:10px}
.more__menu [aria-pressed="true"]{background:var(--raised)}
body[data-view="reading"] #view-reading,body:not([data-view="reading"]) #view-map{display:none}
.more__label{margin:6px 10px 2px;font:600 11px/16px var(--fm);letter-spacing:.08em;
color:var(--ink-3)}
#scheme{display:flex;flex-direction:column;gap:2px}
[data-scheme] i{width:12px;height:12px;border-radius:50%;border:1px solid var(--line-2)}
[data-scheme="dark"] i{background:#12110F}[data-scheme="light"] i{background:#F4F2EF}
.motion-control{display:flex;gap:10px;align-items:center;font-size:13px;min-height:32px;
padding:0 12px;color:var(--ink);border-top:1px solid var(--line);margin-top:4px}

/* ---- the frame: map and panel ------------------------------------------ */
.main{display:grid;grid-template-columns:minmax(0,1fr);height:calc(100svh - 52px);min-height:520px}
body[data-panel="open"] .main{grid-template-columns:minmax(0,1fr) 400px}
.map{position:relative;min-width:0;display:flex;flex-direction:column;overflow:hidden;
background-color:var(--map);background-image:radial-gradient(var(--grid) 1px,transparent 1px);
background-size:24px 24px}
.map>*{flex-shrink:0}
.spatial-map{position:relative;flex:1;min-height:0}
.mapwrap{position:absolute;inset:144px 0 0 0;overflow:hidden}
.stage{width:100%;height:100%}
.stage svg,.stage #schematic,.stage #changemap{display:block;width:100%;height:100%}
.mapbar{position:absolute;left:24px;top:66px;right:200px;z-index:4;display:flex;
flex-direction:column;gap:10px;pointer-events:none}
.mapbar>*{pointer-events:auto}
.mapbar__label{margin:0;height:28px;display:flex;align-items:flex-end;padding-bottom:4px;
font:600 11px/16px var(--fm);letter-spacing:.08em;color:var(--ink-3)}
.question{margin:0;font:500 22px/28px var(--fs);letter-spacing:-.01em;color:var(--ink);
max-width:62ch}
.zoom{position:absolute;right:24px;top:66px;z-index:7;display:flex;align-items:center;gap:6px}
.zoom__seg{display:flex;border:1px solid var(--line-2);border-radius:6px;overflow:hidden}
.zoom button{height:30px;min-height:30px;width:30px;padding:0;border:0;border-radius:0;
display:inline-flex;align-items:center;justify-content:center;background:var(--surface)}
.zoom button:focus-visible{outline-offset:-3px}
.zoom [aria-pressed="true"]{background:var(--card);color:var(--ink)}
#zpct{width:54px;border:solid var(--line-2);border-width:0 1px;font:12px var(--fm)}
.zoom [data-zoom="fit"]{height:32px;min-height:32px;width:32px;border:1px solid var(--line-2);
border-radius:6px}
body[data-view="reading"] .zoom{display:none}
body[data-mode="change"][data-compare="false"] .zoom,
body[data-mode="change"][data-compare="false"] .change-controls{display:none}
body[data-mode="change"][data-compare="false"] .change-view{inset:0}
.map-legend{position:absolute;left:24px;bottom:14px;z-index:4;display:flex;flex-wrap:wrap;
gap:6px 16px;align-items:center;max-width:calc(100% - 380px);font:12px/16px var(--fs);
color:var(--ink-2);background:var(--map);padding:4px 8px;border-radius:4px}
.lg{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.lg__line{display:block;width:18px;border-top:2px solid var(--c,var(--ink-2))}
.lg__line--dash{border-top-style:dashed;border-color:var(--ink-2)}
.lg__card{display:block;width:18px;height:12px;border:1px solid var(--card-line);border-radius:3px}
.lg__card--actor{border-style:dashed}
.lg__card--quiet{opacity:.32;background:var(--card)}
.readout{position:absolute;right:24px;bottom:14px;z-index:4;margin:0;max-width:330px;
font:12px/16px var(--fm);color:var(--ink);background:var(--map);padding:4px 8px;border-radius:4px;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.readout{display:flex;gap:10px;align-items:center}
.readout__more{min-height:0;height:auto;padding:0;border:0;background:transparent;color:var(--ink-2);
font:12px/16px var(--fs);text-decoration:underline;text-underline-offset:3px}
.readout__more:hover{background:transparent;color:var(--ink)}
.hint{font-size:11px;color:var(--ink-3)}
#linkstatus{position:absolute;left:24px;bottom:44px;z-index:4;margin:0;font-size:12px;
  color:var(--ink-2)}
#linkstatus:empty{display:none}

/* ---- the reading panel ---------------------------------------------------- */
.readpanel{min-width:0;height:calc(100svh - 52px);min-height:520px;overflow:auto;
background:var(--surface);
border-left:1px solid var(--line);padding:20px 22px 28px;display:flex;flex-direction:column;
gap:14px}
.readpanel h2{font:600 19px/25px var(--fs);margin:0 0 .4rem;color:var(--ink)}
.readpanel h3{font-size:13px}
.readpanel p{font-size:13px;line-height:1.55}
.drawer__in{display:flex;flex-direction:column;gap:0;position:relative}
.drawer__x{position:absolute;right:0;top:-2px;z-index:2;height:28px;min-height:28px;font-size:12px}
.systemap-panel.on{padding:0;margin:0;background:none;border:0;box-shadow:none}
.source-section{border-top:1px solid var(--line);padding-top:1rem;margin-top:1rem}
.source-section h3{font-size:13px;margin:0 0 .5rem;color:var(--ink)}
.source-unknown{color:var(--ink)}
.module-record{font-size:13px}.module-record p{font-size:12px}.file{font-family:var(--fm)}
.journey-choice,.review-choice{display:block;width:100%;text-align:left;margin:.4rem 0;
padding:.75rem;font-size:13px;overflow-wrap:anywhere;color:var(--ink);border-color:var(--line)}
.journey-choice small,.review-choice small{display:block;color:var(--ink-2);margin:.3rem 0;
font-size:12px}
.journey-choice[aria-pressed="true"],.review-choice[aria-pressed="true"]{border-color:var(--accent);
background:var(--raised)}
.reference{display:flex;flex-direction:column;gap:1rem}
.reference>section,.reference>details,.reference>p{min-width:0;border-top:1px solid var(--line);
padding-top:.7rem;margin:0}
.reference h2{font-size:19px;margin:.1rem 0 .2rem}
.reference>details>summary{color:var(--ink);font-weight:500}
.review-kicker{font:600 11px/16px var(--fm)!important;letter-spacing:.08em;
color:var(--ink-3)!important;
text-transform:uppercase;margin:0!important}
.review-count{font-size:13px}.review-count span{margin-left:1rem}
.review-filters{display:flex;gap:.4rem;margin:.7rem 0}
.review-filters [aria-pressed="true"]{background:var(--raised);border-color:var(--ink-3);
color:var(--ink)}
.review-line{font-family:var(--fm);font-size:12px;overflow-wrap:anywhere;padding:.7rem 0;
color:var(--ink)}
.review-cards{display:flex;gap:.4rem;flex-wrap:wrap;font-size:12px}.review-reason{color:var(--ink)}
#review-detail{border-top:1px solid var(--line);padding-top:1rem}
.rules{padding-left:1.5rem}.rules li{margin:.8rem 0;font-size:13px}
.rules li::marker{color:var(--ink-3);font-family:var(--fm)}
.governs{display:block;margin:.4rem 0}.gv{font-size:12px;margin:.2rem;min-height:28px}
.command{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.3rem;padding:.8rem 0;
border-bottom:1px solid var(--line);font-size:13px}
.command b,.command p{grid-column:1/-1}.command p{margin:0 0 .4rem}
.command button{font-size:12px;min-width:72px}.command code{align-self:center;
overflow-wrap:anywhere;color:var(--ink)}
button.copied{color:var(--ink);border-color:var(--ink-3)}
.legend{display:flex;flex-wrap:wrap;gap:.8rem;font-size:12px;color:var(--ink-2)}
.map-key p{font-size:13px}.lg--solidline{width:22px;border-top:2px solid var(--ink-2)}
.lg--dashline{width:22px;border-top:2px dashed var(--ink-2)}
.source-files{font-size:12px!important;color:var(--ink-3)!important}

/* ---- view rows: Sequences and Changes ------------------------------------ */
.trace-controls,.change-controls,.layer-controls{position:absolute;left:0;right:0;top:0;z-index:6;
height:52px;
display:flex;align-items:center;gap:8px;padding:0 20px;border-bottom:1px solid var(--line);
background:var(--surface)}
body:not([data-mode="trace"]) .trace-controls,
  body:not([data-mode="change"]) .change-controls{display:none}
.trace-controls select{height:32px;min-width:320px;padding:0 10px;border:1px solid var(--line-2);
border-radius:6px;background:var(--raised);color:var(--ink);font-size:13px}
.trace-controls__label{font-size:12px;color:var(--ink-3)}
#jcount{font:12px var(--fm);color:var(--ink-2);padding:0 6px}
.change-view{position:absolute;inset:52px 0 0 0;display:flex;flex-direction:column}
.change-view .stage{position:absolute;inset:92px 0 0 0;width:auto;height:auto}
.change-empty{margin:140px auto 0;max-width:520px;padding:0 24px}
.change-empty h2{font:500 22px/28px var(--fs);margin:0 0 8px}
.change-empty code{display:inline-block;margin:8px 8px 0 0;color:var(--ink)}

/* Boards 4, 5 and 9: the view row spans the window, with the zoom at its end,
   and the panel starts under it. */
@media(min-width:821px){
body[data-mode="trace"] .trace-controls,body[data-mode="change"] .change-controls,
.layer-controls{position:fixed;top:52px;left:0;right:0;z-index:11;padding-right:220px}
.zoom{position:fixed;top:62px;right:20px;z-index:12}
.readpanel{margin-top:52px;height:calc(100svh - 104px)}}

/* ---- text view, the map inside a card ------------------------------------ */
body[data-view="reading"] .map{overflow:auto}
body[data-view="reading"] .spatial-map{display:none}
.atlas{position:relative;padding:162px 24px 40px;max-width:980px}
.submap{position:fixed;inset:1rem;z-index:40;background:var(--bg);border:1px solid var(--line-2);
display:flex;flex-direction:column;box-shadow:0 8px 60px color-mix(in srgb,#000 50%,transparent)}
.submap__bar{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.75rem;
border-bottom:1px solid var(--line)}
.submap__crumb{font-size:13px;overflow-wrap:anywhere;min-width:0}
.submap__frame{flex:1;width:100%;border:0;background:var(--bg)}body.submap-open{overflow:hidden}
.map-links{padding:1rem 24px;font-size:13px}

/* ---- narrow windows ----------------------------------------------------- */
@media(max-width:1100px){body[data-panel="open"] .main{grid-template-columns:minmax(0,1fr) 340px}
.find{width:160px}.views{margin-left:0}.snap{display:none}}
@media(max-width:820px){.bar{gap:10px;padding:0 12px}.find{width:auto;flex:0 1 140px}
.views button{padding:0 9px}
body[data-panel="open"] .main{grid-template-columns:minmax(0,1fr)}
body[data-panel="open"] .readpanel{position:fixed;right:0;top:104px;bottom:0;width:min(400px,100%);
z-index:15;height:auto;box-shadow:-12px 0 40px color-mix(in srgb,#000 40%,transparent)}
.question{font-size:19px;line-height:25px}.readout{max-width:40%}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
html[data-reduce-motion="true"] *{transition:none!important;animation:none!important}
"""
