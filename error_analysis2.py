import json, re, collections, statistics as st, Levenshtein
from rapidfuzz import fuzz
import bisect
from error_analysis import keys, pick, E, S, T, names, lost_total, N, agree
res='scorer/result/drdoc_%s_%s.json'
RUN={'v6':'FINAL_v6','v7':'FINAL_v7','v8':'FINAL_v8','paddle':'PADDLE'}
TB={n:collections.defaultdict(list) for n in names}; RO={n:{} for n in names}
for n in names:
    for x in json.load(open(res%(RUN[n],'text_block_result'))): TB[n][x['img_id']+'.jpg' if not x['img_id'].endswith('.jpg') else x['img_id']].append(x)
    for x in json.load(open(res%(RUN[n],'reading_order_result'))): RO[n][x['img_id']+'.jpg' if not x['img_id'].endswith('.jpg') else x['img_id']]=x
fmt=lambda s: re.sub(r'\s+',' ',re.sub(r'[*_#`>|\\{}$~]|\\[a-zA-Z]+','',s.replace('\n',' '))).strip().lower()
# ---- text loss decomposition
cat=collections.Counter(); pages_used=0
detail=collections.Counter()
for k in keys:
    ents=TB[pick[k]].get(k,[])
    if not ents: continue
    tot=sum(e.get('upper_len',0) for e in ents)
    if tot<=0: continue
    pl=100*(1-E[k]['text'])/100 if False else (100-E[k]['text'])   # text loss in points for this page
    en=sum(e.get('Edit_num',0) for e in ents)
    if en<=0: continue
    parts=collections.Counter()
    for e in ents:
        g,p=e['gt'],e['pred']; ed=e.get('Edit_num',0)
        if g=='' and p!='': parts['extra predicted paragraph (not in reference)']+=ed
        elif p=='' and g!='': parts['reference paragraph we did not output/match']+=ed
        else:
            raw=ed; norm_=Levenshtein.distance(fmt(g),fmt(p)) if ed else 0
            norm_=min(norm_,raw); parts['matched pair: format/markup/whitespace only']+=raw-norm_; parts['matched pair: real wording/OCR differences']+=norm_
    for c,v in parts.items(): cat[c]+=pl*v/en
    pages_used+=1
print(f'== A. TEXT loss ({st.mean(100-E[k]["text"] for k in keys):.2f} points of mean overall-equivalent) split by cause, over {pages_used} pages')
tt=sum(cat.values())
for c,v in cat.most_common(): print(f'   {100*v/tt:5.1f}%  {c}')
# ---- reading-order loss decomposition
lost_missing=lost_order=0; per=[]
for k in keys:
    r=RO[pick[k]].get(k)
    if not r or not r['gt']: continue
    gt,pred=r['gt'],r['pred']; n=max(len(gt),len(pred)); e=Levenshtein.distance(gt,pred); ps=set(pred)
    em=sum(1 for g in gt if g not in ps); lost_missing+=em/n*100; lost_order+=max(0,e-em)/n*100
print(f'\n== B. READING-ORDER loss split (points of the order component, page-averaged)')
tot=lost_missing+lost_order; print(f'   {100*lost_missing/tot:5.1f}%  reference paragraphs missing from our output (never matched)\n   {100*lost_order/tot:5.1f}%  paragraphs present but in the wrong order / extra')
# ---- pages where all candidates agree but score low: what is different?
hi=[k for k in keys if agree[k]>=90 and E[k]['overall']<80]
print(f'\n== C. the {len(hi)} pages where all four candidates are >=90% similar to each other yet score <80')
cc=collections.Counter(); ratio=[]
from common import gt_markdown
for k in hi:
    x=T[pick[k]][k]; gt=gt_markdown('dev',x['subject'],x['document_id'],x['page'])
    gp=len([q for q in re.split(r'\n\s*\n',re.sub(r'!\[[^\]]*\]\([^)]*\)','',gt).strip()) if q.strip()]); pp=len([q for q in re.split(r'\n\s*\n',x['markdown'].strip()) if q.strip()])
    t,o=E[k]['text'],E[k]['order']
    ratio.append(pp/max(1,gp))
    if o is not None and t is not None and o<t-15: cc['order much worse than text (paragraph structure/order mismatch)']+=1
    elif t is not None and t<70: cc['text score itself low (content/wording differs from reference)']+=1
    else: cc['both moderately low']+=1
    if pp>1.5*gp: cc['  (our paragraph count >1.5x reference)']+=1
    if pp<0.67*gp: cc['  (our paragraph count <0.67x reference)']+=1
for c,v in cc.most_common(): print(f'   {v:4d}  {c}')
print(f'   median (our paragraphs / reference paragraphs) on these pages: {st.median(ratio):.2f}')
