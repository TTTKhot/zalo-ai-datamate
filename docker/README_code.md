# DataMate — Zalo AI Challenge 2026 (solution image)

Offline agent that answers Vietnamese questions about the sales data of each shop in `/data`.
Entry point: `bash /code/predict.sh` (no arguments) → `/result/submission.jsonl` + `/result/logs/<business_id>/<id>.json`.

## Approach
1. **Reading data** (`src/datamate/ingest.py`, `profile.py`, `values.py`): every csv / xlsx / sqlite table of a shop is
   read, the header row is found, Vietnamese money (`25k`, `1,39tr`), quantities with units and dates (dd/mm, Excel
   serial, lunar Tết via `calendar.csv`) are parsed. The shop README is read for column descriptions.
2. **Mapping tables to concepts** (`mapper.py`): heuristic scores (header words, values, README) propose a role for each
   table/column (sales line, order, product, customer, purchase, stock, debt…); Qwen checks the proposal (JSON); fixed
   consistency checks (keys must join, required columns) keep or drop roles.
3. **Canonical views** (`rules.py`): the rulebook's default rules (orders counted in revenue, cancelled / returned
   orders, base units, walk-in customers, debts, purchases) are applied once per shop → standard views.
4. **Question → intent** (`intent.py`, `pipeline.py`): Qwen reads the question and writes an intent JSON (metric,
   periods, filters, parameters). Fixed post-processing: date tagger (`timex.py`, `periods.py`), structural repairs and
   general vocabulary cues (`slots.py`), validation with one repair round.
5. **Answer by code** (`metrics.py`): a library of ~35 metrics computes the answer on the views. Logged as `code` /
   `inputs` / `output`.
6. **Cross-check** (`sqlpath.py`): Qwen also writes one DuckDB SQL query over the same views (checked with sqlglot,
   no file / network access); agreement with the metric answer is a feature of the next step. If the metric route has no
   answer, the SQL answer may be used (logged as `code` = the SQL).
7. **Answer or abstain** (`calibration.py`, `calibration.json`): P(correct) per bucket of features (metric, status,
   agreement, XLM-R P(answerable) when present); the answer is written only when P(correct) > 0.5 (score +1/−1/0).

No logic depends on question ids or business ids. Decoding is greedy (`do_sample=False`), so there is no seed and two
runs give the same answers on the same hardware/software.

## Run settings (fixed in `predict.sh`)
- Qwen3.5-4B in fp16 with Hugging Face transformers, thinking mode disabled (`enable_thinking=False`) → log field
  `thinking` is `null`; every raw model output is kept in the log (`llm_raw`, `sql_raw`).
- One process per visible GPU (`src/datamate/launch.py`), shops split by number of questions;
  `/result/submission.jsonl` is rewritten every 15 s from the per-GPU part files (`/result/parts/`), so saved answers
  survive a stop. Missing answers are written as `abstain` at the end.
- `/data` is only read; temporary files go to `/tmp`.

## Models (all inference models together: __TOTAL_PARAMS__ parameters, limit 15B)
__MODEL_TABLE__

## Data
- Training data: only the provided train split (30 shops, 3000 questions with answers), in
  `training_code/data/train/`. Public / private test data are never used for training or for building any rule.
- Self-generated data: __DATA_TEXT__
- Checksums of every packaged file: `training_code/data_manifest.json`.

## Folder layout
```
/code/predict.sh            entry point
/code/README.md             this file
/code/requirements.txt      inference dependencies (torch from the base image)
/code/calibration.json      answer / abstain policy
/code/src/datamate/         inference code
/code/models/               model weights (base model + adapters)
/code/training_code/        training / data-generation code, data, logs, manifest (see its README)
```

## Logs (`/result/logs/<business_id>/<id>.json`)
`id`, `answer` (final answer = submission line without `id`), `elapsed_ms`, `thinking` (null), `code` / `inputs` /
`output` (the metric call with its intent, or the executed SQL), plus pipeline fields: `intent`, `llm_raw`,
`sql_raw`, `agree`, `p_answerable`, `p_correct`, `reason`, `pipeline_answer` (value before the abstain policy).
`/result/logs/<business_id>/shop_report.json` records how the shop's tables were mapped.
