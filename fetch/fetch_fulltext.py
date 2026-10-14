#!/usr/bin/env python3
"""
Fetch open-access full-text PDFs for a list of records, and build a worklist for the rest.

Input: any CSV with a title column and, where available, DOI and PMID columns (column
names are configurable). For each record the script:

  1. Looks up the PMC ID for the PMID (NCBI E-utilities esummary).
  2. Looks up open-access status and PDF links for the DOI (OpenAlex).
  3. Tries, in order: the Europe PMC render of the PMC article, the OpenAlex best
     open-access PDF, every other PDF link OpenAlex lists, and an optional extra URL
     column (e.g. the LILACS "Fulltext URL"). A file is kept only if it starts with %PDF.
  4. Writes <out>/status.csv: one row per record, with the outcome and, for anything
     not downloaded, the best link to open by hand (landing page, DOI through your
     library proxy if --proxy is given, or a Google Scholar title search).

PDFs are named after the record's title, because MetaScreener's Screen Fields page
matches uploaded PDFs to CSV rows by DOI or title in the PDF metadata and otherwise
by filename against title. With --stamp (needs `pip install pypdf`) the CSV title
is also written into each PDF's Title metadata, which makes that match exact.

Re-running is safe: records already downloaded are skipped, and API replies are
cached in <out>/api-cache.json. Only the Python standard library is required.

  python fetch_fulltext.py records.csv --email you@university.edu --out fulltext
  python fetch_fulltext.py records.csv --email you@university.edu --out fulltext \
      --id-col RecordID --proxy "https://go.openathens.net/redirector/<your-inst>?url="
"""
import argparse, csv, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

csv.field_size_limit(10**9)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'
STATUS_COLS = ['id', 'title', 'doi', 'pmid', 'pmcid', 'status', 'source', 'file', 'oa_status',
               'manual_url', 'backup_url', 'note']


class Api:
    """JSON GET/POST with retries and an on-disk cache."""

    def __init__(self, path, email):
        self.path, self.email = path, email
        self.cache = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
        self.n = 0

    def get(self, url, data=None, tries=6):
        key = url + ('?' + data.decode() if data else '')
        if key in self.cache:
            return self.cache[key]
        for t in range(tries):
            try:
                req = urllib.request.Request(url, data=data, headers={
                    'User-Agent': f'metascreener-additions/0.1 (mailto:{self.email})'})
                with urllib.request.urlopen(req, timeout=90) as r:
                    j = json.load(r)
                self.cache[key] = j
                self.n += 1
                if self.n % 20 == 0:
                    self.save()
                return j
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return {}
                if t == tries - 1:
                    raise
                time.sleep(15 * (t + 1) if e.code == 429 else 2 * (t + 1))
            except Exception:
                if t == tries - 1:
                    raise
                time.sleep(2 * (t + 1))

    def save(self):
        json.dump(self.cache, open(self.path, 'w', encoding='utf-8'))


def clean_doi(d):
    d = (d or '').strip().lower()
    return re.sub(r'^(doi:\s*|https?://(dx\.)?doi\.org/)', '', d)


def pmcids(api, pmids, email):
    """PMID -> PMCID via PubMed esummary (the ID Converter endpoint rate-limits hard)."""
    out = {}
    for i in range(0, len(pmids), 200):
        body = urllib.parse.urlencode({'db': 'pubmed', 'id': ','.join(pmids[i:i + 200]), 'retmode': 'json',
                                       'tool': 'metascreener-additions', 'email': email}).encode()
        res = api.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi', data=body).get('result', {})
        for pid in res.get('uids', []):
            for aid in res[pid].get('articleids', []):
                if aid.get('idtype') == 'pmc' and aid.get('value'):
                    out[str(pid)] = aid['value']
        time.sleep(0.4)
    return out


