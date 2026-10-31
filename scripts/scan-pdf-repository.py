#!/usr/bin/env python3
"""Extract a resumable private PDF inventory using local Poppler tools."""
import argparse, concurrent.futures, hashlib, json, re, subprocess
from pathlib import Path

def isbn(value):
    s=re.sub(r'[^0-9X]', '', value.upper())
    if len(s)==10 and re.fullmatch(r'\d{9}[\dX]',s) and sum((10-i)*(10 if c=='X' else int(c)) for i,c in enumerate(s))%11==0:
        s='978'+s[:9]; s+=str(-sum(int(c)*(1 if i%2==0 else 3) for i,c in enumerate(s))%10)
    return s if re.fullmatch(r'97[89]\d{10}',s) and sum(int(c)*(1 if i%2==0 else 3) for i,c in enumerate(s))%10==0 else None

def scan(path,root):
    row={'path':str(path.relative_to(root)), 'size':path.stat().st_size}
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    row['sha256']=h.hexdigest()
    try:
        info=subprocess.run(['pdfinfo',str(path)],capture_output=True,text=True,timeout=30).stdout
        meta=dict(re.findall(r'^([^:\n]+):[ \t]*(.*)$',info,re.M))
        result=subprocess.run(['pdftotext','-f','1','-l','12',str(path),'-'],capture_output=True,text=True,timeout=35)
        text=result.stdout
        row.update(metadata=meta,excerpt=text[:22000],readable=bool(meta.get('Pages')),error=result.stderr[:400] if not meta.get('Pages') else '')
        stem=re.sub(r'(\.pdf)+$','',path.name,flags=re.I)
        author,title=stem.split('_',1) if '_' in stem else ('',stem)
        title=re.sub(r'[_]+',' ',title).strip()
        mt=meta.get('Title','').strip()
        if mt and len(mt)>8 and not re.search(r'(microsoft|untitled|\.doc|acrobat|scan|^\d+$)',mt,re.I): title=mt
        row['title']=title[:1000] or stem[:1000]
        ma=meta.get('Author','').strip()
        row['author']=(ma if ma and not re.search(r'(admin|user|scanner|unknown|epson|canon|^\d+$)',ma,re.I) else author.replace('_',' '))[:300]
        found=[]
        for match in re.finditer(r'ISBN(?:[- ]1[03])?\s*[:：]?\s*([\dXx][\dXx\s‐–-]{8,30})',text,re.I):
            value=isbn(match[1].replace('–','-').replace('‐','-'))
            if value and value not in found:found.append(value)
        row['isbns']=found
        row['dois']=list(dict.fromkeys(re.findall(r'10\.\d{4,9}/[^\s<>"\]]+',text)))[:10]
        row['pages']=meta.get('Pages','')
    except Exception as e:row['error']=str(e)
    return row

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    paths=sorted(x for x in args.root.rglob('*') if x.is_file() and x.suffix.lower()=='.pdf')
    with args.output.open('w') as out, concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for i,row in enumerate(pool.map(lambda f:scan(f,args.root),paths),1):
            out.write(json.dumps(row,ensure_ascii=False)+'\n');out.flush()
            if i%50==0:print(f'{i}/{len(paths)} scanned',flush=True)
