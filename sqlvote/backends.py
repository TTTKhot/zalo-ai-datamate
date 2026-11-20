"""LLM backends. One interface: generate(messages, n, temperature, seed, max_tokens) -> list[str].

OpenAIBackend talks to any local OpenAI-compatible server (vLLM, llama.cpp server, Ollama) - offline.
FnBackend wraps a python function (tests, scripted SQL). An adapter for an in-process transformers model
lives in adapters.py so that this module has no heavy imports.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


class OpenAIBackend:
    def __init__(self, base_url: str, model: str, api_key: str = 'EMPTY', timeout: float = 600.0,
                 extra_body: dict | None = None):
        self.url = base_url.rstrip('/') + '/chat/completions'
        self.model, self.api_key, self.timeout = model, api_key, timeout
        self.extra_body = extra_body or {}
        self.calls = 0

    def generate(self, messages, n: int = 1, temperature: float = 0.0, seed: int | None = None,
                 max_tokens: int = 700) -> list[str]:
        body = {'model': self.model, 'messages': messages, 'n': n, 'temperature': temperature,
                'max_tokens': max_tokens, **self.extra_body}
        if temperature > 0:
            body['top_p'] = 0.95
        if seed is not None:
            body['seed'] = int(seed)
        data = json.dumps(body).encode('utf-8')
        last = None
        for attempt in range(4):
            req = urllib.request.Request(self.url, data=data, headers={
                'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode('utf-8'))
                self.calls += 1
                return [(c.get('message') or {}).get('content') or '' for c in payload.get('choices', [])]
            except urllib.error.HTTPError as exc:      # 4xx is a request problem: do not retry blindly
                last = RuntimeError(f'HTTP {exc.code}: {exc.read().decode("utf-8", "replace")[:300]}')
                if exc.code < 500:
                    break
            except Exception as exc:
                last = exc
            time.sleep(2 * (attempt + 1))
        raise RuntimeError(f'LLM server call failed: {last}')


class FnBackend:
    """fn(messages) -> text. The same text is returned for every requested sample."""

    def __init__(self, fn):
        self.fn = fn
        self.calls = 0

    def generate(self, messages, n: int = 1, temperature: float = 0.0, seed=None, max_tokens: int = 700) -> list[str]:
        self.calls += 1
        return [self.fn(messages)] * n
