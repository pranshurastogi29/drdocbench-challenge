#!/bin/bash
# usage: ./run_c.sh dev|test <tag>   -- v7 prompt with contrast preprocessing, 1600px, low reasoning
cd "$(dirname "$0")"
if [ "$1" = "dev" ]; then SPLIT="--split dev --fold all"; else SPLIT="--split test"; fi
exec .venv/bin/python predict.py $SPLIT --workers 6 --model stealth/space-bunny-alpha --tag "$2" --prompt v7 --max-side 1600 --reasoning low --preprocess contrast > "runs/$2.log" 2>&1
