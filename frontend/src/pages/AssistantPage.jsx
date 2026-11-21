import { useEffect, useReducer, useRef, useState } from 'react'
import { AlertTriangle, Bot, LifeBuoy, Send, ShieldCheck } from 'lucide-react'
import { DemoNotice, PageHeader, Panel, Pill } from '../components/UI'
import { askEmergencyAssistant, MAX_ASSISTANT_MESSAGE_LENGTH } from '../services/emergencyAssistantApi'
import { assistantChatReducer, ASSISTANT_SUGGESTIONS, initialAssistantState } from '../services/assistantChat'

export default function AssistantPage() {
  const [question, setQuestion] = useState('')
  const [chat, dispatch] = useReducer(assistantChatReducer, initialAssistantState)
  const sendingRef = useRef(false)
  const nextMessageId = useRef(0)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [chat.messages, chat.status])

  async function sendQuestion(text) {
    const message = text.trim()
    if (!message || sendingRef.current) return

    sendingRef.current = true
    dispatch({
      type: 'send',
      message: { id: ++nextMessageId.current, role: 'user', content: message },
    })
    setQuestion('')
    try {
      const result = await askEmergencyAssistant(message, {
        history: chat.messages.slice(-10).map(({ role, content }) => ({ role, content })),
      })
      dispatch({
        type: 'reply',
        message: {
          id: ++nextMessageId.current,
          role: 'assistant',
          content: result.answer,
          mode: result.mode,
          fallbackReason: result.fallback_reason,
        },
      })
    } catch (error) {
      setQuestion(message)
      dispatch({ type: 'failure', error: error.message })
    } finally {
      sendingRef.current = false
    }
  }

  function submitQuestion(event) {
    event.preventDefault()
    void sendQuestion(question)
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="EMERGENCY RELIEF COMPANION" title="Emergency assistant" description="Practical flood-safety guidance for preparedness, emergencies, and recovery." action={<Pill tone="amber">GEMINI WHEN CONFIGURED</Pill>} />
      <DemoNotice>INFORMATIONAL GUIDANCE ONLY · The latest real Gemini request returned HTTP 503 UNAVAILABLE; current availability is unverified. Curated fallback guidance remains available. Gemini responses are AI-generated and may be inaccurate; neither response is an official instruction or live alert. This assistant cannot see live flood conditions or determine your exact danger level. In immediate danger, contact your local emergency services and follow official local authority guidance.</DemoNotice>
      <div className="assistant-layout">
        <Panel className="assistant-chat-panel" title="Flood safety chat" subtitle="Recent messages may be sent to Gemini for context when configured; this app does not store chat history." action={<span className="assistant-avatar"><Bot size={18} /></span>}>
          <div className="assistant-message-list" role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions">
            {chat.messages.length === 0 && <p className="assistant-empty-state">Ask a flood-safety question or choose a suggestion below. No previous conversation is preloaded.</p>}
            {chat.messages.map((message) => (
              <div className={`assistant-message assistant-message-${message.role}`} key={message.id}>
                <span className="assistant-message-label">{message.role === 'user' ? 'You' : message.mode === 'gemini' ? 'Gemini · AI-generated' : `Curated fallback${message.fallbackReason ? ' · Gemini unavailable' : ''}`}</span>
                <p>{message.content}</p>
              </div>
            ))}
            {chat.status === 'loading' && <div className="assistant-loading" role="status"><span className="assistant-loading-dot" />Preparing flood-safety guidance…</div>}
            <div ref={messagesEndRef} />
          </div>
          <div className="quick-topic-heading"><span>Suggested questions</span><Pill tone="neutral">FLOOD SAFETY</Pill></div>
          <div className="quick-topics">{ASSISTANT_SUGGESTIONS.map((topic) => <button key={topic} disabled={chat.status === 'loading'} onClick={() => void sendQuestion(topic)}>{topic}</button>)}</div>
          {chat.status === 'error' && <div className="assistant-feedback" role="alert"><AlertTriangle size={16} />{chat.error} Your question remains above; you can try again.</div>}
          <form className="assistant-composer" onSubmit={submitQuestion}>
            <label htmlFor="assistant-question" className="sr-only">Ask the emergency assistant</label>
            <input id="assistant-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={MAX_ASSISTANT_MESSAGE_LENGTH} placeholder="Ask a flood safety question…" disabled={chat.status === 'loading'} />
            <button className="primary-button" type="submit" disabled={!question.trim() || chat.status === 'loading'}><Send size={15} /><span>{chat.status === 'loading' ? 'Sending' : 'Send'}</span></button>
          </form>
          <p className="assistant-composer-note">Maximum {MAX_ASSISTANT_MESSAGE_LENGTH} characters. Press Enter to send. Messages are not stored.</p>
        </Panel>
        <div className="assistant-side-stack">
          <Panel className="assistant-info-panel" title="Safety guidance" subtitle="General advice, not a live incident feed">
            <div className="assistant-capability"><span><ShieldCheck size={17} /></span><div><strong>Move to higher ground when safe</strong><small>Follow evacuation instructions from local authorities.</small></div></div>
            <div className="assistant-capability"><span><ShieldCheck size={17} /></span><div><strong>Stay out of floodwater</strong><small>Do not walk, swim, or drive through it.</small></div></div>
            <div className="assistant-capability"><span><ShieldCheck size={17} /></span><div><strong>Use official sources</strong><small>This guide cannot check your location or conditions.</small></div></div>
          </Panel>
          <div className="urgent-help-card"><div className="urgent-help-icon"><LifeBuoy size={19} /></div><div><Pill tone="red">IMMEDIATE DANGER?</Pill><h3>Contact your local emergency services</h3><p>Do not wait for this assistant. Follow official local authority instructions. No rescue request is sent from this page.</p></div></div>
        </div>
      </div>
    </div>
  )
}
