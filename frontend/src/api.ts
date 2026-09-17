import {
  isStreamlitComponent,
  setComponentValue,
  waitForRecalcResponse,
  waitForStreamlitArgs,
} from './streamlitBridge'
import type { FormState, RecalcResult } from './types'
import type { FormOptions } from './options'

const DISCOVERY_URL =
  'https://raw.githubusercontent.com/pyLexxDramma/ppt-msp-demo/main/sample_data/windows_api_url.txt'

let cachedBase: string | null | undefined

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

export async function fetchPrefill(): Promise<{
  form: FormState
  months: string[]
  com_available: boolean
  options: FormOptions
}> {
  if (isStreamlitComponent()) {
    const args = await waitForStreamlitArgs()
    return args.prefill as {
      form: FormState
      months: string[]
      com_available: boolean
      options: FormOptions
    }
  }
  const base = await resolveApiBase()
  const res = await fetch(apiPath('/api/prefill', base))
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function postRecalc(form: FormState): Promise<RecalcResult> {
  if (isStreamlitComponent()) {
    const id = crypto.randomUUID()
    setComponentValue({ action: 'recalc', id, form })
    const args = await waitForRecalcResponse(id)
    if (args.error) throw new Error(args.error)
    return args.result as RecalcResult
  }
  const base = await resolveApiBase()
  const res = await fetch(apiPath('/api/recalc', base), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form),
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
