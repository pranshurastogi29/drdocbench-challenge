#!/bin/bash
# Complete the dev side of the three core one-page runs (v6/v7/v8 w1) from the 400-page sample to all 986 pages, so that final5b/final5c can be
# validated on ~950 scored pages instead of 383. Resumable: pages already in the output files are skipped.
cd "$(dirname "$0")"
while pgrep -f run_w1_queue2.sh > /dev/null; do sleep 20; done
P=.venv/bin/python
C="--workers 6 --reasoning low --window 1 --max-side 1600"
for v in v7 v6 v8; do $P predict.py --fold all $C --prompt $v --tag ${v}_w1 > runs/full_${v}_w1.log 2>&1; done
echo QUEUE3_DONE > runs/w1_queue3.done
