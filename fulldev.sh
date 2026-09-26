#!/bin/bash
# usage: ./fulldev.sh <tag> <model> <prompt> <reasoning>  -- ALL 986 dev pages, 1600px
cd "$(dirname "$0")"
exec .venv/bin/python predict.py --fold all --workers 6 --model "$2" --tag "$1" --prompt "$3" --max-side 1600 --reasoning "$4" > "runs/$1.log" 2>&1
