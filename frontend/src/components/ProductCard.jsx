import { ShoppingBag, Sparkles } from 'lucide-react';

export default function ProductCard({ product }) {
  return (
    <article className="product-card">
      <div className="product-icon">
        <ShoppingBag size={22} />
      </div>
      <div>
        <p className="category">{product.category}</p>
        <h3>{product.product_name}</h3>
      </div>
      <div className="score-row">
        <span>Score</span>
        <strong>{Number(product.score).toFixed(2)}</strong>
      </div>
      <p className="reason">
        <Sparkles size={15} />
        {product.reason}
      </p>
    </article>
  );
}
