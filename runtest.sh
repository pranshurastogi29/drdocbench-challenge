#!/bin/bash
cd "$(dirname "$0")"
exec .venv/bin/python predict.py --split test --prompt v3 --max-side 1600 --reasoning low --workers 6 --tag final > runs/test_final.log 2>&1
