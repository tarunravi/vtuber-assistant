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
from chat_streamer import ChatStreamer
from llm_transport import LLMTransport
from typing import List

async def classify_emotion_llm(
    client: httpx.AsyncClient,
    host: str,
    model: str,
    last_user: str,
    assistant: str,
    allowed: List[str],
) -> str:
    """Call the LLM to choose exactly one emotion from the allowed list.

    The model must return only the emotion word, nothing else.
    """
    allowed_clean = [e for e in (allowed or []) if isinstance(e, str) and e.strip()]
    allowed_line = ", ".join(allowed_clean) if allowed_clean else "Happy, Sad, Excited, Thinking, Annoyed"
    prompt = (
        "You are an emotion selector for a VTuber.\n"
        "Given the user's message and the assistant's reply, pick exactly one emotion from the allowed list that best matches the assistant's tone.\n"
        f"Allowed emotions (choose exactly one, return only the word): {allowed_line}.\n\n"
        f"User: {last_user or ''}\n"
        f"Assistant: {assistant or ''}\n\n"
        "Answer with only the emotion word (must be exactly as listed in Allowed)."
    )

    # Use core LLM for logging and generation
    core = LLMTransport(host, model, "ollama")
    text = await core.generate(prompt)
    # Keep ASCII letters and spaces only
    text = re.sub(r"[^A-Za-z\s]", " ", text).strip()
    # Try exact match first
    allowed_map = {e.lower(): e for e in allowed_clean}
    parts = [p for p in text.split() if p]
    for p in parts:
        key = p.lower()
        if key in allowed_map:
            return allowed_map[key]
    # Fallback: scan full text for any allowed word
    for e in allowed_clean:
        if re.search(rf"(?i)(?<![A-Za-z]){re.escape(e)}(?![A-Za-z])", text):
            return e
    return allowed_clean[0] if allowed_clean else "Neutral"


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
    llm = ChatStreamer(
        host=host,
        model=model,
        provider=provider,
        allowed_emotions=allowed_emotions,
        prompt_factory=prompt_factory,
    )

    # Maintain per-connection conversation history
    # Each item: {"role": "user"|"assistant", "content": str}
    history = []

    # Memory controls (env overrides for quick tuning)
    max_turns = int(os.getenv("LLM_MEMORY_TURNS", "8"))
    max_chars = int(os.getenv("LLM_MEMORY_CHARS", "4000"))

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
                    # Append user turn to history
                    history.append({"role": "user", "content": user_text})
                    # Buffer assistant text to store after stream completes
                    assistant_accum = []

                    async for event in llm.stream(
                        user_text,
                        history=history,
                        max_turns=max_turns,
                        max_chars=max_chars,
                    ):
                        try:
                            if isinstance(event, dict):
                                et = event.get("type")
                                if et == "text":
                                    data = event.get("data")
                                    if data:
                                        assistant_accum.append(data)
                                        await websocket.send_text(json.dumps({"type": "chunk", "data": data}))
                                else:
                                    # Fallback: treat unknown dict as chunk
                                    await websocket.send_text(json.dumps({"type": "chunk", "data": json.dumps(event)}))
                            else:
                                # Backward-compatible: raw text
                                text_event = str(event)
                                assistant_accum.append(text_event)
                                await websocket.send_text(json.dumps({"type": "chunk", "data": text_event}))
                        except Exception:
                            # Do not break the stream on send errors; try to continue
                            pass
                else:
                    await websocket.send_text(json.dumps({"type": "error", "message": f"Unsupported provider: {provider}"}))

                # Post-process: classify emotion from last user input + assistant response using LLM
                try:
                    assistant_text = "".join(assistant_accum)
                    emotion = await classify_emotion_llm(
                        client,
                        host,
                        model,
                        last_user=user_text,
                        assistant=assistant_text,
                        allowed=allowed_emotions,
                    )
                    if emotion:
                        await websocket.send_text(json.dumps({"type": "emotion", "emotion": emotion}))
                except Exception:
                    pass

                await websocket.send_text(json.dumps({"type": "end"}))
                # Store assistant message in history
                try:
                    if 'assistant_accum' in locals():
                        assistant_text = "".join(assistant_accum)
                        if assistant_text.strip():
                            history.append({"role": "assistant", "content": assistant_text})
                except Exception:
                    pass
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


