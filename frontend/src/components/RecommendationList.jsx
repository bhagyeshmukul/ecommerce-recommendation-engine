import ProductCard from './ProductCard';

export default function RecommendationList({ recommendations, loading }) {
  if (loading) {
    return <div className="state-panel">Loading recommendations...</div>;
  }

  if (!recommendations.length) {
    return <div className="state-panel">No recommendations available.</div>;
  }

  return (
    <section className="recommendation-grid">
      {recommendations.map((product) => (
        <ProductCard key={product.product_id} product={product} />
      ))}
    </section>
  );
}
