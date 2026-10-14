# Milestones

Development summary of the **pranshu29** system for the Dr.DocBench track of the DocInsights 2026 shared task
(EMNLP 2026). Final confirmed result: **rank 7, Overall 84.54** (Text_ED 0.1641, Table TEDS 71.86, Formula CDM 81.84,
Reading Order 85.65). Method, ablations and analysis: `report/acl/paper.pdf`. Leaderboard submissions: `SUBMISSIONS.md`.

All development numbers are on the 986-page development set (66 books), scored locally with the official md2md matcher;
"leaderboard units" means 0.558 x Text + 0.433 x Reading Order (Text = 100 x (1 - Text_ED)), with book-clustered bootstrap
intervals.

## Timeline of kept changes

| # | Date | Change | Development evidence | Leaderboard |
|---|---|---|---|---|
| 1 | Sep | Harness: free OpenRouter VLM (`stealth/space-bunny-alpha`), 2-page windows, 1600 px, prompt v3 | v3 72.24 (dev overstated test by ~4.5) | 67.77 |
| 2 | Sep | Page furniture written last (v4-v5), capitalisation rule (v6), explicit body / furniture sections (v7) | furniture last: reading order +~12; v7 vs v6 +0.7 overall, +1.7 order | - |
| 3 | Sep | Medoid ensemble of three prompt runs + PaddleOCR-VL; paragraph splits snapped to PaddleOCR-VL layout blocks | medoid +1.04 vs v7 (best-of-4 oracle 88.8); snap splits +0.94, snap merges -1.15 (dropped) | 77.25 |
| 4 | Sep | PaddleOCR-VL tables where no candidate has one | TEDS 58.65 -> 67.81 on test | 77.39 |
| 5 | Sep | Contrast-preprocessed run as fifth vote (`final5`) | +0.32 dev, +1.27 test (test pages have 28% lower contrast) | 78.66 |
| 6 | Sep 27 | Formula candidates: italic LaTeX wrappers for short lines | text / order / TEDS identical on all pages | 81.59 |
| 7 | Oct 4 | More wrapper styles, pooled formulas, table candidates | text / order unchanged | 81.97 |
| 8 | Oct 5 | Formula candidates from GPT-6.1 sol-pro transcriptions of 120 test pages | leaderboard evaluation updated this day | 82.52 |
| 9 | Oct 5 | MBR selection with the official matching as utility, furniture merge, spill drop, boundary votes, markup cleanup | MBR +1.19 dev (book CI +0.43..+1.87); + furniture merge +1.84 | 82.88 |
| 10 | Oct 6 | Formula candidates from every run, symbol channel | text / order unchanged | 83.53 |
| 11 | Oct 8 | Column-break runs (v10a / v10b / v11) as MBR candidates and pseudo-references (`mbr8`), gated word consensus | +0.878 dev (Text_ED 0.1264 -> 0.1168, RO 87.79 -> 88.58) | 84.13 |
| 12 | Oct 9 | More candidate sources and wrapper styles (final) | text / order unchanged | **84.54** |

## Pipeline steps: leave-one-out on top of the final selection (925 dev pages)

| Removed | Text_ED | RO | Change |
|---|---|---|---|
| none (final) | 0.1168 | 88.58 | - |
| layout snap + PaddleOCR-VL tables | 0.1204 | 87.11 | -0.84 [-1.34, -0.34] |
| furniture merge | 0.1162 | 87.49 | -0.44 |
| boundary votes | 0.1186 | 88.48 | -0.14 [-0.36, -0.02] |
| spill drop | 0.1187 | 88.55 | -0.12 |
| markup cleanup | 0.1169 | 88.58 | -0.01 |
| (added) gated word consensus | 0.1168 | 88.58 | +0.005 |

## Selection

- MBR over the five base runs beat the medoid by +1.05 (book CI +0.38..+1.85). Weighted MBR, ridge / gradient-boosting rankers on
  16-21 label-free features and paragraph-level fusion were all within noise of plain MBR; a per-page oracle over the same runs is +4.8.
- Six column-break variants as extra pseudo-references: +0.36. v10a / v10b / v11 also as candidates (`mbr8`): +0.878.
- All 17 runs as references: +0.59 (dilutes the column-break signal). Text-weighted utility (0.7 / 0.3): +0.15, trades order for text.
- Stronger models as extra candidates: +0.1..+0.2 once one outlier page is removed; Kimi K2.5 inside `mbr8`: -0.02.

## Segmentation and reading order

