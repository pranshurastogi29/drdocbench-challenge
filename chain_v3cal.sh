#!/bin/bash
# wait for the full v3 dev run, then score it with the official scorer (same pages as the other dev runs)
cd "$(dirname "$0")"
while pgrep -f "[p]redict.py --fold all" >/dev/null; do sleep 15; done
cp runs/dev_all_full_v3.jsonl runs/dev_all_v3_final.jsonl
.venv/bin/python run_md2md_eval.py runs/dev_all_v3_final.jsonl --name FINAL_v3 --restrict-to runs/dev_all_v7_final.jsonl -q > runs/score_FINAL_v3.txt 2>&1
{ echo "v3 dev rows: $(wc -l < runs/dev_all_v3_final.jsonl)  failed windows: $(grep -c FAILED runs/full_v3.log)"; grep -h '^\[' runs/score_FINAL_v3.txt | cut -c1-140; } > runs/v3cal.txt 2>&1
echo done >> runs/v3cal.txt
