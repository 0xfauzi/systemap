// Drives a rendered systemap page's scripts under Node with a small DOM of
// its own, and reports what the keyboard did. No library: the page is the
// generator's output, well formed and closed, so a tag parser of a hundred
// lines reads it, and the scripts touch a known handful of DOM calls, each
// implemented below with the browser's meaning and nothing more. Geometry
// is not modelled: every box is where its attributes say it is, and the
// screen is a 1600 by 900 window whose CSS pixel is one viewBox unit.
//
//     node tests/page_driver.js PAGE.html [--reduced]
//
// prints one JSON object; tests/test_keyboard.py reads it. --reduced makes
// the page's prefers-reduced-motion query match.
'use strict';
const fs = require('fs');
const vm = require('vm');

// ---- the tree -------------------------------------------------------------
const VOID = new Set(['meta', 'link', 'br', 'hr', 'img', 'input', 'source']);
const RAW = new Set(['script', 'style']);
const ENTITIES = {amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", middot: '·', nbsp: ' '};

function decode(text) {
  return text.replace(/&(#x[0-9a-f]+|#[0-9]+|[a-z]+);/gi, (m, e) => {
    if (e[0] === '#') {
      return String.fromCodePoint(e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10));
    }
    return ENTITIES[e] !== undefined ? ENTITIES[e] : m;
  });
}

let focused = null;
let rafQueue = [];
let rafCalls = 0;
let scrolls = [];
const REPORT = {replaceStates: []};

class Text {
  constructor(data) { this.nodeType = 3; this.data = data; this.parentNode = null; }
  get textContent() { return this.data; }
}

