import { EditOutlined, SaveOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { App, Button, Card, Input, Skeleton } from 'antd';
import { useState } from 'react';

import { getSiteNote, setSiteNote } from '@services/sites';

export function SiteNoteEditor({ siteId }: { siteId: string }) {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');

  const { data: note, isLoading } = useQuery({
    queryKey: ['siteNote', siteId],
    queryFn: () => getSiteNote(siteId),
  });

  // Seed the draft from the query result at the moment editing actually
  // starts (not via an effect that re-syncs on every `note` change) — the
  // draft only ever needs to reflect `note` right before the user starts typing.
  const startEditing = () => {
    setDraft(note ?? '');
    setEditing(true);
  };

  const saveMutation = useMutation({
    mutationFn: (text: string) => setSiteNote(siteId, text),
    onSuccess: () => {
      message.success('Site note saved.');
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: ['siteNote', siteId] });
    },
    onError: (err: Error) => message.error(err.message),
  });

  return (
    <Card
      size="small"
      title="Site context"
      className="shadow-card"
      style={{ borderRadius: 12 }}
      extra={
        // Gated on !isLoading too: clicking before the query resolves would
        // seed the draft from a not-yet-loaded `note`, silently discarding
        // an existing note the very first time the user edits it.
        !editing && !isLoading && (
          <Button size="small" icon={<EditOutlined />} onClick={startEditing}>
            {note ? 'Edit' : 'Add note'}
          </Button>
        )
      }
    >
      {isLoading ? (
        <Skeleton active paragraph={{ rows: 2 }} />
      ) : editing ? (
        <div className="flex flex-col gap-2">
          <Input.TextArea
            rows={3}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="e.g. Historical records mention a dense, magnetite-bearing ore body near this site."
            maxLength={4000}
          />
          <div className="flex justify-end gap-2">
            <Button size="small" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button
              size="small"
              type="primary"
              icon={<SaveOutlined />}
              loading={saveMutation.isPending}
              onClick={() => saveMutation.mutate(draft)}
            >
              Save
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-sm" style={{ color: note ? 'var(--text-secondary)' : 'var(--text-muted)' }}>
          {note || 'No site note recorded — the Interpretation Agent runs without extra context.'}
        </p>
      )}
    </Card>
  );
}
