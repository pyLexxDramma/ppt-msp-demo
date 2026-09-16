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
  const res = await fetch('/api/prefill')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function postRecalc(form: FormState): Promise<RecalcResult> {
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
