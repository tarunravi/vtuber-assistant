## Docker Compose and Container Architecture

This project ships with a single-container dev setup that runs both the backend (FastAPI/Uvicorn) and the frontend (Vite) inside one container. The container builds from the local source once, then runs without modifying your host repo.

### What gets built
- **Image base**: `nikolaik/python-nodejs:python3.11-nodejs20` (Python 3.11 + Node 20)
- **Dockerfile**: Copies the entire project into the image (no bind mount), makes `start.sh` executable, and exposes port `5173` for the frontend dev server.
- **No bind mounts**: Your working directory on the host is not modified while the container runs.

### Services and ports
- **Frontend (Vite dev server)**
  - Listens on `0.0.0.0:5173` inside the container
  - Published to the host as `localhost:5173`
- **Backend (Uvicorn/FastAPI)**
  - Listens on `0.0.0.0:8000` inside the container
  - Not published to the host; only reachable from within the container

### WebSocket routing (frontend ↔ backend)
- The frontend talks to the backend via WebSocket at the relative path `/ws`.
- `frontend/vite.config.ts` proxies `/ws` to `http://127.0.0.1:8000` with `ws: true`, so the browser only needs access to `5173`.
- `frontend/scripts/sync-assets.mjs` writes `frontend/public/app-config.json` with `llm.backendWsUrl`:
  - When `FRONTEND_PROXY=1`, it writes a relative path (e.g. `/ws`), so the Vite proxy handles WS to the backend.
  - When proxying is off, it writes an absolute URL assembled from `BACKEND_HOST`/`BACKEND_PORT`.
- `frontend/src/components/ChatPanel.tsx` loads `/app-config.json` at runtime and falls back to `VITE_BACKEND_HOST`/`VITE_BACKEND_PORT` if needed.

### Key files
- `docker-compose.yml`: builds and runs the `vtuber` service, exposing only `5173`.
- `Dockerfile`: builds the image and copies your project in.
- `start.sh`: orchestrates the startup sequence inside the container.
- `frontend/vite.config.ts`: sets up the dev server and WS proxy.
- `frontend/scripts/sync-assets.mjs`: copies the selected Live2D model runtime assets and writes `app-config.json`.

### Environment variables (compose service)
- **FRONTEND_PROXY**: `"1"` enables relative WS path in `app-config.json` so Vite can proxy `/ws`.
- **UVICORN_HOST/UVICORN_PORT**: backend bind address/port inside the container (defaults set to `0.0.0.0:8000`).
- **BACKEND_HOST/BACKEND_PORT**: used by scripts to construct absolute WS URLs when proxying is disabled. With proxying on, they’re not used by the browser.
- npm envs (`npm_config_fund`, `npm_config_audit`) and `FORCE_COLOR` improve install/noise behavior.

### Startup flow (what `start.sh` does)
1. Backend
   - Creates/uses a Python venv under `backend/.venv`
   - `pip install -r backend/requirements.txt`
   - Runs `uvicorn` with host/port from envs
2. Frontend
   - `npm install` in `frontend/`
   - Runs `frontend/scripts/sync-assets.mjs` (after deps are installed) to copy model assets and write `app-config.json`
   - Starts Vite dev server on `5173`

### How to run
```bash
docker compose build --no-cache vtuber
docker compose up vtuber
# open http://localhost:5173
```

### Common customizations
- **Change backend port**
  - Update `UVICORN_PORT` in `docker-compose.yml`
  - Ensure Vite proxy matches by setting `BACKEND_PORT` env in compose (read by `vite.config.ts`), or adjust the proxy target there.
- **Disable proxying (not recommended for dev)**
  - Set `FRONTEND_PROXY=0` and provide `BACKEND_HOST`/`BACKEND_PORT`. The asset sync will write an absolute WS URL.
- **Switch Live2D model**
  - Edit `vtuber.config.json` (`model`, `models[model]`, `timeScale`, `emotions`). The next run will re-sync assets to `frontend/public/model/`.

### Troubleshooting
- **Port already in use**: Something else is on `5173`—stop it or change the published port mapping in `docker-compose.yml`.
- **WebSocket not connecting**: The browser calls `/ws` on `5173`; ensure the container logs show Uvicorn accepting `WebSocket /ws`. If you disabled proxying, confirm the absolute WS URL is reachable.
- **Asset sync errors**: The script logs the path it expects for assets. Ensure the selected model exists under `assets/models/<model>/runtime/` and `vtuber.config.json` is valid JSON.
- **Node module issues after base image updates**: `start.sh` removes `node_modules` within the container before installing to avoid arch mismatches.

### Why no bind mount?
- Keeps the container immutable relative to your host repo and avoids cross-arch/node ABI issues leaking into your working directory.
- If you do want live code edits to reflect instantly inside the container, you can replace the image copy approach with a bind mount:
  - Remove the image `build:` section and add a volume mapping `.:/app` in `docker-compose.yml`.
  - This is optional and not the default here by design.

### Production note (optional)
- For production, you’d typically build the frontend (`npm run build`), serve static files, and run the backend behind a proper HTTP server. The current compose is optimized for fast local iteration with HMR and WS proxying.


