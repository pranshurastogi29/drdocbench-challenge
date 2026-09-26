#!/bin/bash
cd "$(dirname "$0")"
while pgrep -f "[p]redict.py --split dev --fold all" >/dev/null; do sleep 15; done
cp runs/dev_all_v7c_dev.jsonl runs/dev_all_v7c_final.jsonl
.venv/bin/python run_md2md_eval.py runs/dev_all_v7c_final.jsonl --name FINAL_v7C --restrict-to runs/dev_all_v7_final.jsonl -q > runs/score_FINAL_v7C.txt 2>&1
{ echo "v7c dev rows: $(wc -l < runs/dev_all_v7c_final.jsonl)  failed windows: $(grep -c FAILED runs/v7c_dev.log)"
  grep -h '^\[' runs/score_FINAL_v7.txt runs/score_FINAL_v7C.txt | cut -c1-140; echo
  .venv/bin/python contrast_check.py 2>&1 | grep -v -i warning; } > runs/compare_c.txt 2>&1
echo done >> runs/compare_c.txt
