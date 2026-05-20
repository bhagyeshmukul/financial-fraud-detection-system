const fields = ["Time", ...Array.from({ length: 28 }, (_, i) => `V${i + 1}`), "Amount"];

function TransactionForm({ form, onChange, onSubmit, loading }) {
  return (
    <form className="card" onSubmit={onSubmit}>
      <h3>Transaction Input</h3>
      <div className="grid">
        {fields.map((field) => (
          <label key={field}>
            {field}
            <input
              name={field}
              type="number"
              step="any"
              value={form[field]}
              onChange={onChange}
              required
            />
          </label>
        ))}
      </div>
      <button type="submit" disabled={loading}>{loading ? "Predicting..." : "Predict Fraud"}</button>
    </form>
  );
}

export default TransactionForm;
