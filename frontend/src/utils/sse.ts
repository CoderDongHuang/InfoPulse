/**
 * InfoPulse — SSE (Server-Sent Events) Utility
 * ==============================================
 * Creates an SSE connection with heartbeat detection and timeout.
 *
 * Usage:
 *   const conn = createSSEConnection('/anti-scam/analyze', {
 *     body: { keyword: 'test', platforms: ['zhihu'], max_items: 50 },
 *     onProgress: (data) => console.log(data),
 *     onChunk: (text) => appendToDisplay(text),
 *     onResult: (data) => showResult(data),
 *     onWarning: (data) => showWarning(data),
 *     onError: (err) => showError(err),
 *   })
 *   // Later: conn.close()
 */

export interface SSECallbacks {
  onProgress?: (data: any) => void
  onChunk?: (text: string) => void
  onResult?: (data: any) => void
  onWarning?: (data: any) => void
  onError?: (message: string) => void
  onPing?: () => void
  onTimeout?: () => void
}

export interface SSEConnection {
  close: () => void
}

const DEFAULT_TIMEOUT_MS = 30000   // 30s without any event = dead

export function createSSEConnection(
  url: string,
  options: {
    body?: Record<string, any>
    headers?: Record<string, string>
    callbacks: SSECallbacks
  }
): SSEConnection {
  const { body, headers, callbacks } = options
  let lastEventTime = Date.now()
  let timeoutTimer: ReturnType<typeof setInterval> | null = null
  let aborted = false

  // Build the POST-based SSE request using fetch + ReadableStream
  const controller = new AbortController()

  async function connect() {
    try {
      // Get token from Pinia store
      const { useUserStore } = await import('@/stores/user')
      const userStore = useUserStore()

      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${userStore.token}`,
          ...headers,
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      })

      if (!res.ok) {
        const errText = await res.text()
        callbacks.onError?.(`请求失败 (${res.status}): ${errText}`)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) {
        callbacks.onError?.('无法读取响应流')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (!aborted) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''  // Keep incomplete line in buffer

        let eventType = ''
        let eventData = ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6)
          } else if (line === '' && eventType) {
            // End of event — process it
            lastEventTime = Date.now()
            processEvent(eventType, eventData)
            eventType = ''
            eventData = ''
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        callbacks.onError?.(`连接异常: ${err.message}`)
      }
    }
  }

  function processEvent(type: string, data: string) {
    switch (type) {
      case 'progress':
        try { callbacks.onProgress?.(JSON.parse(data)) } catch {}
        break
      case 'chunk':
        callbacks.onChunk?.(data)
        break
      case 'result':
        try { callbacks.onResult?.(JSON.parse(data)) } catch {}
        break
      case 'warning':
        try { callbacks.onWarning?.(JSON.parse(data)) } catch {}
        break
      case 'error':
        callbacks.onError?.(data)
        break
      case 'ping':
        callbacks.onPing?.()
        break
    }
  }

  // --- Timeout Detection ---
  timeoutTimer = setInterval(() => {
    if (Date.now() - lastEventTime > DEFAULT_TIMEOUT_MS) {
      controller.abort()
      callbacks.onTimeout?.()
      if (timeoutTimer) clearInterval(timeoutTimer)
    }
  }, 5000)

  // Start connection
  connect()

  return {
    close() {
      aborted = true
      controller.abort()
      if (timeoutTimer) clearInterval(timeoutTimer)
    },
  }
}
