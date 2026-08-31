import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export type ThemeMode = 'light' | 'dark';

interface ThemeContextValue {
  mode: ThemeMode;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = 'afie-dashboard-theme';

function readInitialMode(): ThemeMode {
  if (typeof window === 'undefined') return 'light';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Intentionally NOT a lazy useState(readInitialMode) initializer: this
  // dashboard is statically exported (next.config.ts's output: 'export'), so
  // the HTML shell is pre-rendered once at BUILD time with no localStorage/
  // matchMedia access ('light' baked in). Reading them in a lazy initializer
  // would make the client's first hydration pass diverge from that baked
  // HTML whenever a visitor has a saved 'dark' preference, triggering a
  // real hydration-mismatch warning. Deferring to an effect (runs strictly
  // after hydration completes) is the documented-safe pattern for this
  // exact case — the one legitimate exception to the set-state-in-effect
  // lint rule below.
  const [mode, setMode] = useState<ThemeMode>('light');

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- see comment above
    setMode(readInitialMode());
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', mode);
    try {
      window.localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      /* private-mode storage can throw — theme just won't persist */
    }
  }, [mode]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      mode,
      toggle: () => setMode((m) => (m === 'light' ? 'dark' : 'light')),
    }),
    [mode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useThemeMode(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useThemeMode must be used within ThemeProvider');
  return ctx;
}
