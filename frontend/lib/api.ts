/* API Client for NOVA Backend */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// --- Health ---
export const getHealth = () => request<{ status: string; app_name: string }>('/api/health');
export const getStatus = () => request<{
  status: string;
  ollama_available: boolean;
  ollama_model: string;
  stt_available: boolean;
  tts_available: boolean;
  database_ok: boolean;
  vector_db_ok: boolean;
}>('/api/status');

// --- Chat ---
export interface ChatResponse {
  message_id: string;
  conversation_id: string;
  response: string;
  nlp?: { intent: string; confidence: number; entities: Record<string, any> };
  tool?: { tool_name: string; success: boolean; result: any; error?: string };
  latency_ms: number;
  llm_duration_ms: number;
  agent_state?: string;  // AgentState value: 'idle' | 'thinking' | 'executing' | 'responding' | 'error'
}

export interface StreamEvent {
  type: 'init' | 'state' | 'token' | 'done' | 'error';
  token?: string;
  agent_state?: string;
  conversation_id?: string;
  message_id?: string;
  response?: string;
  latency_ms?: number;
  error?: string;
  tool_name?: string;
  tool?: any;
  intent?: string;
  plan?: any;
}

export const sendMessage = (message: string, conversation_id?: string) =>
  request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message, conversation_id }),
  });

export async function sendMessageStream(
  message: string,
  conversationId?: string,
  onEvent?: (event: StreamEvent) => void,
): Promise<ChatResponse> {
  const url = `${API_BASE}/api/chat/stream`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });

  if (!res.ok || !res.body) {
    const errorText = await res.text().catch(() => res.statusText);
    throw new Error(errorText || `Stream request failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let fullResponse = '';
  let finalMessageId = '';
  let finalConvId = conversationId || '';
  let finalLatency = 0;
  let finalToolName: string | undefined;
  let finalTool: any;
  let finalIntent: string | undefined;
  let finalPlan: any;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n\n');
    buffer = lines.pop() || '';

    for (const block of lines) {
      const match = block.match(/^data:\s*(.+)$/m);
      if (match) {
        try {
          const event: StreamEvent = JSON.parse(match[1]);
          if (event.type === 'token' && event.token) {
            fullResponse += event.token;
          }
          if (event.conversation_id) {
            finalConvId = event.conversation_id;
          }
          if (event.message_id) {
            finalMessageId = event.message_id;
          }
          if (event.latency_ms) {
            finalLatency = event.latency_ms;
          }
          if (event.tool_name) {
            finalToolName = event.tool_name;
          }
          if (event.tool) {
            finalTool = event.tool;
          }
          if (event.intent) {
            finalIntent = event.intent;
          }
          if (event.plan) {
            finalPlan = event.plan;
          }
          onEvent?.(event);
        } catch {
          // ignore partial json chunk
        }
      }
    }
  }

  return {
    message_id: finalMessageId,
    conversation_id: finalConvId,
    response: fullResponse,
    latency_ms: finalLatency,
    llm_duration_ms: 0,
    agent_state: 'idle',
    tool: finalTool || (finalToolName ? { tool_name: finalToolName, success: true, result: null } : undefined),
    nlp: finalIntent ? { intent: finalIntent, confidence: 1, entities: {} } : undefined,
  };
}

// --- Conversations ---
export interface Conversation { id: string; title: string; created_at: string; updated_at: string; message_count: number; }
export interface Message { id: string; role: string; content: string; intent?: string; tool_name?: string; is_voice: boolean; latency_ms?: number; created_at: string; }
export interface ConversationDetail extends Conversation { messages: Message[]; }

export const getConversations = () => request<Conversation[]>('/api/conversations');
export const getConversation = (id: string) => request<ConversationDetail>(`/api/conversations/${id}`);
export const createConversation = (title?: string) => request<Conversation>('/api/conversations', { method: 'POST', body: JSON.stringify({ title: title || 'New Conversation' }) });
export const deleteConversation = (id: string) => request<void>(`/api/conversations/${id}`, { method: 'DELETE' });

// --- Documents ---
export interface Document { id: string; filename: string; original_filename: string; file_extension: string; file_size_bytes: number; chunk_count: number; status: string; created_at: string; }

export const getDocuments = () => request<Document[]>('/api/documents');
export const deleteDocument = (id: string) => request<void>(`/api/documents/${id}`, { method: 'DELETE' });
export const reindexDocument = (id: string) => request<void>(`/api/documents/${id}/reindex`, { method: 'POST' });

export async function uploadDocument(file: File): Promise<{ id: string; status: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/api/documents/upload`, { method: 'POST', body: formData });
  if (!res.ok) throw new Error('Upload failed');
  return res.json();
}

