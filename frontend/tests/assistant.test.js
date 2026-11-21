import assert from 'node:assert/strict'
import test from 'node:test'
import {
  askEmergencyAssistant,
  MAX_ASSISTANT_MESSAGE_LENGTH,
} from '../src/services/emergencyAssistantApi.js'
import {
  assistantChatReducer,
  ASSISTANT_SUGGESTIONS,
  initialAssistantState,
} from '../src/services/assistantChat.js'

test('emergency assistant client sends the trimmed question and recent history to Django', async () => {
  let requestUrl = ''
  let requestOptions
  const result = await askEmergencyAssistant(
    '  What should I do during a flood?  ',
    {
      history: [{ role: 'assistant', content: 'Follow official instructions.' }],
      fetchImpl: async (url, options) => {
        requestUrl = url
        requestOptions = options
        return {
          ok: true,
          json: async () => ({
            answer: 'Move to higher ground when safe.',
            mode: 'curated_fallback',
            fallback_reason: 'missing_api_key',
          }),
        }
      },
    },
  )

  assert.match(requestUrl, /^http:\/\/127\.0\.0\.1:8000\/api\/assistant\/emergency\/$/)
  assert.equal(requestOptions.method, 'POST')
  assert.equal(requestOptions.headers['Content-Type'], 'application/json')
  assert.deepEqual(JSON.parse(requestOptions.body), {
    message: 'What should I do during a flood?',
    history: [{ role: 'assistant', content: 'Follow official instructions.' }],
  })
  assert.equal(result.mode, 'curated_fallback')
})

test('emergency assistant client preserves Gemini response source and caps context', async () => {
  const history = Array.from({ length: 12 }, (_, index) => ({
    role: index % 2 === 0 ? 'user' : 'assistant',
    content: `Turn ${index}`,
  }))
  let requestBody
  const result = await askEmergencyAssistant('What now?', {
    history,
    fetchImpl: async (_url, options) => {
      requestBody = JSON.parse(options.body)
      return {
        ok: true,
        json: async () => ({ answer: 'Follow official instructions.', mode: 'gemini' }),
      }
    },
  })

  assert.equal(result.mode, 'gemini')
  assert.equal(requestBody.history.length, 10)
  assert.equal(requestBody.history[0].content, 'Turn 2')
})

test('emergency assistant client rejects empty and overlong messages before sending', async () => {
  let requestCount = 0
  const fetchImpl = async () => {
    requestCount += 1
  }
  await assert.rejects(askEmergencyAssistant('  ', { fetchImpl }), /Enter a question/)
  await assert.rejects(
    askEmergencyAssistant('x'.repeat(MAX_ASSISTANT_MESSAGE_LENGTH + 1), { fetchImpl }),
    /1000 characters/,
  )
  assert.equal(requestCount, 0)
})

test('emergency assistant API errors and connection failures are surfaced', async () => {
  await assert.rejects(
    askEmergencyAssistant('What should I do?', {
      fetchImpl: async () => ({
        ok: false,
        status: 400,
        json: async () => ({ message: ['Message is too long.'] }),
      }),
    }),
    /Message is too long/,
  )
  await assert.rejects(
    askEmergencyAssistant('What should I do?', {
      fetchImpl: async () => { throw new Error('offline') },
    }),
    /Cannot connect to the FLOODGUARD emergency assistant service/,
  )
})

test('chat reducer represents sending, loading, reply, and error states', () => {
  const userMessage = { id: 1, role: 'user', content: 'What should I do during a flood?' }
  const loading = assistantChatReducer(initialAssistantState, { type: 'send', message: userMessage })
  assert.equal(loading.status, 'loading')
  assert.deepEqual(loading.messages, [userMessage])

  const assistantMessage = {
    id: 2,
    role: 'assistant',
    content: 'Move to higher ground when safe.',
    mode: 'gemini',
  }
  const replied = assistantChatReducer(loading, { type: 'reply', message: assistantMessage })
  assert.equal(replied.status, 'idle')
  assert.deepEqual(replied.messages, [userMessage, assistantMessage])

  const failed = assistantChatReducer(loading, { type: 'failure', error: 'Service unavailable.' })
  assert.equal(failed.status, 'error')
  assert.equal(failed.error, 'Service unavailable.')
  assert.deepEqual(failed.messages, [userMessage])
})

test('suggested questions cover common emergency topics without seeding fake history', () => {
  assert.equal(initialAssistantState.messages.length, 0)
  assert.equal(ASSISTANT_SUGGESTIONS.length, 5)
  assert.ok(ASSISTANT_SUGGESTIONS.some((question) => question.includes('emergency kit')))
  assert.ok(ASSISTANT_SUGGESTIONS.some((question) => question.includes('trapped by floodwater')))
})
