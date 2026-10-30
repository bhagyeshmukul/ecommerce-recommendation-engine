import { TrendingUp } from "lucide-react";

export default function PopularProducts({ products }) {
  return (
    <section className="panel" aria-labelledby="popular-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">THE BASELINE</p>
          <h2 id="popular-title">Store favorites</h2>
        </div>
        <TrendingUp size={20} />
      </div>
      <p className="muted small-copy">
        Ranked by distinct purchasing customers.
      </p>
      <ol className="popular-list">
        {products.slice(0, 5).map((product, i) => (
          <li key={product.product_id}>
            <span className="list-rank">{i + 1}</span>
            <span>{product.product_name.toLowerCase()}</span>
            <strong>
              {product.score.toLocaleString()}
              <small> buyers</small>
            </strong>
          </li>
        ))}
      </ol>
    </section>
  );
}
