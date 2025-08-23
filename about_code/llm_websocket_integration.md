## LLM + WebSocket Integration (Ollama)

### Overview
This app adds a lightweight LLM chat on top of the Live2D renderer. The architecture follows a clear frontend/backend split and uses a WebSocket to stream tokens from a locally running Ollama instance to the browser.

### Components
- **Backend (FastAPI WebSocket)**: `vtuber/backend/server.py`
  - Exposes a WebSocket endpoint (path from config) that accepts a user prompt and streams LLM tokens back to the client.
  - Talks to Ollama via its HTTP streaming API.

- **LLM Provider (Ollama)**
  - Default model: `qwen2.5` (can be changed in config).
  - Default host: `http://127.0.0.1:11434` (Ollama local server).

- **Frontend (React)**
  - Live2D renderer stays unchanged in `frontend/src/components/Live2D.tsx`.
  - New chat UI `frontend/src/components/ChatPanel.tsx` opens a WebSocket to the backend and renders streamed output.
  - `frontend/scripts/sync-assets.mjs` generates `frontend/public/app-config.json`, including `llm.backendWsUrl`.

### Data Flow
1. Frontend loads `app-config.json` to read `llm.backendWsUrl`.
2. `ChatPanel` connects to the WebSocket and sends `{ "prompt": string }`.
3. Backend calls Ollama `/api/generate` with `stream: true` and forwards each token to the client.
4. Frontend appends streamed chunks to the last assistant message until an `end` event is received.

### WebSocket Protocol
- Client → Server: raw text or `{ "prompt": string }`.
- Server → Client (JSON):
  - `{ "type": "start" }` once per request
  - `{ "type": "chunk", "data": string }` repeated
  - `{ "type": "end" }` when complete
  - On failure: `{ "type": "error", "message": string }`

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

### References (code excerpts)
```1:40:vtuber/backend/server.py
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

```1:60:vtuber/frontend/src/components/ChatPanel.tsx
export default function ChatPanel() {
  // loads backendWsUrl from /app-config.json
  // opens a WebSocket, sends { prompt }, and renders streaming chunks
}
```


