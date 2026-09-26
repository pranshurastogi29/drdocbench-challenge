#!/bin/bash
# usage: ./run_c2.sh dev|test <prompt> <tag>   -- contrast-preprocessed run of the free model, 1600px, low reasoning
cd "$(dirname "$0")"
if [ "$1" = "dev" ]; then SPLIT="--split dev --fold all"; else SPLIT="--split test"; fi
exec .venv/bin/python predict.py $SPLIT --workers 4 --model stealth/space-bunny-alpha --tag "$3" --prompt "$2" --max-side 1600 --reasoning low --preprocess contrast > "runs/$3.log" 2>&1
