export const ASSISTANT_SUGGESTIONS = [
  'What should I do during a flood?',
  'How can I protect my family?',
  'What should I pack in an emergency kit?',
  'What should I do if water enters my house?',
  'How can I help someone trapped by floodwater?',
]

export const initialAssistantState = {
  messages: [],
  status: 'idle',
  error: '',
}

export function assistantChatReducer(state, action) {
  switch (action.type) {
    case 'send':
      return {
        ...state,
        messages: [...state.messages, action.message],
        status: 'loading',
        error: '',
      }
    case 'reply':
      return {
        ...state,
        messages: [...state.messages, action.message],
        status: 'idle',
        error: '',
      }
    case 'failure':
      return { ...state, status: 'error', error: action.error }
    default:
      return state
  }
}
