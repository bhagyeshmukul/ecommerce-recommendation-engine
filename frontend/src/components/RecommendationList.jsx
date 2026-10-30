import ProductCard from "./ProductCard";

export default function RecommendationList({ recommendations, loading }) {
  if (loading)
    return (
      <div className="state-panel" role="status">
        Finding your next discovery…
      </div>
    );
  if (!recommendations.length)
    return (
      <div className="state-panel">
        No unseen products remain for this customer.
      </div>
    );
  return (
    <div className="recommendation-grid">
      {recommendations.map((product, rank) => (
        <ProductCard product={product} rank={rank} key={product.product_id} />
      ))}
    </div>
  );
}
