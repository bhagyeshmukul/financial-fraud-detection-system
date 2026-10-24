/** Edit one profile's raw input contract; features are derived on the server. */
// Generate the original anonymized V1..V28 inputs; their business meanings are unpublished.
const cardFields = [
  "Time",
  "Amount",
  ...Array.from({ length: 28 }, (_, i) => `V${i + 1}`),
];
/** Render the readable payment form or the original 30-input advanced card form. */
export default function TransactionForm({
  profile,
  form,
  setForm,
  onSubmit,
  loading,
}) {
  const fields =
    profile === "banksim"
      ? ["step", "customer", "merchant", "category", "amount"]
      : cardFields;
  return (
    <form className="card" onSubmit={onSubmit}>
      <div className="section-heading">
        <h3>
          {profile === "banksim"
            ? "Score a payment"
            : "Advanced card-data input"}
        </h3>
        <span className="eyebrow">Single transaction</span>
      </div>
      <p className="muted">
        {profile === "banksim"
          ? "Step is an elapsed simulation day. History uses strictly earlier days in this session."
          : "V1–V28 are supplied PCA components. They cannot be recreated from merchant or location inputs."}
      </p>
      <div className="form-grid">
        {/* Repeat the same labelled input pattern; only identifiers/categories are text. */}
        {fields.map((field) => {
          const text = ["customer", "merchant", "category"].includes(field);
          return (
            <label key={field}>
              <span>
                {{
                  step: "Simulation day",
                  customer: "Customer",
                  merchant: "Merchant",
                  category: "Merchant category",
                  amount: "Amount",
                  Time: "Elapsed seconds",
                }[field] || field}
              </span>
              <input
                name={field}
                aria-label={field}
                type={text ? "text" : "number"}
                step={field === "step" ? "1" : "any"}
                min={
                  ["step", "Time", "Amount", "amount"].includes(field)
                    ? "0"
                    : undefined
                }
                value={form[field] ?? ""}
                required
                maxLength={text ? 100 : undefined}
                onChange={
                  /* Copy prior fields so editing one input retains the others. */ (
                    event,
                  ) =>
                    setForm((previous) => ({
                      ...previous,
                      [field]: event.target.value,
                    }))
                }
              />
            </label>
          );
        })}
      </div>
      <button disabled={loading} type="submit">
        {loading ? "Scoring…" : "Score transaction"}
      </button>
    </form>
  );
}
