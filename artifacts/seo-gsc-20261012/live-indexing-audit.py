"""Public unauthenticated GET audit. Saves public bodies and whitelisted metadata only."""
import concurrent.futures
import hashlib
import html
import json
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

OUT = Path('artifacts/seo-gsc-20261012')
(OUT / 'live-bodies').mkdir(parents=True, exist_ok=True)
HEADERS = {'server', 'content-type', 'cache-control', 'x-robots-tag', 'location', 'cf-ray',
           'cf-cache-status', 'cf-mitigated', 'x-vercel-cache', 'x-nextjs-cache', 'age'}
AGENTS = {'browser': 'Mozilla/5.0 (compatible; ClastioPublicAudit/1.0)',
          'googlebot': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}
PATHS = ['/', '/solutions', '/solutions/ai-ppt-maker-for-teachers-uae',
         '/solutions/british-curriculum-lesson-planning', '/solutions/turn-teaching-notes-into-powerpoint',
         '/solutions/how-to-choose-ai-presentation-maker-for-teachers',
         '/solutions/gcse-igcse-lesson-presentations', '/solutions/ai-lesson-planning-costs-and-credits',
         '/pricing', '/faq', '/how-it-works', '/for-schools', '/robots.txt', '/sitemap.xml', '/llms.txt',
         '/solutions/not-a-real-guide', '/api/v1/billing/plans', '/legal/acceptable_use', '/legal/cookie',
         '/solutions/cbse-lesson-planning-uae', '/solutions/differentiated-lesson-presentations',
         '/solutions/eal-lessons-uae', '/solutions/edit-ppt-without-regenerating',
         '/solutions/lesson-planning-for-uae-teachers', '/solutions/personal-ai-teaching-assistant',
         '/solutions/quiz-and-exit-ticket-maker', '/solutions/reuse-school-powerpoint-design',
         '/solutions/stock-images-for-teaching-presentations', '/solutions/worksheet-maker-for-uae-teachers']


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'head'}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'head'}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def audit(job):
    url, agent = job
    name = re.sub(r'[^a-zA-Z0-9_-]', '-', url.split('://', 1)[1]).strip('-') + '-' + agent
    body_path = OUT / 'live-bodies' / (name + '.txt')
    with tempfile.TemporaryDirectory() as temporary:
        headers_path = Path(temporary) / 'headers.txt'
        result = subprocess.run(['curl', '--silent', '--show-error', '--compressed', '--location',
            '--max-redirs', '4', '--max-time', '15', '--max-filesize', '2097152',
            '--user-agent', AGENTS[agent], '--dump-header', str(headers_path),
            '--output', str(body_path), '--write-out', '%{json}', url], capture_output=True, text=True)
        try:
            timing = json.loads(result.stdout)
        except ValueError:
            timing = {}
        raw_headers = headers_path.read_text(errors='replace') if headers_path.exists() else ''
    chain = []
    for block in re.split(r'\r?\n\r?\n', raw_headers):
        lines = block.splitlines()
        if not lines or not lines[0].startswith('HTTP/'):
            continue
        selected = {}
        for line in lines[1:]:
            if ':' in line:
                key, value = line.split(':', 1)
                if key.lower() in HEADERS:
                    selected[key.lower()] = value.strip()
        chain.append({'status_line': lines[0], 'headers': selected})
    body = body_path.read_text(errors='replace') if body_path.exists() else ''
    parser = VisibleText()
    parser.feed(body)
    text = ' '.join(' '.join(parser.parts).split())
    canonicals = re.findall(r'<link\b[^>]*rel=[\"\']canonical[\"\'][^>]*href=[\"\']([^\"\']+)', body, re.I)
    robots = re.findall(r'<meta\b[^>]*name=[\"\'](?:robots|googlebot)[\"\'][^>]*content=[\"\']([^\"\']+)', body, re.I)
    titles = re.findall(r'<title>(.*?)</title>', body, re.S | re.I)
    headings = re.findall(r'<h1\b[^>]*>(.*?)</h1>', body, re.S | re.I)
    links = sorted(set(html.unescape(link) for link in re.findall(r'<a\b[^>]*href=[\"\']([^\"\']+)', body, re.I)))
    return {'requested_url': url, 'agent': agent, 'curl_exit': result.returncode,
        'error': result.stderr.strip()[:300] or None, 'effective_url': timing.get('url_effective'),
        'status': timing.get('http_code'), 'seconds': timing.get('time_total'), 'chain': chain,
        'bytes': len(body.encode()), 'body_file': str(body_path), 'sha256': hashlib.sha256(body.encode()).hexdigest(),
        'title': [html.unescape(title) for title in titles],
        'h1': [html.unescape(re.sub('<[^>]+>', '', heading)) for heading in headings],
        'canonical': canonicals, 'meta_robots': robots, 'visible_words': len(text.split()),
        'text_sample': text[:300], 'internal_links': [link for link in links if link.startswith('/')],
        'markers': {'new_ppt_guide_section': 'What to give an AI lesson presentation maker' in body,
                    'price_loading_shell': 'Loading current plans' in body,
                    'rendered_teacher_card': bool(re.search(r'<h3[^>]*>Teacher</h3>', body)),
                    'challenge_page': any(value in body.lower() for value in
                        ['cf-chl-', 'just a moment', 'verify you are human', 'enable javascript and cookies'])}}


jobs = [('https://clastio.online' + path, 'browser') for path in PATHS]
jobs += [('https://clastio.online' + path, 'googlebot') for path in
         ['/', '/solutions', '/solutions/ai-ppt-maker-for-teachers-uae', '/pricing', '/robots.txt', '/sitemap.xml']]
jobs += [('http://clastio.online/', 'browser'), ('https://www.clastio.online/', 'browser'),
         ('http://www.clastio.online/', 'browser'), ('https://clerk.clastio.online/', 'browser')]
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(audit, jobs))
report = {'checked_at': datetime.now(UTC).isoformat(), 'read_only_public_get': True,
          'note': 'Googlebot user-agent spoofing is not a verified Google crawl or URL Inspection test.',
          'results': results}
(OUT / 'live-indexing-audit.json').write_text(json.dumps(report, indent=2))
print(json.dumps([{'url': r['requested_url'], 'agent': r['agent'], 'status': r['status'],
    'canonical': r['canonical'], 'h1': r['h1'], 'words': r['visible_words'], 'markers': r['markers'],
    'redirects': len(r['chain']) - 1, 'error': r['error']} for r in results], indent=2))
