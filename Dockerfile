# Minimal image to run both backend (FastAPI) and frontend (Vite) together
FROM node:20-bookworm-slim

# Install Python
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend deps first for better layer caching
COPY backend/requirements.txt ./backend/requirements.txt
# Use a virtual environment to avoid Debian's externally-managed environment restriction (PEP 668)
RUN python3 -m venv /opt/venv \
  && /opt/venv/bin/pip install --no-cache-dir -r backend/requirements.txt

# Ensure venv is used by default
ENV PATH="/opt/venv/bin:${PATH}"

# Install frontend deps
COPY frontend/package.json ./frontend/package.json
RUN npm --prefix frontend install --no-fund --no-audit

# Copy the rest of the project
COPY . .

# Environment for servers in container
ENV UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000 \
    BACKEND_PORT=8000 \
    FRONTEND_PROXY=1

# Frontend dev server
EXPOSE 5173

# Run asset sync, start backend in background, then run Vite in foreground
CMD sh -c "node frontend/scripts/sync-assets.mjs && (python3 backend/server.py &) && npm --prefix frontend run dev"


