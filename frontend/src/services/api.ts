import type { Assessment, AssessmentRequest, ChatMessage, FeedbackRequest, Parcel, PipelineStatus, ZoneRule } from '@/types'

const BASE_URL = import.meta.env.VITE_API_URL || ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || `Request failed: ${response.status}`)
  }

  return response.json()
}

export const api = {
  assess: {
    create(data: AssessmentRequest): Promise<Assessment> {
      return request('/api/assess', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    },

    get(id: string): Promise<Assessment> {
      return request(`/api/assess/${id}`)
    },
  },

  parcel: {
    search(address: string): Promise<Parcel> {
      return request(`/api/parcel/search?address=${encodeURIComponent(address)}`)
    },

    get(apn: string): Promise<Parcel> {
      return request(`/api/parcel/${apn}`)
    },
  },

  chat: {
    async stream(
      assessmentId: string,
      message: string,
      onToken: (token: string) => void,
      onDone: () => void,
    ): Promise<void> {
      const response = await fetch(`${BASE_URL}/api/chat/${assessmentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, assessment_id: assessmentId }),
      })

      if (!response.ok) {
        throw new Error('Chat request failed')
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value, { stream: true })
        const lines = text.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (data === '[DONE]') {
              onDone()
              return
            }
            try {
              const parsed = JSON.parse(data)
              if (parsed.token) onToken(parsed.token)
            } catch {
              // skip malformed chunks
            }
          }
        }
      }
      onDone()
    },

    history(assessmentId: string): Promise<ChatMessage[]> {
      return request(`/api/chat/${assessmentId}/history`)
    },
  },

  feedback: {
    submit(data: FeedbackRequest): Promise<void> {
      return request('/api/feedback', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    },
  },

  admin: {
    pipelineStatus(): Promise<PipelineStatus> {
      return request('/api/admin/pipeline/status')
    },

    rules(zoneClass?: string): Promise<ZoneRule[]> {
      const params = zoneClass ? `?zone_class=${zoneClass}` : ''
      return request(`/api/admin/rules${params}`)
    },

    triggerIngestion(): Promise<{ status: string; stats: Record<string, number> }> {
      return request('/api/admin/pipeline/trigger', { method: 'POST' })
    },
  },
}
