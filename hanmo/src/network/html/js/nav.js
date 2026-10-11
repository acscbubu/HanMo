// Shared page chrome: the sidebar order, and the name and version line at the
// top of the page.
//
// Each group of links is its own container, so a drag can only reorder within
// the group it started in. The order lives in localStorage rather than on the
// device: it is a per-browser display preference and the firmware never reads
// it back. A saved order that no longer matches the links is not an error --
// keys we recognise are placed first and anything new keeps its markup
// position after them.
(function () {
  'use strict';

  var PREFIX = 'crossmux.nav.';
  // How far a press has to travel before it counts as a drag instead of a tap.
  var DRAG_THRESHOLD = 5;

  function storageKey(container) {
    // Category names are localised, so an order saved in one language must not
    // be applied to another.
    var lang = document.documentElement.lang;
    // One-time key migration: old four-item orders must not push Device to the end.
    // Subsequent drag preferences still persist; other groups keep their keys.
    var group = container.dataset.navGroup;
    return PREFIX + group + (group === 'pages' ? '.v2' : '') + (lang ? '.' + lang : '');
  }

  function items(container) {
    return Array.prototype.filter.call(container.children, function (el) {
      return el.dataset.navKey !== undefined;
    });
  }

  function save(container) {
    var order = items(container).map(function (el) { return el.dataset.navKey; });
    try {
      localStorage.setItem(storageKey(container), JSON.stringify(order));
    } catch (e) {
      // Private browsing or a full quota: the order just will not stick.
    }
  }

  function applySavedOrder(container) {
    var saved = null;
    try {
      saved = JSON.parse(localStorage.getItem(storageKey(container)));
    } catch (e) {
      saved = null;
    }
    if (!Array.isArray(saved) || !saved.length) return;

    var current = items(container);
    var remaining = {};
    current.forEach(function (el) { remaining[el.dataset.navKey] = el; });

    var ordered = [];
    saved.forEach(function (key) {
      if (remaining[key]) {
        ordered.push(remaining[key]);
        delete remaining[key];
      }
    });
    current.forEach(function (el) {
      if (remaining[el.dataset.navKey]) ordered.push(el);
    });
    ordered.forEach(function (el) { container.appendChild(el); });
    var languageSwitch = container.querySelector(".web-language-switch");
    if (languageSwitch) container.appendChild(languageSwitch);
  }

  // A stacked column is decided along y. A wrapped row or a grid has to pick
  // the row first and only then the position inside it.
  function isVertical(container) {
    var list = items(container);
    if (list.length < 2) return true;
    var first = list[0].getBoundingClientRect();
    var second = list[1].getBoundingClientRect();
    return Math.abs(second.top - first.top) >= Math.abs(second.left - first.left);
  }

  function goesBefore(target, x, y, vertical) {
    var rect = target.getBoundingClientRect();
    if (vertical) return y < rect.top + rect.height / 2;
    if (y < rect.top) return true;
    if (y > rect.bottom) return false;
    return x < rect.left + rect.width / 2;
  }

  // A drag ends on the link itself, so the browser would otherwise follow it.
  // Swallow that one click, and stop waiting if it never arrives (touch).
  function swallowNextClick(item) {
    function done() {
      item.removeEventListener('click', onClick, true);
      clearTimeout(timer);
    }
    function onClick(event) {
      event.preventDefault();
      event.stopPropagation();
      done();
    }
    var timer = setTimeout(done, 400);
    item.addEventListener('click', onClick, true);
  }

  function beginDrag(container, item, startX, startY) {
    var vertical = isVertical(container);
    var origNext = item.nextSibling;
    var dragging = false;

    function move(event) {
      if (!dragging) {
        if (Math.abs(event.clientX - startX) < DRAG_THRESHOLD &&
            Math.abs(event.clientY - startY) < DRAG_THRESHOLD) {
          return;
        }
        dragging = true;
        item.classList.add('nav-dragging');
        container.classList.add('nav-reordering');
      }
      event.preventDefault();
      // .nav-dragging takes the item out of hit testing, so this reports
      // whatever sits under the pointer rather than the item being dragged.
      var under = document.elementFromPoint(event.clientX, event.clientY);
      var target = under && under.closest ? under.closest('[data-nav-key]') : null;
      if (!target || target.parentElement !== container) return;
      container.insertBefore(
        item,
        goesBefore(target, event.clientX, event.clientY, vertical) ? target : target.nextSibling);
    }

    function finish(event) {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', finish);
      window.removeEventListener('pointercancel', finish);
      if (!dragging) return;
      item.classList.remove('nav-dragging');
      container.classList.remove('nav-reordering');
      if (event.type === 'pointerup') {
        save(container);
        swallowNextClick(item);
      } else {
        // The gesture was taken away from us; put the item back where it was.
        container.insertBefore(item, origNext);
      }
    }

    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', finish);
    window.addEventListener('pointercancel', finish);
  }

  function bind(container) {
    if (container.dataset.navBound) return;
    container.dataset.navBound = '1';
    container.addEventListener('pointerdown', function (event) {
      if (event.button) return;
      var item = event.target.closest ? event.target.closest('[data-nav-key]') : null;
      if (!item || item.parentElement !== container) return;
      beginDrag(container, item, event.clientX, event.clientY);
    });
  }

  // Safe to call again once a group has been filled in at runtime.
  function refresh() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-nav-group]'), function (container) {
      applySavedOrder(container);
      bind(container);
    });
  }

  // ---- Browser-only language selector -------------------------------------
  // The device language remains untouched. The query is carried by sidebar
  // links so each of the three page bundles can be chosen per browser.
  var WEB_UI_STORAGE_KEY = 'hanmo.web-ui';

  function supportedWebLanguage(value) {
    return value === 'en' || value === 'zh-CN' || value === 'zh-Hant' ? value : null;
  }

  function savedWebLanguage() {
    try {
      return supportedWebLanguage(localStorage.getItem(WEB_UI_STORAGE_KEY));
    } catch (e) { return null; /* private browsing: use the page's default */ }
  }

  function currentWebLanguage() {
    return supportedWebLanguage(document.documentElement.lang) || 'en';
  }

  function pageWithWebLanguage(value, href) {
    var url = new URL(href || window.location.href);
    url.searchParams.set('ui', value);
    return url.pathname + url.search + url.hash;
  }

  function setupWebLanguage() {
    var nav = document.querySelector('.shell > .nav-links');
    if (!nav || document.getElementById('web-language')) return;
    var url = new URL(window.location.href);
    var requested = url.searchParams.get('ui');
    var selected = supportedWebLanguage(requested) || savedWebLanguage();
    if (selected) {
      try { localStorage.setItem(WEB_UI_STORAGE_KEY, selected); } catch (e) { /* still usable */ }
    }
    var label = document.createElement('label');
    label.className = 'web-language-switch';
    label.textContent = currentWebLanguage() === 'en' ? 'Language' :
      currentWebLanguage() === 'zh-Hant' ? '\u8a9e\u8a00' : '\u8bed\u8a00';
    if (!document.getElementById('web-language-style')) {
      var style = document.createElement('style');
      style.id = 'web-language-style';
      style.textContent = '.web-language-switch{display:flex;flex-direction:column;gap:4px;' +
        'padding:8px 4px;font-size:0.85rem;}' +
        '.web-language-switch select{min-width:0;max-width:100%;min-height:44px;' +
        'font:inherit;color:inherit;background:inherit;border:1px solid currentColor;' +
        'border-radius:6px;padding:4px;}' +
        '@media(max-width:720px){.shell>.nav-links>.web-language-switch{grid-column:1/-1;}}';
      document.head.appendChild(style);
    }
    var picker = document.createElement('select');
    picker.id = 'web-language';
    picker.setAttribute('aria-label', label.textContent);
    picker.innerHTML = '<option value="en">English</option>' +
      '<option value="zh-CN">\u7b80\u4f53\u4e2d\u6587</option>' +
      '<option value="zh-Hant">\u7e41\u9ad4\u4e2d\u6587</option>';
    picker.value = selected || currentWebLanguage();
    picker.addEventListener('change', function () {
      try { localStorage.setItem(WEB_UI_STORAGE_KEY, picker.value); } catch (e) { /* continue */ }
      window.location.assign(pageWithWebLanguage(picker.value));
    });
    label.appendChild(picker);
    nav.appendChild(label);
    Array.prototype.forEach.call(document.querySelectorAll('[data-nav-group="pages"] a[href]'), function (link) {
      var href = link.getAttribute('href');
      if (!href || href.charAt(0) === '#' || /^[a-z]+:/i.test(href)) return;
      link.href = pageWithWebLanguage(picker.value, link.href);
    });
    // Opening a bookmark without a query still honours this browser's saved
    // choice; one reload selects the correct pre-compressed HTML bundle.
    if (selected && requested !== selected) window.location.replace(pageWithWebLanguage(selected));
  }

  // ---- Name and version ---------------------------------------------------
  // Whoever flashed this owns the name at the top of the page, so it is
  // fetched rather than baked into the markup and a pencil edits it in place.
  // It is stored on the device, not in this browser: the device is what was
  // renamed, and it should read the same from any phone in the house.
  var STYLE =
    '.brand{display:flex;align-items:center;justify-content:center;gap:10px;}' +
    '[data-brand]{display:inline-flex;align-items:center;gap:6px;}' +
    '.brand-edit{display:inline-flex;align-items:center;justify-content:center;' +
    // A fixed size rather than an em: the same control sits beside a heading
    // and beside a table row, and a thumb has to reach both.
    'width:26px;height:26px;padding:0;border:0;border-radius:6px;' +
    'background:transparent;color:inherit;opacity:0.4;cursor:pointer;}' +
    '.brand-edit:hover,.brand-edit:focus-visible{opacity:1;background:rgba(128,128,128,0.2);}' +
    '.brand-edit svg{width:16px;height:16px;}' +
    '.brand-input{font:inherit;color:inherit;background:transparent;border:0;' +
    'border-bottom:2px solid currentColor;padding:0 2px;min-width:6ch;}';

  var PENCIL =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>';

  var RENAME_LABEL = document.documentElement.lang === 'zh-CN' ? '\u91cd\u547d\u540d' :
    document.documentElement.lang === 'zh-Hant' ? '\u91cd\u65b0\u547d\u540d' : 'Rename';
  var pageTitle = document.title;
  var brandingRequest = null;

  function branding() {
    if (!brandingRequest) {
      brandingRequest = fetch('/api/branding')
        .then(function (response) { return response.ok ? response.json() : {}; })
        .catch(function () { return {}; });
    }
    return brandingRequest;
  }

  function brandText(host) {
    var text = host.querySelector('.brand-text');
    if (!text) {
      text = document.createElement('span');
      text.className = 'brand-text';
      text.textContent = host.textContent.trim();
      host.textContent = '';
      host.appendChild(text);
    }
    return text;
  }

  function paintBrand(saved) {
    Array.prototype.forEach.call(document.querySelectorAll('[data-brand]'), function (host) {
      var field = host.getAttribute('data-brand');
      var fallback = host.getAttribute('data-brand-default') || '';
      var value = (saved && saved[field]) || fallback;
      brandText(host).textContent = value;
      // The tab carries the same name inside a page-specific phrase, so swap
      // it out of whatever wording the page chose rather than rewriting it.
      if (field === 'title' && fallback && pageTitle.indexOf(fallback) >= 0) {
        document.title = pageTitle.split(fallback).join(value);
      }
    });
  }

  function editBrand(host) {
    var text = brandText(host);
    if (text.hidden) return;
    var field = host.getAttribute('data-brand');

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'brand-input';
    input.maxLength = 39;
    input.value = text.textContent;
    input.size = Math.max(input.value.length, 8);
    text.hidden = true;
    host.insertBefore(input, text);
    input.focus();
    input.select();

    function close(keep) {
      if (!input.parentNode) return;
      var typed = input.value.trim();
      input.parentNode.removeChild(input);
      text.hidden = false;
      if (!keep) return;
      var payload = {};
      payload[field] = typed;
      fetch('/api/branding', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      }).then(function (response) {
        return response.ok ? response.json() : branding();
      }).then(function (saved) {
        brandingRequest = Promise.resolve(saved);
        paintBrand(saved);
      });
    }

    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') close(true);
      else if (event.key === 'Escape') close(false);
    });
    input.addEventListener('blur', function () { close(true); });
  }

  function setupBrand() {
    var hosts = document.querySelectorAll('[data-brand]');
    if (!hosts.length) return;
    if (!document.getElementById('brand-style')) {
      var style = document.createElement('style');
      style.id = 'brand-style';
      style.textContent = STYLE;
      document.head.appendChild(style);
    }
    Array.prototype.forEach.call(hosts, function (host) {
      if (host.dataset.brandBound) return;
      host.dataset.brandBound = '1';
      if (!host.getAttribute('data-brand-default')) {
        host.setAttribute('data-brand-default', host.textContent.trim());
      }
      brandText(host);
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'brand-edit';
      button.title = RENAME_LABEL;
      button.setAttribute('aria-label', RENAME_LABEL);
      button.innerHTML = PENCIL;
      button.addEventListener('click', function () { editBrand(host); });
      host.appendChild(button);
    });
  }

  // Call again once a page has learned a better fallback, such as the build
  // version that /api/status reports.
  function refreshBranding() {
    setupBrand();
    branding().then(paintBrand);
  }

  window.crossmuxNav = {refresh: refresh, refreshBranding: refreshBranding};
  refresh();
  refreshBranding();
  setupWebLanguage();
})();