def openalex(api, dois, email):
    """DOI -> OA status, best PDF, all PDF links, landing page."""
    out = {}
    for i in range(0, len(dois), 50):
        part = dois[i:i + 50]
        j = api.get('https://api.openalex.org/works?' + urllib.parse.urlencode(
            {'filter': 'doi:' + '|'.join(part), 'per-page': 50, 'mailto': email,
             'select': 'doi,open_access,best_oa_location,locations'}))
        for w in j.get('results', []):
            d = clean_doi(w.get('doi'))
            best = w.get('best_oa_location') or {}
            pdfs = [best.get('pdf_url')] + [loc.get('pdf_url') for loc in w.get('locations') or []]
            out[d] = {'oa_status': (w.get('open_access') or {}).get('oa_status') or '',
                      'pdfs': list(dict.fromkeys(p for p in pdfs if p)),
                      'landing': best.get('landing_page_url') or ''}
        time.sleep(0.15)
    return out


def pmc_bucket_pdf(pmcid):
    """URL of the article PDF in PMC's AWS open-data bucket (open-access subset only), latest version."""
    url = 'https://pmc-oa-opendata.s3.amazonaws.com/?' + urllib.parse.urlencode({'list-type': 2, 'prefix': pmcid + '.'})
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=60) as r:
        keys = re.findall(r'<Key>([^<]+)</Key>', r.read().decode())
    pdfs = sorted((k for k in keys if re.fullmatch(re.escape(pmcid) + r'\.(\d+)/' + re.escape(pmcid) + r'\.\1\.pdf', k)),
                  key=lambda k: int(k.split('/')[0].split('.')[1]))
    return 'https://pmc-oa-opendata.s3.amazonaws.com/' + pdfs[-1] if pdfs else ''


