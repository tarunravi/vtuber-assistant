from __future__ import annotations

from typing import List, Optional, Dict


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

    def _format_history(
        self,
        history: Optional[List[Dict[str, str]]],
        max_turns: int,
        max_chars: int,
    ) -> str:
        if not history:
            return ""

        # Keep only the last N user/assistant pairs
        # History items are expected as dicts: {"role": "user"|"assistant", "content": str}
        # Normalize to pairs while preserving order
        pairs: List[List[str]] = []
        current_pair: List[str] = []
        for item in history:
            role = (item.get("role") or "").strip().lower()
            content = (item.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                # Start a new pair
                if current_pair:
                    pairs.append(current_pair)
                current_pair = [f"User: {content}"]
            elif role == "assistant":
                if not current_pair:
                    # If assistant comes first, start with empty user context
                    current_pair = ["User: "]
                current_pair.append(f"Assistant: {content}")
                pairs.append(current_pair)
                current_pair = []
        if current_pair:
            pairs.append(current_pair)

        # Only last max_turns pairs
        if max_turns > 0:
            pairs = pairs[-max_turns:]

        lines: List[str] = []
        for pair in pairs:
            lines.extend(pair)

        history_text = "\n".join(lines)
        if max_chars > 0 and len(history_text) > max_chars:
            # Truncate from the start to keep recent context
            history_text = history_text[-max_chars:]
        return history_text

    def build_final_prompt(
        self,
        user_text: str,
        history: Optional[List[Dict[str, str]]] = None,
        max_turns: int = 8,
        max_chars: int = 4000,
    ) -> str:
        system = self.build_system_prompt()
        history_block = self._format_history(history, max_turns=max_turns, max_chars=max_chars)
        parts: List[str] = [system]
        if history_block:
            parts.append("Conversation so far:")
            parts.append(history_block)
        parts.append(f"User: {user_text or ''}")
        parts.append("Assistant:")
        return "\n\n".join(parts)


