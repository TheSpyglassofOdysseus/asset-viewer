// Lightweight DOM-free smoke test of the actual production navigation renderer.
// Run: node tests/test_character_roster_nav.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../asset_viewer/static/app.js'), 'utf8');
const start = source.indexOf('function revisionNumber(');
const end = source.indexOf('function provenanceText(', start);
assert(start > 0 && end > start);

const select = {innerHTML: '', value: ''};
const search = {value: '', oninput: null};
const nav = {innerHTML: '', querySelectorAll: () => []};
const state = {
  collections: [
    {slug: 'chr-003-prior-edrin-v002', label: 'Prior Edrin v002', available: true},
    {slug: 'chr-003-prior-edrin-v008', label: 'Prior Edrin v008', available: true},
    {slug: 'other-project', label: 'Other project', available: true},
  ],
  roster: Array.from({length: 100}, (_, index) => ({
    id: 'CHR-' + String(index + 1).padStart(3, '0'),
    name: index === 2 ? 'Prior Edrin' : 'Character ' + String(index + 1),
    faction: 'Test faction',
    collections: index === 2
      ? ['chr-003-prior-edrin-v002', 'chr-003-prior-edrin-v008']
      : [],
  })),
  rosterExpanded: new Set(), rosterQuery: '', otherCollectionsExpanded: false, active: '',
};
const elements = {'#collection': select, '#collectionNav': nav, '#characterSearch': search};
const context = {
  state,
  $: selector => elements[selector] || null,
  esc: value => String(value).replace(/[&<>"]/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[ch])),
  switchCollection: () => Promise.resolve(),
  showError: error => {throw error;},
};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);
vm.runInContext("renderCollections('chr-003-prior-edrin-v008')", context);
assert.equal((nav.innerHTML.match(/class="roster-character-link(?: active)?"/g) || []).length, 100);
assert(nav.innerHTML.includes('Character roster · 100'));
const edrin = nav.innerHTML.split('data-character-id="CHR-003"')[1]?.split('</a>')[0];
assert(edrin, 'Prior Edrin character collection should be linked');
assert(nav.innerHTML.includes('/characters/CHR-003'), 'one canonical character link');
assert(!nav.innerHTML.includes('data-collection="chr-003-prior-edrin-v008"'), 'legacy revisions should not appear as separate sidebar rows');
assert(nav.innerHTML.includes('<details id="otherCollections" class="roster-other"'));
assert(nav.innerHTML.includes('Other collections · 1'));
assert(!nav.innerHTML.includes('<details id="otherCollections" class="roster-other" open>'));
assert(select.innerHTML.includes('<optgroup label="Character collections">'));
assert(select.innerHTML.includes('value="character:CHR-003"'));
assert(select.innerHTML.includes('<optgroup label="Other collections">'));
state.roster = [];
vm.runInContext("renderCollections('other-project')", context);
assert(!nav.innerHTML.includes('roster-character'), 'non-roster galleries use original flat navigation');
assert(nav.innerHTML.includes('data-collection="other-project"'));
console.log('PASS: exactly 100 canonical character collection links, no revision sidebar duplication, other grouping, mobile grouping, flat fallback');
