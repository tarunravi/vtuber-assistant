## LLM + WebSocket Integration (Ollama)

### Overview
This app adds a lightweight LLM chat on top of the Live2D renderer. The architecture follows a clear frontend/backend split and uses a WebSocket to stream tokens from a locally running Ollama instance to the browser.

### Components
- **Backend (FastAPI WebSocket)**: `backend/server.py`
  - Exposes a WebSocket endpoint (path from config) that accepts a user prompt and streams assistant text back to the client.
  - Uses `ChatStreamer` to build prompts and stream tokens, and `classify_emotion_llm` to classify emotion post-stream.

- **Transport**: `backend/llm_transport.py`
  - `LLMTransport` handles Ollama HTTP streaming.

- **Chat orchestration**: `backend/chat_streamer.py`
  - `ChatStreamer` composes prompts (via `PromptFactory`), cleans tokens, and emits text events.

- **LLM Provider (Ollama)**
  - Default model: `qwen2.5` (configurable).
  - Default host: `http://127.0.0.1:11434` (configurable).

- **Frontend (React)**
  - Live2D renderer in `frontend/src/components/Live2D.tsx`.
  - Chat UI `frontend/src/components/ChatPanel.tsx` opens a WebSocket and renders streamed output.
  - `frontend/scripts/sync-assets.mjs` generates `frontend/public/app-config.json`, including `llm.backendWsUrl`.

### Data Flow
1. Frontend loads `app-config.json` to read `llm.backendWsUrl`.
2. `ChatPanel` connects to the WebSocket and sends `{ "prompt": string }`.
3. Backend appends the user message to per-connection conversation history.
4. Backend streams via `ChatStreamer` (Ollama `/api/generate` under the hood), forwarding clean text chunks.
5. Frontend appends streamed chunks to the last assistant message until an `end` event is received.
6. Backend stores the complete assistant response and then classifies a single emotion; sends it to the client.

### WebSocket Protocol
- Client → Server: raw text or `{ "prompt": string }`.
- Server → Client (JSON):
  - `{ "type": "start" }` once per request
  - `{ "type": "chunk", "data": string }` repeated
  - `{ "type": "end" }` when complete
  - On failure: `{ "type": "error", "message": string }`

### Conversation Memory
The system maintains per-connection conversation history to provide context for more coherent and contextual responses:

**Memory Structure:**
- Each WebSocket connection maintains a `history` list of message objects
- Format: `{"role": "user"|"assistant", "content": "message text"}`
- History is included in LLM prompts to maintain conversation continuity

**Memory Limits:**
- **Turn Limit**: Maximum number of user/assistant pairs to remember (default: 8)
- **Character Limit**: Maximum total characters in history (default: 4000)
- Both limits can be configured via environment variables:
  - `LLM_MEMORY_TURNS`: Number of conversation turns to remember
  - `LLM_MEMORY_CHARS`: Maximum characters in conversation history

**Memory Flow:**
1. User message is appended to history before LLM call
2. LLM receives system prompt + conversation history + current user message
3. Assistant response is buffered during streaming
4. Complete assistant response is stored in history after streaming completes
5. History is automatically truncated to respect configured limits

**Benefits:**
- Maintains conversation context across multiple turns
- Allows for follow-up questions and references to previous messages
- Provides more coherent and contextual responses
- Memory is per-connection, so different browser sessions don't interfere

### Configuration
- Root config: `vtuber/vtuber.config.json`
  - Example:
  ```
  {
    "model": "mao",
    "timeScale": 6,
    "llm": {
      "provider": "ollama",
      "model": "qwen2.5",
      "host": "http://127.0.0.1:11434",
      "wsPath": "/ws"
    }
  }
  ```
  - `wsPath` controls the backend WebSocket route.

- Frontend app config: `frontend/scripts/sync-assets.mjs` writes `frontend/public/app-config.json` like:
  ```json
  { "model": "mao", "entry": "/model/mao_pro.model3.json", "timeScale": 6, "llm": { "backendWsUrl": "ws://127.0.0.1:8000/ws" } }
  ```

### Key Implementation Points
- Backend dynamically registers the WebSocket route using `wsPath` from the root config.
- Streaming is implemented by forwarding each JSON line from Ollama to the client as a `chunk`.
- The frontend maintains a conversation list and live-updates the most recent assistant message with incoming chunks.
- **Conversation Memory**: Each WebSocket connection maintains per-session conversation history to provide context for LLM responses.

### Running Locally
- Single command from repo root:
  - `./start.sh` (from project root)
  - Starts backend (FastAPI on `127.0.0.1:8000`) and frontend (Vite dev server).

- Requirements:
  - Ollama running locally: `ollama serve`
  - Model pulled: `ollama pull qwen2.5`

### Extensibility
- To change the LLM: update `llm.model` or `llm.host` in `vtuber.config.json`.
- To change WebSocket path: update `llm.wsPath` and restart. The frontend picks up the new URL via `app-config.json` on next dev run.
- To adjust memory limits: set environment variables `LLM_MEMORY_TURNS` (default: 8) and `LLM_MEMORY_CHARS` (default: 4000) before starting the backend.

### References (code excerpts)
```1:40:backend/server.py
import json
from typing import AsyncGenerator
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import httpx

# ... omitted for brevity ...

async def stream_ollama(client: httpx.AsyncClient, host: str, model: str, prompt: str) -> AsyncGenerator[str, None]:
    url = f"{host}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": True}
    async with client.stream("POST", url, json=payload, timeout=None) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            # parse JSONL and yield tokens
            # ...
            pass
```

**Conversation Memory Implementation:**
```python
# vtuber/backend/server.py - WebSocket handler
async def ws_chat(websocket: WebSocket):
    # Maintain per-connection conversation history
    history = []
    max_turns = int(os.getenv("LLM_MEMORY_TURNS", "8"))
    max_chars = int(os.getenv("LLM_MEMORY_CHARS", "4000"))
    
    # Append user turn, call LLM with history, store assistant response
    history.append({"role": "user", "content": user_text})
    async for event in llm.stream(user_text, history=history, max_turns=max_turns, max_chars=max_chars):
        # ... streaming logic ...
    history.append({"role": "assistant", "content": assistant_text})
```

```python
# vtuber/backend/prompt_factory.py - History formatting
def build_final_prompt(self, user_text: str, history=None, max_turns=8, max_chars=4000):
    system = self.build_system_prompt()
    history_block = self._format_history(history, max_turns, max_chars)
    # Include conversation context before current user message
    return f"{system}\n\nConversation so far:\n{history_block}\n\nUser: {user_text}\nAssistant:"
```

```1:60:frontend/src/components/ChatPanel.tsx
export default function ChatPanel() {
  // loads backendWsUrl from /app-config.json
  // opens a WebSocket, sends { prompt }, and renders streaming chunks
}
```


