type StreamlitArgs = {
  prefill?: unknown
  result?: unknown
  error?: string | null
  request_id?: string | null
}

export type ComponentEvent =
  | { action: 'recalc'; id: string; form: unknown; mpp_upload_id?: string | null }
  | { action: 'mpp_upload_start'; id: string; filename: string; size: number }
  | { action: 'mpp_upload_chunk'; id: string; chunk: string; index: number }
  | { action: 'mpp_upload_finish'; id: string }
  | { action: 'mpp_clear'; id: string }

type ArgsListener = (args: StreamlitArgs) => void

const listeners = new Set<ArgsListener>()
let lastArgs: StreamlitArgs | null = null
let readySent = false
let heightTimer: number | null = null
let lastPostedHeight = 0

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

/** Высота контента, без window.innerHeight — иначе после раскрытия iframe не сжимается. */
function measureContentHeight(): number {
  const root = document.getElementById('root')
  if (root) {
    return Math.ceil(Math.max(root.scrollHeight, root.offsetHeight, root.getBoundingClientRect().height))
  }
  const body = document.body
  const doc = document.documentElement
  return Math.ceil(
    Math.max(body?.scrollHeight || 0, body?.offsetHeight || 0, doc?.scrollHeight || 0, doc?.offsetHeight || 0),
  )
}

function ensureListener(): void {
  if (readySent) return
  readySent = true
  document.documentElement.setAttribute('data-streamlit-component', '1')
  window.addEventListener('message', onMessage)
  post('streamlit:componentReady', { apiVersion: 1 })
  syncHeight()
  window.addEventListener('resize', () => syncHeight())
  document.addEventListener('toggle', () => syncHeight(), true)
  const ro = new ResizeObserver(() => syncHeight())
  ro.observe(document.documentElement)
  const root = document.getElementById('root')
  if (root) ro.observe(root)
  window.setTimeout(() => syncHeight(), 100)
  window.setTimeout(() => syncHeight(), 500)
  window.setTimeout(() => syncHeight(), 1500)
}

export function syncHeight(): void {
  if (!isStreamlitComponent() && !readySent) return
  if (heightTimer != null) window.clearTimeout(heightTimer)
  heightTimer = window.setTimeout(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const height = Math.max(measureContentHeight(), 480)
        if (Math.abs(height - lastPostedHeight) < 2) return
        lastPostedHeight = height
        post('streamlit:setFrameHeight', { height })
      })
    })
  }, 30)
}

export function setComponentValue(value: ComponentEvent): void {
  ensureListener()
  post('streamlit:setComponentValue', { value })
}

export function subscribeArgs(fn: ArgsListener): () => void {
  ensureListener()
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

/** Ждём echo request_id после любого действия компонента (чанк / clear / start). */
export function waitForComponentAck(requestId: string, timeoutMs = 45000): Promise<StreamlitArgs> {
  ensureListener()
  if (lastArgs?.request_id === requestId) {
    if (lastArgs.error) return Promise.reject(new Error(lastArgs.error))
    return Promise.resolve(lastArgs)
  }
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      off()
      reject(new Error('Streamlit не подтвердил шаг загрузки'))
    }, timeoutMs)
    const off = subscribeArgs((args) => {
      if (args.request_id !== requestId) return
      window.clearTimeout(timer)
      off()
      if (args.error) {
        reject(new Error(args.error))
        return
      }
      resolve(args)
    })
  })
}

export function waitForRecalcResponse(requestId: string, timeoutMs = 30000): Promise<StreamlitArgs> {
  ensureListener()
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

/** Ждём, пока Streamlit подтвердит сохранение .mpp в session_state. */
export function waitForMppUploadAck(requestId: string, timeoutMs = 90000): Promise<StreamlitArgs> {
  ensureListener()
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      off()
      reject(new Error('Streamlit не принял файл .mpp'))
    }, timeoutMs)
    const off = subscribeArgs((args) => {
      if (args.request_id !== requestId) return
      if (args.error) {
        window.clearTimeout(timer)
        off()
        reject(new Error(args.error))
        return
      }
      const ready = Boolean(
        (args.prefill as { mpp_upload?: { ready?: boolean } } | undefined)?.mpp_upload?.ready,
      )
      if (!ready) return
      window.clearTimeout(timer)
      off()
      resolve(args)
    })
  })
}
