#!/bin/zsh
# test-time augmentation runs of the column-break prompt v10a (free model, expires 2026-10-05): contrast image, temperature 0.5, shifted window grid
cd ~/Desktop/drdocbench
B=(--workers 4 --max-side 1600 --reasoning low --prompt v10a)
for split in dev test; do
  F=(); [ $split = dev ] && F=(--fold all) || F=(--split test)
  nohup .venv/bin/python predict.py $F $B --preprocess contrast --tag v10ac > runs/${split}_v10ac.log 2>&1 &
  nohup .venv/bin/python predict.py $F $B --temperature 0.5 --tag v10at > runs/${split}_v10at.log 2>&1 &
  nohup .venv/bin/python predict.py $F $B --offset 1 --tag v10ao > runs/${split}_v10ao.log 2>&1 &
done
