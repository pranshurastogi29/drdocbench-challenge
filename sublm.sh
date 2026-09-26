#!/bin/bash
# usage: ./sublm.sh <tag> <model> <prompt> <reasoning>  -- fold A, 48-window subset, 1600px
cd "$(dirname "$0")"
exec .venv/bin/python predict.py --fold a --subset 48 --workers 6 --model "$2" --tag "$1" --prompt "$3" --max-side 1600 --reasoning "$4" > "runs/$1.log" 2>&1
