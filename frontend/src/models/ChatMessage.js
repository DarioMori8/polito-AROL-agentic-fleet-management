/**
 * Default shape for a chat message.
 * Used by ChatBubble and any service that produces messages.
 * @typedef {object} ChatMessage
 * @property {('user'|'assistant')} sender - Who sent the message.
 * @property {string} text - The message content.
 * @property {string} timestamp - ISO timestamp of the message.
 * @property {('sent'|'sending'|'error')} status - Message status.
 * @property {Array.<object>} citations - Citations for the message.
 * @property {object} metadata - Additional metadata.
 * @property {string} [thinkingText] - Accumulated LLM internal reasoning (thinking events). Optional.
 */
export const DEFAULT_CHAT_MESSAGE = {
    sender: 'assistant',
    text: '',
    timestamp: '',
    status: 'sent',
    citations: [],
    metadata: {},
    thinkingText: '',
};