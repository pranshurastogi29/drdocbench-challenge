#!/bin/bash
cd "$(dirname "$0")"
.venv/bin/python run_md2md_eval.py "runs/dev_all_$1.jsonl" --name "FULL_$1" --restrict-to runs/dev_all_full_luna.jsonl -q > "runs/score_$1.txt" 2>&1
