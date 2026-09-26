# Large artifacts (not in git)

| Artifact | Path | sha256 (first 20) | How to regenerate |
|---|---|---|---|
| Page images + manifest for Kaggle | `kaggle/drdocbench_pages.zip` | b6330c526ba2fac9b154 | `python kaggle/build_package.py` (needs `data/`) |
| PaddleOCR-VL 1.6 output, all 1,495 pages | `kaggle/results/paddle/paddleocrvl_results.zip` (unzip to `.../out/`) | 9724c54564a9e06ba334 | `kaggle/paddleocr_vl.ipynb` via `kaggle/run_kaggle.py push paddle` (4.6 h on 2x T4) |
| MinerU 2.7.6 output (pipeline backend), 1,495 pages | `~/Downloads/mineru_results/` | (folder) | `kaggle/mineru.ipynb` via `run_kaggle.py push mineru2` (about 1 h); tested and rejected |
| Raw dataset | `data/` | - | `hf download 2077AIDataFoundation/DrDocBench --repo-type dataset --local-dir data` |
| Official scorer | `scorer/` | - | see `SCORER_PIN.txt` |

Small archives that ARE tracked: `artifacts/candidates_dev.tar.gz` and `artifacts/candidates_test.tar.gz` (the LLM, Paddle and MinerU
candidate outputs used to build every submission).
External resources to disclose in a technical report: `stealth/space-bunny-alpha` (OpenRouter), PaddleOCR-VL 1.6 with PP-DocLayoutV3.
