import { readFile, rm, mkdir, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import fse from 'fs-extra'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

// Use script location to find project root - more reliable in Docker
const scriptDir = __dirname
const projectRoot = join(scriptDir, '..', '..') // Go up from scripts/frontend to project root
const rootConfigPath = join(projectRoot, 'vtuber.config.json')
const frontendPublicDir = join(projectRoot, 'frontend/public')

const modelMap = {
  mao: {
    src: join(projectRoot, 'assets/models/mao_pro/runtime'),
    entry: 'mao_pro.model3.json'
  },
  shizuku: {
    src: join(projectRoot, 'assets/models/shizuku/runtime'),
    entry: 'shizuku.model3.json'
  },
  ellot: {
    src: join(projectRoot, 'assets/models/ellot/runtime'),
    entry: 'ellot.model3.json'
  }
}

async function main() {
  const configRaw = existsSync(rootConfigPath) ? await readFile(rootConfigPath, 'utf-8') : '{}'
  const rootConfig = JSON.parse(configRaw)
  const selected = ['mao', 'shizuku', 'ellot'].includes(rootConfig.model) ? rootConfig.model : 'mao'
  const perModel = (rootConfig.models && rootConfig.models[selected]) || {}
  const parsedScale = Number(perModel.timeScale ?? rootConfig.timeScale)
  const timeScale = Number.isFinite(parsedScale) && parsedScale > 0 ? parsedScale : 1
  const emotions = perModel.emotions && typeof perModel.emotions === 'object' ? perModel.emotions : {}
  const { src, entry } = modelMap[selected]

  // Check if the source directory exists
  if (!existsSync(src)) {
    throw new Error(`Could not find model assets for ${selected} at path: ${src}\nWorking directory: ${projectRoot}`)
  }

  const modelOutDir = join(frontendPublicDir, 'model')
  if (existsSync(modelOutDir)) await rm(modelOutDir, { recursive: true, force: true })
  await mkdir(modelOutDir, { recursive: true })
  await fse.copy(src, modelOutDir)

  const llm = rootConfig.llm || {}
  const wsPath = typeof llm.wsPath === 'string' ? llm.wsPath : '/ws'
  // Support proxying through the frontend dev server so only port 5173 is exposed
  const useProxy = String(process.env.FRONTEND_PROXY || '').toLowerCase() === '1' || String(process.env.FRONTEND_PROXY || '').toLowerCase() === 'true'
  let backendWsUrl
  if (useProxy) {
    // Relative path lets Vite proxy handle WS to backend
    backendWsUrl = wsPath
  } else {
    // Use environment variables for Docker compatibility
    const backendHost = process.env.BACKEND_HOST || '127.0.0.1'
    const backendPort = process.env.BACKEND_PORT || '8000'
    backendWsUrl = `ws://${backendHost}:${backendPort}${wsPath}`
  }

  const appConfig = { model: selected, entry: `/model/${entry}`, timeScale, emotions, llm: { backendWsUrl } }
  await writeFile(join(frontendPublicDir, 'app-config.json'), JSON.stringify(appConfig))
}

main()
