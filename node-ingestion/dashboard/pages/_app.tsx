import 'antd/dist/reset.css';
import '../styles/globals.css';

import { QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider, App as AntApp } from 'antd';
import type { AppProps } from 'next/app';
import Head from 'next/head';

import { AppShell } from '@components/layout/AppShell';
import { useLiveEvents } from '@lib/useLiveEvents';
import { queryClient } from '@lib/react-query';
import { darkTheme, lightTheme } from '@lib/theme/antd-theme';
import { ThemeProvider, useThemeMode } from '@lib/theme/ThemeContext';

function Shell({ Component, pageProps }: AppProps) {
  const { mode } = useThemeMode();
  useLiveEvents();

  return (
    <ConfigProvider theme={mode === 'dark' ? darkTheme : lightTheme}>
      <Head>
        {/* Fallback for any page that doesn't render a PageHeader (e.g. 404). */}
        <title>AFIE — Multi-Physics Inversion</title>
        <meta
          name="description"
          content="Agentic Field-Data Inversion Engine — 13 geophysical methods, one agentic inversion and interpretation pipeline."
        />
      </Head>
      <AntApp>
        <AppShell>
          <Component {...pageProps} />
        </AppShell>
      </AntApp>
    </ConfigProvider>
  );
}

export default function App(props: AppProps) {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <Shell {...props} />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
