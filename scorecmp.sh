#!/bin/bash
# usage: ./scorecmp.sh <predictions-basename> <name> <restrict-basename>  -- official md2md scoring on the shared pages
cd "$(dirname "$0")"
.venv/bin/python run_md2md_eval.py "runs/$1.jsonl" --name "$2" --restrict-to "runs/$3.jsonl" -q > "runs/score_$2.txt" 2>&1
