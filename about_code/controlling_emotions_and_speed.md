## Controlling Emotions and Speed in the Avatar

This document explains how the app controls Live2D model expressions (emotions) and the playback speed behavior of the avatar.

### Where the logic lives
- UI and runtime control: `vtuber/frontend/src/components/Live2D.tsx`
- Frontend app config (generated): `vtuber/frontend/public/app-config.json`
- Root config (source of truth): `vtuber/vtuber.config.json`
- Asset/config sync: `vtuber/frontend/scripts/sync-assets.mjs`

## Emotions (Expressions)

### How expressions are discovered per model
- Primary source: `Expressions` section from the model's `.model3.json` (e.g., `mao_pro.model3.json`).
- The app tries to read expression names via the library's model setting. If unavailable, it falls back to reading `FileReferences.Expressions` in the model JSON and preloads each `.exp3.json` file at runtime.

Resulting expression names are shown in a dropdown overlay. Selecting an entry triggers the expression on the avatar via the library API.

### Triggering an expression
The select dropdown calls `sprite.setExpression({ expressionId: value })` when the user chooses an emotion:

```181:212:vtuber/frontend/src/components/Live2D.tsx
        <label htmlFor="expression-select" style={{ fontSize: 14 }}>Emotion:</label>
        <select
          id="expression-select"
          value={selectedExpression}
          onChange={(e) => {
            const value = e.target.value
            setSelectedExpression(value)
            if (value) spriteRef.current?.setExpression({ expressionId: value })
          }}
          disabled={expressions.length === 0}
          style={{
            fontSize: 14,
            padding: '6px 8px',
            borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.3)',
            background: '#111',
            color: '#fff',
          }}
        >
          {expressions.length === 0 ? (
            <option value="">No expressions</option>
          ) : (
            <>
              <option value="">Select emotion…</option>
              {expressions.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </>
          )}
        </select>
```

Notes:
- Expression names are model-specific. For example, Mao exposes names like `exp_01`…`exp_08`, while other models may have different sets or none.
- To provide human-friendly labels, map the raw names (e.g., `exp_01`) to your own labels in the component before rendering.

## Speed Control

### Source of truth
Speed is configured in `vtuber/vtuber.config.json` via `timeScale`:

```json
{
  "model": "mao",
  "timeScale": 6
}
```

The asset sync script copies this value into `vtuber/frontend/public/app-config.json` whenever you run `npm run dev` or `npm run build`.

### How the app applies speed
The frontend reads `timeScale` from `/app-config.json` and accelerates the Live2D internals by scaling time derived from `Date.now()` (used by the underlying SDK). This makes all motions, idle, and expressions progress faster.

```17:41:vtuber/frontend/src/components/Live2D.tsx
      try {
        const res = await fetch('/app-config.json')
        const cfg = await res.json()
        const view = canvasRef.current as HTMLCanvasElement
        
        app = new Application()
        await app.init({ view, backgroundAlpha: 0, resizeTo: window })
        
        const timeScale = Number.isFinite(cfg.timeScale) && cfg.timeScale > 0 ? cfg.timeScale : 6
        if (timeScale !== 1) {
          try {
            const originalNow = Date.now
            // @ts-ignore
            Date.now = () => originalNow() * timeScale
            restoreDateNow = () => {
              // @ts-ignore
              Date.now = originalNow
            }
          } catch {}
        }
```

Additionally, the app reduces fade-in/out durations for preloaded expressions and motions to make transitions feel snappier.

### Updating speed during development
1. Edit `vtuber/vtuber.config.json` and change `timeScale`.
2. Re-run `npm run dev` (or `npm run build`) so the sync script regenerates `frontend/public/app-config.json` with the updated value.
3. Refresh the browser.

### Implementation details and cleanup
- The old ticker-only approach was removed; Pixi’s ticker doesn’t control the Live2D SDK’s internal delta time.
- A URL override (e.g., `?timeScale=6`) used during development was removed. Speed is controlled only via config now, per requirement.
- The sync script reads from `vtuber/vtuber.config.json` and writes `app-config.json` with `{ model, entry, timeScale }` used by the frontend.

## Troubleshooting
- Speed didn’t change: Ensure you stopped and re-ran `npm run dev` so the sync script rewrites `app-config.json` with the new `timeScale`.
- No expressions listed: The model may not define any; the UI disables the dropdown. For models with expressions, names are discovered from the `.model3.json` file under `FileReferences.Expressions`.


