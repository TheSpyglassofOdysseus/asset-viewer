let state = {
  collections: [],
  images: [],
  filtered: [],
  current: 0,
  csrf: '',
  selected: new Set(),
  active: '',
  reviewState: null,
  compareAssets: [],
  compareMode: 'side',
};

const $ = selector => document.querySelector(selector);
const grid = $('#grid');
const modal = $('#modal');
const compareModal = $('#compareModal');
const esc = value => String(value).replace(/[&<>\"]/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[char]));
const keyFor = asset => asset.asset_id || asset.rel;
const assetSrc = asset => asset.preview || asset.thumb;

function collectionFromLocation() {
  const match = location.pathname.match(/^\/c\/([^/]+)$/);
  if (match) return decodeURIComponent(match[1]);
  return new URLSearchParams(location.search).get('collection') || '';
}

function collectionUrl(slug) {
  return '/c/' + encodeURIComponent(slug);
}

function assetFromLocation() {
  return new URLSearchParams(location.search).get('asset') || '';
}

function assetUrl(asset) {
  return collectionUrl(asset.collection) + '?asset=' + encodeURIComponent(asset.asset_id || asset.rel);
}

async function session() {
  const response = await fetch('/api/session', {cache: 'no-store'});
  if (!response.ok) throw new Error('Session request failed');
  const data = await response.json();
  state.csrf = data.csrf;
}

async function apiPost(path, payload) {
  const response = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Asset-Viewer-CSRF': state.csrf},
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

async function load(requested, force = false) {
  const requestedAsset = assetFromLocation();
  const desired = requested || state.active || collectionFromLocation();
  const params = new URLSearchParams();
  if (desired) params.set('collection', desired);
  if (force) params.set('refresh', '1');
  const response = await fetch('/api/gallery' + (params.toString() ? '?' + params : ''), {cache: 'no-store'});
  if (!response.ok) throw new Error('Gallery request failed');
  const data = await response.json();
  state.collections = data.collections;
  state.images = data.images;
  state.active = data.active;
  state.reviewState = data.review_state;
  state.selected.clear();
  renderCollections(data.active);
  applyFilter();
  updateBulk();
  updateReviewState();
  if (data.active && location.pathname !== collectionUrl(data.active)) {
    history.replaceState(null, '', collectionUrl(data.active));
  }

  const scan = data.scan || {};
  const trunc = scan.truncated ? ` · scan incomplete (${scan.reason})` : '';
  const delta = (scan.added || scan.changed || scan.removed || scan.renamed)
    ? ` · scan +${scan.added || 0} ~${scan.changed || 0} -${scan.removed || 0} ↪${scan.renamed || 0}`
    : '';
  const review = state.reviewState;
  const pending = review
    ? ` · ${review.unreviewed} unreviewed · ${review.complete ? 'review complete' : 'review pending'}`
    : '';
  $('#summary').textContent = `${data.images.length} images · ${data.collections.length} collections${pending}${trunc}${delta}`;
  if (requestedAsset) {
    const index = state.filtered.findIndex(asset => (asset.asset_id || asset.rel) === requestedAsset);
    if (index >= 0) openAt(index, false);
  }
}

function renderCollections(active) {
  const select = $('#collection');
  select.innerHTML = state.collections.map(collection =>
    `<option value="${esc(collection.slug)}">${esc(collection.label)}${collection.available === false ? ' — unavailable' : ''}</option>`
  ).join('');
  if (active && state.collections.some(collection => collection.slug === active)) select.value = active;
}

function applyFilter() {
  const filter = $('#filter').value;
  const query = $('#search').value.trim().toLowerCase();
  const sort = $('#sort').value;
  let rows = state.images.filter(asset => {
    const statusMatch = filter === 'all' ||
      (filter === 'new' ? asset.is_new : (filter === 'unreviewed' ? !asset.status : asset.status === filter));
    const haystack = `${asset.name} ${asset.rel} ${asset.comment || ''}`.toLowerCase();
    return statusMatch && (!query || haystack.includes(query));
  });
  const rank = {'': 0, maybe: 1, approved: 2, rejected: 3};
  rows = [...rows].sort((a, b) => {
    if (sort === 'oldest') return a.mtime - b.mtime;
    if (sort === 'name') return a.rel.localeCompare(b.rel);
    if (sort === 'status') return (rank[a.status] - rank[b.status]) || a.rel.localeCompare(b.rel);
    if (sort === 'size') return b.size - a.size || a.rel.localeCompare(b.rel);
    if (sort === 'resolution') return ((b.width || 0) * (b.height || 0)) - ((a.width || 0) * (a.height || 0));
    return b.mtime - a.mtime;
  });
  state.filtered = rows;
  grid.innerHTML = rows.map((asset, index) => {
    const selected = state.selected.has(keyFor(asset));
    return `<article class="card ${selected ? 'selected' : ''}" data-i="${index}" tabindex="0">
      <button class="select-toggle" data-select="${index}" type="button" aria-label="${selected ? 'Deselect' : 'Select'} ${esc(asset.name)}">${selected ? '✓' : '+'}</button>
      <img class="thumb" loading="lazy" src="${esc(asset.thumb)}" alt="">
      <span class="badge ${esc(asset.status || '')}">${esc(asset.status || 'unreviewed')}</span>
      <div class="caption">
        <div class="name">${esc(asset.name)}</div>
        <div class="path">${esc(asset.rel)}</div>
        <div class="meta-row">${asset.is_new ? '<span class="new-dot">new</span>' : ''}${asset.comment ? '<span class="note-dot">note</span>' : ''}</div>
      </div>
    </article>`;
  }).join('');
  $('#empty').classList.toggle('hidden', rows.length > 0);
  grid.querySelectorAll('.card').forEach(element => {
    element.onclick = event => {
      if (event.target.closest('[data-select]')) return;
      openAt(Number(element.dataset.i));
    };
    element.onkeydown = event => {
      if ((event.key === 'Enter' || event.key === ' ') && !event.target.closest('[data-select]')) {
        event.preventDefault();
        openAt(Number(element.dataset.i));
      }
    };
  });
  grid.querySelectorAll('[data-select]').forEach(button => {
    button.onclick = event => {
      event.stopPropagation();
      toggleSelection(Number(button.dataset.select));
    };
  });
}

function toggleSelection(index) {
  const asset = state.filtered[index];
  const key = keyFor(asset);
  state.selected.has(key) ? state.selected.delete(key) : state.selected.add(key);
  applyFilter();
  updateBulk();
}

function updateBulk() {
  const count = state.selected.size;
  $('#bulkbar').classList.toggle('hidden', count === 0);
  $('#selectedCount').textContent = `${count} selected`;
  $('#compare').disabled = count < 2;
}

function updateReviewState() {
  const button = $('#reviewComplete');
  const review = state.reviewState;
  if (!review) {
    button.disabled = true;
    button.textContent = 'Review status';
    return;
  }
  button.classList.toggle('complete-state', review.complete);
  if (review.scan_incomplete) {
    button.textContent = 'Scan incomplete';
    button.disabled = true;
  } else if (review.empty) {
    button.textContent = 'No assets';
    button.disabled = true;
  } else if (review.complete) {
    button.textContent = '✓ Review complete';
    button.disabled = false;
  } else if (review.unreviewed > 0) {
    button.textContent = `${review.unreviewed} left to review`;
    button.disabled = true;
  } else if (review.stale) {
    button.textContent = 'Re-complete review';
    button.disabled = false;
  } else {
    button.textContent = 'Mark review complete';
    button.disabled = false;
  }
}

async function refreshReviewState() {
  if (!state.active) return;
  const response = await fetch('/api/pending?collection=' + encodeURIComponent(state.active), {cache: 'no-store'});
  if (!response.ok) return;
  const data = await response.json();
  state.reviewState = data.collections[0] || null;
  updateReviewState();
}

function openAt(index, updateUrl = true) {
  if (!state.filtered.length) return;
  state.current = (index + state.filtered.length) % state.filtered.length;
  const asset = state.filtered[state.current];
  $('#full').src = assetSrc(asset);
  $('#full').alt = asset.name;
  $('#filename').textContent = asset.name;
  $('#details').textContent = `${asset.rel} · ${asset.width || '?'}×${asset.height || '?'} · ${formatBytes(asset.size)}`;
  $('#original').href = asset.file;
  $('#comment').value = asset.comment || '';
  $('#historyPanel').classList.add('hidden');
  const notice = $('#previewNotice');
  notice.textContent = asset.preview_error || '';
  notice.classList.toggle('hidden', !asset.preview_error);
  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  if (updateUrl && asset.asset_id) history.replaceState(null, '', assetUrl(asset));
  if (asset.is_new) {
    asset.is_new = false;
    apiPost('/api/seen', {collection: asset.collection, rel: asset.rel}).then(refreshReviewState).catch(console.error);
  }
}

function close() {
  modal.classList.add('hidden');
  $('#full').src = '';
  if (state.active) history.replaceState(null, '', collectionUrl(state.active));
  if (compareModal.classList.contains('hidden')) document.body.style.overflow = '';
}

const step = amount => openAt(state.current + amount);

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
  return (bytes / 1073741824).toFixed(2) + ' GB';
}

function updateLocal(assetOrRel, patch) {
  const asset = state.images.find(item => item.asset_id === assetOrRel || item.rel === assetOrRel);
  if (asset) Object.assign(asset, patch);
}

async function review(status) {
  const asset = state.filtered[state.current];
  const comment = $('#comment').value;
  await apiPost('/api/review', {collection: asset.collection, asset_id: asset.asset_id, status, comment});
  updateLocal(asset.asset_id || asset.rel, {status, comment, is_new: false});
  applyFilter();
  await refreshReviewState();
  const index = state.filtered.findIndex(item => keyFor(item) === keyFor(asset));
  if (index >= 0) openAt(index); else close();
}

async function saveComment() {
  const asset = state.filtered[state.current];
  const comment = $('#comment').value;
  await apiPost('/api/comment', {collection: asset.collection, asset_id: asset.asset_id, comment});
  updateLocal(asset.asset_id || asset.rel, {comment, is_new: false});
  applyFilter();
  await refreshReviewState();
}

async function bulkReview(status) {
  const assets = state.images.filter(asset => state.selected.has(keyFor(asset)));
  const rels = assets.map(asset => asset.rel);
  if (!rels.length) return;
  await apiPost('/api/review', {collection: state.active, rels, status});
  for (const asset of assets) updateLocal(asset.asset_id || asset.rel, {status, is_new: false});
  state.selected.clear();
  applyFilter();
  updateBulk();
  await refreshReviewState();
}

async function undoReview() {
  const asset = state.filtered[state.current];
  const data = await apiPost('/api/undo', {collection: asset.collection, asset_id: asset.asset_id});
  updateLocal(asset.asset_id || asset.rel, {status: data.result.status, comment: data.result.comment});
  $('#comment').value = data.result.comment;
  applyFilter();
  await refreshReviewState();
  await showHistory(asset.asset_id);
}

async function showHistory(assetIdOverride) {
  const asset = assetIdOverride
    ? state.images.find(item => item.asset_id === assetIdOverride || item.rel === assetIdOverride)
    : state.filtered[state.current];
  if (!asset) return;
  const params = new URLSearchParams({collection: asset.collection, asset_id: asset.asset_id || '', rel: asset.rel});
  const response = await fetch('/api/review-history?' + params, {cache: 'no-store'});
  if (!response.ok) throw new Error('History request failed');
  const data = await response.json();
  const panel = $('#historyPanel');
  panel.innerHTML = data.events.length ? data.events.map(event =>
    `<div class="history-event"><strong>${esc(event.action.replaceAll('_', ' '))}</strong><span>${esc(event.created_at)} · ${esc(event.old_status || 'unreviewed')} → ${esc(event.new_status || 'unreviewed')}${event.undone_at ? ' · undone' : ''}</span></div>`
  ).join('') : '<div class="history-event"><span>No review changes yet.</span></div>';
  panel.classList.remove('hidden');
}

async function toggleComplete() {
  if (!state.reviewState) return;
  const path = state.reviewState.complete ? '/api/reopen' : '/api/complete';
  const data = await apiPost(path, {collection: state.active});
  state.reviewState = data.review_state;
  updateReviewState();
}

async function copyPath() {
  const asset = state.filtered[state.current];
  if (!asset) return;
  await navigator.clipboard.writeText(asset.rel);
  const button = $('#copyPath');
  const original = button.textContent;
  button.textContent = 'Copied';
  setTimeout(() => { button.textContent = original; }, 900);
}

async function copyReviewLink() {
  const asset = state.filtered[state.current];
  if (!asset) return;
  await navigator.clipboard.writeText(location.origin + assetUrl(asset));
  const button = $('#copyReviewLink');
  const original = button.textContent;
  button.textContent = 'Copied';
  setTimeout(() => { button.textContent = original; }, 900);
}

function clearSelection() {
  state.selected.clear();
  applyFilter();
  updateBulk();
}

function selectedAssets() {
  return state.images.filter(asset => state.selected.has(keyFor(asset))).slice(0, 4);
}

function renderCompare() {
  const assets = state.compareAssets;
  const gridElement = $('#compareGrid');
  const overlayControl = $('#overlayControl');
  document.querySelectorAll('[data-compare-mode]').forEach(button => {
    const needsTwo = button.dataset.compareMode !== 'side';
    button.disabled = needsTwo && assets.length !== 2;
    button.classList.toggle('active', button.dataset.compareMode === state.compareMode);
  });
  if (state.compareMode !== 'side' && assets.length !== 2) state.compareMode = 'side';
  overlayControl.classList.toggle('hidden', state.compareMode !== 'overlay');

  if (state.compareMode === 'side') {
    $('#compareHint').textContent = 'Side by side supports up to four assets.';
    gridElement.className = 'compare-grid';
    gridElement.innerHTML = assets.map(asset =>
      `<article class="compare-item"><img src="${esc(assetSrc(asset))}" alt=""><div><strong>${esc(asset.name)}</strong><span>${esc(asset.status || 'unreviewed')}${asset.comment ? ' · ' + esc(asset.comment) : ''}</span></div></article>`
    ).join('');
    return;
  }

  const [left, right] = assets;
  const difference = state.compareMode === 'difference';
  $('#compareHint').textContent = difference
    ? 'Difference mode is clearest for equally sized variants.'
    : 'Blend between two variants to spot composition changes.';
  gridElement.className = 'compare-grid compare-single';
  gridElement.innerHTML = `<div class="compare-stack ${difference ? 'difference' : ''}">
    <img class="compare-bottom" src="${esc(assetSrc(left))}" alt="${esc(left.name)}">
    <img class="compare-top" src="${esc(assetSrc(right))}" alt="${esc(right.name)}" style="opacity:${difference ? 1 : Number($('#overlayRange').value) / 100}">
    <div class="compare-stack-labels"><span>${esc(left.name)}</span><span>${esc(right.name)}</span></div>
  </div>`;
}

function setCompareMode(mode) {
  if (mode !== 'side' && state.compareAssets.length !== 2) return;
  state.compareMode = mode;
  renderCompare();
}

function openCompare() {
  state.compareAssets = selectedAssets();
  if (state.compareAssets.length < 2) return;
  state.compareMode = 'side';
  $('#overlayRange').value = '50';
  renderCompare();
  compareModal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeCompare() {
  compareModal.classList.add('hidden');
  if (modal.classList.contains('hidden')) document.body.style.overflow = '';
}

$('#collection').onchange = () => {
  const slug = $('#collection').value;
  history.pushState(null, '', collectionUrl(slug));
  load(slug).catch(showError);
};
$('#filter').onchange = applyFilter;
$('#sort').onchange = applyFilter;
$('#search').oninput = applyFilter;
$('#refresh').onclick = () => load(state.active, true).catch(showError);
$('#reviewComplete').onclick = () => toggleComplete().catch(showError);
$('#close').onclick = close;
$('#prev').onclick = () => step(-1);
$('#next').onclick = () => step(1);
$('#saveComment').onclick = () => saveComment().catch(showError);
$('#undoReview').onclick = () => undoReview().catch(showError);
$('#showHistory').onclick = () => showHistory().catch(showError);
$('#copyPath').onclick = () => copyPath().catch(showError);
$('#copyReviewLink').onclick = () => copyReviewLink().catch(showError);
$('#compare').onclick = openCompare;
$('#closeCompare').onclick = closeCompare;
$('#clearSelection').onclick = clearSelection;
$('#overlayRange').oninput = () => {
  const top = $('#compareGrid .compare-top');
  if (top && state.compareMode === 'overlay') top.style.opacity = Number($('#overlayRange').value) / 100;
};
document.querySelectorAll('.review button[data-status]').forEach(button => {
  button.onclick = () => review(button.dataset.status).catch(showError);
});
document.querySelectorAll('[data-bulk-status]').forEach(button => {
  button.onclick = () => bulkReview(button.dataset.bulkStatus).catch(showError);
});
document.querySelectorAll('[data-compare-mode]').forEach(button => {
  button.onclick = () => setCompareMode(button.dataset.compareMode);
});

window.onpopstate = () => load(collectionFromLocation()).catch(showError);
document.onkeydown = event => {
  if (!compareModal.classList.contains('hidden')) {
    if (event.key === 'Escape') closeCompare();
    return;
  }
  if (modal.classList.contains('hidden')) return;
  if (event.target && (event.target.tagName === 'TEXTAREA' || event.target.tagName === 'INPUT')) return;
  if (event.key === 'Escape') close();
  else if (event.key === 'ArrowLeft') step(-1);
  else if (event.key === 'ArrowRight') step(1);
  else if (event.key.toLowerCase() === 'a') review('approved').catch(showError);
  else if (event.key.toLowerCase() === 'm') review('maybe').catch(showError);
  else if (event.key.toLowerCase() === 'r') review('rejected').catch(showError);
};

function showError(error) {
  console.error(error);
  $('#summary').textContent = error.message || 'Viewer error';
}

(async () => {
  try {
    await session();
    await load(collectionFromLocation());
  } catch (error) {
    showError(error);
  }
})();
