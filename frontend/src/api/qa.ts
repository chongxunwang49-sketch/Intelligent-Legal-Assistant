import http, { TOKEN_KEY } from './index'

export interface QAEvent {
  type: 'meta' | 'content' | 'done' | 'error'
  data: any
}

export const qaApi = {
  ask: (data: { question: string; conversation_id?: number | null }) => http.post<any>('/qa/ask', data),
  quota: () => http.get<any>('/qa/quota'),
  conversations: (params?: any) => http.get<any>('/qa/conversations', { params }),
  messages: (conversation_id: number) => http.get<any>(`/qa/conversations/${conversation_id}/messages`),
  feedback: (data: any) => http.post<any>('/qa/feedback', data),
  deleteConversation: (id: number) => http.delete<any>(`/qa/conversations/${id}`),
  renameConversation: (id: number, title: string) => http.patch<any>(`/qa/conversations/${id}`, { title }),
  suggestions: () => http.get<any>('/qa/suggestions'),
  /** SSE：fetch 流式读取，逐事件回调 */
  askStream: (data: { question: string; conversation_id?: number | null }, onEvent: (ev: QAEvent) => void) => {
    const token = localStorage.getItem(TOKEN_KEY)
    return fetch('/api/v1/qa/ask/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(data),
    }).then(async (resp) => {
      if (resp.status === 429) {
        onEvent({ type: 'error', data: { message: '今日问答额度已用完' } })
        return
      }
      const reader = resp.body!.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          const t = line.trim()
          if (!t.startsWith('data: ')) continue
          const payload = t.slice(6).trim()
          if (payload === '[DONE]') return
          try {
            onEvent(JSON.parse(payload) as QAEvent)
          } catch {
            /* ignore partial */
          }
        }
      }
    })
  },
}
