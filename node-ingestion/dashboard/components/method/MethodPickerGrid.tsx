import { SearchOutlined } from '@ant-design/icons';
import { Input } from 'antd';
import { useMemo, useState } from 'react';

import { MethodCard } from '@components/method/MethodCard';
import { METHOD_CATALOG, METHOD_FAMILIES } from '@constants/methods';

export function MethodPickerGrid({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return METHOD_CATALOG;
    return METHOD_CATALOG.filter(
      (m) =>
        m.displayName.toLowerCase().includes(q) ||
        m.description.toLowerCase().includes(q) ||
        m.family.toLowerCase().includes(q),
    );
  }, [query]);

  return (
    <div className="flex flex-col gap-5">
      <Input
        allowClear
        size="large"
        placeholder="Search methods (e.g. gravity, seismic, lithology)…"
        prefix={<SearchOutlined style={{ color: 'var(--text-muted)' }} />}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {METHOD_FAMILIES.map((family) => {
        const methods = filtered.filter((m) => m.family === family);
        if (!methods.length) return null;
        return (
          <div key={family}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>
              {family}
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {methods.map((m) => (
                <MethodCard key={m.id} method={m} selected={m.id === selectedId} onClick={() => onSelect(m.id)} />
              ))}
            </div>
          </div>
        );
      })}

      {filtered.length === 0 && (
        <p className="py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
          No methods match &ldquo;{query}&rdquo;.
        </p>
      )}
    </div>
  );
}
