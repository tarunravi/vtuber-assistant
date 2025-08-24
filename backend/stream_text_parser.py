from __future__ import annotations

import re
from typing import List, Tuple, Optional


class StreamTextParser:
    """Generic incremental parser for streamed text.

    Features:
    - Optionally strips all non-English (non-ASCII printable) characters.
    - Extracts bracketed tags like [Tag] and returns only those that are allowed (if provided).
    - Removes any bracketed segments from the output: allowed tags are removed and emitted as tags; disallowed ones are dropped to avoid roleplay asides.
    - Handles partial tags across chunk boundaries.

    API:
      parser = StreamTextParser(allowed_tags=[...], strip_non_english=True)
      clean_text, tags = parser.process_chunk(chunk)
      tail_text, last_tag = parser.finish()
    """

    _NON_ASCII_PATTERN = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]+")

    def __init__(self, allowed_tags: Optional[List[str]] = None, strip_non_english: bool = True) -> None:
        self.allowed_set = set(allowed_tags or [])
        self.strip_non_english = strip_non_english
        self._carry = ""
        self._last_tag: Optional[str] = None
        self._has_output_text = False
        self._has_output_non_ws = False
        # Precompile a leading bare-tag pattern to catch cases like "Gaming text..."
        if self.allowed_set:
            # Exact-case match, tags are assumed to be single words
            alternation = "|".join(sorted((re.escape(t) for t in self.allowed_set), key=len, reverse=True))
            self._leading_tag_re = re.compile(rf"^(?:{alternation})(?=[\s\.,!?:;]|$)")
        else:
            self._leading_tag_re = None

    def _filter_chars(self, text: str) -> str:
        if not self.strip_non_english or not text:
            return text
        return self._NON_ASCII_PATTERN.sub("", text)

    def process_chunk(self, chunk: str) -> Tuple[str, List[str]]:
        if not chunk:
            return "", []

        chunk = self._filter_chars(chunk)
        combined = self._carry + chunk
        out_parts: List[str] = []
        tags_found: List[str] = []
        i = 0

        # Handle a bare leading tag like "Gaming " at the very start (allowing leading whitespace)
        if not self._has_output_non_ws and self._leading_tag_re is not None and combined:
            j = 0
            while j < len(combined) and combined[j].isspace():
                j += 1
            m = self._leading_tag_re.match(combined[j:]) if j < len(combined) else None
            if m:
                tag = m.group(0)
                self._last_tag = tag
                tags_found.append(tag)
                i = j + m.end()
                # Skip immediate spaces after the tag
                while i < len(combined) and combined[i].isspace():
                    i += 1

        while True:
            open_idx = combined.find("[", i)
            if open_idx == -1:
                break
            close_idx = combined.find("]", open_idx + 1)
            if close_idx == -1:
                break

            inner = (combined[open_idx + 1 : close_idx] or "").strip()
            if not self.allowed_set or inner in self.allowed_set:
                if open_idx > i:
                    out_parts.append(combined[i:open_idx])
                self._last_tag = inner
                tags_found.append(inner)
                i = close_idx + 1
            else:
                # Drop disallowed bracketed content entirely (prevents roleplay/asides)
                i = close_idx + 1

        tail = combined[i:]
        last_open = tail.rfind("[")
        last_close = tail.rfind("]")
        if last_open != -1 and (last_close == -1 or last_open > last_close):
            if last_open > 0:
                out_parts.append(tail[:last_open])
            self._carry = tail[last_open:]
        else:
            if tail:
                out_parts.append(tail)
            self._carry = ""

        text_out = "".join(out_parts)
        if text_out:
            self._has_output_text = True
            if any(not ch.isspace() for ch in text_out):
                self._has_output_non_ws = True
        return text_out, tags_found

    def finish(self) -> Tuple[str, Optional[str]]:
        residual = self._carry
        self._carry = ""
        return residual, self._last_tag