// --- Notes ---
export interface Note { id: string; title: string; content: string; tags?: string; created_at: string; updated_at: string; }
export const getNotes = () => request<Note[]>('/api/notes');
export const createNote = (title: string, content: string = '') => request<Note>('/api/notes', { method: 'POST', body: JSON.stringify({ title, content }) });
export const updateNote = (id: string, data: { title?: string; content?: string }) => request<Note>(`/api/notes/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteNote = (id: string) => request<void>(`/api/notes/${id}`, { method: 'DELETE' });

// --- Reminders ---
export interface Reminder { id: string; title: string; description?: string; scheduled_at?: string; status: string; created_at: string; }
export const getReminders = () => request<Reminder[]>('/api/reminders');
export const createReminder = (title: string, scheduled_at?: string) => request<Reminder>('/api/reminders', { method: 'POST', body: JSON.stringify({ title, scheduled_at }) });
export const updateReminder = (id: string, data: Partial<Reminder>) => request<Reminder>(`/api/reminders/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteReminder = (id: string) => request<void>(`/api/reminders/${id}`, { method: 'DELETE' });

// --- Memory ---
export interface MemoryItem { id: string; content: string; category: string; source: string; created_at: string; }
export const getMemories = () => request<MemoryItem[]>('/api/memory');
export const createMemory = (content: string, category: string = 'general') => request<void>('/api/memory', { method: 'POST', body: JSON.stringify({ content, category }) });
export const deleteMemory = (id: string) => request<void>(`/api/memory/${id}`, { method: 'DELETE' });

// --- Analytics ---
export interface Analytics {
  total_conversations: number; total_messages: number; voice_requests: number;
  avg_response_latency_ms: number; avg_stt_duration_ms: number; avg_llm_duration_ms: number;
  avg_tts_duration_ms: number; rag_searches: number; tool_executions: number; total_errors: number;
  intent_distribution: Record<string, number>; tool_usage: Record<string, number>;
  messages_per_day: { date: string; count: number }[];
}
export const getAnalytics = () => request<Analytics>('/api/analytics');

// --- Voice ---
export async function transcribeAudio(audioBlob: Blob): Promise<{ text: string; duration_ms: number }> {
  const formData = new FormData();
  formData.append('file', audioBlob, 'recording.webm');
  const res = await fetch(`${API_BASE}/api/voice/transcribe`, { method: 'POST', body: formData });
  if (!res.ok) throw new Error('Transcription failed');
  return res.json();
}

export async function voiceRespond(audioBlob: Blob, conversationId?: string): Promise<{
  message_id?: string;
  conversation_id?: string;
  transcript: string;
  response: string;
  agent_state?: string;
  stt_duration_ms?: number;
  llm_duration_ms?: number;
  tts_duration_ms?: number;
  total_latency_ms?: number;
  has_audio?: boolean;
}> {
  const formData = new FormData();
  formData.append('file', audioBlob, 'recording.webm');
  if (conversationId) formData.append('conversation_id', conversationId);
  const res = await fetch(`${API_BASE}/api/voice/respond`, { method: 'POST', body: formData });
  if (!res.ok) throw new Error('Voice response failed');
  return res.json();
}

export async function speakText(text: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/voice/speak`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error('Speech synthesis failed');
  return res.blob();
}

/** Check if wake word is present in a short audio clip. Never throws. */
export async function wakeCheck(audioBlob: Blob): Promise<{ detected: boolean; transcript: string }> {
  try {
    const formData = new FormData();
    formData.append('file', audioBlob, 'wake.webm');
    const res = await fetch(`${API_BASE}/api/voice/wake-check`, { method: 'POST', body: formData });
    if (!res.ok) return { detected: false, transcript: '' };
    return res.json();
  } catch {
    return { detected: false, transcript: '' };
  }
}

