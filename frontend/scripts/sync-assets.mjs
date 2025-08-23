import { readFile, rm, mkdir, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import fse from 'fs-extra'

const rootConfigPath = '/Users/tarun/Anime/vtuber/vtuber.config.json'
const frontendPublicDir = '/Users/tarun/Anime/vtuber/frontend/public'

const modelMap = {
  mao: {
    src: '/Users/tarun/Anime/vtuber/assets/models/mao_pro/runtime',
    entry: 'mao_pro.model3.json'
  },
  shizuku: {
    src: '/Users/tarun/Anime/vtuber/assets/models/shizuku/runtime',
    entry: 'shizuku.model3.json'
  },
  ellot: {
    src: '/Users/tarun/Anime/vtuber/assets/models/ellot/runtime',
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

  const modelOutDir = join(frontendPublicDir, 'model')
  if (existsSync(modelOutDir)) await rm(modelOutDir, { recursive: true, force: true })
  await mkdir(modelOutDir, { recursive: true })
  await fse.copy(src, modelOutDir)

  const llm = rootConfig.llm || {}
  const wsPath = typeof llm.wsPath === 'string' ? llm.wsPath : '/ws'
  const backendWsUrl = `ws://127.0.0.1:8000${wsPath}`

  const appConfig = { model: selected, entry: `/model/${entry}`, timeScale, emotions, llm: { backendWsUrl } }
  await writeFile(join(frontendPublicDir, 'app-config.json'), JSON.stringify(appConfig))
}

main()

