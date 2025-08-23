import { useEffect, useRef, useState } from 'react'
import { Application, Ticker } from 'pixi.js'
import { Live2DSprite } from 'easy-live2d'

export default function Live2D() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const spriteRef = useRef<Live2DSprite | null>(null)
  const exprFileMapRef = useRef<Record<string, string>>({})
  const [expressions, setExpressions] = useState<string[]>([])
  const [selectedExpression, setSelectedExpression] = useState<string>('')
  const [emotionOptions, setEmotionOptions] = useState<{ label: string; value: string }[]>([])

  useEffect(() => {
    let app: Application | null = null
    let sprite: Live2DSprite | null = null
    let resizeHandler: (() => void) | null = null
    let restoreDateNow: (() => void) | null = null

    const run = async () => {
      try {
        const res = await fetch('/app-config.json')
        const cfg = await res.json()
        const view = canvasRef.current as HTMLCanvasElement
        
        app = new Application()
        await app.init({ view, backgroundAlpha: 0, resizeTo: window })
        
        // Load timeScale from config: affects Live2D internal timing (ToolManager uses Date.now)
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

        sprite = new Live2DSprite()
        await sprite.init({ modelPath: cfg.entry, ticker: Ticker.shared })
        spriteRef.current = sprite
        
        app.stage.addChild(sprite)
        
        // Helper to reduce fade times for expressions and motions
        const reduceFades = () => {
          try {
            const modelAny: any = sprite
            const inner = modelAny?._model
            // Expressions
            const exprMap = inner?._expressions
            if (exprMap && typeof exprMap.getSize === 'function' && Array.isArray(exprMap._keyValues)) {
              for (let i = 0; i < exprMap.getSize(); i++) {
                const pair = exprMap._keyValues[i]
                const motion = pair?.second
                if (motion && typeof motion.setFadeInTime === 'function') motion.setFadeInTime(0.15)
                if (motion && typeof motion.setFadeOutTime === 'function') motion.setFadeOutTime(0.15)
              }
            }
            // Motions (including Idle)
            const motionMap = inner?._motions
            if (motionMap && typeof motionMap.getSize === 'function' && Array.isArray(motionMap._keyValues)) {
              for (let i = 0; i < motionMap.getSize(); i++) {
                const pair = motionMap._keyValues[i]
                const motion = pair?.second
                if (motion && typeof motion.setFadeInTime === 'function') motion.setFadeInTime(0.2)
                if (motion && typeof motion.setFadeOutTime === 'function') motion.setFadeOutTime(0.2)
              }
            }
          } catch {}
        }

        // Extract available expression names from the model setting (if any)
        try {
          const count = sprite.modelSetting && typeof sprite.modelSetting.getExpressionCount === 'function'
            ? sprite.modelSetting.getExpressionCount()
            : 0
          if (count > 0) {
            const names: string[] = []
            for (let i = 0; i < count; i++) {
              const name = sprite.modelSetting.getExpressionName(i)
              if (name) names.push(name)
            }
            setExpressions(names)
            reduceFades()
            // Build map of expression name -> file path for lazy-load fallback
            try {
              const modelRes = await fetch(cfg.entry)
              const modelJson = await modelRes.json()
              const exprArr = modelJson?.FileReferences?.Expressions
              if (Array.isArray(exprArr) && exprArr.length > 0) {
                const basePath = cfg.entry.replace(/[^/]+$/, '')
                const tmp: Record<string, string> = {}
                for (const expr of exprArr) {
                  const name = (expr?.Name || expr?.name) as string
                  const file = (expr?.File || expr?.file) as string
                  if (!name || !file) continue
                  tmp[name] = basePath + file
                }
                exprFileMapRef.current = tmp
              } else {
                exprFileMapRef.current = {}
              }
            } catch {
              exprFileMapRef.current = {}
            }
          } else {
            // Fallback: read and also preload expressions directly when library modelSetting has none
            try {
              const modelRes = await fetch(cfg.entry)
              const modelJson = await modelRes.json()
              const exprArr = modelJson?.FileReferences?.Expressions
              if (Array.isArray(exprArr) && exprArr.length > 0) {
                const basePath = cfg.entry.replace(/[^/]+$/, '') // e.g. /model/
                const names: string[] = []
                const tmp: Record<string, string> = {}
                for (const expr of exprArr) {
                  const name = expr?.Name || expr?.name
                  const file = expr?.File || expr?.file
                  if (!name || !file || typeof name !== 'string' || typeof file !== 'string') continue
                  try {
                    const res = await fetch(basePath + file)
                    const buf = await res.arrayBuffer()
                    // Access underlying model internals to register expression, since the lib didn't
                    // auto-load them when modelSetting had none
                    const modelAny: any = sprite
                    const motion = modelAny._model?.loadExpression?.(buf, buf.byteLength, name)
                    if (motion && modelAny._model?._expressions?.setValue) {
                      if (typeof motion.setFadeInTime === 'function') motion.setFadeInTime(0.15)
                      if (typeof motion.setFadeOutTime === 'function') motion.setFadeOutTime(0.15)
                      modelAny._model._expressions.setValue(name, motion)
                    }
                    names.push(name)
                    tmp[name] = basePath + file
                  } catch {}
                }
                setExpressions(names)
                exprFileMapRef.current = tmp
                reduceFades()
              } else {
                setExpressions([])
                exprFileMapRef.current = {}
              }
            } catch {
              setExpressions([])
              exprFileMapRef.current = {}
            }
          }
        } catch (e) {
          // If model has no expressions, ensure UI reflects that gracefully
          setExpressions([])
          exprFileMapRef.current = {}
        }

        // Build emotion options from cfg.emotions mapping if present
        try {
          const mapping = cfg.emotions && typeof cfg.emotions === 'object' ? cfg.emotions as Record<string, string> : {}
          const opts: { label: string; value: string }[] = []
          const seen = new Set<string>()
          for (const [label, exprId] of Object.entries(mapping)) {
            if (typeof label !== 'string' || typeof exprId !== 'string') continue
            if (!exprId.startsWith('exp_')) continue
            if (seen.has(label)) continue
            opts.push({ label, value: exprId })
            seen.add(label)
          }
          // If no mapping provided, fall back to raw expression names
          if (opts.length === 0 && Array.isArray(expressions) && expressions.length > 0) {
            setEmotionOptions(expressions.map((n) => ({ label: n, value: n })))
          } else {
            setEmotionOptions(opts)
          }
        } catch {
          setEmotionOptions([])
        }
        
        const resize = () => {
          if (!sprite || !app) return
          const w = app.renderer.width
          const h = app.renderer.height
          const sx = w / (sprite.width || 1)
          const sy = h / (sprite.height || 1)
          const s = Math.min(sx, sy) * 0.9
          sprite.scale.set(s)
          sprite.x = w / 2
          sprite.y = h / 2
          // @ts-ignore
          if (sprite.anchor && typeof sprite.anchor.set === 'function') sprite.anchor.set(0.5, 0.5)
        }
        
        resize()
        resizeHandler = resize
        window.addEventListener('resize', resize)
      } catch (error) {
        console.error('Failed to initialize Live2D model:', error)
      }
    }

    run()

    return () => {
      if (resizeHandler) window.removeEventListener('resize', resizeHandler)
      if (app) app.destroy(true)
      if (restoreDateNow) restoreDateNow()
    }
  }, [])

  return (
    <div style={{ width: '100vw', height: '100vh', position: 'relative' }}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
      <div
        style={{
          position: 'absolute',
          top: 12,
          left: 12,
          background: 'rgba(0,0,0,0.5)',
          padding: '8px 10px',
          borderRadius: 8,
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          zIndex: 10,
        }}
      >
        <label htmlFor="expression-select" style={{ fontSize: 14 }}>Emotion:</label>
        <select
          id="expression-select"
          value={selectedExpression}
          onChange={async (e) => {
            const value = e.target.value
            setSelectedExpression(value)
            if (value) {
              // Try public API
              try { spriteRef.current?.setExpression({ expressionId: value }) } catch {}
              // Fallback: directly trigger via internals if available
              try {
                const modelAny: any = spriteRef.current
                const inner = modelAny?._model
                const motion = inner?._expressions?.getValue?.(value)
                if (motion && inner?._expressionManager?.startMotion) {
                  inner._expressionManager.startMotion(motion, false)
                } else if (exprFileMapRef.current && exprFileMapRef.current[value]) {
                  // Lazy-load expression file and register
                  const url = exprFileMapRef.current[value]
                  try {
                    const res = await fetch(url)
                    const buf = await res.arrayBuffer()
                    const loaded = inner?.loadExpression?.(buf, buf.byteLength, value)
                    if (loaded) {
                      if (typeof loaded.setFadeInTime === 'function') loaded.setFadeInTime(0.15)
                      if (typeof loaded.setFadeOutTime === 'function') loaded.setFadeOutTime(0.15)
                      inner?._expressions?.setValue?.(value, loaded)
                      inner?._expressionManager?.startMotion?.(loaded, false)
                    }
                  } catch {}
                }
              } catch {}
            }
          }}
          disabled={emotionOptions.length === 0}
          style={{
            fontSize: 14,
            padding: '6px 8px',
            borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.3)',
            background: '#111',
            color: '#fff',
          }}
        >
          {emotionOptions.length === 0 ? (
            <option value="">No expressions</option>
          ) : (
            <>
              <option value="">Select emotion…</option>
              {emotionOptions.map((opt) => (
                <option key={opt.label} value={opt.value}>{opt.label}</option>
              ))}
            </>
          )}
        </select>
      </div>
    </div>
  )
}

