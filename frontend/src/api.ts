import {
  isStreamlitComponent,
  setComponentValue,
  waitForComponentAck,
  waitForMppUploadAck,
  waitForRecalcResponse,
  waitForStreamlitArgs,
} from './streamlitBridge'
import type { FormState, RecalcResult } from './types'
import type { FormOptions } from './options'

const DISCOVERY_URL =
  'https://raw.githubusercontent.com/pyLexxDramma/ppt-msp-demo/main/sample_data/windows_api_url.txt'

/** ~90KB сырых байт → ~120KB base64 — безопасно для postMessage Streamlit. */
const STREAMLIT_CHUNK_CHARS = 120_000
const MAX_MPP_BYTES = 40 * 1024 * 1024

type PendingUpload = {
  uploadId: string
  filename: string
  size: number
  b64: string
  /** Следующий индекс чанка (0 = ещё нужен start). */
  nextIndex: number
  phase: 'start' | 'chunks' | 'finish'
}

let cachedBase: string | null | undefined
/** In-memory resume после remount React внутри того же iframe. */
let memoryPending: PendingUpload | null = null
let streamlitUploadInFlight: Promise<{
  upload_id: string
  filename: string
  size: number
}> | null = null

export type PrefillResponse = {
  form: FormState
  months: string[]
  com_available: boolean
  options: FormOptions
  mpp_upload?: {
    ready?: boolean
    filename?: string | null
    host_managed?: boolean
  }
}

function readPending(): PendingUpload | null {
  return memoryPending
}

function writePending(p: PendingUpload | null): void {
  memoryPending = p
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

async function uploadMppHttp(file: File, base: string): Promise<{
  upload_id: string
  filename: string
  size: number
}> {
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

/** Продолжает chunked-загрузку (в т.ч. после remount React в том же iframe). */
async function continueStreamlitUpload(pending: PendingUpload): Promise<{
  upload_id: string
  filename: string
  size: number
}> {
  if (streamlitUploadInFlight) return streamlitUploadInFlight

  streamlitUploadInFlight = (async () => {
    let state = { ...pending }

    if (state.phase === 'start') {
      const id = crypto.randomUUID()
      setComponentValue({
        action: 'mpp_upload_start',
        id,
        filename: state.filename,
        size: state.size,
      })
      await waitForComponentAck(id)
      state = { ...state, phase: 'chunks', nextIndex: 0 }
      writePending(state)
    }

    if (state.phase === 'chunks') {
      if (!state.b64) {
        writePending(null)
        throw new Error('Пустой файл .mpp')
      }
      while (state.nextIndex * STREAMLIT_CHUNK_CHARS < state.b64.length) {
        const from = state.nextIndex * STREAMLIT_CHUNK_CHARS
        const chunk = state.b64.slice(from, from + STREAMLIT_CHUNK_CHARS)
        const id = crypto.randomUUID()
        setComponentValue({
          action: 'mpp_upload_chunk',
          id,
          chunk,
          index: state.nextIndex,
        })
        await waitForComponentAck(id)
        state = { ...state, nextIndex: state.nextIndex + 1 }
        writePending(state)
      }
      state = { ...state, phase: 'finish' }
      writePending(state)
    }

    if (state.phase === 'finish') {
      const id = crypto.randomUUID()
      setComponentValue({ action: 'mpp_upload_finish', id })
      await waitForMppUploadAck(id)
      writePending(null)
    }

    return {
      upload_id: state.uploadId,
      filename: state.filename,
      size: state.size,
    }
  })().finally(() => {
    streamlitUploadInFlight = null
  })

  return streamlitUploadInFlight
}

async function uploadMppViaStreamlit(file: File): Promise<{
  upload_id: string
  filename: string
  size: number
}> {
  if (file.size > MAX_MPP_BYTES) {
    throw new Error(`Файл больше ${MAX_MPP_BYTES / (1024 * 1024)} МБ`)
  }
  const b64 = await fileToBase64(file)
  const pending: PendingUpload = {
    uploadId: crypto.randomUUID(),
    filename: file.name,
    size: file.size,
    b64,
    nextIndex: 0,
    phase: 'start',
  }
  writePending(pending)
  return continueStreamlitUpload(pending)
}

/** Если iframe пересоздали mid-upload — дожимаем из sessionStorage. */
export async function resumePendingMppUpload(): Promise<{
  upload_id: string
  filename: string
  size: number
} | null> {
  if (!isStreamlitComponent()) return null
  const pending = readPending()
  if (!pending?.b64) return null
  return continueStreamlitUpload(pending)
}

export async function uploadMpp(file: File): Promise<{
  upload_id: string
  filename: string
  size: number
}> {
  if (file.size > MAX_MPP_BYTES) {
    throw new Error(`Файл больше ${MAX_MPP_BYTES / (1024 * 1024)} МБ`)
  }

  // 1) HTTP API (локальный uvicorn / Windows-туннель) — с жёстким timeout
  const base = await resolveApiBase()
  if (base || !isStreamlitComponent()) {
    try {
      return await uploadMppHttp(file, base)
    } catch (e) {
      if (!isStreamlitComponent()) throw e
      // на Streamlit падаем на chunked в session_state
    }
  }

  // 2) Streamlit: чанки base64 → session_state (не один огромный postMessage)
  if (isStreamlitComponent()) {
    return uploadMppViaStreamlit(file)
  }

  throw new Error('Не удалось загрузить .mpp')
}

export async function clearMppUpload(): Promise<void> {
  writePending(null)
  if (!isStreamlitComponent()) return
  const id = crypto.randomUUID()
  setComponentValue({ action: 'mpp_clear', id })
  try {
    await waitForComponentAck(id, 15000)
  } catch {
    /* ignore */
  }
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
