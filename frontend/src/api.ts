import {
  isStreamlitComponent,
  setComponentValue,
  waitForMppUploadAck,
  waitForRecalcResponse,
  waitForStreamlitArgs,
} from './streamlitBridge'
import type { FormState, RecalcResult } from './types'
import type { FormOptions } from './options'

const DISCOVERY_URL =
  'https://raw.githubusercontent.com/pyLexxDramma/ppt-msp-demo/main/sample_data/windows_api_url.txt'

let cachedBase: string | null | undefined

export type PrefillResponse = {
  form: FormState
  months: string[]
  com_available: boolean
  options: FormOptions
  mpp_upload?: {
    ready?: boolean
    filename?: string | null
  }
}

async function resolveApiBase(): Promise<string> {
  if (cachedBase !== undefined) return cachedBase || ''
  const fromEnv = String(import.meta.env.VITE_API_URL || '').trim().replace(/\/$/, '')
  if (fromEnv.startsWith('http')) {
    cachedBase = fromEnv
    return fromEnv
  }
  try {
    const res = await fetch(DISCOVERY_URL, { cache: 'no-store' })
    if (res.ok) {
      const line = (await res.text())
        .split('\n')
        .map((s) => s.trim())
        .find((s) => s.startsWith('https://'))
      if (line) {
        const candidate = line.replace(/\/$/, '')
        try {
          const health = await fetch(`${candidate}/api/health`, { cache: 'no-store' })
          if (health.ok) {
            cachedBase = candidate
            return candidate
          }
        } catch {
          /* хост недоступен — локальный /api */
        }
      }
    }
  } catch {
    /* offline */
  }
  cachedBase = ''
  return ''
}

function apiPath(path: string, base: string): string {
  if (!base) return path
  return `${base}${path}`
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data?.detail === 'string') return data.detail
    return JSON.stringify(data?.detail ?? data)
  } catch {
    return res.statusText || 'Ошибка запроса'
  }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const raw = String(reader.result || '')
      const idx = raw.indexOf(',')
      resolve(idx >= 0 ? raw.slice(idx + 1) : raw)
    }
    reader.onerror = () => reject(new Error('Не удалось прочитать файл'))
    reader.readAsDataURL(file)
  })
}

export async function fetchPrefill(): Promise<PrefillResponse> {
  if (isStreamlitComponent()) {
    const args = await waitForStreamlitArgs()
    return args.prefill as PrefillResponse
  }
  const base = await resolveApiBase()
  const res = await fetch(apiPath('/api/prefill', base))
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function uploadMpp(file: File): Promise<{
  upload_id: string
  filename: string
  size: number
}> {
  // 1) HTTP API (локальный uvicorn / Windows-туннель)
  const base = await resolveApiBase()
  if (base || !isStreamlitComponent()) {
    try {
      const body = new FormData()
      body.append('file', file)
      const res = await fetch(apiPath('/api/mpp/upload', base), {
        method: 'POST',
        body,
      })
      if (res.ok) return res.json()
      if (!isStreamlitComponent()) throw new Error(await parseError(res))
    } catch (e) {
      if (!isStreamlitComponent()) throw e
    }
  }

  // 2) Streamlit: кладём файл в session_state родителя
  if (isStreamlitComponent()) {
    const id = crypto.randomUUID()
    const mpp_b64 = await fileToBase64(file)
    setComponentValue({
      action: 'mpp_upload',
      id,
      filename: file.name,
      mpp_b64,
    })
    await waitForMppUploadAck(id)
    return { upload_id: id, filename: file.name, size: file.size }
  }

  throw new Error('Не удалось загрузить .mpp')
}

export async function clearMppUpload(): Promise<void> {
  if (!isStreamlitComponent()) return
  const id = crypto.randomUUID()
  setComponentValue({ action: 'mpp_clear', id })
}

export async function postRecalc(
  form: FormState,
  opts?: { mppUploadId?: string | null },
): Promise<RecalcResult> {
  if (isStreamlitComponent()) {
    const id = crypto.randomUUID()
    setComponentValue({
      action: 'recalc',
      id,
      form,
      mpp_upload_id: opts?.mppUploadId || null,
    })
    const args = await waitForRecalcResponse(id)
    if (args.error) throw new Error(args.error)
    return args.result as RecalcResult
  }
  const base = await resolveApiBase()
  const res = await fetch(apiPath('/api/recalc', base), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...form,
      mpp_upload_id: opts?.mppUploadId || undefined,
    }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export function downloadUrl(jobId: string, kind: 'mpp' = 'mpp'): string {
  const base = cachedBase || ''
  return apiPath(`/api/jobs/${jobId}/${kind}`, base)
}

export function mppDownloadHref(result: RecalcResult): string | null {
  if (result.mpp_b64) {
    return `data:application/vnd.ms-project;base64,${result.mpp_b64}`
  }
  if (result.downloads?.mpp && result.job_id) {
    return downloadUrl(result.job_id)
  }
  return null
}