class Element {
  constructor(tag, svg) {
    this.nodeType = 1;
    this.tag = tag;
    this.inSvg = svg;
    this.attrs = new Map();
    this.childNodes = [];
    this.parentNode = null;
    this.listeners = {};
    this.style = makeStyle();
    this.dataset = new Proxy({}, {
      get: (_, name) => this.getAttribute('data-' + kebab(name)),
      set: (_, name, value) => { this.setAttribute('data-' + kebab(name), String(value)); return true; },
      has: (_, name) => this.hasAttribute('data-' + kebab(name)),
    });
    this.classList = {
      add: (...names) => names.forEach((n) => { const s = this._classes(); s.add(n); this._setClasses(s); }),
      remove: (...names) => names.forEach((n) => { const s = this._classes(); s.delete(n); this._setClasses(s); }),
      toggle: (n, force) => {
        const s = this._classes();
        const on = force === undefined ? !s.has(n) : !!force;
        if (on) s.add(n); else s.delete(n);
        this._setClasses(s);
        return on;
      },
      contains: (n) => this._classes().has(n),
    };
  }
  get tagName() { return this.inSvg ? this.tag : this.tag.toUpperCase(); }
  get id() { return this.getAttribute('id') || ''; }
  set id(v) { this.setAttribute('id', v); }
  _classes() { return new Set((this.getAttribute('class') || '').split(/\s+/).filter(Boolean)); }
  _setClasses(s) { this.setAttribute('class', Array.from(s).join(' ')); }
  get className() { return this.getAttribute('class') || ''; }
  getAttribute(n) { return this.attrs.has(n) ? this.attrs.get(n) : null; }
  setAttribute(n, v) { this.attrs.set(n, String(v)); }
  removeAttribute(n) { this.attrs.delete(n); }
  hasAttribute(n) { return this.attrs.has(n); }
  get hidden() { return this.hasAttribute('hidden'); }
  set hidden(v) { if (v) this.setAttribute('hidden', ''); else this.removeAttribute('hidden'); }
  get disabled() { return this.hasAttribute('disabled'); }
  set disabled(v) { if (v) this.setAttribute('disabled', ''); else this.removeAttribute('disabled'); }
  get value() {
    if (this.tag === 'select') {
      if (this._value !== undefined) return this._value;
      const opts = this.querySelectorAll('option');
      const sel = opts.find((o) => o.hasAttribute('selected')) || opts[0];
      return sel ? sel.getAttribute('value') : '';
    }
    return this._value === undefined ? (this.getAttribute('value') || '') : this._value;
  }
  set value(v) { this._value = String(v); }
  get children() { return this.childNodes.filter((c) => c.nodeType === 1); }
  get firstChild() { return this.childNodes[0] || null; }
  get textContent() { return this.childNodes.map((c) => c.textContent).join(''); }
  set textContent(v) {
    this.childNodes.forEach((c) => { c.parentNode = null; });
    this.childNodes = [];
    if (v !== '' && v !== null && v !== undefined) this.appendChild(new Text(String(v)));
  }
  get innerHTML() { return this.childNodes.map(serialize).join(''); }
  set innerHTML(html) {
    this.childNodes.forEach((c) => { c.parentNode = null; });
    this.childNodes = [];
    parseInto(String(html), this, this.inSvg);
  }
  appendChild(node) {
    if (node.parentNode) node.parentNode.removeChild(node);
    node.parentNode = this;
    this.childNodes.push(node);
    return node;
  }
  removeChild(node) {
    const i = this.childNodes.indexOf(node);
    if (i >= 0) { this.childNodes.splice(i, 1); node.parentNode = null; }
    return node;
  }
  contains(node) {
    for (let n = node; n; n = n.parentNode) if (n === this) return true;
    return false;
  }
  closest(sel) {
    const parts = parseSelectorList(sel);
    for (let n = this; n && n.nodeType === 1; n = n.parentNode) if (matchesAny(n, parts)) return n;
    return null;
  }
  matches(sel) { return matchesAny(this, parseSelectorList(sel)); }
  querySelectorAll(sel) {
    const parts = parseSelectorList(sel);
    const out = [];
    walk(this, (n) => { if (matchesAny(n, parts)) out.push(n); });
    return out;
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  addEventListener(type, fn, opts) {
    const capture = opts === true || (opts && opts.capture);
    (this.listeners[type] = this.listeners[type] || []).push({fn, capture: !!capture});
  }
  removeEventListener(type, fn) {
    this.listeners[type] = (this.listeners[type] || []).filter((l) => l.fn !== fn);
  }
  dispatchEvent(ev) { return dispatch(this, ev); }
  click() { return this.dispatchEvent(new EventImpl('click', {bubbles: true})); }
  focus() {
    const focusable = this.hasAttribute('tabindex') || ['button', 'select', 'a', 'input'].includes(this.tag);
    if (!focusable || this.disabled) return;
    focused = this;
    this.dispatchEvent(new EventImpl('focus', {bubbles: false}));
  }
  blur() { if (focused === this) focused = null; }
  getBoundingClientRect() { return {top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0}; }
  scrollIntoView(opts) { scrolls.push(opts && opts.behavior ? opts.behavior : 'auto'); }
  get offsetWidth() { return this.id === 'drawer' ? 380 : 0; }
  get offsetHeight() { return 0; }
  getScreenCTM() { return {a: 1, b: 0, c: 0, d: 1, e: 0, f: 0, inverse() { return this; }}; }
  get viewBox() {
    const v = (this.getAttribute('viewBox') || '0 0 0 0').trim().split(/[\s,]+/).map(Number);
    return {baseVal: {x: v[0], y: v[1], width: v[2], height: v[3]}};
  }
  setPointerCapture() {}
}

function kebab(name) { return name.replace(/[A-Z]/g, (c) => '-' + c.toLowerCase()); }

function makeStyle() {
  const props = {};
  return new Proxy(props, {
    get: (t, name) => {
      if (name === 'setProperty') return (n, v) => { t[n] = v; };
      if (name === 'getPropertyValue') return (n) => t[n] || '';
      if (name === 'removeProperty') return (n) => { delete t[n]; };
      return t[name] === undefined ? '' : t[name];
    },
    set: (t, name, v) => { t[name] = v; return true; },
  });
}

function serialize(node) {
  if (node.nodeType === 3) return node.data;
  const attrs = Array.from(node.attrs).map(([k, v]) => ` ${k}="${v}"`).join('');
  return `<${node.tag}${attrs}>${node.childNodes.map(serialize).join('')}</${node.tag}>`;
}

function walk(root, visit) {
  root.childNodes.forEach((c) => { if (c.nodeType === 1) { visit(c); walk(c, visit); } });
}

// ---- the parser -------------------------------------------------------------
function parseInto(html, root, svg) {
  const stack = [root];
  let svgDepth = svg ? 1 : 0;
  let i = 0;
  const top = () => stack[stack.length - 1];
  while (i < html.length) {
    const lt = html.indexOf('<', i);
    if (lt < 0) { top().appendChild(new Text(decode(html.slice(i)))); break; }
    if (lt > i) top().appendChild(new Text(decode(html.slice(i, lt))));
    if (html.startsWith('<!--', lt)) { i = html.indexOf('-->', lt) + 3; continue; }
    if (html[lt + 1] === '!') { i = html.indexOf('>', lt) + 1; continue; }
    if (html[lt + 1] === '/') {
      const end = html.indexOf('>', lt);
      const name = html.slice(lt + 2, end).trim().toLowerCase();
      for (let k = stack.length - 1; k > 0; k--) {
        if (stack[k].tag === name) {
          while (stack.length > k) { const closed = stack.pop(); if (closed.tag === 'svg') svgDepth--; }
          break;
        }
      }
      i = end + 1;
      continue;
    }
    let j = lt + 1;
    while (j < html.length && /[A-Za-z0-9:-]/.test(html[j])) j++;
    const name = html.slice(lt + 1, j).toLowerCase();
    const el = new Element(name, svgDepth > 0 || name === 'svg');
    // attributes
    for (;;) {
      while (j < html.length && /\s/.test(html[j])) j++;
      if (html[j] === '>' || html.startsWith('/>', j)) break;
      let k = j;
      while (k < html.length && !/[\s=>\/]/.test(html[k])) k++;
      const attr = html.slice(j, k);
      j = k;
      while (j < html.length && /\s/.test(html[j])) j++;
      let value = '';
      if (html[j] === '=') {
        j++;
        while (j < html.length && /\s/.test(html[j])) j++;
        const q = html[j];
        if (q === '"' || q === "'") {
          const close = html.indexOf(q, j + 1);
          value = decode(html.slice(j + 1, close));
          j = close + 1;
        } else {
          k = j;
          while (k < html.length && !/[\s>]/.test(html[k])) k++;
          value = decode(html.slice(j, k));
          j = k;
        }
      }
      if (attr) el.attrs.set(attr, value);
    }
    const selfClosed = html.startsWith('/>', j);
    i = html.indexOf('>', j) + 1;
    top().appendChild(el);
    if (selfClosed || VOID.has(name)) continue;
    if (RAW.has(name)) {
      const close = html.indexOf('</' + name, i);
      el.appendChild(new Text(html.slice(i, close)));
      i = html.indexOf('>', close) + 1;
      continue;
    }
    stack.push(el);
    if (name === 'svg') svgDepth++;
  }
}

// ---- selectors: compound selectors joined by descendant or child combinators ----
function parseSelectorList(sel) {
  return sel.split(',').map((one) => {
    const parts = [];
    const tokens = one.trim().replace(/\s*>\s*/g, ' > ').split(/\s+/);
    let combinator = ' ';
    tokens.forEach((tok) => {
      if (tok === '>') { combinator = '>'; return; }
      parts.push({combinator, compound: parseCompound(tok)});
      combinator = ' ';
    });
    return parts;
  });
}

function parseCompound(tok) {
  const out = {tag: null, id: null, classes: [], attrs: [], nots: []};
  const re = /([A-Za-z][A-Za-z0-9_-]*)|#([A-Za-z0-9_-]+)|\.([A-Za-z0-9_-]+)|\[([A-Za-z0-9_-]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\]]*)))?\]|:not\(([^)]*)\)/g;
  let m;
  while ((m = re.exec(tok)) !== null) {
    if (m[1] !== undefined) out.tag = m[1].toLowerCase();
    else if (m[2] !== undefined) out.id = m[2];
    else if (m[3] !== undefined) out.classes.push(m[3]);
    else if (m[4] !== undefined) {
      const value = m[5] !== undefined ? m[5] : (m[6] !== undefined ? m[6] : m[7]);
      out.attrs.push({name: m[4], value: value === undefined ? null : value});
    } else if (m[8] !== undefined) out.nots.push(parseCompound(m[8]));
  }
  return out;
}

function matchesCompound(el, c) {
  if (c.tag && el.tag !== c.tag) return false;
  if (c.id && el.id !== c.id) return false;
  if (c.classes.length) { const s = el._classes(); if (!c.classes.every((k) => s.has(k))) return false; }
  for (const a of c.attrs) {
    if (!el.hasAttribute(a.name)) return false;
    if (a.value !== null && el.getAttribute(a.name) !== a.value) return false;
  }
  return c.nots.every((n) => !matchesCompound(el, n));
}

function matchesChain(el, parts, k) {
  if (!matchesCompound(el, parts[k].compound)) return false;
  if (k === 0) return true;
  const comb = parts[k].combinator;
  if (comb === '>') {
    const p = el.parentNode;
    return !!(p && p.nodeType === 1 && matchesChain(p, parts, k - 1));
  }
  for (let p = el.parentNode; p && p.nodeType === 1; p = p.parentNode) if (matchesChain(p, parts, k - 1)) return true;
  return false;
}

function matchesAny(el, list) { return list.some((parts) => matchesChain(el, parts, parts.length - 1)); }

// ---- events -------------------------------------------------------------------
class EventImpl {
  constructor(type, init) {
    init = init || {};
    this.type = type;
    this.bubbles = !!init.bubbles;
    this.detail = init.detail;
    this.key = init.key || '';
    this.altKey = !!init.altKey; this.ctrlKey = !!init.ctrlKey; this.metaKey = !!init.metaKey;
    this.shiftKey = !!init.shiftKey;
    this.defaultPrevented = false;
    this._stop = false; this._stopNow = false;
    this.target = null; this.currentTarget = null;
  }
  preventDefault() { this.defaultPrevented = true; }
  stopPropagation() { this._stop = true; }
  stopImmediatePropagation() { this._stop = true; this._stopNow = true; }
}
class CustomEventImpl extends EventImpl {}
class KeyboardEventImpl extends EventImpl {}

let documentNode = null;
let windowObject = null;

function dispatch(target, ev) {
  ev.target = target;
  const path = [];
  for (let n = target; n; n = n.parentNode) path.push(n);
  if (documentNode && path[path.length - 1] !== documentNode) path.push(documentNode);
  if (windowObject) path.push(windowObject);
  const run = (node, capture) => {
    const list = (node.listeners && node.listeners[ev.type]) || [];
    for (const l of list.slice()) {
      if (l.capture !== capture) continue;
      ev.currentTarget = node;
      l.fn.call(node, ev);
      if (ev._stopNow) return;
    }
  };
  for (let k = path.length - 1; k > 0 && !ev._stop; k--) run(path[k], true);
  if (!ev._stop) { run(target, true); if (!ev._stopNow) run(target, false); }
  if (ev.bubbles) for (let k = 1; k < path.length && !ev._stop; k++) run(path[k], false);
  return !ev.defaultPrevented;
}

// ---- document and window ---------------------------------------------------------
function load(html, reducedMotion) {
  const doc = new Element('#document', false);
  documentNode = doc;
  parseInto(html, doc, false);
  const htmlEl = doc.querySelector('html');
  const body = doc.querySelector('body');
  Object.defineProperty(doc, 'body', {get: () => body});
  Object.defineProperty(doc, 'documentElement', {get: () => htmlEl});
  // A focused element that has left the tree is no longer the active one;
  // the browser hands focus to the body.
  const connected = (n) => { for (; n; n = n.parentNode) if (n === doc) return true; return false; };
  Object.defineProperty(doc, 'activeElement', {get: () => (focused && connected(focused) ? focused : body)});
  doc.getElementById = (id) => { let out = null; walk(doc, (n) => { if (!out && n.id === id) out = n; }); return out; };
  doc.createElementNS = (ns, name) => new Element(name, true);
  doc.createElement = (name) => new Element(name.toLowerCase(), false);

  const win = {
    listeners: {},
    innerWidth: 1600,
    innerHeight: 900,
    document: doc,
    location: {hash: '', pathname: '/index.html', search: '', href: 'http://127.0.0.1/index.html'},
    history: {replaceState: (_s, _t, url) => {
      REPORT.replaceStates.push(url);
      win.location.hash = url.startsWith('#') ? url : '';
    }},
    matchMedia: (q) => ({matches: reducedMotion && /prefers-reduced-motion/.test(q), addEventListener() {}}),
    requestAnimationFrame: (cb) => { rafCalls++; const id = rafQueue.length + 1; rafQueue.push({id, cb}); return id; },
    cancelAnimationFrame: (id) => { rafQueue = rafQueue.filter((f) => f.id !== id); },
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push({fn, capture: false}); },
    dispatchEvent(ev) { ev.target = this; (this.listeners[ev.type] || []).forEach((l) => l.fn.call(this, ev)); return true; },
    scrollTo() {},
    getComputedStyle: () => makeStyle(),
    Event: EventImpl,
    CustomEvent: CustomEventImpl,
    KeyboardEvent: KeyboardEventImpl,
    console,
    Math, JSON, Object, Array, String, Number, parseInt, parseFloat, isNaN, Infinity, NaN,
    decodeURIComponent, encodeURIComponent, setTimeout: (cb) => { cb(); return 0; }, clearTimeout() {},
  };
  win.window = win;
  win.self = win;
  windowObject = win;
  return {doc, win};
}

