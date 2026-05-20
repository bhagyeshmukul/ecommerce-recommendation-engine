export default function PopularProducts({ products }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Popular Products</h2>
      </div>
      <div className="popular-list">
        {products.slice(0, 6).map((product) => (
          <div key={product.product_id} className="popular-item">
            <span>{product.product_name}</span>
            <strong>{Number(product.score).toFixed(1)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
