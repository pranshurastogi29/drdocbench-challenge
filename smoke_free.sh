#!/bin/bash
# smoke test: free vision models, one at a time (free tier = 20 requests/min across all free models), same 40 dev windows (seed 0), prompt v7, 1600px, reasoning low
cd "$(dirname "$0")"
run() { tag="$1"; model="$2"
  .venv/bin/python predict.py --split dev --fold all --subset 40 --workers 2 --model "$model" --tag "$tag" --prompt v7 --max-side 1600 --reasoning low > "runs/${tag}.log" 2>&1; }
run sm_dots     "dots-studio/dots-3-note-preview:free"
run sm_qwen     "qwen/qwen3.8-27b:free"
run sm_gemma31  "google/gemma-4-31b-it:free"
run sm_gemma26  "google/gemma-4-26b-a4b-it:free"
run sm_nemo     "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
echo done > runs/smoke_free.done