function runFrames(win) {
  // Play queued animation frames with a clock that moves 20 ms a frame,
  // until the page queues no more; bounded so a runaway loop ends.
  let now = 0;
  for (let guard = 0; rafQueue.length && guard < 200; guard++) {
    const batch = rafQueue; rafQueue = [];
    now += 20;
    batch.forEach((f) => f.cb(now));
  }
}

// ---- the scenario ----------------------------------------------------------------
function main() {
  const args = process.argv.slice(2);
  const reduced = args.includes('--reduced');
  const file = args.find((a) => !a.startsWith('--'));
  const html = fs.readFileSync(file, 'utf8');
  const {doc, win} = load(html, reduced);
  const context = vm.createContext(win);
  doc.querySelectorAll('script').forEach((s) => { vm.runInContext(s.textContent, context); });
  runFrames(win);

  const svg = doc.getElementById('schematic');
  const A = svg.systemap;
  const key = (k, target) => {
    const ev = new KeyboardEventImpl('keydown', {key: k, bubbles: true});
    dispatch(target || doc.body, ev);
    runFrames(win);
    return ev.defaultPrevented;
  };
  const report = {
    reduced,
    layers: A.layers.map((l) => l.id),
    buttons: doc.querySelectorAll('[data-layer-btn]').map((b) => b.dataset.layerBtn),
    readings: Object.keys(A.detail._meta.readings || {}),
    initialLayer: A.state.layer,
    replaceStates: REPORT.replaceStates,
  };
  const pressed = () => doc.querySelectorAll('[data-layer-btn]').filter((b) => b.getAttribute('aria-pressed') === 'true').map((b) => b.dataset.layerBtn);

  // Arrows switch readings while no journey is on.
  const arrows = [];
  key('ArrowRight'); arrows.push({after: 'right', layer: A.state.layer, pressed: pressed()});
  key('ArrowRight'); arrows.push({after: 'right', layer: A.state.layer, pressed: pressed()});
  key('ArrowLeft'); arrows.push({after: 'left', layer: A.state.layer, pressed: pressed()});
  key('ArrowLeft'); arrows.push({after: 'left', layer: A.state.layer, pressed: pressed()});
  key('ArrowLeft'); arrows.push({after: 'left', layer: A.state.layer, pressed: pressed()});
  report.arrows = arrows;
  // ... and are left alone inside the journey select.
  const select = doc.getElementById('journey');
  report.arrowInSelectPrevented = key('ArrowRight', select);
  report.layerAfterSelectArrow = A.state.layer;
  // Back to the first reading for what follows.
  while (A.state.layer !== report.layers[0]) key('ArrowRight');

  // Tab order: every card takes focus, in the order it is written.
  const nodes = svg.querySelectorAll('.node');
  report.nodeOrder = nodes.map((n) => {
    const box = n.querySelector('.node__box');
    return {id: n.dataset.id, x: +box.getAttribute('x'), y: +box.getAttribute('y'), tabindex: n.getAttribute('tabindex'), role: n.getAttribute('role'), label: n.getAttribute('aria-label')};
  });
  report.svgTabindex = svg.getAttribute('tabindex');

  // Enter on a focused card opens its wheel; Escape closes it and gives
  // the focus back.
  const drawer = doc.getElementById('drawer');
  const panel = doc.getElementById('panel');
  const withEdges = nodes.find((n) => (A.detail[n.dataset.id].edges || []).length > 1);
  withEdges.focus();
  const before = {rafCalls};
  const enterPrevented = key('Enter', withEdges);
  report.enter = {
    id: withEdges.dataset.id,
    prevented: enterPrevented,
    focus: A.state.focus,
    drawerHidden: drawer.hidden,
    dock: drawer.dataset.dock,
    panelOn: panel.classList.contains('on'),
    spokes: panel.querySelectorAll('.systemap-w__spoke').length,
    edges: (A.detail[withEdges.dataset.id].edges || []).length,
    spokesFocusable: panel.querySelectorAll('.systemap-w__spoke').every((s) => s.getAttribute('tabindex') === '0' && s.getAttribute('role') === 'button'),
    hash: REPORT.replaceStates[REPORT.replaceStates.length - 1],
    rafCallsForFraming: rafCalls - before.rafCalls,
    activeElement: doc.activeElement.dataset ? doc.activeElement.dataset.id : doc.activeElement.tag,
  };
  // Focus moves into the wheel (Tab, in a browser; here the spoke is focused
  // directly) and Escape from there closes the drawer and returns to the card.
  const spoke = panel.querySelector('.systemap-w__spoke');
  spoke.focus();
  report.peekOnFocus = A.state.peek;
  const escPrevented = key('Escape', spoke);
  report.escape = {
    prevented: escPrevented,
    focus: A.state.focus,
    drawerHidden: drawer.hidden,
    panelOn: panel.classList.contains('on'),
    panelEmpty: panel.childNodes.length === 0,
    activeElement: doc.activeElement.dataset ? doc.activeElement.dataset.id : doc.activeElement.tag,
    hashCleared: REPORT.replaceStates[REPORT.replaceStates.length - 1],
    hash: win.location.hash,
  };
  // Space opens too, as a button would.
  key(' ', withEdges);
  report.spaceOpens = A.state.focus === withEdges.dataset.id;
  key('Escape');

  // A journey: the arrows step it, Escape ends it.
  const journeys = A.journeys;
  const j = {count: journeys.length};
  if (journeys.length) {
    select.value = '0';
    select.dispatchEvent(new EventImpl('change', {bubbles: true}));
    runFrames(win);
    const count = doc.getElementById('jcount');
    j.started = count.textContent;
    j.stripHidden = doc.getElementById('strip').hidden;
    key('ArrowRight'); j.afterRight = count.textContent;
    j.layerUnchanged = A.state.layer === report.layers[0];
    key('ArrowLeft'); j.afterLeft = count.textContent;
    key('ArrowLeft'); j.afterLeftAtStart = count.textContent;
    j.stepButtons = doc.querySelectorAll('[data-step]').length;
    j.steps = journeys[0].steps.length;
    key('Escape');
    j.ended = count.textContent;
    j.stripHiddenAfter = doc.getElementById('strip').hidden;
    j.selectReset = select.value;
    j.journeyState = A.state.journey;
  }
  report.journey = j;
  report.rafCalls = rafCalls;
  report.scrolls = scrolls;
  process.stdout.write(JSON.stringify(report) + '\n');
}

main();
