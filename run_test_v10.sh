#!/bin/zsh
# test-set runs of the reading-order prompts (free model expires 2026-10-05), same settings as v7
cd ~/Desktop/drdocbench
C=(--split test --workers 3 --max-side 1600 --reasoning low)
.venv/bin/python predict.py $C --prompt v10a --tag v10a > runs/test_v10a.log 2>&1 &
.venv/bin/python predict.py $C --prompt v10b --tag v10b > runs/test_v10b.log 2>&1 &
wait
echo ALLDONE
