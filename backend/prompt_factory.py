from __future__ import annotations

from typing import List


class PromptFactory:
    """
    Builds a system-style prompt that combines:
    - Persona prompt text
    - Dynamic list of allowed emotion names
    - Global style/behavior rules
    And composes a final prompt with the user text for streaming to the LLM.
    """

    def __init__(self, persona_prompt: str, emotion_names: List[str]):
        self.persona_prompt = (persona_prompt or "").strip()
        self.emotion_names = [e.strip() for e in (emotion_names or []) if isinstance(e, str) and e.strip()]

    def build_system_prompt(self) -> str:
        parts: List[str] = []
        if self.persona_prompt:
            parts.append(self.persona_prompt)
        if self.emotion_names:
            emotions_line = ", ".join(self.emotion_names)
            parts.append(
                "In your response, always start with a single emotion tag in square brackets, "
                f"exactly one of these: [{emotions_line}]. Pick the most relevant emotion for your answer. "
                "Try to use different emotions in subsequent message if suitable."
                "Never use any other emotion names and do not invent new ones."
            )
        parts.append(
            "Write only in plain English. "
            "Never use emojis or emoticons. "
            "Keep responses very concise and directly answer the question. "
            "Do not introduce yourself or state your persona explicitly on simple messages (unless asked directly); "
            "keep the personality implicit and subtle, surfacing naturally only when appropriate."
        )
        return "\n".join(p.strip() for p in parts if p and p.strip())

    def build_final_prompt(self, user_text: str) -> str:
        system = self.build_system_prompt()
        return f"{system}\n\nUser: {user_text or ''}\nAssistant:"


