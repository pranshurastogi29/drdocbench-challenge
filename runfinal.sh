#!/bin/bash
# usage: ./runfinal.sh <prompt> <tag>   -- full test split with the chosen prompt, low reasoning, 1600px
cd "$(dirname "$0")"
exec .venv/bin/python predict.py --split test --prompt "$1" --max-side 1600 --reasoning low --workers 6 --tag "$2" > "runs/test_$2.log" 2>&1
