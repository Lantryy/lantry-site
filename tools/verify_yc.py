"""Cross-check every YC portfolio line against YC's public directory (yc-oss mirror).
Source of truth for website + logo = the YC company whose batch matches ours and whose
name (or former name) matches, or whose website domain matches. Prints every change."""
import json, re, io, sys, urllib.request
from PIL import Image
SITE='/Users/hassanlantry/lantry-site'
YC=json.load(open(sys.argv[1]))
BATCH={'X25':'Spring 2025','S25':'Summer 2025','F25':'Fall 2025','W26':'Winter 2026','X26':'Spring 2026','S26':'Summer 2026'}
def norm(n): return re.sub(r'[^a-z0-9]','',re.sub(r'\b(inc|labs?|ai|technologies|corp|co|the)\b','',re.sub(r'\(.*?\)','',n.lower())))
def dom(u):
    if not u: return None
    d=re.sub(r'^https?://','',u.strip().lower()); d=re.sub(r'^www\.','',d).split('/')[0].split('?')[0]
    return d or None
by_batch={}
for c in YC: by_batch.setdefault(c.get('batch'),[]).append(c)
s=open(SITE+'/data.js').read(); data=json.loads(re.search(r'PORTFOLIO = (\[.*?\]);',s).group(1))
changes=[]; unmatched=[]; logo_updates=[]; renames=[]
for c in data:
    if c['b']=='SR007': continue
    pool=by_batch.get(BATCH[c['b']],[])
    n=norm(c['n'])
    hits=[y for y in pool if norm(y['name'])==n or any(norm(f)==n for f in y.get('former_names',[]))]
    if c['d']:
        dh=[y for y in pool if dom(y.get('website'))==c['d']]
        if dh: hits=dh+[h for h in hits if h not in dh]
    if not hits:
        # exact name in another batch with same domain → probably batch typo in sheet
        anyb=[y for y in YC if (norm(y['name'])==n) and c['d'] and dom(y.get('website'))==c['d']]
        if anyb: hits=anyb
    if not hits:
        unmatched.append(c); continue
    y=hits[0]
    yd=dom(y.get('website'))
    if yd and yd!=c['d']:
        changes.append((c['n'],c['b'],c['d'],yd,y['url'])); c['d']=yd
    c['yc']=y['url']
    if y['name'].strip().lower()!=c['n'].strip().lower() and y['name'].strip():
        renames.append((c['n'],y['name'],c['b'])); c['n']=y['name'].strip()
    if y.get('small_logo_thumb_url'): logo_updates.append((c,y['small_logo_thumb_url']))
# refresh logos from YC for matched companies
UA={'User-Agent':'Mozilla/5.0'}
got=0
for c,u in logo_updates:
    try:
        with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=15) as r: b=r.read()
        im=Image.open(io.BytesIO(b)); im.load(); im=im.convert('RGBA')
        if max(im.size)>256: im.thumbnail((256,256),Image.LANCZOS)
        slug=re.sub(r'[^a-z0-9]+','-',c['n'].lower()).strip('-') or 'co'
        p=f'assets/logos/{slug}.png'; im.save(SITE+'/'+p,optimize=True); c['l']=p; got+=1
    except Exception: pass
out=[{k:v for k,v in c.items() if k!='yc'} for c in data]
s=re.sub(r'PORTFOLIO = \[.*?\];','PORTFOLIO = '+json.dumps(out,ensure_ascii=False,separators=(',',':'))+';',s,flags=re.S)
open(SITE+'/data.js','w').write(s)
yc_total=sum(1 for c in data if c['b']!='SR007')
print(f'YC lines: {yc_total}  matched: {yc_total-len(unmatched)}  unmatched: {len(unmatched)}  logos refreshed from YC: {got}')
print('\nWEBSITE CHANGES (name | batch | sheet -> YC):')
for n,b,o,nw,u in changes: print(f'  {n} | {b} | {o} -> {nw}')
print('\nRENAMED TO YC CURRENT NAME (sheet -> YC):')
for o,n,b in renames: print(f'  {o} -> {n} | {b}')
print('\nUNMATCHED (kept sheet data, review manually):')
for c in unmatched: print(f"  {c['n']} | {c['b']} | {c['d']}")
