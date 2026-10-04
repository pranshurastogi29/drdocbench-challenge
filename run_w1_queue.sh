#!/bin/bash
# One-page-per-request (window=1) free-model runs, sequential (the free tier rate-limits parallel runs). Order = value if we run out of time:
# 1 test v7 (the run with dev evidence), 2-4 dev 400-page sample for the other three ensemble candidates, 5-7 their test runs.
cd "$(dirname "$0")"
P=.venv/bin/python
C="--workers 6 --max-side 1600 --reasoning low --window 1"
$P predict.py --split test  $C --prompt v7 --tag v7_w1  > runs/test_v7_w1.log 2>&1
$P predict.py --fold all --subset 400 $C --prompt v6 --tag v6_w1  > runs/v6_w1.log 2>&1
$P predict.py --fold all --subset 400 $C --prompt v8 --tag v8_w1  > runs/v8_w1.log 2>&1
$P predict.py --fold all --subset 400 $C --prompt v7 --preprocess contrast --tag v7c_w1 > runs/v7c_w1.log 2>&1
$P predict.py --split test  $C --prompt v6 --tag v6_w1  > runs/test_v6_w1.log 2>&1
$P predict.py --split test  $C --prompt v8 --tag v8_w1  > runs/test_v8_w1.log 2>&1
$P predict.py --split test  $C --prompt v7 --preprocess contrast --tag v7c_w1 > runs/test_v7c_w1.log 2>&1
echo QUEUE_DONE > runs/w1_queue.done
