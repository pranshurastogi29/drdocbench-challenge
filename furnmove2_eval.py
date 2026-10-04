"""Running heads into the merged furniture tail (dev).

furnmove.py moved book-level running heads (short edge paragraphs repeating on >= 2 other pages of the book) in front of the trailing furniture,
and lost (-0.13 order) because the order inside the tail still had to match the reference's hidden annotation order. With the furniture merge
(furnmerge.py) the moved line can be MERGED into the tail block, where its order no longer counts; and when the same line is already in the tail
(the model wrote the header twice, top and bottom) the top copy is a duplicate and is dropped instead of moved.
Pipeline per page: MBR base5 pick -> snap -> Paddle tables -> [furnmove, per book] -> furniture merge (moved lines count as furniture).
  python furnmove2_eval.py
"""
import collections, json, os, random, re, statistics as st, sys
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
import mbr
from build_submission import para, MAX_ADD
from common import gt_markdown
from ensemble_lab import gt_score
from sel_lab import BASE5, U, pick_mbr

K = lambda s: re.sub(r"[\W\d_]", "", re.sub(r"<[^>]+>", " ", s).lower())


def pre(a):
    k, md = a
    from snap import snap
    from tablefix import fix
    import paddle_ingest
    s = snap(md, k, mode="split")
    if para(s) - para(md) > MAX_ADD: s = md
    s, _ = fix(s, k, replace=False)
    try: fur = [re.sub(r"[\W_]", "", t.lower()) for _, t in paddle_ingest.furniture(k)]
    except Exception: fur = []
    return k, s, fur


def finish(ps, flagged, fur, mode, max_tail):
    """ps: paragraphs; flagged: indices of running heads (furnmove); returns Markdown"""
    from furnmerge import merge_tail
    if mode != "none" and flagged:
        n = len(ps); t = n
        while t > 0 and ((t - 1) in flagged or re.fullmatch(r"\W*\d{1,4}\W*", ps[t - 1])):
            t -= 1
        tailkeys = {K(p) for p in ps[t:]}
        moved = [ps[i] for i in sorted(flagged) if i < t and K(ps[i]) not in tailkeys]
        drop = {i for i in flagged if i < t}
        rest = [p for i, p in enumerate(ps) if i not in drop]
        t2 = t - len(drop)
        ps = rest[:t2] + (moved if mode == "move" else []) + rest[t2:]
        fur = fur + [re.sub(r"[\W_]", "", p.lower()) for p in moved]
    return merge_tail("\n\n".join(ps), max_tail, 60, fur)


def flag_book(pages, min_pages=2, sim=90, top=2, bottom=4):
    from rapidfuzz import fuzz
    plain = lambda p: not re.match(r"\s*(#|<|\||[-*+]\s|\$|!\[)", p) and "\n" not in p.strip()
    edge = {pg: [(i, K(p)) for i, p in enumerate(ps) if (i < top or i >= len(ps) - bottom) and plain(p) and 4 <= len(K(p)) <= 100] for pg, ps in pages.items()}
    out = {}
    for pg in pages:
        out[pg] = {i for i, k in edge[pg] if sum(any(fuzz.ratio(k, k2) >= sim for _, k2 in edge[o]) for o in pages if o != pg) >= min_pages}
    return out


def score(a):
    k, subj, md = a; doc, pg = k.rsplit("_", 1)
    return k, gt_score(md, gt_markdown("dev", subj, doc, int(pg)))


if __name__ == "__main__":
    C = json.load(open(os.path.join(ROOT, "runs/selcache_dev.json"))); C = {k: v for k, v in C.items() if all(v["gt"][n] for n in v["gt"])}
    with Pool(11, initializer=mbr._init) as P: PRE = {k: (s, f) for k, s, f in P.map(pre, [(k, v["raw"][pick_mbr(v, BASE5)]) for k, v in sorted(C.items())], chunksize=4)}
    paras = lambda md: [p.strip() for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]
    books = collections.defaultdict(dict)
    for k in PRE: books[k.rsplit("_", 1)[0]][int(k.rsplit("_", 1)[1])] = paras(PRE[k][0])
    variants = {}
    for mp in (2, 3):
        FL = {}
        for doc, pages in books.items():
            for pg, s in flag_book(pages, min_pages=mp).items(): FL[f"{doc}_{pg}"] = s
        for mode in ("move", "dropdup"):
            for mt in (2, 3):
                variants[f"min_pages {mp}, {mode}, tail {mt}"] = {k: finish(books[k.rsplit('_', 1)[0]][int(k.rsplit('_', 1)[1])], FL[k], PRE[k][1], mode, mt) for k in PRE}
    base = {k: finish(books[k.rsplit('_', 1)[0]][int(k.rsplit('_', 1)[1])], set(), PRE[k][1], "none", 2) for k in PRE}
    bad = sum(paras(base[k]) != paras(C[k]["proc"][pick_mbr(C[k], BASE5)]) for k in PRE)
    print(f"baseline vs cached pipeline: {bad} pages differ in paragraphs"); assert bad == 0
    base = {k: C[k]["proc"][pick_mbr(C[k], BASE5)] for k in PRE}
    for V in variants.values():
        for k in V:
            if paras(V[k]) == paras(base[k]): V[k] = base[k]
    todo = {(k, md) for V in variants.values() for k, md in V.items() if md != base[k]}
    with Pool(11, initializer=mbr._init) as P: S = {(k, md): s for (k, s), (k2, md) in zip(P.map(score, [(k, C[k]["subject"], md) for k, md in sorted(todo)], chunksize=2), sorted(todo))}
    for name, V in variants.items():
        by = collections.defaultdict(list); d = []
        for k in PRE:
            b = C[k]["gt"][pick_mbr(C[k], BASE5)]; a = S.get((k, V[k]), b); by[k.rsplit("_", 1)[0]].append(U(a) - U(b))
            if V[k] != base[k]: d.append((U(a) - U(b), a[0] - b[0], a[1] - b[1]))
        bk = list(by); rng = random.Random(0); m = lambda bs: sum(sum(by[x]) for x in bs) / sum(len(by[x]) for x in bs)
        bt = sorted(m(rng.choices(bk, k=len(bk))) for _ in range(2000))
        print(f"{name:32s} {m(bk):+.3f}/page [{bt[50]:+.3f},{bt[1949]:+.3f}]  {len(d)} pages changed, better/worse {sum(x[0] > 0 for x in d)}/{sum(x[0] < 0 for x in d)}; "
              f"text {sum(x[1] for x in d)/len(PRE):+.3f} order {sum(x[2] for x in d)/len(PRE):+.3f}", flush=True)
