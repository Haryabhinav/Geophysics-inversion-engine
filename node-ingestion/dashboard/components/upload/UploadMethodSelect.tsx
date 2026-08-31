import { Select } from 'antd';

import { METHOD_CATALOG } from '@constants/methods';

/**
 * LITHOLOGY is excluded: it's a classification job (labeled train + unlabeled
 * predict feature matrices), not a time/amplitude curve, and has no
 * `/ingest/field-data`-shaped route to submit to (see `types.ts`'s
 * `BoreholeClassificationJobPayload` — a different wire shape entirely).
 * Every method here fits the same curve the parser extracts.
 */
const CURVE_FIT_METHODS = METHOD_CATALOG.filter((m) => !m.isClassification);

export function UploadMethodSelect({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (id: string) => void;
}) {
  return (
    <Select
      size="large"
      style={{ width: '100%' }}
      placeholder="Which method does this data belong to?"
      value={value ?? undefined}
      onChange={onChange}
      showSearch
      optionFilterProp="label"
      options={CURVE_FIT_METHODS.map((m) => ({
        value: m.id,
        label: `${m.displayName} — ${m.family}`,
      }))}
    />
  );
}
