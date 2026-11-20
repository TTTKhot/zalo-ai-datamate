# DataMate - submission image (Zalo AI Challenge 2026). Build context = build/docker_context made by
#   python docker/make_context.py ...   (see docker/HUONG_DAN.md)
# Base: PyTorch 2.7.1 + CUDA 12.8 (Blackwell / RTX 5090, compute capability 12.0). We do not use vLLM: the model runs
# with Hugging Face transformers, one process per GPU (no NCCL / tensor parallelism).
ARG BASE=pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime
FROM ${BASE}
ENTRYPOINT []
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 PYTHONPATH=/code/src \
    TOKENIZERS_PARALLELISM=false
WORKDIR /code
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt
# weights first: kept in cache when only the code changes
COPY models/ /code/models/
COPY training_code/ /code/training_code/
COPY predict.sh README.md calibration.json /code/
COPY src/ /code/src/
RUN chmod +x /code/predict.sh && \
    python -c "import torch, transformers, peft, duckdb, sqlglot, datamate.launch, datamate.predict; print('torch', torch.__version__, 'cuda', torch.version.cuda, 'transformers', transformers.__version__)"
CMD ["bash", "/code/predict.sh"]
