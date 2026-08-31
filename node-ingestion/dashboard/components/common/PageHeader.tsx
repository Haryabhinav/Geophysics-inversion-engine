import { Typography } from 'antd';
import Head from 'next/head';
import type { ReactNode } from 'react';

/** Suffix so a browser tab / bookmark identifies the app, not just the page. */
const APP_NAME = 'AFIE';

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      {/* Rendered here rather than per page so the document title can never
          drift from the heading the user is actually looking at. Next merges
          this with _app's default, page-level winning. */}
      <Head>
        <title>{`${title} · ${APP_NAME}`}</title>
      </Head>
      <div>
        <Typography.Title level={3} style={{ margin: 0 }}>
          {title}
        </Typography.Title>
        {description && (
          <Typography.Text style={{ color: 'var(--text-secondary)' }}>{description}</Typography.Text>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
