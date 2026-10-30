import { ArrowUpRight, Users, TrendingUp } from "lucide-react";

/** Source labels matter: a neighbor score and a buyer count have different units. */
export default function ProductCard({ product, rank }) {
  const personalized = product.source === "user_cosine";
  return (
    <article className={`product-card tone-${rank % 4}`}>
      <div className="product-art" aria-hidden="true">
        <span className="product-monogram">
          {product.product_name
            .split(" ")
            .filter(Boolean)
            .slice(0, 2)
            .map((word) => word[0])
            .join("")}
        </span>
        <span className="rank">{String(rank + 1).padStart(2, "0")}</span>
        <ArrowUpRight size={20} />
      </div>
      <div className="product-copy">
        <p className="product-code">PRODUCT {product.product_id}</p>
        <h3>{product.product_name.toLowerCase()}</h3>
        <p className="reason">
          {personalized ? <Users size={14} /> : <TrendingUp size={14} />}
          {product.reason}
        </p>
        <div className="score-line">
          <span>{personalized ? "Ranking score" : "Distinct buyers"}</span>
          <strong>
            {personalized
              ? product.score.toFixed(3)
              : product.score.toLocaleString()}
          </strong>
        </div>
        {personalized && product.evidence.length > 0 && (
          <details>
            <summary>Why this recommendation?</summary>
            <p>
              Customers with similar purchase histories also bought this item.
              Strongest contributors:
            </p>
            <ul>
              {product.evidence.map((person) => (
                <li key={person.user_id}>
                  Customer {person.user_id} · cosine{" "}
                  {person.similarity.toFixed(3)} · contribution{" "}
                  {person.contribution.toFixed(3)}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </article>
  );
}
