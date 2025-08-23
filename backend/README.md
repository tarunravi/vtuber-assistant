# Backend (FastAPI + WebSocket)

## Prerequisites
- Python 3.10+
- Ollama running locally with the target model pulled
  - Install Ollama: https://ollama.com
  - Start Ollama: `ollama serve`
  - Pull model (default qwen2.5): `ollama pull qwen2.5`

## Install
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```
python server.py
```
- WebSocket endpoint: `ws://127.0.0.1:8000/ws`

## Config
- Reads `vtuber.config.json` from the project root
- Example `llm` section:
```
{
  "llm": {
    "provider": "ollama",
    "model": "qwen2.5",
    "host": "http://127.0.0.1:11434",
    "wsPath": "/ws"
  }
}
```

## Protocol
- Client sends either a raw string or `{ "prompt": string }`
- Server streams messages:
  - `{ "type": "start" }`
  - `{ "type": "chunk", "data": string }` (repeated)
  - `{ "type": "end" }`
  - On error: `{ "type": "error", "message": string }`

