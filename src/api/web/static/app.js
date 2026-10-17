(() => {
  'use strict';
  const query = (selector, root = document) => root.querySelector(selector);
  const all = (selector, root = document) => [...root.querySelectorAll(selector)];
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const csrf = () => query('meta[name="csrf-token"]').content;
  let maps = [], layers = [], mapRequest, panelFocus;
  const icons = () => window.lucide?.createIcons();
  const notify = message => { query('#global-feedback').textContent = message; };
  const animate = (target, from) => {
    if (!reduced.matches && window.gsap && target) gsap.fromTo(target, from, { opacity: 1, x: 0, y: 0, duration: .24, ease: 'power2.out', clearProps: 'transform,opacity' });
  };
  async function json(url, options = {}) {
    const response = await fetch(url, { credentials: 'same-origin', ...options });
    if (response.status === 401) { location.assign('/signin'); throw new Error('Session expirée.'); }
    if (!response.ok) throw new Error('La requête a échoué. Vérifiez la sélection et réessayez.');
    return response.json();
  }
  function createMap(identifier) {
    const map = L.map(identifier, { zoomControl: true, worldCopyJump: true }).setView([32, 10], 3);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(map);
    maps.push(map);
    return map;
  }
  function closePanel() {
    query('#panel-root').replaceChildren();
    query('#workspace').inert = false;
    query('.app-header').inert = false;
    if (panelFocus?.isConnected) panelFocus.focus();
  }
  function clearMaps() {
    mapRequest?.abort();
    maps.forEach(map => map.remove());
    maps = []; layers = [];
  }
  function syncTheme() {
    const preference = document.documentElement.dataset.theme;
    const dark = preference === 'dark' || (preference === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
    all('[data-theme-toggle]').forEach(button => {
      button.setAttribute('aria-checked', String(dark));
      query('[name="theme"]', button.form).value = dark ? 'light' : 'dark';
    });
  }
  function style(color) { return { color, weight: 2, fillColor: color, fillOpacity: .22 }; }
  function draw(data, map, color, changes = false) {
    const layer = L.geoJSON(data, { style: item => style(changes ? ({ added: '#21a16e', removed: '#d85c55', shared: '#d8ac43' }[item.properties.change]) : color) }).addTo(map);
    layers.push(layer);
    return layer;
  }
  async function renderMaps() {
    const first = query('#map-first'), second = query('#map-second');
    if (!first || !maps.length) return;
    mapRequest?.abort();
    mapRequest = new AbortController();
    const options = { signal: mapRequest.signal };
    layers.forEach(layer => layer.remove()); layers = [];
    const split = query('[name="map-mode"]:checked').value === 'split';
    const diff = query('#map-diff').checked && first.value && second.value;
    query('#map-secondary').hidden = !split;
    query('#map-details').disabled = !first.value;
    all('.diff-key').forEach(item => { item.hidden = !diff; });
    all('[data-map-id]').forEach(item => item.classList.toggle('selected', item.dataset.mapId === first.value));
    maps.forEach(map => map.invalidateSize());
    query('#map-status').textContent = first.value ? 'Chargement…' : 'Choisir une zone';
    try {
      const identifiers = [first.value, second.value];
      const data = await Promise.all(identifiers.map(identifier => identifier ? json(`/maps/${identifier}.geojson`, options) : null));
      if (options.signal.aborted) return;
      data.forEach((item, index) => {
        if (!item) return;
        draw(item, maps[split ? index : 0], index ? '#416dc5' : '#247d71');
      });
      if (diff) {
        const changes = await json(`/maps/difference?first=${first.value}&second=${second.value}`, options);
        if (options.signal.aborted) return;
        if (!split) { layers.forEach(layer => layer.remove()); layers = []; }
        draw(changes, maps[0], '', true);
        if (split) draw(changes, maps[1], '', true);
      }
      const bounds = L.featureGroup(layers.filter(layer => layer.getBounds().isValid())).getBounds();
      if (bounds.isValid()) maps.forEach(map => map.fitBounds(bounds, { padding: [25, 25], maxZoom: 12, animate: !reduced.matches }));
      query('#map-status').textContent = first.value ? `${first.selectedOptions[0].textContent}${second.value ? ' / ' + second.selectedOptions[0].textContent : ''}` : 'Choisir une zone';
    } catch (error) { if (error.name !== 'AbortError') notify(error.message); }
  }
  function init() {
    icons(); syncTheme();
    const page = query('[data-page]');
    all('.tabs .nav-link').forEach(link => {
      const active = new URL(link.href || location.href).pathname === location.pathname;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
    query('.map-menu > summary')?.classList.toggle('active', page?.dataset.page === 'maps');
    if (query('#map-primary')) {
      createMap('map-primary'); createMap('map-secondary');
      ['#map-first', '#map-second', '#map-diff'].forEach(selector => query(selector).addEventListener('change', renderMaps));
      all('[name="map-mode"]').forEach(input => input.addEventListener('change', renderMaps));
      const source = query('#map-first');
      query('#nav-map-select').innerHTML = source.innerHTML;
      void renderMaps();
      query('#map-details').onclick = () => htmx.ajax('GET', `/catalogs/${source.value}`, { target: '#panel-root' });
    }
    if (query('#builder-map')) createMap('builder-map');
    animate(page, { opacity: 0, y: 6 });
  }
  document.addEventListener('htmx:configRequest', event => { event.detail.headers['X-CSRFToken'] = csrf(); });
  document.addEventListener('htmx:beforeSwap', event => {
    if (event.detail.xhr.status === 422 || event.detail.xhr.status === 409) { event.detail.shouldSwap = true; event.detail.isError = false; }
    if (event.detail.target.id === 'workspace' && event.detail.shouldSwap) { clearMaps(); closePanel(); }
    if (event.detail.target.id === 'panel-root') panelFocus = document.activeElement;
  });
  document.addEventListener('htmx:afterSwap', event => {
    icons();
    if (event.detail.target.id === 'workspace') {
      all('details[open]').forEach(details => { details.open = false; });
      init(); query('#workspace').focus({ preventScroll: true });
    }
    if (event.detail.target.id === 'panel-root') {
      const panel = query('.side-panel');
      query('#workspace').inert = true; query('.app-header').inert = true;
      animate(panel, { opacity: 0, x: 30 }); query('button', panel)?.focus();
    }
  });
  document.addEventListener('htmx:responseError', event => {
    if (event.detail.xhr.status === 401) location.assign('/signin');
    else notify(event.detail.xhr.status === 403 ? 'Accès refusé.' : 'Une erreur est survenue. Réessayez.');
  });
  document.addEventListener('htmx:sendError', () => notify('Connexion au serveur indisponible.'));
  document.addEventListener('click', async event => {
    const target = event.target.closest('button, a, [data-close-panel]');
    if (!target) return;
    notify('');
    if (target.matches('[data-close-panel]')) closePanel();
    if (target.matches('[data-cancel-confirm]')) {
      query(target.dataset.cancelConfirm || '#source-confirm')?.replaceChildren();
    }
    if (target.matches('[data-add-source]')) {
      const fragment = query('#operation-template').content.cloneNode(true);
      query('[name="source_id"]', fragment).value = target.dataset.addSource;
      query('.operation-source', fragment).textContent = target.dataset.sourceName;
      const code = document.createElement('small'); code.textContent = target.dataset.sourceCode;
      query('.operation-source', fragment).append(code); query('#operation-list').append(fragment); icons();
    }
    if (target.matches('[data-remove-step]')) target.closest('.operation-row').remove();
    if (target.matches('[data-move]')) {
      const row = target.closest('.operation-row'), previous = row.previousElementSibling, next = row.nextElementSibling;
      if (target.dataset.move === '-1' && previous) row.parentNode.insertBefore(row, previous);
      if (target.dataset.move === '1' && next) row.parentNode.insertBefore(next, row);
    }
    if (target.matches('[data-map-id]')) { query('#map-first').value = target.dataset.mapId; await renderMaps(); }
    if (target.id === 'preview-button') {
      const form = query('#builder-form');
      if (!form.reportValidity()) return;
      target.disabled = true; query('#preview-status').textContent = 'Calcul…';
      try {
        const response = await fetch('/builder/preview', { method: 'POST', body: new FormData(form), headers: { 'X-CSRFToken': csrf() } });
        if (!response.ok) { query('#builder-feedback').innerHTML = await response.text(); query('#preview-status').textContent = 'Calcul refusé'; return; }
        layers.forEach(layer => layer.remove()); layers = [];
        const layer = draw(await response.json(), maps[0], '#247d71');
        maps[0].fitBounds(layer.getBounds(), { padding: [20, 20], maxZoom: 12, animate: !reduced.matches });
        query('#preview-status').textContent = 'Aperçu à jour'; query('#builder-feedback').replaceChildren();
      } catch (error) { notify(error.message); }
      finally { target.disabled = false; }
    }
    if (target.matches('[data-logout]')) {
      const response = await fetch('/auth/logout', { method: 'POST', headers: { 'X-CSRFToken': csrf() } });
      if (response.ok) location.assign('/signin'); else notify('La déconnexion a échoué.');
    }
  });
  document.addEventListener('change', event => {
    if (event.target.matches('[data-select-all]')) all('[name="source_id"]', event.target.form).forEach(input => { input.checked = event.target.checked; });
    if (event.target.closest('#builder-form')) { if (query('#preview-status')) query('#preview-status').textContent = 'Aperçu à recalculer'; }
  });
  document.addEventListener('input', event => {
    if (event.target.matches('[data-filter-maps]')) all('.map-record').forEach(record => { record.hidden = !record.textContent.toLocaleLowerCase().includes(event.target.value.toLocaleLowerCase()); });
  });
  document.addEventListener('keydown', event => {
    if (!query('.side-panel')) return;
    if (event.key === 'Escape') closePanel();
    if (event.key === 'Tab') {
      const focusable = all('button, a[href], select, input', query('.side-panel')).filter(item => !item.disabled);
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  document.addEventListener('submit', async event => {
    if (event.target.id !== 'signin-form') return;
    event.preventDefault();
    const form = event.target, button = query('button', form); button.disabled = true;
    try {
      const response = await fetch('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify(Object.fromEntries(new FormData(form))) });
      if (response.ok) location.assign('/'); else query('#signin-feedback').textContent = response.status === 401 ? 'Identifiant ou mot de passe incorrect.' : 'Connexion impossible.';
    } catch { query('#signin-feedback').textContent = 'Serveur indisponible.'; }
    finally { button.disabled = false; }
  });
  document.addEventListener('toggle', async event => {
    if (!event.target.matches('.map-menu') || !event.target.open || query('#nav-map-select option[value]:not([value=""])')) return;
    try {
      const records = await json('/maps/options');
      records.forEach(record => query('#nav-map-select').add(new Option(`${record.name} · ${record.code} · v${record.version}`, record.id)));
    } catch (error) { notify(error.message); }
  }, true);
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', syncTheme);
  init();
})();