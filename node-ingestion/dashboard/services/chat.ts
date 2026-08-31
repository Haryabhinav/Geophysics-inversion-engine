import { http } from '@lib/http';
import type { ChatAnswer, ChatHistoryResponse } from '@types_/api';

/**
 * Site Chat Agent: ask a natural-language question about one site's own run
 * and interpretation history (`POST /sites/:siteId/chat` ->
 * python-agent's `POST /chat/query`). Node persists both the question and
 * the answer, so `getChatHistory` replays the full transcript on load.
 */
export async function getChatHistory(siteId: string): Promise<ChatHistoryResponse> {
  const { data } = await http.get<ChatHistoryResponse>(`/sites/${encodeURIComponent(siteId)}/chat`);
  return data;
}

export async function sendChatMessage(siteId: string, question: string): Promise<ChatAnswer> {
  const { data } = await http.post<ChatAnswer>(`/sites/${encodeURIComponent(siteId)}/chat`, { question });
  return data;
}
