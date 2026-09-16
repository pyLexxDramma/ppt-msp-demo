import {
  isStreamlitComponent,
  setComponentValue,
  waitForRecalcResponse,
  waitForStreamlitArgs,
} from './streamlitBridge'
import type { FormState, RecalcResult } from './types'
import type { FormOptions } from './options'

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
  const res = await fetch('/api/prefill')
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
  const res = await fetch('/api/recalc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export function downloadUrl(jobId: string, kind: 'mpp' = 'mpp'): string {
  return `/api/jobs/${jobId}/${kind}`
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
