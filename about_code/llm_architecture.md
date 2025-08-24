## LLM Architecture: Transport and Chat Layers

### Overview
The LLM stack is split into two clear layers:
- `LLMTransport` (low-level HTTP streaming to Ollama)
- `ChatStreamer` (prompt composition, token cleaning, event streaming)

Emotion selection is performed after streaming completes via a separate classification call.

### Files
- Transport: `backend/llm_transport.py`
  - Class: `LLMTransport`
  - Methods: `stream(prompt) -> AsyncGenerator[str]`, `generate(prompt) -> str`

- Chat: `backend/chat_streamer.py`
  - Class: `ChatStreamer`
  - Emits only text events: `{ "type": "text", "data": str }`
  - Builds prompts via `backend/prompt_factory.py`
  - Strips emojis and non-English noise

- Server: `backend/server.py`
  - WebSocket handler uses `ChatStreamer` for streaming
  - Calls `classify_emotion_llm(...)` post-stream to produce exactly one emotion

### Rationale
- Simpler responsibilities: transport vs chat orchestration
- Easier testing and substitution (swap transport/provider without touching chat logic)
- Cleaner WebSocket protocol: text chunks first, then a single emotion event

### Protocol Summary
- Client → Server: `{ "prompt": string }`
- Server → Client:
  - `{ "type": "start" }`
  - `{ "type": "chunk", "data": string }` (repeated)
  - `{ "type": "emotion", "emotion": string }` (once, post-stream)
  - `{ "type": "end" }`

### Migration Notes
- Old shims `backend/llm_client.py` and `backend/llm_core.py` were removed.
- Any references should import `ChatStreamer` and `LLMTransport` directly.


