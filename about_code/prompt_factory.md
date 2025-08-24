## Prompt Factory: Personas, Emotions, and Style Rules

### What it does
The Prompt Factory composes the final instruction sent to the LLM by combining:
- Persona prompt (from config `prompts[prompt]`)
- Style and response constraints (plain English, concise answers, no emojis)

It keeps persona and behavior centralized and consistent without hardcoding model-specific details.

### Where it lives
- Backend class: `vtuber/backend/prompt_factory.py`
- Used by: `vtuber/backend/server.py` (WebSocket handler)

### Related configuration
- Root config: `vtuber/vtuber.config.json`
  - `model`: currently selected Live2D model (e.g., `ellot`, `mao`).
  - `prompts`: dictionary of reusable persona prompts (e.g., `prompt1`, `prompt2`).
  - `prompt`: which persona key to use from `prompts`.

Example (trimmed):
```json
{
  "model": "ellot",
  "prompt": "prompt1",
  "prompts": {
    "prompt1": "You're Elliot, the smart but lazy gamer...",
    "prompt2": "You're Mao, the creative artist..."
  },
  "models": {
    "ellot": {
      "emotions": {
        "Searching": "exp_01",
        "Happy": "exp_03"
        // ...
      }
    }
  }
}
```

### How it builds the prompt
Given the selected `prompt`, the factory:
1) Reads the persona text from `prompts[prompt]`.
2) Produces a system instruction that:
   - Forbids emojis or special characters; plain English only.
   - Emphasizes concise, directly-on-topic answers.
   - Keeps persona implicit on simple messages (e.g., saying “hi”), surfacing personality subtly only when appropriate.
3) Composes the final prompt by combining:
   - System instructions
   - Recent conversation history (if provided)
   - Current user message

Code (simplified):
```python
# vtuber/backend/prompt_factory.py
class PromptFactory:
    def __init__(self, persona_prompt: str, emotion_names: list[str]):
        self.persona_prompt = persona_prompt.strip() if persona_prompt else ""
        self.emotion_names = [e for e in (emotion_names or []) if isinstance(e, str) and e.strip()]

    def build_system_prompt(self) -> str:
        parts = []
        if self.persona_prompt:
            parts.append(self.persona_prompt)
        parts.append(
            "Write only in plain English. "
            "Keep responses very concise and directly answer the question. "
            "Do not introduce yourself or state your persona explicitly on simple messages; "
            "keep the personality implicit and subtle, surfacing naturally only when appropriate."
        )
        return "\n".join(p.strip() for p in parts if p and p.strip())

    def build_final_prompt(
        self,
        user_text: str,
        history: Optional[List[Dict[str, str]]] = None,
        max_turns: int = 8,
        max_chars: int = 4000,
    ) -> str:
        system = self.build_system_prompt()
        history_block = self._format_history(history, max_turns, max_chars)
        parts: List[str] = [system]
        if history_block:
            parts.append("Conversation so far:")
            parts.append(history_block)
        parts.append(f"User: {user_text or ''}")
        parts.append("Assistant:")
        return "\n\n".join(parts)
```

### How the server uses it
- On each WebSocket message, the backend loads config once at startup and constructs a `PromptFactory` with:
  - `persona_prompt`: from `prompts[prompt]`
  - `emotion_names`: from `models[model].emotions` keys
- It then calls `build_final_prompt(user_text, history, max_turns, max_chars)` with conversation history and streams the result to the LLM (Ollama).
- The conversation history is maintained per-connection and automatically truncated to respect memory limits.

Key lines (trimmed):
```python
# vtuber/backend/server.py
from prompt_factory import PromptFactory

CFG = load_llm_config()
emotion_names = CFG["emotion_names"]
persona_prompt = CFG["persona_prompt"]
prompt_factory = PromptFactory(persona_prompt, emotion_names)
final_prompt = prompt_factory.build_final_prompt(user_text)
```

### Why this design
- **Separation of concerns**: Persona and style live in one place; server code stays small.
- **Implicit persona**: Friendly style without forced self-introductions.
- **Conversation memory**: Maintains context across multiple turns for more coherent responses.

### Switching persona or model
- Change `prompt` to `prompt1`/`prompt2` in `vtuber/vtuber.config.json` to switch personas.
- Change `model` to switch character; the allowed emotion tags update automatically.

### Conversation Memory
The PromptFactory now supports conversation history to provide context for more coherent responses:

**History Format:**
- History is passed as a list of dictionaries: `{"role": "user"|"assistant", "content": "message"}`
- The factory formats this into a readable conversation block
- History is included before the current user message in the final prompt

**Memory Controls:**
- `max_turns`: Maximum number of user/assistant pairs to include (default: 8)
- `max_chars`: Maximum total characters in the history section (default: 4000)
- Both limits help prevent prompts from becoming too long while maintaining context

**Example Prompt Structure:**
```
[System instructions with persona and emotions]

Conversation so far:
User: Hello, how are you?
Assistant: [Happy] I'm doing great! How about you?
User: What's your favorite game?

User: What's your favorite game?
Assistant:
```

**Benefits:**
- Maintains conversation continuity across multiple turns
- Allows the LLM to reference previous messages and maintain context
- Provides more coherent and contextual responses
- Memory limits prevent prompts from becoming unwieldy

### Notes
- Conversation memory is maintained per-WebSocket connection in the server, not in the PromptFactory itself.


