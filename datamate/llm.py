"""Local Qwen backend (offline). One instance is shared by the mapper, the intent step and the SQL step.

`load_qwen` is the single place that builds the model, so the LoRA trainer (train_lora.py) and
inference load the same module tree and an adapter trained on one loads on the other.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


def load_qwen(model_path: str, quantize_4bit: bool = False, prefer: str | None = None, device_map='auto'):
    """Return (model, processor_or_tokenizer, loader_name).

    Qwen3.5 ships as an image-text-to-text checkpoint; older transformers / text-only checkpoints
    load as causal LMs. `prefer` forces the class recorded next to a LoRA adapter."""
    import torch
    from transformers import AutoProcessor, AutoTokenizer
    import transformers
    dtype_key = 'dtype' if tuple(int(x) for x in transformers.__version__.split('.')[:2]) >= (4, 56) else 'torch_dtype'
    kwargs = {'device_map': device_map, 'local_files_only': True,
              dtype_key: torch.float16 if torch.cuda.is_available() else torch.float32}
    if quantize_4bit and torch.cuda.is_available():
        from transformers import BitsAndBytesConfig
        kwargs['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                                           bnb_4bit_compute_dtype=torch.float16,
                                                           bnb_4bit_use_double_quant=True)
        kwargs.pop(dtype_key)
    order = ['multimodal', 'causal']
    if prefer in order:
        order.remove(prefer)
        order.insert(0, prefer)
    last = None
    for name in order:
        try:
            if name == 'multimodal':
                from transformers import AutoModelForMultimodalLM as Auto
                processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
            else:
                from transformers import AutoModelForCausalLM as Auto
                processor = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            model = Auto.from_pretrained(model_path, **kwargs)
            return model, processor, name
        except Exception as exc:          # try the other class
            last = exc
    if 'quantization_config' in kwargs:   # e.g. bitsandbytes without kernels for this GPU: same weights in fp16
        print(f'!! 4-bit load failed ({last!r}); loading fp16 instead', flush=True)
        return load_qwen(model_path, False, prefer, device_map)
    raise RuntimeError(f'cannot load {model_path}: {last!r}')


def tokenizer_of(processor):
    return getattr(processor, 'tokenizer', processor)


def chat_ids(processor, messages, add_generation_prompt=True):
    """Token ids of a chat prompt (thinking disabled), as a python list."""
    tok = tokenizer_of(processor)
    text = tok.apply_chat_template(messages, add_generation_prompt=add_generation_prompt, tokenize=False,
                                   enable_thinking=False)
    return tok(text, add_special_tokens=False)['input_ids']


class QwenBackend:
    def __init__(self, model_path: str, quantize_4bit: bool = False, max_new_tokens: int = 384,
                 adapter: str | None = None):
        import torch
        self.torch = torch
        self.max_new_tokens = max_new_tokens
        prefer = None
        if adapter and (Path(adapter) / 'datamate_loader.json').exists():
            prefer = json.loads((Path(adapter) / 'datamate_loader.json').read_text())['loader']
        self.model, self.processor, self.loader = load_qwen(model_path, quantize_4bit, prefer)
        self.adapter = adapter
        if adapter:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, adapter)
        self.model.eval()
        self.calls = 0
        self.seconds = 0.0

    def base(self):
        """Same weights with the LoRA adapter switched off (mapper, SQL route)."""
        return _BaseView(self) if self.adapter else self

    def generate(self, messages, max_new_tokens=None, use_adapter=True) -> str:
        import contextlib
        started = time.perf_counter()
        ids = chat_ids(self.processor, messages)
        input_ids = self.torch.tensor([ids], device=self.model.device)
        off = self.model.disable_adapter() if (self.adapter and not use_adapter) else contextlib.nullcontext()
        try:
            with self.torch.inference_mode(), off:
                out = self.model.generate(input_ids=input_ids, attention_mask=self.torch.ones_like(input_ids),
                                          max_new_tokens=max_new_tokens or self.max_new_tokens, do_sample=False)
            text = tokenizer_of(self.processor).decode(out[0][len(ids):], skip_special_tokens=True)
        finally:
            if self.torch.cuda.is_available():
                self.torch.cuda.empty_cache()
        self.calls += 1
        self.seconds += time.perf_counter() - started
        return text


class _BaseView:
    def __init__(self, backend):
        self.backend = backend

    @property
    def calls(self):
        return self.backend.calls

    def generate(self, messages, max_new_tokens=None):
        return self.backend.generate(messages, max_new_tokens, use_adapter=False)


class ReplayBackend:
    """Returns stored outputs; lets CI re-run the pipeline on logged LLM answers without a GPU."""
    def __init__(self, outputs: list[str]):
        self.outputs = list(outputs)
        self.calls = 0

    def generate(self, messages, max_new_tokens=None) -> str:
        self.calls += 1
        return self.outputs.pop(0) if self.outputs else ''


class FnBackend:
    """Backend from a python function messages -> text (tests, scripted SQL)."""
    def __init__(self, fn):
        self.fn = fn
        self.calls = 0

    def generate(self, messages, max_new_tokens=None) -> str:
        self.calls += 1
        return self.fn(messages)
