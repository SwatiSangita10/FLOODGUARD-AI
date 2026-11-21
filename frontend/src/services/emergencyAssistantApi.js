const API_BASE = (import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
export const MAX_ASSISTANT_MESSAGE_LENGTH = 1000

function responseError(body, status) {
  if (typeof body?.detail === 'string') return body.detail
  if (Array.isArray(body?.message)) return body.message.join(' ')
  if (typeof body?.message === 'string') return body.message
  return `Emergency assistant service returned HTTP ${status}.`
}

export async function askEmergencyAssistant(message, { history = [], fetchImpl = fetch } = {}) {
  const trimmedMessage = message.trim()
  if (!trimmedMessage) throw new Error('Enter a question before sending.')
  if (trimmedMessage.length > MAX_ASSISTANT_MESSAGE_LENGTH) {
    throw new Error(`Keep your question to ${MAX_ASSISTANT_MESSAGE_LENGTH} characters or fewer.`)
  }
  const recentHistory = history.slice(-10).map(({ role, content }) => ({ role, content }))

  let response
  try {
    response = await fetchImpl(`${API_BASE}/api/assistant/emergency/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: trimmedMessage, history: recentHistory }),
    })
  } catch (error) {
    throw new Error('Cannot connect to the FLOODGUARD emergency assistant service.')
  }

  let body
  try {
    body = await response.json()
  } catch (error) {
    body = null
  }
  if (!response.ok) throw new Error(responseError(body, response.status))
  if (typeof body?.answer !== 'string' || !body.answer.trim()) {
    throw new Error('The emergency assistant returned an invalid response. Please try again.')
  }
  return body
}
