import { useEffect, useRef, useState } from "react";

/** Preserve separators while typing; the canonical parent value remains parsed. */
export function ScenarioSeparatedInput({ label, values, separator, disabled, limit, onChange }: {
  label: string; values: string[]; separator: "\n" | ","; disabled: boolean; limit: number; onChange: (values: string[]) => void;
}) {
  const text = values.join(separator === "," ? ", " : "\n");
  const [raw, setRaw] = useState(text);
  const focused = useRef(false);
  useEffect(() => { if (!focused.current) setRaw(text); }, [text]);
  return <label className="block">{label}<textarea disabled={disabled} className="field-base min-h-20 w-full" value={raw}
    onFocus={() => { focused.current = true; }}
    onBlur={() => { focused.current = false; setRaw(text); }}
    onChange={event => { setRaw(event.target.value); onChange(event.target.value.split(separator).map(item => item.trim()).filter(Boolean).slice(0, limit)); }}
  /></label>;
}
