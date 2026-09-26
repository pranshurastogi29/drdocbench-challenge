#!/bin/bash
# official md2md scores for every dev experiment, on the common page set of each fold
cd "$(dirname "$0")"
run() { .venv/bin/python run_md2md_eval.py "runs/$1.jsonl" --name "$2" --restrict-to "runs/$3.jsonl" -q 2>&1 | grep '^\[' ; }
echo "### FOLD A (tuning fold), pages of runs/dev_a_a_v6"
for x in dev_a_v0:A_v0_orig dev_a_v1_hi_low:A_v1 dev_a_v0_hi_low:A_v0_1600_low dev_a_a24:A_v0_2400_low dev_a_a16m:A_v0_1600_med dev_a_v2_hi_low:A_v2 dev_a_v3_hi_low:A_v3 dev_a_a_v4:A_v4 dev_a_a_v5:A_v5 dev_a_a_v6:A_v6; do run "${x%%:*}" "${x##*:}" dev_a_a_v6; done
echo "### FOLD B (held-out), pages of runs/dev_b_b_v6"
for x in dev_b_b_v0_base:B_v0_orig dev_b_b_v3:B_v3 dev_b_b_v4:B_v4 dev_b_b_v5:B_v5 dev_b_b_v6:B_v6; do run "${x%%:*}" "${x##*:}" dev_b_b_v6; done
