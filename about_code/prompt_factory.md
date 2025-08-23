## Prompt Factory: Personas, Emotions, and Style Rules

### What it does
The Prompt Factory composes the final instruction sent to the LLM by combining:
- Persona prompt (from config `prompts[prompt]`)
- Dynamic emotion instruction (valid emotions pulled from the selected Live2D model)
- Style and response constraints (plain English, no emojis/special characters, concise answers)

This keeps persona and behavior centralized and consistent without hardcoding model-specific details.

### Where it lives
- Backend class: `vtuber/backend/prompt_factory.py`
- Used by: `vtuber/backend/server.py` (WebSocket handler)

### Related configuration
- Root config: `vtuber/vtuber.config.json`
  - `model`: currently selected Live2D model (e.g., `ellot`, `mao`).
  - `models[MODEL_NAME].emotions`: map of Emotion → expression id. The emotion names (keys) become the LLM’s allowed emotion tags.
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
Given the selected `prompt` and `model`, the factory:
1) Reads the persona text from `prompts[prompt]`.
2) Reads the emotion names from `models[model].emotions` keys.
3) Produces a system instruction that:
   - Requires responses to start with exactly one valid emotion tag: `[Emotion]`.
   - Forbids emojis or special characters; plain English only.
   - Emphasizes concise, directly-on-topic answers.
   - Keeps persona implicit on simple messages (e.g., saying “hi”), surfacing personality subtly only when appropriate.
4) Composes the final single-field prompt for streaming to the LLM.

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
        if self.emotion_names:
            emotions_line = ", ".join(self.emotion_names)
            parts.append(
                "In your response, always start with a single emotion tag in square brackets, "
                f"exactly one of these: [{emotions_line}]. Pick the most relevant emotion for your answer."
            )
        parts.append(
            "Write only in plain English without emojis or special characters. "
            "Keep responses very concise and directly answer the question. "
            "Do not introduce yourself or state your persona explicitly on simple messages; "
            "keep the personality implicit and subtle, surfacing naturally only when appropriate."
        )
        return "\n".join(p.strip() for p in parts if p and p.strip())

    def build_final_prompt(self, user_text: str) -> str:
        system = self.build_system_prompt()
        return f"{system}\n\nUser: {user_text or ''}\nAssistant:"
```

### How the server uses it
- On each WebSocket message, the backend loads config once at startup and constructs a `PromptFactory` with:
  - `persona_prompt`: from `prompts[prompt]`
  - `emotion_names`: from `models[model].emotions` keys
- It then calls `build_final_prompt(user_text)` and streams the result to the LLM (Ollama).

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
- **Dynamic**: Emotions come from the currently selected model; no hardcoding.
- **Separation of concerns**: Persona and style live in one place; server code stays small.
- **Implicit persona**: Friendly style without forced self-introductions.

### Switching persona or model
- Change `prompt` to `prompt1`/`prompt2` in `vtuber/vtuber.config.json` to switch personas.
- Change `model` to switch character; the allowed emotion tags update automatically.

### Notes
- No frontend changes are required. The emotion tag at the start of each assistant message can be used by the UI if desired.


