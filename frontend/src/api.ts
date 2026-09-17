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

const MAX_MPP_BYTES = 40 * 1024 * 1024
/** Порог: выше — только HTTP (туннель), не base64 в postMessage. */
const STREAMLIT_B64_MAX = 1.5 * 1024 * 1024

let cachedBase: string | null | undefined
/** Файл, выбранный в React на Streamlit — уходит на сервер при пересчёте. */
let streamlitPendingFile: File | null = null

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

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  timeoutMs: number,
): Promise<Response> {
  const ctrl = new AbortController()
  const timer = window.setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    return await fetch(input, { ...init, signal: ctrl.signal })
  } finally {
    window.clearTimeout(timer)
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
    const res = await fetchWithTimeout(DISCOVERY_URL, { cache: 'no-store' }, 8000)
    if (res.ok) {
      const line = (await res.text())
        .split('\n')
        .map((s) => s.trim())
        .find((s) => s.startsWith('https://'))
      if (line) {
        const candidate = line.replace(/\/$/, '')
        try {
          const health = await fetchWithTimeout(
            `${candidate}/api/health`,
            { cache: 'no-store' },
            4000,
          )
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

export type MppUploadResult = {
  upload_id: string
  filename: string
  size: number
  options?: FormOptions
  warning?: string | null
  com_available?: boolean
}

async function uploadMppHttp(file: File, base: string): Promise<MppUploadResult> {
  const body = new FormData()
  body.append('file', file)
  const res = await fetchWithTimeout(
    apiPath('/api/mpp/upload', base),
    { method: 'POST', body },
    90_000,
  )
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function uploadMpp(file: File): Promise<MppUploadResult> {
  if (file.size > MAX_MPP_BYTES) {
    throw new Error(`Файл больше ${MAX_MPP_BYTES / (1024 * 1024)} МБ`)
  }

  const base = await resolveApiBase()
  if (!base && isStreamlitComponent()) {
    throw new Error(
      'Нет живого Windows API (MS Project). Без него .mpp не читается — загрузка отменена.',
    )
  }

  try {
    const info = await uploadMppHttp(file, base || '')
    if (!info.options?.tasks?.length) {
      throw new Error(
        info.warning ||
          (info.options == null
            ? 'Windows API не вернул задачи из .mpp. Обновите хост с MS Project и перезапустите API — загрузка отменена.'
            : 'В .mpp нет leaf-задач с ВОР (Text13). Загрузка отменена — данные были бы некорректны.'),
      )
    }
    streamlitPendingFile = null
    return info
  } catch (e) {
    streamlitPendingFile = null
    const msg = e instanceof Error ? e.message : 'Не удалось загрузить .mpp'
    if (msg.includes('отменена') || msg.includes('Text13') || msg.includes('Windows API')) {
      throw e instanceof Error ? e : new Error(msg)
    }
    throw new Error(
      `${msg} Нужен доступный Windows API с MS Project. Загрузка отменена.`,
    )
  }
}

export async function clearMppUpload(): Promise<void> {
  streamlitPendingFile = null
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
    let mpp_upload_id: string | null =
      opts?.mppUploadId && opts.mppUploadId !== 'browser-pending' && opts.mppUploadId !== 'session'
        ? opts.mppUploadId
        : null
    let mpp_b64: string | null = null

    const pending = streamlitPendingFile
    if (pending) {
      const base = await resolveApiBase()
      if (base) {
        try {
          const up = await uploadMppHttp(pending, base)
          mpp_upload_id = up.upload_id
        } catch {
          /* ниже — base64 в событии recalc */
        }
      }
      if (!mpp_upload_id) {
        if (pending.size > STREAMLIT_B64_MAX) {
          throw new Error(
            'Файл слишком большой для Streamlit без Windows-туннеля. ' +
              'Запустите API/tunnel или выберите файл меньше 1.5 МБ.',
          )
        }
        mpp_b64 = await fileToBase64(pending)
      }
    }

    setComponentValue({
      action: 'recalc',
      id,
      form,
      mpp_upload_id,
      mpp_b64,
      mpp_filename: pending?.name ?? null,
    })
    const args = await waitForRecalcResponse(id, 180_000)
    if (args.error) throw new Error(args.error)
    return args.result as RecalcResult
  }

  const base = await resolveApiBase()
  const res = await fetchWithTimeout(
    apiPath('/api/recalc', base),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...form,
        mpp_upload_id: opts?.mppUploadId || undefined,
      }),
    },
    180_000,
  )
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
