export default function UserHistory({ history }) {
  return (
    <section className="panel history-panel" aria-labelledby="history-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">THE SIGNAL</p>
          <h2 id="history-title">Recent purchases</h2>
        </div>
        <span className="small-label">Latest {history.length}</span>
      </div>
      {history.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Invoice</th>
                <th>Quantity</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item, index) => (
                <tr key={`${item.invoice_id}-${item.product_id}-${index}`}>
                  <td>
                    <span className="history-product">
                      {item.product_name.toLowerCase()}
                    </span>
                    <span className="muted product-code">
                      {item.product_id}
                    </span>
                  </td>
                  <td>{item.invoice_id}</td>
                  <td>{item.quantity}</td>
                  <td>{item.timestamp.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-copy">
          This customer has no recorded purchases. The engine starts with
          store-wide popularity.
        </p>
      )}
    </section>
  );
}
