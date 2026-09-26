#!/bin/bash
# Qwen3.8 Flash (paid, ~$0.003/window): full dev then test, prompt v7, 1600px, contrast preprocessing, reasoning low
cd "$(dirname "$0")"
.venv/bin/python predict.py --split dev --fold all --workers 8 --model qwen/qwen3.8-flash --tag flash_dev --prompt v7 --max-side 1600 --reasoning low --preprocess contrast > runs/flash_dev.log 2>&1
.venv/bin/python predict.py --split test --workers 8 --model qwen/qwen3.8-flash --tag flash_test --prompt v7 --max-side 1600 --reasoning low --preprocess contrast > runs/flash_test.log 2>&1
echo done > runs/flash.done
