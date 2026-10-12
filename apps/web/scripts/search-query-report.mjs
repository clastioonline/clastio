// Offline analysis of an English-language Google Search Console Queries CSV export.
import { readFileSync, statSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { matchingSearchIntents, searchQueryPatterns } from '../lib/search-query-patterns.ts';

export function parseCsv(text) {
  const rows = [];
  let row = [], field = '', quoted = false, closed = false;
  for (let index = 0; index < text.length; index++) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') { field += '"'; index++; }
      else if (char === '"') { quoted = false; closed = true; }
      else field += char;
    } else if (char === '"') {
      if (field || closed) throw new Error('Unexpected quote in CSV field.');
      quoted = true;
    } else if (char === ',' || char === '\n' || char === '\r') {
      row.push(field); field = ''; closed = false;
      if (char !== ',') {
        if (char === '\r' && text[index + 1] === '\n') index++;
        if (row.some(value => value.trim())) rows.push(row);
        row = [];
      }
    } else {
      if (closed) throw new Error('Unexpected text after a quoted CSV field.');
      field += char;
    }
  }
  if (quoted) throw new Error('Unclosed quoted CSV field.');
  row.push(field);
  if (row.some(value => value.trim())) rows.push(row);
  return rows;
}

export function summarizeSearchCsv(csv) {
  const rows = parseCsv(csv.replace(/^\uFEFF/, ''));
  if (!rows.length) throw new Error('The CSV is empty.');
  const headers = rows.shift().map(value => value.trim().toLowerCase());
  const queryIndex = headers.findIndex(value => ['top queries', 'query', 'queries'].includes(value));
  const clicksIndex = headers.indexOf('clicks'), impressionsIndex = headers.indexOf('impressions');
  if ([queryIndex, clicksIndex, impressionsIndex].some(index => index < 0)) {
    throw new Error('Expected an English Queries CSV with Top queries (or Query), Clicks and Impressions columns.');
  }
  const count = (value, rowNumber, column) => {
    const raw = (value || '').trim().replace(/,/g, '');
    if (!/^\d+$/.test(raw) || !Number.isSafeInteger(Number(raw))) throw new Error(`Invalid ${column} count on CSV row ${rowNumber}.`);
    return Number(raw);
  };
  const totals = { query_rows: 0, clicks: 0, impressions: 0 };
  const segments = new Map(searchQueryPatterns.map(pattern => [pattern.id, { id: pattern.id, label: pattern.label, page: pattern.page, regex: pattern.regex, query_rows: 0, clicks: 0, impressions: 0 }]));
  const unclassified = { query_rows: 0, clicks: 0, impressions: 0 };
  rows.forEach((row, index) => {
    if (row.length !== headers.length) throw new Error(`Wrong column count on CSV row ${index + 2}.`);
    const query = row[queryIndex].trim();
    if (!query) throw new Error(`Empty query on CSV row ${index + 2}.`);
    const clicks = count(row[clicksIndex], index + 2, 'Clicks');
    const impressions = count(row[impressionsIndex], index + 2, 'Impressions');
    const matches = matchingSearchIntents(query);
    const targets = [totals, ...(matches.length ? matches.map(pattern => segments.get(pattern.id)) : [unclassified])];
    for (const target of targets) {
      target.query_rows++;
      target.clicks += clicks;
      target.impressions += impressions;
      if (!Number.isSafeInteger(target.clicks) || !Number.isSafeInteger(target.impressions)) throw new Error('Metric total exceeds safe integer range.');
    }
  });
  const withCtr = value => ({ ...value, ctr_percent: value.impressions ? Math.round(value.clicks / value.impressions * 10000) / 100 : null });
  return {
    scope: 'Exported query rows only; anonymized/omitted queries and export limits can prevent reconciliation with property totals.',
    overlap: 'Segments overlap. Do not add segment totals together. Matching a phrase does not prove purchase intent.',
    totals: withCtr(totals), segments: [...segments.values()].map(withCtr), unclassified: withCtr(unclassified),
  };
}

function main() {
  const [argument, ...extra] = process.argv.slice(2);
  if (!argument || argument === '--help') {
    console.log('Usage: npm run seo:queries -- /path/to/Queries.csv\n       npm run seo:queries -- --patterns\nFilter Country=United Arab Emirates and export Queries from Search Console first. Analysis runs locally; no network requests.');
    return;
  }
  if (extra.length) throw new Error('Provide one CSV path or --patterns.');
  if (argument === '--patterns') {
    // Print raw expressions: copying a JSON-escaped \\b would change its RE2 meaning.
    console.log(searchQueryPatterns.map(pattern => `${pattern.label}\n${pattern.regex}\nTarget: ${pattern.page}`).join('\n\n'));
    return;
  }
  if (statSync(argument).size > 20 * 1024 * 1024) throw new Error('CSV exceeds the 20 MiB local-analysis limit.');
  console.log(JSON.stringify(summarizeSearchCsv(readFileSync(argument, 'utf8')), null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
