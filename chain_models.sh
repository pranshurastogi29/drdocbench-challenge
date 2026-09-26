#!/bin/bash
cd ~/Desktop/drdocbench
for t in kimi muse sol; do
  .venv/bin/python run_md2md_eval.py runs/dev_a_a_$t.jsonl --name PART_$t --restrict-to runs/dev_a_a_$t.jsonl -q > runs/score_PART_$t.txt 2>&1 &
  .venv/bin/python run_md2md_eval.py runs/dev_all_v7_final.jsonl --name V7ON_$t --restrict-to runs/dev_a_a_$t.jsonl -q > runs/score_V7ON_$t.txt 2>&1 &
done
wait
{ for t in kimi muse sol; do echo "##### $t (pages finished before the credit limit: $(wc -l < runs/dev_a_a_$t.jsonl))"; grep -h '^\[' runs/score_V7ON_$t.txt runs/score_PART_$t.txt | cut -c1-135; .venv/bin/python compare_runs.py V7ON_$t PART_$t 2>&1 | head -6 | sed -n '1p;2p;3p;4p'; echo; done; } > runs/compare_models.txt 2>&1
echo done >> runs/compare_models.txt
