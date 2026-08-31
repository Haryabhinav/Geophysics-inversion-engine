import {
  AppstoreOutlined,
  ClusterOutlined,
  HistoryOutlined,
  MoonOutlined,
  PlayCircleOutlined,
  SunOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { Badge, Layout, Menu, Tooltip, Typography } from 'antd';
import { useRouter } from 'next/router';
import Link from 'next/link';
import type { ReactNode } from 'react';

import { useThemeMode } from '@lib/theme/ThemeContext';
import { useLiveStore } from '@store/useLiveStore';

const { Header, Sider, Content } = Layout;

const NAV_ITEMS = [
  { key: '/', label: 'Overview', icon: <AppstoreOutlined /> },
  { key: '/run', label: 'Run a Method', icon: <PlayCircleOutlined /> },
  { key: '/upload', label: 'Upload Data', icon: <UploadOutlined /> },
  { key: '/history', label: 'History', icon: <HistoryOutlined /> },
  { key: '/sites', label: 'Site Reports', icon: <ClusterOutlined /> },
];

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { mode, toggle } = useThemeMode();
  const connected = useLiveStore((s) => s.connected);

  // Exact-segment match, not a raw `startsWith`: '/run' must not also claim
  // '/runs' (the run-DETAIL page, deliberately not its own nav item — see
  // DESIGN.md 14.4 for why it isn't named '/results').
  const selectedKey =
    NAV_ITEMS.find((item) =>
      item.key === '/' ? router.pathname === '/' : router.pathname === item.key || router.pathname.startsWith(`${item.key}/`),
    )?.key ?? '/';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={232} theme={mode === 'dark' ? 'dark' : 'light'} breakpoint="lg" collapsedWidth={0}>
        <div className="flex items-center gap-2 px-5 py-5">
          <span className="text-2xl leading-none">🛰️</span>
          <div className="leading-tight">
            <div className="font-bold text-[15px] tracking-tight" style={{ color: 'var(--text-primary)' }}>
              AFIE
            </div>
            <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
              Multi-Physics Inversion
            </div>
          </div>
        </div>
        <Menu
          mode="inline"
          theme={mode === 'dark' ? 'dark' : 'light'}
          selectedKeys={[selectedKey]}
          items={NAV_ITEMS.map((item) => ({
            key: item.key,
            icon: item.icon,
            label: <Link href={item.key}>{item.label}</Link>,
          }))}
          style={{ borderInlineEnd: 'none' }}
        />
      </Sider>

      <Layout>
        <Header
          className="flex items-center justify-between border-b"
          style={{ borderColor: 'var(--border-hairline)', background: 'var(--card-bg)', paddingInline: 24 }}
        >
          <Typography.Text strong style={{ fontSize: 15 }}>
            {NAV_ITEMS.find((item) => item.key === selectedKey)?.label ?? 'Dashboard'}
          </Typography.Text>

          <div className="flex items-center gap-4">
            <Tooltip title={connected ? 'Live updates connected' : 'Reconnecting…'}>
              <span className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
                <Badge status={connected ? 'success' : 'error'} />
                {connected ? 'Live' : 'Offline'}
              </span>
            </Tooltip>
            <Tooltip title={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
              <button
                onClick={toggle}
                aria-label="Toggle theme"
                className="flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:opacity-80"
                style={{ background: 'var(--page-bg)', color: 'var(--text-secondary)' }}
              >
                {mode === 'dark' ? <SunOutlined /> : <MoonOutlined />}
              </button>
            </Tooltip>
          </div>
        </Header>

        <Content style={{ background: 'var(--page-bg)' }}>
          <div className="mx-auto w-full max-w-[1240px] px-6 py-8">{children}</div>
        </Content>
      </Layout>
    </Layout>
  );
}
