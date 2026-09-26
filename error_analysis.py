import json, re, glob, collections, statistics as st
from rapidfuzz import fuzz
from compare_runs import load
from reading_order import load_page
from common import gt_markdown

names=['v6','v7','v8','paddle']
S={'v6':load('FINAL_v6'),'v7':load('FINAL_v7'),'v8':load('FINAL_v8'),'paddle':load('PADDLE')}
files={'v6':'runs/dev_all_full_bunny.jsonl','v7':'runs/dev_all_v7_final.jsonl','v8':'runs/dev_all_v8_final.jsonl','paddle':'runs/paddle_dev.jsonl'}
T={n:{f"{x['document_id']}_{x['page']}.jpg":x for x in map(json.loads,open(f))} for n,f in files.items()}
keys=sorted(set.intersection(*[set(S[n]) for n in S]))
nz=lambda s: re.sub(r'\s+',' ',s.lower())[:6000]
def medoid(k):
    sc={n:sum(fuzz.ratio(nz(T[n][k]['markdown']),nz(T[m][k]['markdown'])) for m in names if m!=n) for n in names}
    return max(names,key=lambda n:(sc[n],n=='v7')), sc
pick={};agree={}
for k in keys:
    c,sc=medoid(k); pick[k]=c; agree[k]=sum(sc.values())/12   # mean pairwise similarity across the 4 candidates
E={k:S[pick[k]][k] for k in keys}; N=len(keys)
ov=[E[k]['overall'] for k in keys]; lost_total=sum(100-x for x in ov)
print(f'ENSEMBLE (medoid of v6,v7,v8,paddle): {N} scored dev pages, mean overall {st.mean(ov):.2f}')

print('\n== 1. Score distribution and where the lost points are')
for lo,hi,name in ((95,101,'>=95'),(90,95,'90-95'),(80,90,'80-90'),(60,80,'60-80'),(30,60,'30-60'),(-1,30,'<30')):
    s=[x for x in ov if lo<=x<hi]; print(f'  {name:6s} pages {len(s):4d} ({100*len(s)/N:4.1f}%)  mean {st.mean(s) if s else 0:5.1f}  share of all lost points {100*sum(100-x for x in s)/lost_total:4.1f}%')

print('\n== 2. Which component loses the points (each page: loss split evenly across the components it has)')
loss=collections.Counter(); cnt=collections.Counter()
for k in keys:
    comps={c:E[k][c] for c in ('text','order','teds') if E[k][c] is not None}
    for c,v in comps.items(): loss[c]+=(100-v)/len(comps); cnt[c]+=1
tot=sum(loss.values())
for c in ('text','order','teds'): print(f'  {c:6s} on {cnt[c]:4d} pages  -> {loss[c]/N:5.2f} points off the mean overall ({100*loss[c]/tot:.0f}% of the total loss)')

print('\n== 3. What ALL four candidates get wrong (ensemble cannot fix these)')
best=[max(S[n][k]['overall'] for n in names) for k in keys]
print(f'  oracle best-of-4 mean: {st.mean(best):.2f}   (gap to 100 = {100-st.mean(best):.1f}; gap ensemble->oracle = {st.mean(best)-st.mean(ov):.1f})')
for thr in (95,90,80):
    n=sum(b<thr for b in best); print(f'  pages where even the BEST candidate is < {thr}: {n:4d} ({100*n/N:.0f}%)   share of ensemble lost points: {100*sum(100-E[k]["overall"] for k,b in zip(keys,best) if b<thr)/lost_total:.0f}%')
print('  candidate agreement vs score: (mean pairwise text similarity of the 4 outputs)')
for lo,hi in ((90,101),(80,90),(60,80),(0,60)):
    s=[E[k]['overall'] for k in keys if lo<=agree[k]<hi]
    if s: print(f'    agreement {lo:3d}-{min(hi,100):3d}: pages {len(s):4d}  mean score {st.mean(s):5.1f}   pages <80: {sum(x<80 for x in s):3d}')
hi=[k for k in keys if agree[k]>=90]; print(f'  -> among the {len(hi)} pages where all candidates agree (>=90% similar), {sum(E[k]["overall"]<80 for k in hi)} still score <80: agreed-upon output that the reference still disagrees with')

print('\n== 4. Page types (attributes from the ground-truth metadata)')
attr=collections.defaultdict(list)
for k in keys:
    doc,pg=k.rsplit('_',1); pg=int(pg[:-4]); rec=load_page('dev',T['v7'][k]['subject'],doc,pg)
    if not rec: continue
    pa=rec['page_info'].get('page_attribute',{})
    attr[('layout',pa.get('layout'))].append(E[k]['overall']); attr[('source',pa.get('data_source'))].append(E[k]['overall'])
    attr[('challenge',pa.get('challenge_type'))].append(E[k]['overall'])
    for f in (pa.get('special_issue') or []): attr[('flag',f)].append(E[k]['overall'])
    if not (pa.get('special_issue') or []): attr[('flag','(none)')].append(E[k]['overall'])
rows=[(a,v,s) for (a,v),s in attr.items() if len(s)>=15]
for a,v,s in sorted(rows,key=lambda r:st.mean(r[2])):
    print(f'  {a:9s} {str(v):24s} pages {len(s):4d}  mean {st.mean(s):5.1f}  share of lost points {100*sum(100-x for x in s)/lost_total:4.1f}%')

print('\n== 5. What 95 would take')
med=st.median(ov); print(f'  median page scores {med:.1f}; pages >=95: {100*sum(x>=95 for x in ov)/N:.0f}%; 75th percentile {sorted(ov)[int(.75*N)]:.1f}')
for name,fix in (('raise every page <50 to 85',lambda x: 85 if x<50 else x),('raise every page <80 to 90',lambda x: 90 if x<80 else x),('cap losses: no page below 90',lambda x: max(x,90)),('no page below 95',lambda x: max(x,95))):
    print(f'  {name:32s} -> mean {st.mean(fix(x) for x in ov):.2f}')
