// One logical character collection. Existing per-revision source registrations
// are read-only inputs and retain their original reviews and deep links.
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"]/g, character =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[character]));
const characterIdFromPath = () => {
  const match = location.pathname.match(/^\/characters\/(CHR-\d{3})$/i);
  return match ? match[1].toUpperCase() : null;
};
const revisionNumber = item => {
  const match = (item.slug + ' ' + item.label).match(/(?:^|[^a-z0-9])v0*(\d+)(?:[^0-9]|$)/i);
  return match ? Number(match[1]) : -1;
};
let roster = [];
let collectionIndex = new Map();
let selected = null;
let loadSequence = 0;

function renderRoster(query = '') {
  const normalized = query.trim().toLowerCase();
  const filtered = roster.filter(char =>
    [char.id, char.name, char.faction].join(' ').toLowerCase().includes(normalized));
  $('#roster').innerHTML = filtered.map(char =>
    `<a href="/characters/${encodeURIComponent(char.id)}" class="character-link${char.id === selected?.id ? ' active' : ''}"${char.id === selected?.id ? ' aria-current="page"' : ''}><span class="id">${esc(char.id)}</span><span class="name">${esc(char.name)}</span></a>`
  ).join('');
}

function revisionTitle(item) {
  const number = revisionNumber(item);
  return number >= 0 ? `Revision v${String(number).padStart(3, '0')}` : 'Earlier artwork';
}

async function loadRevision(item, details, sequence) {
  const body = details.querySelector('.revision-body');
  if (body.dataset.loaded === 'true' || body.dataset.loading === 'true') return;
  body.dataset.loading = 'true';
  body.textContent = 'Loading artwork…';
  try {
    const response = await fetch('/api/gallery?collection=' + encodeURIComponent(item.slug), {cache:'no-store'});
    if (!response.ok) throw new Error('Gallery unavailable');
    const data = await response.json();
    if (sequence !== loadSequence) return;
    const assets = (data.images || []).filter(asset => asset.present !== false);
    const statuses = assets.reduce((counts, asset) => {
      const status = asset.status || 'unreviewed';
      counts[status] = (counts[status] || 0) + 1;
      return counts;
    }, {});
    const statusText = ['approved','maybe','rejected','unreviewed']
      .filter(k => statuses[k]).map(k => `${statuses[k]} ${k}`).join(' · ');
    const header = `<div class="revision-meta"><span>${assets.length} image${assets.length === 1 ? '' : 's'}</span><span>${esc(statusText)}</span><a class="review-link" href="/c/${encodeURIComponent(item.slug)}">Review this revision</a></div>`;
    const tiles = assets.map(asset => {
      const link = `/c/${encodeURIComponent(item.slug)}?asset=${encodeURIComponent(asset.asset_id || asset.rel)}`;
      return `<a class="asset" href="${link}" title="Open review: ${esc(asset.name)}"><img src="${esc(asset.thumb)}" loading="lazy" alt="${esc(asset.name)}"><span class="asset-caption"><strong>${esc(asset.name)}</strong><small>${esc(asset.status || 'Needs review')}</small></span></a>`;
    }).join('');
    body.innerHTML = header + (tiles ? `<div class="assets">${tiles}</div>` : '<p>No images registered for this revision.</p>');
    body.dataset.loaded = 'true';
  } catch (error) {
    if (sequence === loadSequence) body.textContent = 'Could not load this revision. Please try again.';
  } finally {
    body.dataset.loading = 'false';
  }
}

async function openCharacter(id, replace = false) {
  const character = roster.find(item => item.id === id);
  if (!character) {
    $('#message').textContent = 'Character not found in the canonical roster.';
    $('#revisions').innerHTML = '';
    return;
  }
  const sequence = ++loadSequence;
  selected = character;
  if (!replace) history.pushState({character: character.id}, '', '/characters/' + character.id);
  document.title = `${character.id} — ${character.name} — Asset Viewer`;
  $('#characterTitle').textContent = `${character.id} — ${character.name}`;
  // This is the canonical *single* character collection API. Raw source
  // collection records are compatibility references, not top-level entries.
  const response = await fetch('/api/characters/' + encodeURIComponent(character.id), {cache:'no-store'});
  if (!response.ok) throw new Error('Character collection unavailable');
  const canonical = await response.json();
  if (sequence !== loadSequence) return;
  const rows = (canonical.revisions || []).map(revision => ({
    ...collectionIndex.get(revision.source_slug),
    slug: revision.source_slug,
    label: revision.label,
  }));
  $('#characterSummary').textContent = `${rows.length} revision${rows.length === 1 ? '' : 's'} · One character collection · Existing files and review decisions preserved`;
  $('#message').textContent = '';
  renderRoster($('#rosterSearch').value);
  if (!rows.length) {
    $('#revisions').innerHTML = '<div class="no-art">No artwork generated for this character yet.</div>';
    return;
  }
  $('#revisions').innerHTML = rows.map((row,index) =>
    `<details class="revision" data-revision="${esc(row.slug)}"${index === 0 ? ' open' : ''}><summary><span class="revision-title">${esc(revisionTitle(row))}</span><span class="revision-label">${esc(row.label)}</span></summary><div class="revision-body" aria-live="polite"></div></details>`
  ).join('');
  $('#revisions').querySelectorAll('details[data-revision]').forEach(details => {
    const item = collectionIndex.get(details.dataset.revision);
    details.addEventListener('toggle', () => {
      if (details.open) loadRevision(item, details, sequence);
    });
    if (details.open) loadRevision(item, details, sequence);
  });
}

async function initialize() {
  const response = await fetch('/api/gallery', {cache:'no-store'});
  if (!response.ok) throw new Error('Could not load the collection roster.');
  const result = await response.json();
  roster = result.roster || [];
  collectionIndex = new Map((result.collections || []).map(item => [item.slug,item]));
  $('#rosterSearch').addEventListener('input', event => renderRoster(event.target.value));
  const id = characterIdFromPath() || roster[0]?.id;
  if (!id) throw new Error('No canonical character roster configured.');
  await openCharacter(id, true);
}

window.addEventListener('popstate', () => openCharacter(characterIdFromPath(), true));
initialize().catch(error => {
  $('#message').textContent = error.message || 'Could not load character collections.';
});
