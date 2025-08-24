from __future__ import annotations

import re
from typing import AsyncGenerator, List, Optional, Dict, Any

from prompt_factory import PromptFactory
from stream_text_parser import StreamTextParser
from llm_transport import LLMTransport


class ChatStreamer:
    """High-level chat streaming orchestrator.

    - Builds final prompts using PromptFactory and conversation history
    - Streams clean plain-English text tokens (no emojis) via LLMTransport
    - Emits events of shape {"type": "text", "data": str}
    """

    def __init__(
        self,
        host: str,
        model: str,
        provider: str,
        allowed_emotions: List[str],
        prompt_factory: PromptFactory,
        default_emotion: Optional[str] = None,
    ) -> None:
        self.host = host.rstrip("/") if host else "http://127.0.0.1:11434"
        self.model = model
        self.provider = provider
        self.prompt_factory = prompt_factory
        self.allowed_emotions = [e for e in (allowed_emotions or []) if isinstance(e, str) and e.strip()]
        allowed_set = set(self.allowed_emotions)
        if default_emotion and default_emotion in allowed_set:
            self.default_emotion = default_emotion
        elif self.allowed_emotions:
            non_generic = [e for e in self.allowed_emotions if e.lower() not in {"happy", "neutral"}]
            self.default_emotion = non_generic[0] if non_generic else self.allowed_emotions[0]
        else:
            self.default_emotion = "Neutral"

        self._emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002700-\U000027BF"  # Dingbats
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U00002600-\U000026FF"  # Misc symbols
            "\U00002B00-\U00002BFF"  # arrows
            "\U00002300-\U000023FF"  # technical
            "]+",
            flags=re.UNICODE,
        )

    def _remove_emojis(self, text: str) -> str:
        return self._emoji_pattern.sub("", text)

    async def _stream_core(self, prompt: str) -> AsyncGenerator[str, None]:
        core = LLMTransport(self.host, self.model, self.provider)
        async for tok in core.stream(prompt):
            yield tok

    async def stream(
        self,
        user_text: str,
        history: Optional[List[Dict[str, str]]] = None,
        max_turns: int = 8,
        max_chars: int = 4000,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        final_prompt = self.prompt_factory.build_final_prompt(
            user_text,
            history=history,
            max_turns=max_turns,
            max_chars=max_chars,
        )

        if self.provider != "ollama":
            raise RuntimeError(f"Unsupported provider: {self.provider}")

        parser = StreamTextParser(allowed_tags=None, strip_non_english=True)

        async for raw_token in self._stream_core(final_prompt):
            token = self._remove_emojis(raw_token)
            if not token:
                continue

            text_out, _ = parser.process_chunk(token)
            if text_out:
                yield {"type": "text", "data": text_out}

        tail_text, _ = parser.finish()
        if tail_text:
            yield {"type": "text", "data": tail_text}


