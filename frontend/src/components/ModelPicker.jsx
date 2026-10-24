/** Choose the policy that really scores transactions; report inspection is separate. */
export default function ModelPicker({
  choices = [],
  value,
  onChange,
  disabled = false,
  label = "Prediction model",
}) {
  // Older manifests still support champion scoring without a candidate menu.
  const options = choices.length
    ? choices
    : [{ id: "champion", label: "Current champion", available: true }];
  const selected = options.find((item) => item.id === value);
  return (
    <label>
      {label}
      <select
        aria-label={label}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {/* Keep unavailable policies visible instead of silently hiding them. */}
        {options.map((choice) => (
          <option
            key={choice.id}
            value={choice.id}
            disabled={!choice.available}
          >
            {choice.label}
            {choice.available ? "" : " · unavailable"}
          </option>
        ))}
      </select>
      {selected?.reason && <small className="muted">{selected.reason}</small>}
    </label>
  );
}
