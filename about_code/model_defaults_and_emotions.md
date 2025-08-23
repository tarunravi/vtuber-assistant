## VTuber model defaults and emotion mapping

### Overview
- **Per-model defaults** are now supported in `vtuber/vtuber.config.json` (e.g., timeScale, emotion labels).
- The **asset sync script** writes model-specific `timeScale` and `emotions` into `frontend/public/app-config.json`.
- The **Live2D UI** shows human-readable emotion labels and maps them to the correct `exp_##` expression. If an expression isn’t registered, it is **lazy-loaded** at selection time.

### Root configuration
File: `vtuber/vtuber.config.json`

```json
{
  "model": "mao",
  "models": {
    "mao": {
      "timeScale": 6,
      "emotions": {
        "Happy": "exp_01",
        "Thinking": "exp_03",
        "Excited": "exp_04",
        "Sad": "exp_05",
        "Concerned": "exp_05",
        "Blushing": "exp_06",
        "Embarassed": "exp_06",
        "Shocked": "exp_07",
        "Flustered": "exp_07",
        "Annoyed": "exp_08",
        "Mad": "exp_08"
      }
    },
    "ellot": {
      "timeScale": 4,
      "emotions": {
        "Searching": "exp_01",
        "Concentrating": "exp_01",
        "Gaming": "exp_01",
        "Sad": "exp_02",
        "Happy": "exp_03",
        "Excited": "exp_04",
        "Nerd": "exp_05",
        "Cunning": "exp_06",
        "Lying": "exp_06",
        "Evil": "exp_06",
        "Scheming": "exp_06",
        "Blushing": "exp_08",
        "Embarassed": "exp_08",
        "Mad": "exp_09",
        "Annoyed": "exp_09"
      }
    }
  },
  "llm": {
    "provider": "ollama",
    "model": "qwen2.5",
    "host": "http://127.0.0.1:11434",
    "wsPath": "/ws"
  }
}
```

Notes:
- `model` selects the active model.
- `models[<name>].timeScale` overrides animation timing per model.
- `models[<name>].emotions` maps human-readable labels → `exp_##` ids.

### Asset sync script
File: `vtuber/frontend/scripts/sync-assets.mjs`

- Reads the root config and selected model.
- Resolves `timeScale` from `models[model].timeScale` (fallback: top-level `timeScale`, then `1`).
- Copies the selected model’s runtime assets to `frontend/public/model`.
- Writes `frontend/public/app-config.json` including:

```json
{
  "model": "mao",
  "entry": "/model/mao_pro.model3.json",
  "timeScale": 6,
  "emotions": { "Happy": "exp_01", "Thinking": "exp_03", "...": "..." },
  "llm": { "backendWsUrl": "ws://127.0.0.1:8000/ws" }
}
```

This file is auto-generated on `npm run dev` and `npm run build`.

### Live2D frontend behavior
File: `vtuber/frontend/src/components/Live2D.tsx`

- Applies `timeScale` by temporarily scaling `Date.now()` for Live2D timing.
- Loads the model and extracts available expressions via `modelSetting`. If not listed, it preloads them directly from the model’s `Expressions` references.
- Reduces fade-in/out times for smoother, snappier expression changes.
- Builds the Emotion dropdown from `cfg.emotions` so users see labels (e.g., “Happy”).
- On selection, it attempts expression change via the public API `setExpression({ expressionId })`. If not registered yet:
  - Tries the underlying expression manager directly.
  - If still missing, it lazy-loads the `exp_##.exp3.json`, registers it with the model, then starts the expression.

This fixes cases where some models (e.g., Ellot) didn’t initially react to selection.

### Adding another model
To add a new model with labels and defaults:
1. Add the model in the sync script’s `modelMap` with `src` and `entry`.
2. Add a `models["<your-model>"]` block in `vtuber.config.json` with `timeScale` and an `emotions` mapping.
3. Set `model` to your new model in `vtuber.config.json`.
4. Start the frontend (`npm run dev`) to sync and generate `app-config.json`.

### Known defaults
- `mao`: `timeScale = 6`
- `ellot`: `timeScale = 4`

### Troubleshooting
- Emotion not changing:
  - Ensure the label maps to a valid `exp_##` present in the model’s `Expressions`.
  - Make sure `app-config.json` contains `emotions` for the active model.
  - Restart the dev server to regenerate `app-config.json` if you changed `vtuber.config.json`.


