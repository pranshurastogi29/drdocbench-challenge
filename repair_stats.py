import json, glob
from PIL import Image
from common import list_pages, windows
import repair
from repair import paras, ptext, norm, fuzz, big_image
rows = {(r["document_id"], r["page"]): r["markdown"] for r in map(json.loads, open("runs/dev_all_rebuilt_final7t.jsonl", encoding="utf-8"))}
print("== spill windows: moved paragraphs (count, chars, direction), and Paddle text length per page")
for (subj, doc), pages in list_pages("dev").items():
    for w in windows(pages, 2):
        if len(w) < 2: continue
        (a, _), (b, _) = w; ma, mb = rows[(doc, a)], rows[(doc, b)]
        na, nb = repair.spill(ma, mb, f"{doc}_{a}", f"{doc}_{b}")
        if (na, nb) == (ma, mb): continue
        ta, tb = ptext(f"{doc}_{a}"), ptext(f"{doc}_{b}")
        pa, pb = paras(ma), paras(mb); moved_ab = [p for p in pa if p not in paras(na)]; moved_ba = [p for p in pb if p not in paras(nb)]
        print(f"  {doc[:8]} {a}-{b}: a->b {len(moved_ab)} paras {sum(len(p) for p in moved_ab)} chars | b->a {len(moved_ba)} paras {sum(len(p) for p in moved_ba)} chars | paddle text {len(ta)}/{len(tb)} | our {len(ma)}/{len(mb)}")
print("== figdrop pages")
size = {(d, p): Image.open(path).size for (s, d), pg in list_pages("dev").items() for p, path in pg}
for k, md in rows.items():
    stem = f"{k[0]}_{k[1]}"
    if not big_image(stem, size[k], 0.3): continue
    new = repair.figdrop(md, stem, size[k], 0.3)
    if new != md: print(f"  {k[0][:8]}_{k[1]}: dropped {len(md)-len(new)} of {len(md)} chars; paddle text {len(ptext(stem))}; ratio paddle/ours {len(ptext(stem))/max(1,len(norm(md))):.2f}")
