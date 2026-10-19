'use strict';
// Project-first directory layered over the original local-first review catalog.
// Does not mutate review state or infer release/owner approval from timestamps.
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const allowed = raw => {
  const url=String(raw || '');
  return /^\/(?:asset-viewer(?:\/|$)|onlyfridges(?:\/|$))/.test(url) ||
    /^https:\/\/github\.com\/TheSpyglassofOdysseus\/asset-viewer\/issues\/47$/.test(url) ||
    /^#(?:archive|reviews)$/.test(url) ? url : '#archive';
};
const collectionUrl = slug => '/asset-viewer/c/' + encodeURIComponent(slug);
const normalize = str => String(str || '').toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
let projects = [], collections=[], pending=[], search='';
const projectMarkup = p => `<article class="project-card" data-project="${esc(p.id)}">
  <div class="card-heading"><div><div class="category">${esc(p.category)}</div><h3>${esc(p.name)}</h3></div><span class="status">${esc(p.status)}</span></div>
  <p class="card-desc">${esc(p.description)}</p>
  <a class="pin" href="${esc(allowed(p.pin.url))}"><span class="pin-label">Pinned review destination ↗</span><strong>${esc(p.pin.name)}</strong><small>${esc(p.pin.detail)}</small></a>
  <nav class="card-links" aria-label="${esc(p.name)} shortcuts">${p.links.map(l=>`<a href="${esc(allowed(l.url))}"${l.url.startsWith('https:')?' target="_blank" rel="noopener noreferrer"':''}>${esc(l.label)} ↗</a>`).join('')}</nav>
</article>`;
const matching = (item,term) => normalize(JSON.stringify(item)).includes(term);
function renderProjects(){
  const found=projects.filter(p=>!search||matching(p,search));
  $('projectCards').innerHTML=found.length?found.map(projectMarkup).join(''):'<p class="empty">No matching projects. Search the collection index below for individual revisions.</p>';
  $('projectCount').textContent=`${found.length} project areas`;
}
function renderReviews(){
  const labels=new Map(collections.map(c=>[c.slug,c.label]));
  const rows=pending.filter(x=>(x.unreviewed||x.new) && (!search||matching([x.collection,x.label],search)))
    .sort((a,b)=>(b.new||0)-(a.new||0)||(b.unreviewed||0)-(a.unreviewed||0));
  $('reviewCount').textContent=`${rows.length} collections need review`;
  $('reviewList').innerHTML=rows.length?
    rows.slice(0,8).map(r=>`<a class="review-row" href="${esc(collectionUrl(r.collection))}"><span><strong>${esc(r.label||labels.get(r.collection)||r.collection)}</strong><small>${esc(r.collection)}</small></span><span class="review-count">${Number(r.unreviewed||0)} pending${r.new?' · '+Number(r.new)+' new':''} ↗</span></a>`).join(''):
    '<p class="empty" style="padding:16px">No matching pending reviews.</p>';
}
function renderCollections(){
  const found=collections.filter(c=>!search||matching([c.label,c.slug,c.group],search)).sort((a,b)=>a.label.localeCompare(b.label));
  $('collectionCount').textContent=`${found.length} collections`;
  $('archiveSummary').textContent=search?'· matching search':'· collapsed by default';
  $('collectionList').innerHTML=found.length?found.map(c=>`<a href="${esc(collectionUrl(c.slug))}">${esc(c.label)} ↗</a>`).join(''):'<p class="empty">No matching source collections.</p>';
  if(search && found.length)$('allCollections').open=true;
}
function render(){renderProjects();renderReviews();renderCollections()}
async function jsonFetch(url){
  const r=await fetch(url,{cache:'no-store',credentials:'same-origin'});
  if(!r.ok)throw new Error('HTTP '+r.status+' for '+url);
  return r.json();
}
async function initialize(){
  $('search').addEventListener('input',event=>{
    search=normalize(event.target.value.trim());render();
  });
  const [directory,catalog,reviewQueue]=await Promise.allSettled([
    jsonFetch('/asset-viewer/characters/projects/projects.json'),
    jsonFetch('/asset-viewer/api/gallery'),
    jsonFetch('/asset-viewer/api/pending')
  ]);
  if(directory.status==='fulfilled'&&Array.isArray(directory.value.projects))projects=directory.value.projects;
  else $('projectCards').innerHTML='<p class="empty">Project directory unavailable; use the character roster above.</p>';
  if(catalog.status==='fulfilled'&&Array.isArray(catalog.value.collections))collections=catalog.value.collections;
  else $('collectionList').innerHTML='<p class="empty">Cannot retrieve source collections.</p>';
  if(reviewQueue.status==='fulfilled'&&Array.isArray(reviewQueue.value.collections))pending=reviewQueue.value.collections;
  else $('reviewList').innerHTML='<p class="empty" style="padding:16px">Review queue unavailable. Open an individual source collection to check it.</p>';
  if(directory.status==='fulfilled')renderProjects();
  if(catalog.status==='fulfilled')renderCollections();
  if(reviewQueue.status==='fulfilled')renderReviews();
}
initialize().catch(error=>{
  console.error(error);$('reviewList').textContent='Review data unavailable; use the original collection links.';
});