- Column-break split import from the v10 runs (at least two of three runs agree): +1.00 per page on dev but -0.02 on the leaderboard,
  because most of the development gain came from splits inside list blocks, a development-book convention. Without splits inside one
  layout block: -0.005 dev; any one of three runs: RO +0.27, Text_ED +0.0033.
- Reading-order loss of the final pipeline (11.4 points on dev): displaced body blocks 3.74, unmatched body blocks 1.83, titles 1.31,
  page numbers 1.21, running headers 0.96, captions 1.02. The references order page-end furniture by annotation order; the furniture
  merge neutralises it where PaddleOCR-VL labels the lines.
- Geometric column-major reordering (-3.2..-4.5 RO), consensus order (-1.08 RO), moving running heads (-0.2..-0.3 per page),
  merging short paragraphs (-0.6..-1.1), list chunking under the 300-character limit (-0.8..-1.8), page-number tail merges
  (-0.08..-0.62): all worse.

## Word-level consensus

- Plain majority vote across runs: -0.06 (32 pages worse, 6 better): the runs share one model and its errors.
- Gated vote (near-spellings only, not at paragraph edges, confirmed by PaddleOCR-VL / MinerU or a dictionary): +0.006, no page worse;
  on test it changes 33 words on 24 pages (e.g. ATHAWAY -> HATHAWAY, Macmillian -> Macmillan, Polish diacritics).

## Where the test error is

Three diagnostic submissions blanked groups of test books; the leaderboard change gives each group's own scores (pipeline of step 6):

| Test books | Pages | Text_ED | RO |
|---|---|---|---|
| G1: subjects absent from dev | 120 | 0.200 | 77.4 |
| G2: highest run disagreement | 120 | 0.203 | 80.7 |
| G3: half of the rest | 134 | 0.157 | 85.0 |
| G4: other half (derived) | 135 | 0.120 | 87.5 |

On dev, text error splits into matched blocks with edits (49%), our text no reference block contains (40%) and missing reference
text (11%); half of it sits on 8% of the pages, where the reference made a book-specific choice (picture text kept as an image, a
directory kept as a table, crossword clues kept as one block).

## Development gains that did not transfer to the leaderboard

| Change | Dev | Leaderboard |
|---|---|---|
| Contrast runs as extra votes | +0.39 | -0.84 |
| One-page windows as the candidate pool | +1.02 | -0.63 |
| GPT-6.1 sol-pro on the 120 hardest pages | +0.06 | -0.47 |
| Drop text PaddleOCR-VL lacks | +0.02 | -0.21 |
| Column splits including list splits | +1.00 | -0.02 |
| Index-entry splits | +0.08 | -0.02 |
| End-to-end-tuned formula pools (tested whether the leaderboard scores end-to-end; it does not) | +1.09 | -3.00 |

## Models

| Model | Result on dev |
|---|---|
| Kimi K2.5 alone (OpenRouter) | Text_ED 0.0614 vs 0.0857, RO 85.20 vs 88.45: -0.05 |
| Kimi K2.5 alone (Hugging Face host) | -4.19 |
| Gemini 3.8 Flash alone | -0.56 |
| Kimi K2.6 (no thinking) alone | -3.14 |
| GPT-6 sol-pro alone (897 pages) | -3.19 |
| GPT-6 sol-pro / GPT-6.1 / Kimi order applied to our text | -1.07 / -1.32 / -1.34 |
| Kimi K2.5 proofreading our page with the image | -2.6 as returned; word-level fixes only +-0.00 |
| MiMo v2.6 Pro, GLM-5.3 Flash, DeepSeek V4.1 Flash | 6-9 points below the free model |
| Claude Sonnet 5.5 | declined to transcribe copyrighted book pages |
| PaddleOCR-VL / MinerU paragraph boundaries on our text | -1.4..-1.7 |

## Scorer mechanics

- Consecutive predicted blocks are joined to one reference block only if that block is at most 300 normalised characters and the
  page has at most 3600 reference x prediction pairs.
- Our unmatched blocks cost nothing while any reference block is unmatched; once every reference block is matched they are counted.
- Normalisation keeps word characters only (runs of 4+ underscores become 4): punctuation and Markdown emphasis do not count; case and
  digits do.
- Display formulas and tables are matched separately from text and order, by best match; text and reading order are scored only
  where the reference has text, tables only where both sides have one.
- Overall is the mean of the components available on a page, averaged over pages; a least-squares fit over leaderboard rows gave
  0.558 Text + 0.433 RO + 0.054 CDM + 0.006 TEDS - 3.9.
