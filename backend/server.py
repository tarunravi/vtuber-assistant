import json
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import httpx


ROOT_CONFIG_PATH = "/Users/tarun/Anime/vtuber/vtuber.config.json"


def load_llm_config():
    try:
        with open(ROOT_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    llm = cfg.get("llm", {}) or {}
    provider = llm.get("provider", "ollama")
    model = llm.get("model", "qwen2.5")
    host = llm.get("host", "http://127.0.0.1:11434")
    ws_path = llm.get("wsPath", "/ws")
    return {
        "provider": provider,
        "model": model,
        "host": host.rstrip("/"),
        "ws_path": ws_path,
    }


async def stream_ollama(client: httpx.AsyncClient, host: str, model: str, prompt: str) -> AsyncGenerator[str, None]:
    url = f"{host}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": True}
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


app = FastAPI()

# Allow local dev origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Configure WebSocket route based on config
CFG = load_llm_config()
WS_PATH = CFG["ws_path"] if CFG.get("ws_path") else "/ws"

async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    cfg = CFG
    provider = cfg["provider"]
    model = cfg["model"]
    host = cfg["host"]

    async with httpx.AsyncClient() as client:
        try:
            while True:
                msg = await websocket.receive_text()
                try:
                    payload = json.loads(msg)
                    user_text = payload.get("prompt") or payload.get("message") or ""
                except Exception:
                    user_text = msg

                if not user_text.strip():
                    await websocket.send_text(json.dumps({"type": "error", "message": "Empty prompt"}))
                    continue

                await websocket.send_text(json.dumps({"type": "start"}))

                if provider == "ollama":
                    async for token in stream_ollama(client, host, model, user_text):
                        await websocket.send_text(json.dumps({"type": "chunk", "data": token}))
                else:
                    await websocket.send_text(json.dumps({"type": "error", "message": f"Unsupported provider: {provider}"}))

                await websocket.send_text(json.dumps({"type": "end"}))
        except WebSocketDisconnect:
            return
        except Exception as e:
            try:
                await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
            except Exception:
                pass

# Register the websocket route dynamically
app.add_api_websocket_route(WS_PATH, ws_chat)


if __name__ == "__main__":
    # Default dev server bind
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)


