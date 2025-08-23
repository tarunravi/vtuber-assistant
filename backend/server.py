import json
from typing import AsyncGenerator
import os
from pathlib import Path
import re

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import httpx
from prompt_factory import PromptFactory
from llm_client import LLMClient


# Resolve project root config regardless of CWD (works for local and Docker)
ROOT_CONFIG_PATH = str((Path(__file__).resolve().parent.parent / "vtuber.config.json").resolve())


def load_llm_config():
    try:
        with open(ROOT_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}

    # LLM settings
    llm = cfg.get("llm", {}) or {}
    provider = llm.get("provider", "ollama")
    model = llm.get("model", "qwen2.5")
    # Allow overriding host via environment so containers can call host services
    host = os.getenv("LLM_HOST") or os.getenv("OLLAMA_HOST") or llm.get("host", "http://127.0.0.1:11434")
    ws_path = llm.get("wsPath", "/ws")

    # Persona and emotions
    selected_model_key = (cfg.get("model") or "").strip()
    selected_prompt_key = (cfg.get("prompt") or "").strip()
    prompts = cfg.get("prompts", {}) or {}
    models_cfg = cfg.get("models", {}) or {}
    persona_prompt = (prompts.get(selected_prompt_key) or "").strip()
    emotion_names = []
    try:
        model_entry = models_cfg.get(selected_model_key) or {}
        emotions_map = model_entry.get("emotions", {}) or {}
        # Keep the order as defined in JSON keys iteration (Python 3.7+ preserves insertion order)
        emotion_names = [name for name in emotions_map.keys() if isinstance(name, str) and name.strip()]
    except Exception:
        emotion_names = []

    return {
        "provider": provider,
        "model": model,
        "host": host.rstrip("/"),
        "ws_path": ws_path,
        "persona_prompt": persona_prompt,
        "emotion_names": emotion_names,
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


# Configure WebSocket route and prompt factory based on config
CFG = load_llm_config()
WS_PATH = CFG["ws_path"] if CFG.get("ws_path") else "/ws"
prompt_factory = PromptFactory(CFG.get("persona_prompt", ""), CFG.get("emotion_names", []))

async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    cfg = CFG
    provider = cfg["provider"]
    model = cfg["model"]
    host = cfg["host"]
    allowed_emotions = cfg.get("emotion_names", [])
    llm = LLMClient(
        host=host,
        model=model,
        provider=provider,
        allowed_emotions=allowed_emotions,
        prompt_factory=prompt_factory,
    )

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
                    async for event in llm.stream(user_text):
                        try:
                            if isinstance(event, dict):
                                et = event.get("type")
                                if et == "emotion":
                                    await websocket.send_text(json.dumps({"type": "emotion", "emotion": event.get("emotion")}))
                                elif et == "text":
                                    data = event.get("data")
                                    if data:
                                        await websocket.send_text(json.dumps({"type": "chunk", "data": data}))
                                else:
                                    # Fallback: treat unknown dict as chunk
                                    await websocket.send_text(json.dumps({"type": "chunk", "data": json.dumps(event)}))
                            else:
                                # Backward-compatible: raw text
                                await websocket.send_text(json.dumps({"type": "chunk", "data": str(event)}))
                        except Exception:
                            # Do not break the stream on send errors; try to continue
                            pass
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
    # Use environment variables for Docker compatibility
    host = os.getenv("UVICORN_HOST", "127.0.0.1")
    port = int(os.getenv("UVICORN_PORT", "8000"))
    uvicorn.run("server:app", host=host, port=port, reload=False)


