/**
 * The handful of design tokens that hand-styled components reference
 * directly, in ONE place.
 *
 * Two kinds live here, and the distinction matters:
 *
 * - `BRAND` / `TINT` are CSS-variable references (`var(--brand)`), so they
 *   follow the light/dark switch automatically — see styles/globals.css.
 *   Anything alpha-blending them must use `color-mix()`, not hex-suffix
 *   concatenation (`${color}33`), which only works on a literal hex string.
 * - `STATUS_COLOR` is deliberately literal hex and deliberately NOT
 *   theme-varying: it's the dataviz skill's fixed *status* palette, reserved
 *   for state (converged / max-iterations / error) and never reused as a
 *   categorical series color. Every status is always rendered with an icon
 *   and a text label too, never color alone.
 */

/** Theme-aware brand accent — resolves to brand.500 (light) / brand.400 (dark). */
export const BRAND = 'var(--brand)';

/** Alpha-blend a CSS color (variable or hex) without leaving the token system. */
export const tint = (color: string, percent: number): string =>
  `color-mix(in srgb, ${color} ${percent}%, transparent)`;

export const STATUS_COLOR = {
  good: '#0ca30c',
  warning: '#d2900f',
  serious: '#ec835a',
  critical: '#d03b3b',
  neutral: '#64748b',
} as const;

export type StatusTone = keyof typeof STATUS_COLOR;
