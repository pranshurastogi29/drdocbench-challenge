#!/bin/bash
# usage: ./sub.sh <tag> <prompt> <max-side> <reasoning>   (fold A, 48-window subset)
cd "$(dirname "$0")"
exec .venv/bin/python predict.py --fold a --subset 48 --workers 5 --tag "$1" --prompt "$2" --max-side "$3" --reasoning "$4" > "runs/$1.log" 2>&1
