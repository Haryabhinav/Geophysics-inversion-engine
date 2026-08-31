import { RobotOutlined, SendOutlined, UserOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { App, Avatar, Button, Card, Empty, Input, Skeleton, Tag } from 'antd';
import { useState } from 'react';

import { BRAND } from '@lib/theme/tokens';
import { getChatHistory, sendChatMessage } from '@services/chat';
import type { ChatMessage } from '@types_/api';

/**
 * Chat with a site's own run/interpretation history — scoped per-site, same
 * as Joint Interpretation and Site Reports, since a site's run history
 * (a handful to a few dozen results) is small enough for the agent to read
 * directly with no retrieval step (see python-agent's app/agent/chat_agent.py).
 */
export function SiteChatPanel({ siteId }: { siteId: string }) {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['chatHistory', siteId],
    queryFn: () => getChatHistory(siteId),
  });

  const askMutation = useMutation({
    mutationFn: (q: string) => sendChatMessage(siteId, q),
    onSuccess: () => {
      setQuestion('');
      void queryClient.invalidateQueries({ queryKey: ['chatHistory', siteId] });
    },
    onError: (err: Error) => message.error(err.message),
  });

  const submit = () => {
    const trimmed = question.trim();
    if (!trimmed || askMutation.isPending) return;
    askMutation.mutate(trimmed);
  };

  const messages: ChatMessage[] = data?.messages ?? [];

  return (
    <Card size="small" title="Ask about this site" className="shadow-card" style={{ borderRadius: 12 }}>
      <div className="flex flex-col gap-3">
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 3 }} />
        ) : messages.length === 0 ? (
          <Empty
            description="Ask a question about this site's runs — e.g. 'Why didn't the TDEM run converge?'"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : (
          <div className="flex max-h-[420px] flex-col gap-3 overflow-y-auto pr-1">
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-2 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <Avatar
                  size="small"
                  icon={m.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                  style={{ background: m.role === 'user' ? 'var(--text-muted)' : BRAND }}
                />
                <div
                  className="max-w-[80%] rounded-lg px-3 py-2 text-sm"
                  style={{
                    background: m.role === 'user' ? 'var(--page-bg)' : 'var(--card-bg)',
                    border: '1px solid var(--border-hairline)',
                  }}
                >
                  <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{m.content}</p>
                  {m.citedRuns.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {m.citedRuns.map((jobId) => (
                        <Tag key={jobId} style={{ fontSize: 11 }}>
                          {jobId}
                        </Tag>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <Input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onPressEnter={submit}
            placeholder="Ask a question about this site's data…"
            maxLength={2000}
            disabled={askMutation.isPending}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={askMutation.isPending}
            disabled={!question.trim()}
            onClick={submit}
          />
        </div>
      </div>
    </Card>
  );
}
