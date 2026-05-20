export default function UserHistory({ history }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>User History</h2>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>Category</th>
              <th>Event</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            {history.slice(0, 8).map((item, index) => (
              <tr key={`${item.product_id}-${index}`}>
                <td>{item.product_name || item.product_id}</td>
                <td>{item.category || '-'}</td>
                <td>{item.interaction_type}</td>
                <td>{Number(item.interaction_score).toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
