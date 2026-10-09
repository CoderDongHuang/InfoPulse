export interface SSECallbacks {
  onProgress?: (data: any) => void
  onChunk?: (text: string) => void
  onResult?: (data: any) => void
  onWarning?: (data: any) => void
  onError?: (message: string) => void
  onPing?: () => void
  onTimeout?: () => void
  onEvent?: (type: string, data: any) => void
}

export interface SSEConnection { close: () => void }

export function createSSEConnection(
  url: string,
  options: { body?: Record<string, any>; headers?: Record<string, string>; callbacks: SSECallbacks },
): SSEConnection {
  const controller = new AbortController()
  let closed = false
  let terminal = false
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
  let lastEventAt = Date.now()

  const finish = () => {
    if (closed) return
    closed = true
    window.clearInterval(timer)
    controller.abort()
    void reader?.cancel().catch(() => {})
  }
  const fail = (message: string) => {
    if (closed) return
    terminal = true
    finish()
    options.callbacks.onError?.(message)
  }

  const dispatch = (type: string, raw: string) => {
    if (closed) return
    lastEventAt = Date.now()
    let parsed: any = raw
    try { parsed = JSON.parse(raw) } catch { /* text event */ }
    if (['result', 'error', 'done', 'message.completed', 'message.failed'].includes(type)) {
      terminal = true
      finish()
    }
    options.callbacks.onEvent?.(type, parsed)
    if (type === 'progress') options.callbacks.onProgress?.(parsed)
    else if (type === 'chunk') options.callbacks.onChunk?.(typeof parsed === 'string' ? parsed : raw)
    else if (type === 'result') options.callbacks.onResult?.(parsed)
    else if (type === 'warning') options.callbacks.onWarning?.(parsed)
    else if (type === 'error') options.callbacks.onError?.(parsed?.message || raw)
    else if (type === 'ping') options.callbacks.onPing?.()
  }

  const connect = async () => {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...options.headers },
        body: options.body ? JSON.stringify(options.body) : undefined,
        signal: controller.signal,
      })
      if (closed) { void response.body?.cancel(); return }
      if (!response.ok) {
        let message = `请求失败（${response.status}）`
        try { message = (await response.json()).detail || message } catch { /* no body */ }
        fail(message)
        return
      }
      reader = response.body?.getReader()
      if (!reader) throw new Error('浏览器无法读取流式响应')
      const decoder = new TextDecoder()
      let buffer = ''
      while (!closed) {
        const { value, done } = await reader.read()
        if (closed) break
        if (done) {
          if (!terminal) fail('Stream ended before a terminal event')
          break
        }
        buffer += decoder.decode(value, { stream: true })
        buffer = buffer.replace(/\r\n/g, '\n')
        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() || ''
        for (const block of blocks) {
          let type = 'message'
          const data: string[] = []
          for (const line of block.split('\n')) {
            if (line.startsWith('event:')) type = line.slice(6).trim()
            if (line.startsWith('data:')) data.push(line.slice(5).trim())
          }
          if (data.length) dispatch(type, data.join('\n'))
        }
      }
    } catch (error: any) {
      if (!closed) fail(`连接异常：${error.message}`)
    } finally {
      finish()
    }
  }

  const timer = window.setInterval(() => {
    if (!closed && Date.now() - lastEventAt > 70000) {
      finish()
      if (options.callbacks.onTimeout) options.callbacks.onTimeout()
      else options.callbacks.onError?.('Stream timed out')
    }
  }, 5000)
  void connect()

  return { close: finish }
}
