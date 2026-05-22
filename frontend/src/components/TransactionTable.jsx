// Static sample table to illustrate expected prediction output shape.
function TransactionTable() {
  const sampleRows = [
    { id: 1, amount: 220.4, probability: 0.03, label: "Not Fraud" },
    { id: 2, amount: 1880.2, probability: 0.84, label: "Fraud" },
    { id: 3, amount: 44.9, probability: 0.09, label: "Not Fraud" },
  ];

  return (
    <div className="card">
      <h3>Sample Transactions</h3>
      <table>
        <thead><tr><th>ID</th><th>Amount</th><th>Fraud Probability</th><th>Label</th></tr></thead>
        <tbody>
          {sampleRows.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td><td>{row.amount}</td><td>{(row.probability * 100).toFixed(1)}%</td><td>{row.label}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default TransactionTable;
