interface SecretFieldProps {
  label: string;
  value: string;
  onChange(value: string): void;
  autoComplete: string;
  inputMode?: "text" | "numeric";
  maxLength?: number;
  hint?: string;
  digitsOnly?: boolean;
}

import { useState } from "react";

export function SecretField({ label, value, onChange, autoComplete, inputMode = "text", maxLength, hint, digitsOnly = false }: SecretFieldProps) {
  const [visible, setVisible] = useState(false);
  return <label>
    {label}
    <div className="password-field">
      <input
        type={visible ? "text" : "password"}
        inputMode={inputMode}
        autoComplete={autoComplete}
        maxLength={maxLength}
        value={value}
        onChange={(event) => onChange(digitsOnly ? event.target.value.replace(/\D/g, "") : event.target.value)}
        required
      />
      <button type="button" onClick={() => setVisible((current) => !current)} aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`}>
        {visible ? "Hide" : "Show"}
      </button>
    </div>
    {hint && <small className="field-hint">{hint}</small>}
  </label>;
}
