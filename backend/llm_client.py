from __future__ import annotations

import json
import re
from typing import AsyncGenerator, List, Optional, Dict, Any

import httpx

from prompt_factory import PromptFactory


class LLMClient:
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
        elif "Happy" in allowed_set:
            self.default_emotion = "Happy"
        elif self.allowed_emotions:
            self.default_emotion = self.allowed_emotions[0]
        else:
            self.default_emotion = "Neutral"

        # Regex to remove emojis and symbols outside basic ASCII ranges
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

    async def stream(self, user_text: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream events from the LLM while parsing the leading [Emotion] tag.

        Yields structured events:
        - {"type": "emotion", "emotion": str}
        - {"type": "text", "data": str}
        """
        final_prompt = self.prompt_factory.build_final_prompt(user_text)

        if self.provider != "ollama":
            raise RuntimeError(f"Unsupported provider: {self.provider}")

        emotion_emitted = False
        prefix_buffer = ""
        allowed_set = set(self.allowed_emotions)

        async for raw_token in self._stream_ollama(final_prompt):
            token = self._remove_emojis(raw_token)
            if not emotion_emitted:
                prefix_buffer += token
                # Decide when we have enough to validate the opening tag
                if "]" in prefix_buffer or "\n" in prefix_buffer or len(prefix_buffer) > 64:
                    m = re.match(r"^\s*\[([^\[\]]{1,32})\]\s*", prefix_buffer)
                    used_emotion = None
                    remainder = prefix_buffer
                    if m:
                        candidate = (m.group(1) or "").strip()
                        used_emotion = candidate if candidate in allowed_set else self.default_emotion
                        remainder = prefix_buffer[m.end():]
                    else:
                        used_emotion = self.default_emotion
                        remainder = prefix_buffer.lstrip()

                    # Emit emotion event once
                    yield {"type": "emotion", "emotion": used_emotion}
                    emotion_emitted = True
                    prefix_buffer = ""
                    # Emit any leftover text (without the emotion tag)
                    if remainder:
                        yield {"type": "text", "data": remainder}
            else:
                if token:
                    yield {"type": "text", "data": token}

        # If stream ended before we emitted the emotion, emit default and any buffered text
        if not emotion_emitted:
            yield {"type": "emotion", "emotion": self.default_emotion}
            if prefix_buffer.strip():
                yield {"type": "text", "data": self._remove_emojis(prefix_buffer)}


