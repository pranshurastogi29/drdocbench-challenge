# Leaderboard submissions

Scored submissions of team **pranshu29** on the Dr.DocBench EvalAI leaderboard, in order. Dashes: component not recorded.
The leaderboard's evaluation changed between the October 4 and October 5 uploads, so compare later rows with each other.

| Date | Submission | Text_ED | TEDS | CDM | RO | Overall | Note |
|---|---|---|---|---|---|---|---|
| Sep | v3 single run | - | - | - | - | 67.77 | first baseline |
| Sep | medoid + layout snap | - | - | - | - | 77.25 | ensemble and PaddleOCR-VL snap |
| Sep | + PaddleOCR-VL tables | - | 67.81 | - | - | 77.39 | |
| Sep | `final5` | 0.1681 | 68.0 | 0 | 82.85 | 78.66 | contrast run as fifth vote |
| Sep 27 | `final5_wd` | 0.1681 | 68.0 | 55.0 | 82.85 | 81.59 | first formula candidates |
| Sep 27 | `final8_wd` | 0.1834 | - | - | - | 80.73 | contrast runs as extra votes (reversed) |
| Sep 27 | `final9_wd` | 0.1875 | - | - | - | 80.41 | + page repairs (reversed) |
| Sep 28 | `final5t` | - | - | - | - | 78.65 | table crop vote, isolated |
| Sep 28 | `final5t_wd` | - | - | - | - | 81.56 | table crop vote + formula candidates |
| Sep 28 | `final7` | 0.1838 | - | - | 82.56 | 77.82 | confirms the contrast-vote regression |
| Oct 2 | `final5ti_wd` | - | - | - | - | 81.54 | + index-entry splits |
| Oct 2 | `final5x_wd` | 0.1682 | 68.0 | 54.78 | 82.27 | 81.38 | drop text PaddleOCR-VL lacks |
| Oct 2-4 | `probe_G1`, `probe_G2`, `probe_G3` | 0.3568 / 0.3560 / 0.3901 | - | - | 64.6 / 63.82 / 60.48 | 62.99 / 63.39 / 59.61 | diagnostic: groups of books blanked to decode their error |
| Oct 4 | `final5b_wd` | 0.1853 | 66.82 | 55.74 | 83.21 | 80.96 | one-page windows as the pool (reversed) |
| Oct 4 | `ab_g2_sol61` | 0.1775 | 65.0 | 57.88 | 82.62 | 81.12 | GPT-6.1 sol-pro on the 120 hardest pages |
| Oct 4 | `final5_fc6t` | 0.1681 | 71.86 | 63.21 | 82.85 | 81.97 | more wrapper styles, pools, table candidates |
| Oct 5 | `final5_fc10t` | 0.1724 | 71.86 | 65.86 | 84.44 | 82.52 | GPT-6.1 formula candidates; evaluation updated |
| Oct 5 | `final5m_fc10t_fm_sd_bv_ac` | 0.1689 | 71.86 | 65.79 | 84.91 | 82.88 | MBR selection, furniture merge, spill drop, boundary votes, cleanup |
| Oct 5 | `final5m_fc10t_fm_sd_bv_ac_si3k2` | 0.1734 | 71.86 | 65.79 | 85.39 | 82.86 | column-break split import |
| Oct 6 | `e2e_pools_am` | 0.1727 | 71.86 | 12.54 | 84.91 | 79.88 | end-to-end hypothesis test (refuted) |
| Oct 6 | `cdm_max` | 0.1689 | 71.86 | 76.54 | 84.91 | 83.53 | formula candidates from every run |
| Oct 8 | `cdm_max_mbr8_cons` | 0.1641 | 71.86 | 76.79 | 85.65 | 84.13 | column-break runs in MBR, gated word consensus |
| Oct 9 | **`cdm_max2_mbr8_cons`** | **0.1641** | **71.86** | **81.84** | **85.65** | **84.54** | **final** |

## Final confirmed leaderboard (2026-10-13)

| Rank | Team | Text_ED | Table_TEDS | Formula_CDM | Reading_Order | Overall |
|---|---|---|---|---|---|---|
| 1 | ohmyyuan | 0.1395 | 65.51 | 75.91 | 89.91 | 87.28 |
| 2 | AIKHEMIST | 0.1464 | 70.68 | 76.71 | 86.43 | 85.83 |
| 3 | OC | 0.1399 | 72.57 | 48.80 | 87.97 | 85.63 |
| 4 | ppppppp | 0.1326 | 73.13 | 72.19 | 85.86 | 85.58 |
| 5 | tranquil | 0.1442 | 72.57 | 50.26 | 87.73 | 85.30 |
| 6 | Zhiheng | 0.1445 | 65.65 | 73.61 | 84.45 | 84.64 |
| **7** | **pranshu29** | **0.1641** | **71.86** | **81.84** | **85.65** | **84.54** |

Every uploaded file was rebuilt byte-identically by `stack.py` / `build_submission.py` from the archived model outputs; the
outputs themselves are not published (they are transcriptions of copyrighted book pages).
