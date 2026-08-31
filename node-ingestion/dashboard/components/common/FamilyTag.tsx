import { FAMILY_COLOR, type MethodFamily } from '@constants/methods';
import { tint } from '@lib/theme/tokens';

export function FamilyTag({ family }: { family: MethodFamily }) {
  const color = FAMILY_COLOR[family];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ background: tint(color, 10), color }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {family}
    </span>
  );
}
