// The script of the systemap website: the theme, the docs menu on a phone,
// the current section in "On this page", and the Copy button.
// The page head sets data-theme before the page shows. The theme key and values
// are those of the map page, so the site and the map page keep one selection.
(function(){
  'use strict';
  var KEY = 'systemap-theme';
  var root = document.documentElement;
  var device = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;

  function stored(){ try { return localStorage.getItem(KEY); } catch(e){ return null; } }
  function store(value){ try { localStorage.setItem(KEY, value); } catch(e){} }
  function current(){ return root.getAttribute('data-theme') === 'light' ? 'light' : 'dark'; }
  function each(selector, fn){ Array.prototype.forEach.call(document.querySelectorAll(selector), fn); }

  // A <picture> shows the image of the device theme. After a selection on the
  // page, each source with data-scheme shows only in its own theme.
  function pictures(){
    var theme = current();
    each('source[data-scheme]', function(s){
      s.media = s.getAttribute('data-scheme') === theme ? 'all' : 'not all';
    });
  }
  function label(){
    var b = document.getElementById('theme');
    if(!b){ return; }
    var name = current() === 'dark' ? 'Paper theme' : 'Ink theme';
    b.setAttribute('aria-label', name);
    b.title = name;
    b.hidden = false;
  }
  function apply(theme, keep){
    if(keep){
      root.classList.add('theming');
      window.setTimeout(function(){ root.classList.remove('theming'); }, 300);
      store(theme);
    }
    root.setAttribute('data-theme', theme);
    pictures();
    label();
  }

  function themes(){
    var b = document.getElementById('theme');
    if(b){ b.addEventListener('click', function(){ apply(current() === 'dark' ? 'light' : 'dark', true); }); }
    if(device && device.addEventListener){
      device.addEventListener('change', function(e){
        var s = stored();
        if(s !== 'dark' && s !== 'light'){ apply(e.matches ? 'light' : 'dark', false); }
      });
    }
    pictures();
    label();
  }

  // On a phone, the docs navigation is a list that a button opens.
  function menu(){
    var b = document.querySelector('.docbar__btn');
    var nav = document.getElementById('side');
    if(!b || !nav){ return; }
    b.hidden = false;
    function set(open){
      b.setAttribute('aria-expanded', open ? 'true' : 'false');
      if(open){ nav.setAttribute('data-open', ''); } else { nav.removeAttribute('data-open'); }
    }
    b.addEventListener('click', function(){ set(b.getAttribute('aria-expanded') !== 'true'); });
    document.addEventListener('keydown', function(e){
      if(e.key === 'Escape' && b.getAttribute('aria-expanded') === 'true'){ set(false); b.focus(); }
    });
    nav.addEventListener('click', function(e){ if(e.target.closest('a')){ set(false); } });
  }

  // "On this page" marks the last section heading above the top part of the window.
  function sections(){
    var links = document.querySelectorAll('.toc a');
    if(!links.length){ return; }
    var heads = [];
    Array.prototype.forEach.call(links, function(a){
      var h = document.getElementById(a.getAttribute('href').slice(1));
      if(h){ heads.push({h:h, a:a}); }
    });
    var ticking = false;
    function mark(){
      ticking = false;
      var line = 96, now = null;
      heads.forEach(function(x){ if(x.h.getBoundingClientRect().top <= line){ now = x; } });
      heads.forEach(function(x){
        if(x === now){ x.a.setAttribute('aria-current', 'true'); } else { x.a.removeAttribute('aria-current'); }
      });
    }
    window.addEventListener('scroll', function(){
      if(!ticking){ ticking = true; window.requestAnimationFrame(mark); }
    }, {passive:true});
    mark();
  }

  function copies(){
    if(!navigator.clipboard || !window.isSecureContext){ return; }
    each('[data-copy]', function(b){
      b.hidden = false;
      b.addEventListener('click', function(){
        navigator.clipboard.writeText(b.getAttribute('data-copy')).then(function(){
          b.textContent = 'Copied';
          window.setTimeout(function(){ b.textContent = 'Copy'; }, 1600);
        }, function(){ b.textContent = 'Copy'; });
      });
    });
  }

  themes();
  menu();
  sections();
  copies();
})();
