#!/bin/bash
# test-set crop passes (same settings as the dev passes t1/t2/t3)
cd "$(dirname "$0")"
.venv/bin/python table_crops.py --split test --tag t1 --preprocess contrast --max-side 1600 > runs/tables_test_t1.log 2>&1
.venv/bin/python table_crops.py --split test --tag t2 --preprocess none --max-side 1200 > runs/tables_test_t2.log 2>&1
.venv/bin/python table_crops.py --split test --tag t3 --preprocess contrast --max-side 2000 > runs/tables_test_t3.log 2>&1
