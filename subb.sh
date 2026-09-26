#!/bin/bash
# usage: ./subb.sh <tag> <prompt> <max-side> <reasoning|none>   (fold B held-out, 48-window subset)
cd "$(dirname "$0")"
R=(); [ "$4" != "none" ] && R=(--reasoning "$4")
exec .venv/bin/python predict.py --fold b --subset 48 --workers 6 --tag "$1" --prompt "$2" --max-side "$3" "${R[@]}" > "runs/$1.log" 2>&1
