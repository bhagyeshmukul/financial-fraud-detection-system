/** Browse saved predictions and edit investigation notes without rescoring transactions. */
import { useState } from "react";
import { percent } from "./MetricsCard";
/** Keep modal edits local until the server confirms a successful review update. */
export default function TransactionTable({ logs, onReview }) {
  const [editing, setEditing] = useState(null);
  const [notes, setNotes] = useState("");
  const [state, setState] = useState("open");
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Amount</th>
            <th>Fraud score</th>
            <th>Risk</th>
            <th>Decision</th>
            <th>Model used</th>
            <th>Review</th>
            <th>Recorded</th>
          </tr>
        </thead>
        <tbody>
          {/* Preserve each database ID as the React key across filtering and pagination. */}
          {logs.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>
                {row.transaction_amount.toLocaleString(undefined, {
                  maximumFractionDigits: 2,
                })}
              </td>
              <td>{percent(row.fraud_probability)}</td>
              <td>
                <span className={`badge ${row.risk_level.toLowerCase()}`}>
                  {row.risk_level}
                </span>
              </td>
              <td>{row.prediction_label}</td>
              <td
                title={
                  row.routing_reason ||
                  "Model metadata was not stored by this earlier version."
                }
              >
                {row.used_model || "Earlier record"}
                {row.requested_model === "auto" ? " · Auto" : ""}
              </td>
              <td>
                <button
                  className="text-button"
                  onClick={() => {
                    // Copy the selected row into the modal; do not mutate its stored snapshot.
                    setEditing(row);
                    setNotes(row.notes);
                    setState(row.review_state);
                  }}
                >
                  {row.review_state.replace("_", " ")}
                </button>
              </td>
              <td>{new Date(row.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!logs.length && (
        <p className="empty">No predictions match these filters.</p>
      )}
      {editing && (
        <div className="modal-backdrop">
          <form
            className="card modal"
            aria-label="Review prediction"
            onSubmit={async (event) => {
              // Close only after persistence succeeds; keep edits visible on failure.
              event.preventDefault();
              if (await onReview(editing.id, state, notes)) setEditing(null);
            }}
          >
            <h3>Review prediction #{editing.id}</h3>
            <p className="muted">
              Analyst notes are separate from verified fraud labels and model
              evaluation.
            </p>
            <label>
              Review state
              <select
                value={state}
                onChange={(event) => setState(event.target.value)}
              >
                <option value="open">Open</option>
                <option value="under_review">Under review</option>
                <option value="closed">Closed</option>
              </select>
            </label>
            <label>
              Notes
              <textarea
                aria-label="Review notes"
                maxLength={4000}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
            <div className="button-row">
              <button type="submit">Save review</button>
              <button
                type="button"
                className="secondary"
                onClick={() => setEditing(null)}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
