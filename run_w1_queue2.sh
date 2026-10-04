#!/bin/bash
# Extra one-page (window=1) free-model candidates, each: dev 400-page sample first (same pages as the earlier w1 samples), then test.
cd "$(dirname "$0")"
while pgrep -f run_w1_queue.sh > /dev/null; do sleep 20; done      # the first queue (contrast test run) must finish first: free tier rate-limits parallel runs
P=.venv/bin/python
C="--workers 6 --reasoning low --window 1"
$P predict.py --fold all --subset 400 $C --max-side 1200 --prompt v7 --tag v7sw1 > runs/v7sw1.log 2>&1
$P predict.py --split test            $C --max-side 1200 --prompt v7 --tag v7sw1 > runs/test_v7sw1.log 2>&1
$P predict.py --fold all --subset 400 $C --max-side 1600 --prompt v5 --tag v5w1  > runs/v5w1.log 2>&1
$P predict.py --split test            $C --max-side 1600 --prompt v5 --tag v5w1  > runs/test_v5w1.log 2>&1
$P predict.py --fold all --subset 400 $C --max-side 1600 --prompt v7 --temperature 0.5 --tag v7tw1 > runs/v7tw1.log 2>&1
$P predict.py --split test            $C --max-side 1600 --prompt v7 --temperature 0.5 --tag v7tw1 > runs/test_v7tw1.log 2>&1
echo QUEUE2_DONE > runs/w1_queue2.done
