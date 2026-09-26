"""Table post-processing experiments scored with table_lab (dev, final5 predictions)."""
import re, sys, time
from table_lab import gt_tables, load_pred, score
G = gt_tables(); P = load_pred(sys.argv[1] if len(sys.argv) > 1 else "runs/dev_all_final5.jsonl")
ROW = re.compile(r"<tr\b[^>]*>.*?</tr>", re.S | re.I); CELL = re.compile(r"(<t([dh])\b[^>]*>)(.*?)(</t[dh]>)", re.S | re.I)

def cells_of(row): return CELL.findall(row)

def wrap_th(t):      return CELL.sub(lambda m: m.group(1) + (f"<strong>{m.group(3)}</strong>" if m.group(2).lower() == "h" and m.group(3).strip() else m.group(3)) + m.group(4), t)
def wrap_row0(t):
    rows = ROW.findall(t)
    if not rows: return t
    new = CELL.sub(lambda m: m.group(1) + (f"<strong>{m.group(3)}</strong>" if m.group(3).strip() and "<strong" not in m.group(3) else m.group(3)) + m.group(4), rows[0])
    return t.replace(rows[0], new, 1)
def br_to_space(t):  return re.sub(r"<br\s*/?>", " ", t, flags=re.I)
def no_bold(t):      return re.sub(r"</?(strong|em|b|i)\b[^>]*>", "", t, flags=re.I)
def drop_title_row(t):
    rows = ROW.findall(t)
    if len(rows) > 1 and len(cells_of(rows[0])) == 1 and "colspan" in rows[0].lower(): return t.replace(rows[0], "", 1)
    return t
def drop_empty_rows(t):
    return ROW.sub(lambda m: "" if cells_of(m.group(0)) and all(not re.sub(r"<[^>]+>|\s", "", c[2]) for c in cells_of(m.group(0))) else m.group(0), t)
EXPS = {"baseline": None, "th_bold": wrap_th, "row0_bold": wrap_row0, "br_to_space": br_to_space, "no_bold(control)": no_bold,
        "drop_title_row": drop_title_row, "drop_empty_rows": drop_empty_rows}
if __name__ == "__main__":
    base = None
    for n, f in EXPS.items():
        t0 = time.time(); m, flat = score(P, f, G=G); base = base if base is not None else m
        print(f"{n:20s} {m:6.2f}  ({m-base:+.2f})  {time.time()-t0:.0f}s", flush=True)
