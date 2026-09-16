type StreamlitArgs = {
  prefill?: unknown
  result?: unknown
  error?: string | null
  request_id?: string | null
}

type RecalcEvent = {
  action: 'recalc'
  id: string
  form: unknown
}

type ArgsListener = (args: StreamlitArgs) => void

const listeners = new Set<ArgsListener>()
let lastArgs: StreamlitArgs | null = null
let readySent = false

function post(type: string, extra: Record<string, unknown> = {}): void {
  window.parent.postMessage({ isStreamlitMessage: true, type, ...extra }, '*')
}

export function isStreamlitComponent(): boolean {
  try {
    const href = window.location.href
    return href.includes('/component/') || href.includes('streamlitUrl=')
  } catch {
    return false
  }
}

function onMessage(event: MessageEvent): void {
  const data = event.data
  if (!data || data.type !== 'streamlit:render') return
  lastArgs = (data.args || {}) as StreamlitArgs
  listeners.forEach((fn) => fn(lastArgs as StreamlitArgs))
}

function ensureListener(): void {
  if (readySent) return
  readySent = true
  window.addEventListener('message', onMessage)
  post('streamlit:componentReady', { apiVersion: 1 })
  syncHeight()
  window.addEventListener('resize', syncHeight)
  const ro = new ResizeObserver(() => syncHeight())
  ro.observe(document.documentElement)
  const root = document.getElementById('root')
  if (root) ro.observe(root)
  // После гидрации React высота растёт асинхронно
  window.setTimeout(syncHeight, 100)
  window.setTimeout(syncHeight, 500)
  window.setTimeout(syncHeight, 1500)
}

export function syncHeight(): void {
  const root = document.getElementById('root')
  const height = Math.max(
    root?.scrollHeight || 0,
    document.documentElement.scrollHeight,
    document.body?.scrollHeight || 0,
    document.documentElement.offsetHeight,
    window.innerHeight,
    900,
  )
  post('streamlit:setFrameHeight', { height })
}

export function setComponentValue(value: RecalcEvent): void {
  post('streamlit:setComponentValue', { value })
}

export function subscribeArgs(fn: ArgsListener): () => void {
  listeners.add(fn)
  if (lastArgs) fn(lastArgs)
  return () => {
    listeners.delete(fn)
  }
}

export function currentArgs(): StreamlitArgs | null {
  return lastArgs
}

export function waitForStreamlitArgs(timeoutMs = 15000): Promise<StreamlitArgs> {
  ensureListener()
  if (lastArgs?.prefill) return Promise.resolve(lastArgs)
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      off()
      reject(new Error('Streamlit не передал данные формы'))
    }, timeoutMs)
    const off = subscribeArgs((args) => {
      if (!args?.prefill) return
      window.clearTimeout(timer)
      off()
      resolve(args)
    })
  })
}

export function waitForRecalcResponse(requestId: string, timeoutMs = 30000): Promise<StreamlitArgs> {
  if (lastArgs?.request_id === requestId && (lastArgs.result || lastArgs.error)) {
    return Promise.resolve(lastArgs)
  }
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      off()
      reject(new Error('Streamlit не ответил на пересчёт'))
    }, timeoutMs)
    const off = subscribeArgs((args) => {
      if (args.request_id !== requestId) return
      if (!args.result && !args.error) return
      window.clearTimeout(timer)
      off()
      resolve(args)
    })
  })
}
