from __future__ import annotations

import json
import os
from typing import AsyncGenerator

import httpx


class LLMTransport:
    """Low-level LLM transport for streaming and full text generation.

    Currently supports the Ollama HTTP API. Provides:
    - stream(prompt): async token generator
    - generate(prompt): async full text
    """

    def __init__(self, host: str, model: str, provider: str) -> None:
        self.host = host.rstrip("/") if host else "http://127.0.0.1:11434"
        self.model = model
        self.provider = provider

    async def _stream_ollama(self, prompt: str) -> AsyncGenerator[str, None]:
        url = f"{self.host}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": True}
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, json=payload, timeout=None) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = data.get("response")
                    if token:
                        yield token
                    if data.get("done") is True:
                        break

    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        if self.provider != "ollama":
            raise RuntimeError(f"Unsupported provider: {self.provider}")
        enable_logs = bool(int(os.getenv("LLM_DEBUG", "0")))
        if enable_logs:
            print("\n===== LLM REQUEST =====")
            print(prompt)
            print("===== STREAM START =====")
        buffer = []
        async for tok in self._stream_ollama(prompt):
            if tok:
                buffer.append(tok)
                yield tok
        final_text = "".join(buffer)
        if enable_logs:
            print("\n===== LLM OUTPUT =====")
            print(final_text)
            print("=======================\n")

    async def generate(self, prompt: str) -> str:
        out = []
        async for tok in self.stream(prompt):
            if tok:
                out.append(tok)
        return "".join(out)


