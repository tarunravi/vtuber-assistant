from __future__ import annotations

from typing import List, Tuple


class EmotionTagParser:
    """Incremental parser that removes [Emotion] tags and tracks last valid emotion.

    Usage pattern:
    - Initialize with allowed_emotions and a default_emotion.
    - Call process_chunk() for each streamed text token. It returns:
        (clean_text_without_tags, newly_detected_emotions_in_order)
      The returned emotions are only those discovered in this chunk (after carry).
    - Call finish() at the end to flush any residual text and get the last emotion value.
    """

    def __init__(self, allowed_emotions: List[str], default_emotion: str) -> None:
        self.allowed_set = set(allowed_emotions or [])
        self.default_emotion = default_emotion
        self._carry = ""
        self._last_emotion = default_emotion

    def process_chunk(self, chunk: str) -> Tuple[str, List[str]]:
        if not chunk:
            return "", []

        combined = self._carry + chunk
        out_parts: List[str] = []
        emotions_found: List[str] = []
        i = 0

        while True:
            open_idx = combined.find("[", i)
            if open_idx == -1:
                break
            close_idx = combined.find("]", open_idx + 1)
            if close_idx == -1:
                break

            inner = (combined[open_idx + 1 : close_idx] or "").strip()
            if inner in self.allowed_set:
                # Append text before the tag; drop the tag itself
                if open_idx > i:
                    out_parts.append(combined[i:open_idx])
                self._last_emotion = inner
                emotions_found.append(inner)
                i = close_idx + 1
            else:
                # Not a valid emotion tag; keep as regular text up to and including ']'
                if close_idx + 1 > i:
                    out_parts.append(combined[i:close_idx + 1])
                i = close_idx + 1

        tail = combined[i:]
        last_open = tail.rfind("[")
        last_close = tail.rfind("]")
        if last_open != -1 and (last_close == -1 or last_open > last_close):
            # Keep any text before the last '[' and carry the possible partial tag
            if last_open > 0:
                out_parts.append(tail[:last_open])
            self._carry = tail[last_open:]
        else:
            if tail:
                out_parts.append(tail)
            self._carry = ""

        return "".join(out_parts), emotions_found

    def finish(self) -> Tuple[str, str]:
        residual = self._carry
        self._carry = ""
        return residual, self._last_emotion