def download(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/pdf,*/*'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def safe_name(title, rid, used):
    """Filename from the title, so MetaScreener's filename-vs-title match works."""
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f�]', ' ', title or rid)
    base = re.sub(r'\s+', ' ', base).strip(' .')[:140].rstrip(' .') or rid
    name, k = base, 2
    while name.lower() in used:
        name, k = f'{base} ({k})', k + 1
    used.add(name.lower())
    return name + '.pdf'


def stamp(path, title, doi):
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter(clone_from=PdfReader(path))
    meta = {'/Title': title}
    if doi:
        meta['/DOI'] = doi
    w.add_metadata(meta)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as fh:
        w.write(fh)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('csv', help='input CSV of records')
    ap.add_argument('--email', required=True, help='your contact email (sent to NCBI and OpenAlex as etiquette requires)')
    ap.add_argument('--out', default='fulltext', help='output folder (default: fulltext)')
    ap.add_argument('--id-col', help='unique ID column (default: row number)')
    ap.add_argument('--title-col', default='Title')
    ap.add_argument('--doi-col', default='DOI')
    ap.add_argument('--pmid-col', default='PMID')
    ap.add_argument('--url-col', help='optional column with an extra full-text URL to try')
    ap.add_argument('--proxy', default='', help='library proxy prefix for manual links, e.g. an OpenAthens redirector')
    ap.add_argument('--stamp', action='store_true', help='write the CSV title into PDF metadata (needs pypdf)')
    ap.add_argument('--limit', type=int, help='only process the first N records (for testing)')
    a = ap.parse_args()

    if a.stamp:
        try:
            import pypdf  # noqa: F401
        except ImportError:
            sys.exit('--stamp needs pypdf: pip install pypdf')

    pdf_dir = os.path.join(a.out, 'pdfs')
    os.makedirs(pdf_dir, exist_ok=True)
    status_path = os.path.join(a.out, 'status.csv')
    api = Api(os.path.join(a.out, 'api-cache.json'), a.email)

    with open(a.csv, encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))
    for col in (a.title_col, a.id_col):
        if col and rows and col not in rows[0]:
            sys.exit(f'column {col!r} not in {a.csv}; columns are: {", ".join(rows[0])}')
    if a.limit:
        rows = rows[:a.limit]
    recs = [{'id': (r.get(a.id_col) if a.id_col else str(i + 1)).strip(),
             'title': (r.get(a.title_col) or '').strip(),
             'doi': clean_doi(r.get(a.doi_col)),
             'pmid': re.sub(r'\D', '', r.get(a.pmid_col) or ''),
             'extra': (r.get(a.url_col) or '').strip().split(' ')[0] if a.url_col else ''} for i, r in enumerate(rows)]

    old = {}
    if os.path.exists(status_path):
        with open(status_path, encoding='utf-8-sig') as fh:
            old = {r['id']: r for r in csv.DictReader(fh)}
    used = {r['file'][:-4].lower() for r in old.values() if r.get('file')}

    print(f'{len(recs)} records; looking up PMC IDs and open-access links ...')
    pmc = pmcids(api, sorted({r['pmid'] for r in recs if r['pmid']}), a.email)
    oa = openalex(api, sorted({r['doi'] for r in recs if r['doi']}), a.email)
    api.save()

    def proxied(u):
        return a.proxy + urllib.parse.quote(u, safe='') if a.proxy else u

    out = []
    try:
        fetch_all(a, recs, old, used, pmc, oa, pdf_dir, proxied, out)
    finally:  # an interrupted run still records what it fetched
        with open(status_path, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, STATUS_COLS, extrasaction='ignore')
            w.writeheader()
            w.writerows(out + [p for k, p in old.items() if k not in {o['id'] for o in out}])
    ok = sum(r['status'] == 'ok' for r in out)
    print(f'\n{ok} of {len(out)} PDFs in {pdf_dir}; the other {len(out) - ok} are listed in {status_path} '
          f'with a link to open by hand.')


def fetch_all(a, recs, old, used, pmc, oa, pdf_dir, proxied, out):
    for r in recs:
        prev = old.get(r['id'])
        if prev and prev['status'] == 'ok' and os.path.exists(os.path.join(pdf_dir, prev['file'])):
            out.append(prev)
            continue
        o = oa.get(r['doi'], {})
        row = {'id': r['id'], 'title': r['title'], 'doi': r['doi'], 'pmid': r['pmid'],
               'pmcid': pmc.get(r['pmid'], ''), 'oa_status': o.get('oa_status', '') if r['doi'] else 'no_doi',
               'status': '', 'source': '', 'file': '', 'manual_url': '', 'backup_url': '', 'note': ''}
        tries, notes = [], []
        if row['pmcid']:
            try:
                u = pmc_bucket_pdf(row['pmcid'])
                if u:
                    tries.append(('pmc_oa', u))
            except Exception as e:
                notes.append(f'pmc_oa: {type(e).__name__}')
            tries.append(('europepmc', f"https://europepmc.org/articles/{row['pmcid']}?pdf=render"))
        tries += [('openalex', u) for u in o.get('pdfs', [])]
        if r['extra']:
            tries.append(('extra_url', r['extra']))
        for src, url in tries:
            try:
                data = download(url)
            except Exception as e:
                notes.append(f'{src}: {type(e).__name__} {str(e)[:60]}')
                continue
            if data[:5] == b'%PDF-':
                name = safe_name(r['title'], r['id'], used)
                path = os.path.join(pdf_dir, name)
                try:
                    with open(path, 'wb') as fh:
                        fh.write(data)
                except OSError:  # e.g. the Windows 260-character path limit
                    name = safe_name(r['id'], r['id'], used)
                    path = os.path.join(pdf_dir, name)
                    with open(path, 'wb') as fh:
                        fh.write(data)
                if a.stamp:
                    try:
                        stamp(path, r['title'], r['doi'])
                    except Exception as e:
                        notes.append(f'stamp failed: {type(e).__name__}')
                row.update(status='ok', source=src, file=name, manual_url=url)
                break
            notes.append(f'{src}: not a PDF ({len(data)} bytes)')
            time.sleep(0.5)
        else:
            scholar = 'https://scholar.google.com/scholar?q=' + urllib.parse.quote(f'"{r["title"][:200]}"')
            doi_url = proxied('https://doi.org/' + r['doi']) if r['doi'] else ''
            if row['pmcid']:
                first = f"https://pmc.ncbi.nlm.nih.gov/articles/{row['pmcid']}/"
            elif o.get('landing'):
                first = o['landing']
            elif doi_url:
                first = doi_url
            elif r['pmid']:
                first = f"https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}/"
            else:
                first = scholar
            row.update(status='needs_manual', manual_url=first,
                       backup_url=doi_url if doi_url and doi_url != first else scholar)
        row['note'] = '; '.join(notes)
        out.append(row)
        print(f"{row['id']:>10}  {row['status']:12} {row['source']}")
        time.sleep(0.2)


if __name__ == '__main__':
    main()
