import type {
  AdminFeedback,
  Assessment,
  AssessmentRequest,
  ChatMessage,
  FeedbackRequest,
  Parcel,
  PipelineStatus,
  ZoneRule,
} from '@/types'

const BASE_URL = import.meta.env.VITE_API_URL || ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {}
  if (options?.body) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    headers,
    ...options,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || `Request failed: ${response.status}`)
  }

  if (response.status === 204) return undefined as T
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
      signal?: AbortSignal,
    ): Promise<void> {
      const response = await fetch(`${BASE_URL}/api/chat/${assessmentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, assessment_id: assessmentId }),
        signal,
      })

      if (!response.ok) {
        throw new Error('Chat request failed')
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

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

    updateRule(ruleId: string, data: Partial<ZoneRule>): Promise<ZoneRule> {
      return request(`/api/admin/rules/${ruleId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      })
    },

    feedback(rating?: string): Promise<AdminFeedback[]> {
      const params = rating ? `?rating=${encodeURIComponent(rating)}` : ''
      return request(`/api/admin/feedback${params}`)
    },

    triggerIngestion(): Promise<{ status: string; stats: Record<string, number> }> {
      return request('/api/admin/pipeline/trigger', { method: 'POST' })
    },
  },

  geojson: {
    export(assessmentId: string): Promise<any> {
      return request(`/api/assess/${assessmentId}/geojson`)
    },

    exportUrl(assessmentId: string): string {
      return `${BASE_URL}/api/assess/${assessmentId}/geojson`
    },
  },
}
