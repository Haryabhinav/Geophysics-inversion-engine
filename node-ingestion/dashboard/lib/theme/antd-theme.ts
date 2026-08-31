import type { ThemeConfig } from 'antd';
import resolveConfig from 'tailwindcss/resolveConfig';

import tailwindConfig from '../../tailwind.config';

const { theme } = resolveConfig(tailwindConfig);
// resolveConfig's types don't know about our custom color keys — narrow once here.
const colors = theme.colors as unknown as Record<string, Record<string, string> | string>;
const scale = (key: string) => colors[key] as Record<string, string>;

const commonToken = {
  colorSuccess: scale('success')['500'],
  colorWarning: scale('alert')['500'],
  colorError: scale('error')['500'],
  fontSizeHeading1: 30,
  fontSizeHeading2: 24,
  fontSizeHeading3: 18,
  fontSizeHeading4: 16,
  fontSizeHeading5: 15,
  fontSize: 14,
  borderRadius: 8,
  fontFamily:
    'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif',
};

export const lightTheme: ThemeConfig = {
  cssVar: true,
  hashed: false,
  token: {
    ...commonToken,
    colorPrimary: scale('brand')['500'],
    colorLink: scale('brand')['500'],
    colorTextHeading: scale('neutral')['900'],
    colorText: scale('neutral')['800'],
    colorTextSecondary: scale('neutral')['500'],
    colorBorder: scale('grayShades')['100'],
    colorBgLayout: '#F7F8FA',
    boxShadow: '0 2px 8px rgba(11,11,11,0.08)',
  },
  components: {
    Layout: { bodyBg: '#F9F9F7', headerBg: '#ffffff', siderBg: '#ffffff' },
    Menu: {
      itemActiveBg: scale('brand')['50'],
      itemSelectedBg: scale('brand')['50'],
      itemSelectedColor: scale('brand')['600'],
    },
    Card: { borderRadiusLG: 12 },
    Tag: { defaultBg: scale('neutral')['100'] },
  },
};

export const darkTheme: ThemeConfig = {
  cssVar: true,
  hashed: false,
  token: {
    ...commonToken,
    colorPrimary: scale('brand')['400'],
    colorLink: scale('brand')['400'],
    colorBgContainer: scale('dark')['900'],
    colorBgLayout: scale('dark')['950'],
    colorTextHeading: scale('dark')['100'],
    colorText: scale('dark')['200'],
    colorTextSecondary: scale('dark')['400'],
    colorBorder: scale('dark')['700'],
    boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
  },
  components: {
    Layout: {
      bodyBg: scale('dark')['950'],
      headerBg: scale('dark')['900'],
      siderBg: scale('dark')['900'],
    },
    Menu: {
      itemActiveBg: scale('dark')['800'],
      itemSelectedBg: scale('dark')['800'],
      itemSelectedColor: scale('brand')['400'],
      darkItemBg: scale('dark')['900'],
    },
    Card: { borderRadiusLG: 12, colorBgContainer: scale('dark')['900'] },
    Tag: { defaultBg: scale('dark')['800'] },
  },
};
