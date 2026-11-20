# CŨ (v6, CUDA 12.4, không chạy trên RTX 5090) — bản nộp thật: docker/Dockerfile + docker/HUONG_DAN.md
# DataMate v6 - offline image: code (training + inference), weights, calibration, predict.sh, README.
# Build context layout (prepared by the Kaggle notebook, section 8):
#   models/Qwen3.5-4B/   base LLM            models/intent_lora/  LoRA adapter (step 1)
#   models/xlmr_ans/     XLM-R classifier     models/vit5_norm/    optional normaliser (step 4)
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1 MODELS=/models
WORKDIR /app
COPY requirements.txt .
# transformers must be new enough for Qwen3.5 (pin the exact version the notebook printed)
ARG TRANSFORMERS_SPEC="transformers>=5.0"
RUN pip install --no-cache-dir -r requirements.txt "$TRANSFORMERS_SPEC" && \
    (pip install --no-cache-dir flash-linear-attention || echo "fla kernels unavailable: slower but correct")
COPY models/ /models/
COPY datamate ./datamate
COPY tests ./tests
COPY notebooks ./notebooks
COPY calibration.json predict.sh README.md ./
RUN chmod +x predict.sh
ENTRYPOINT ["./predict.sh"]
