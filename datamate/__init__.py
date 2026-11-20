"""DataMate v6: schema mapping -> rule library -> metric library, two routes + learned abstention.

Layers (each one is shop-agnostic):
  ingest       read csv/xlsx/sqlite/parquet, find header rows, group same-header sheets/files
  values       parse money / quantity / date / datetime written in Vietnamese shop formats
  profile      schema cards (header, inferred kind, samples, README description)
  concepts     rulebook concepts (entities + fields) the rule library understands
  mapper       heuristic candidates + LLM JSON mapping + fixed validation
  rules        canonical views built once from a validated mapping
  metrics      metric functions over the canonical views
  intent       question -> metric JSON (LLM; full prompt or compact prompt for the LoRA model)
  sft_data     v6 step 1: answer-verified intent labels for finetuning
  train_lora   v6 step 1: QLoRA trainer (Kaggle T4)
  sqlpath      v6 step 2: LLM-written SQL over the canonical views (sqlglot + duckdb), agreement
  answerability v6 step 3: XLM-R P(answerable | question, shop capabilities)
  neural_norm  v6 step 4: guarded seq2seq normaliser (hint only)
  calibration  answer / abstain / unanswerable policy learned from train
  eval_grouped, report  shop-held-out evaluation, before/after tables
"""
