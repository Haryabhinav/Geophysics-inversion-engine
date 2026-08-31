import type { Config } from 'tailwindcss';

// An original design-token set for this dashboard (structured the same way
// a typical AntD+Tailwind app organizes tokens, but with independently
// chosen values — see JOURNEY.md for why).
const config: Config = {
  darkMode: ['selector', '[data-theme="dark"]'],
  corePlugins: {
    // AntD ships its own base styles; Tailwind's preflight would fight them.
    preflight: false,
  },
  content: ['./pages/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        neutral: {
          50: '#F8FAFC',
          100: '#F1F5F9',
          200: '#E2E8F0',
          300: '#CBD5E1',
          400: '#94A3B8',
          500: '#64748B',
          600: '#475569',
          700: '#334155',
          800: '#1E293B',
          900: '#0F172A',
        },
        dark: {
          50: '#F6F6F7',
          100: '#E9E9EC',
          200: '#D3D3D9',
          300: '#AEAEB8',
          400: '#84848F',
          500: '#5C5C68',
          600: '#42424C',
          700: '#2E2E36',
          800: '#1C1C21',
          900: '#101014',
          950: '#08080A',
        },
        brand: {
          50: '#EEF3FF',
          100: '#DCE7FF',
          200: '#B9CFFF',
          300: '#8FB0FF',
          400: '#5C87FA',
          500: '#3563E9',
          600: '#2748B8',
          700: '#1D3690',
          800: '#152867',
          900: '#0C1740',
        },
        success: {
          50: '#EEFBF3',
          100: '#D6F5E1',
          200: '#AEEBC7',
          300: '#7ADCA8',
          400: '#3FC183',
          500: '#1FA366',
          600: '#158253',
          700: '#0F6641',
          800: '#0B4C31',
          900: '#073323',
        },
        alert: {
          50: '#FFF8EB',
          100: '#FEECC7',
          200: '#FDDA92',
          300: '#FBC158',
          400: '#F7A62E',
          500: '#EF8B14',
          600: '#C96D0D',
          700: '#9F520C',
          800: '#753C0C',
          900: '#4A2508',
        },
        error: {
          50: '#FEF1F1',
          100: '#FDDCDC',
          200: '#FAB6B6',
          300: '#F58686',
          400: '#EE5555',
          500: '#DE2E2E',
          600: '#B31F1F',
          700: '#8C1919',
          800: '#671414',
          900: '#3F0D0D',
        },
        grayShades: {
          50: '#F4F4F5',
          100: '#E5E5E7',
          200: '#D1D1D6',
          300: '#B0B0B8',
          400: '#5C5C68',
          500: '#48484F',
          600: '#3A3A40',
          700: '#2E2E33',
          800: '#212124',
          900: '#141416',
        },
        // Chart-only slots (dataviz skill's validated categorical/status
        // palettes) — kept separate from the brand tokens above so a chart
        // series is never confused with a UI/status color.
        viz: {
          series1: '#2a78d6',
          series2: '#eb6834',
          series3: '#1baf7a',
          series4: '#eda100',
          series5: '#e87ba4',
          series6: '#008300',
          series7: '#4a3aa7',
          series8: '#e34948',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'sans-serif',
        ],
      },
      borderRadius: {
        card: '12px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(11,11,11,0.04), 0 1px 8px rgba(11,11,11,0.04)',
      },
    },
  },
  plugins: [],
};

export default config;
