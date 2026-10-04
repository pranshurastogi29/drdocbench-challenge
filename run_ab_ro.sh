#!/bin/zsh
# A/B of reading-order prompt rules on dev multi-column windows (runs/ab_ro_windows.json): fresh v7 baseline vs v10a vs v10b, same settings as v7
cd ~/Desktop/drdocbench
C=(--fold all --windows runs/ab_ro_windows.json --workers 4 --max-side 1600 --reasoning low)
.venv/bin/python predict.py $C --prompt v7   --tag ab_v7   > runs/ab_v7.log 2>&1 &
.venv/bin/python predict.py $C --prompt v10a --tag ab_v10a > runs/ab_v10a.log 2>&1 &
.venv/bin/python predict.py $C --prompt v10b --tag ab_v10b > runs/ab_v10b.log 2>&1 &
wait
echo ALLDONE
