import json, re, io, os, html, warnings, urllib.request, concurrent.futures as cf
warnings.filterwarnings("ignore")
import openpyxl
from PIL import Image

SRC = '/Users/hassanlantry/SeriesA_blast/investor-updates/src/app/api/sync-all-data/company-data.json'
XLSX = '/Users/hassanlantry/Downloads/Suivi Batch - YC  (2).xlsx'
SITE = '/Users/hassanlantry/lantry-site'
LOGOS = SITE + '/assets/logos'
os.makedirs(LOGOS, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36'}
GENERIC = {'gmail.com','googlemail.com','outlook.com','hotmail.com','yahoo.com','icloud.com','me.com','proton.me','protonmail.com','live.com'}
BATCH = {'YC X25':'X25','YC S25':'S25','YC F25':'F25','YC W26':'W26','YC X26':'X26','YC S26':'S26'}

def clean_domain(d):
    if not d: return None
    d = str(d).strip()
    if '@' in d: d = d.split('@',1)[1]
    d = re.sub(r'^https?://','',d); d = re.sub(r'^www\.','',d); d = d.split('/')[0].lower()
    if d in GENERIC or d.startswith('acompanyinstealth'): return None
    return d if re.match(r'^[a-z0-9.-]+\.[a-z]+$', d) else None
def clean_name(n): return re.sub(r'\s*\((?:S|W|X|F)20\d\d\)\s*$', '', n).strip()
def slugify(n): return re.sub(r'-+','-',re.sub(r'[^a-z0-9]+','-',n.lower())).strip('-')

def get(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.headers.get('Content-Type',''), r.read()

def fetch_image(url):
    try:
        st, ct, body = get(url)
        if st != 200 or not body: return None
        if 'svg' in ct or body[:200].lstrip().startswith(b'<svg') or b'<svg' in body[:300]:
            return ('svg', body)
        im = Image.open(io.BytesIO(body)); im.load()
        return ('raster', im)
    except Exception:
        return None

def yc_logo(row):
    cands = [slugify(row['name'])]
    base = re.sub(r'\b(ai|inc|labs|technologies|corp)\b\.?$', '', row['name'], flags=re.I).strip(' ,.')
    if base and slugify(base) not in cands: cands.append(slugify(base))
    for slug in cands:
        try:
            st, ct, body = get(f'https://www.ycombinator.com/companies/{slug}')
        except Exception:
            continue
        t = html.unescape(body.decode('utf-8','ignore'))
        logo = re.search(r'(https://bookface-images\.s3\.amazonaws\.com/small_logos/[a-f0-9]+\.(?:png|jpg|jpeg))', t)
        site = re.search(r'"website":"([^"]*)"', t)
        batch = re.search(r'"batch":"([A-Za-z]\d{2,4})"', t)
        if not logo: continue
        dom = clean_domain(site.group(1)) if site else None
        ok = (dom and row['domain'] and (dom == row['domain'] or dom.split('.')[0] == row['domain'].split('.')[0]))
        b = (batch.group(1).upper() if batch else '')
        want = row['batch'].replace('X','P')
        ok = ok or (b and (b == want or b == row['batch'] or b[0]+b[-2:] == want))
        if ok: return logo.group(1)
    return None

def save(row, img):
    kind, data = img
    slug = slugify(row['name']) or 'co'
    if kind == 'svg':
        p = f'{LOGOS}/{slug}.svg'; open(p,'wb').write(data); return 'assets/logos/'+slug+'.svg'
    im = data.convert('RGBA')
    if max(im.size) > 256: im.thumbnail((256,256), Image.LANCZOS)
    p = f'{LOGOS}/{slug}.png'; im.save(p, optimize=True); return 'assets/logos/'+slug+'.png', im.size

def resolve(row):
    tried = []
    if row.get('bookface'):
        img = fetch_image(row['bookface'])
        if img: return save(row, img), 'bookface'
    if row['program'] == 'YC':
        u = yc_logo(row)
        if u:
            img = fetch_image(u)
            if img: return save(row, img), 'ycpage'
    if row['domain']:
        img = fetch_image(f"https://{row['domain']}/apple-touch-icon.png")
        if img and img[0]=='raster' and min(img[1].size) >= 64: return save(row, img), 'touch'
        img = fetch_image(f"https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://{row['domain']}&size=256")
        if img: return save(row, img), 'favicon'
    return None, 'none'

rows = []
for x in json.load(open(SRC)):
    rows.append({'name': clean_name(x['name']), 'domain': clean_domain(x['domain']), 'bookface': x['logoUrl'], 'batch': BATCH[x['ycBatchName']], 'program': 'YC'})
wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
for r in list(wb['Batch SR007 - A16Z'].iter_rows(values_only=True))[1:]:
    if not r[0]: continue
    st = (r[4] or '').strip()
    if st[:2] in ('6-','7-','8-') or st.startswith('10-'):
        rows.append({'name': str(r[0]).strip(), 'domain': clean_domain(r[3]), 'bookface': None, 'batch': 'SR007', 'program': 'Speedrun'})

# SR007 enrichment from the demo-day directory (website + logo), matched by name
try:
    sr = open('/Users/hassanlantry/sr007-demo-day/data.js').read()
    sr_items = json.loads(re.search(r'=\s*(\[.*\]);?\s*$', sr, re.S).group(1))
    for row in rows:
        if row['program'] != 'Speedrun': continue
        for it in sr_items:
            if slugify(it.get('name','')) == slugify(row['name']) or slugify(row['name']) in slugify(it.get('name','')):
                row['domain'] = row['domain'] or clean_domain(it.get('website') or it.get('url') or '')
                lg = it.get('logo') or it.get('image')
                if lg and not lg.startswith('http'):
                    lp = '/Users/hassanlantry/sr007-demo-day/' + lg.lstrip('./')
                    if os.path.exists(lp): row['bookface'] = 'file://' + lp
                break
except Exception as e:
    print('sr007 enrich failed', e)

def fetch_local_or_remote(row):
    if row.get('bookface','') and row['bookface'].startswith('file://'):
        p = row['bookface'][7:]
        try:
            body = open(p,'rb').read()
            img = ('svg', body) if p.endswith('.svg') else ('raster', Image.open(io.BytesIO(body)))
            return save(row, img), 'sr007'
        except Exception: pass
        row['bookface'] = None
    return resolve(row)

with cf.ThreadPoolExecutor(16) as ex:
    results = list(ex.map(fetch_local_or_remote, rows))
from collections import Counter
src = Counter(); out = []
for row, (res, how) in zip(rows, results):
    src[how] += 1
    path = res[0] if isinstance(res, tuple) else res
    out.append({'n': row['name'], 'd': row['domain'], 'b': row['batch'], 'l': path})
out.sort(key=lambda r: re.sub(r'^(the )','',r['n'].lower()))
with open(SITE+'/data.js','w') as f:
    f.write('// Generated by build_logos.py — public fields only (name, website, batch, local logo path).\n')
    f.write('window.PORTFOLIO = ' + json.dumps(out, ensure_ascii=False, separators=(',',':')) + ';\n')
print('total', len(out), 'sources', dict(src))
print('no logo:', [r['n'] for r in out if not r['l']])
