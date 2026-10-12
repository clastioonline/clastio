import assert from 'node:assert/strict';
import { test } from 'node:test';
import { matchingSearchIntents, searchQueryPatterns } from '../lib/search-query-patterns.ts';
import { parseCsv, summarizeSearchCsv } from '../scripts/search-query-report.mjs';

test('pre-purchase intent matches both word orders and does not confuse typography with PPT', () => {
  const ids = query => matchingSearchIntents(query).map(pattern => pattern.id);
  assert.ok(ids('Editable AI PowerPoint for teachers in DUBAI').includes('ai-presentations'));
  assert.ok(ids('PowerPoint from textbook PDF').includes('source-conversion'));
  assert.ok(ids('PDF to PowerPoint').includes('source-conversion'));
  assert.ok(ids('IGCSE physics lesson slides').includes('gcse-igcse'));
  assert.ok(ids('AI lesson planner costs AED').includes('cost'));
  assert.ok(!ids('AI typography').includes('ai-presentations'));
  assert.ok(!ids('uneditable invoice').includes('editable-exports'));
  assert.ok(!ids('KSC bank').includes('british'));
});

test('each segment supports its examples and uses RE2-compatible constructs', () => {
  for (const pattern of searchQueryPatterns) {
    assert.ok(!/\(\?[=!<]|\\[1-9]/.test(pattern.regex), pattern.id);
    for (const example of pattern.examples) assert.ok(matchingSearchIntents(example).some(item => item.id === pattern.id), `${pattern.id}: ${example}`);
  }
  assert.throws(() => matchingSearchIntents('x'.repeat(1025)), /exceeds/);
});

test('sparse GSC Abu Dhabi variants are contextual and MoE navigation is not a product claim', () => {
  const ids = query => matchingSearchIntents(query).map(pattern => pattern.id);
  for (const query of ['slides creation in abu dhabi', 'slide creation in abu dhabi',
    'Abu-Dhabi slide maker', 'create slides Abudhabi']) {
    assert.ok(ids(query).includes('uae'), query);
    assert.ok(ids(query).includes('abu-dhabi-slides'), query);
    assert.ok(ids(query).includes('presentation-creation'), query);
    assert.ok(!ids(query).includes('ai-presentations'), 'AI use cannot be inferred from a city/slide query');
  }
  for (const query of ['moe uae', 'UAE MoE curriculum', 'MoE-U.A.E textbooks', 'Ministry of Education UAE']) {
    assert.ok(ids(query).includes('moe-context'), query);
  }
  assert.ok(!ids('moe uae').includes('teacher-context'));
  assert.ok(!ids('landslides in Abu Dhabi').includes('abu-dhabi-slides'));
  assert.ok(!ids('Abu Dhabi bank opening').includes('presentation-creation'));
  assert.ok(!ids('Ministry of Education Oman').includes('moe-context'));
});

test('CSV imports handle quotes, commas, BOM and CRLF without double-counting overlapping totals', () => {
  const report = summarizeSearchCsv('\uFEFFTop queries,Clicks,Impressions,CTR,Position\r\n"editable AI PPT, Dubai",10,"1,000",1%,4\r\nunknown topic,0,0,0%,0\r\n');
  assert.deepEqual(report.totals, { query_rows: 2, clicks: 10, impressions: 1000, ctr_percent: 1 });
  assert.equal(report.segments.find(item => item.id === 'uae').clicks, 10);
  assert.equal(report.segments.find(item => item.id === 'ai-presentations').clicks, 10);
  assert.equal(report.unclassified.query_rows, 1);
  assert.equal(report.unclassified.ctr_percent, null);
  assert.match(report.overlap, /Do not add/);
  assert.deepEqual(parseCsv('a,b\n"a ""quote""",x\n'), [['a', 'b'], ['a "quote"', 'x']]);
});

test('invalid imports fail explicitly instead of silently reporting zero traffic', () => {
  assert.throws(() => summarizeSearchCsv('Page,Clicks\n/,3'), /Expected/);
  assert.throws(() => summarizeSearchCsv('Query,Clicks,Impressions\nAI PPT,-1,10'), /Invalid Clicks/);
  assert.throws(() => summarizeSearchCsv('Query,Clicks,Impressions\nAI PPT,1,'), /Invalid Impressions/);
  assert.throws(() => summarizeSearchCsv('Query,Clicks,Impressions\n"AI PPT,1,10'), /Unclosed/);
  assert.throws(() => summarizeSearchCsv('Query,Clicks,Impressions\nAI PPT,1,10,extra'), /Wrong column/);
});
