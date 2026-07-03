import type { DatasetMeta } from "../data/datasets";

interface Props {
  datasets: DatasetMeta[];
  value: string;
  onChange: (file: string) => void;
}

/** Dropdown for choosing which catalogue CSV to display. Renders nothing when
 *  only a single dataset is available (no choice to make). */
export default function DatasetPicker({ datasets, value, onChange }: Props) {
  if (datasets.length < 2) return null;

  const current = datasets.find((d) => d.file === value);

  return (
    <label className="dataset-picker" title={current?.description ?? undefined}>
      <span className="dataset-picker__label">Dataset</span>
      <select
        className="dataset-picker__select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Dataset"
      >
        {datasets.map((d) => (
          <option key={d.file} value={d.file} title={d.description ?? undefined}>
            {d.label}
          </option>
        ))}
      </select>
    </label>
  );
}
