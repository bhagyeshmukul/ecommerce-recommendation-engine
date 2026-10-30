const METRICS = [
  ["ndcg_at_k", "NDCG"],
  ["precision_at_k", "Precision"],
  ["recall_at_k", "Recall"],
  ["map_at_k", "MAP"],
  ["coverage", "Catalog coverage"],
];
const percentage = (number) =>
  number == null ? "Unavailable" : `${(number * 100).toFixed(2)}%`;

/** All displayed values come from the frozen December report, never UI activity. */
export default function MetricsPanel({ metrics }) {
  if (!metrics) return null;
  const change = metrics.ndcg_relative_change_percent;
  return (
    <section
      className="panel evaluation-panel"
      aria-labelledby="evaluation-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">MEASURED, NOT ASSUMED</p>
          <h2 id="evaluation-title">Offline evaluation</h2>
        </div>
        <span className="badge">TOP {metrics.k}</span>
      </div>
      <p className="muted small-copy">
        December 2011 holdout ·{" "}
        {metrics.cohort.evaluated_users.toLocaleString()} returning customers ·
        full catalog ranking
      </p>
      <div className="evaluation-summary">
        <strong>
          {change == null
            ? "—"
            : `${change >= 0 ? "+" : ""}${change.toFixed(1)}%`}
        </strong>
        <span>
          relative NDCG@{metrics.k} change
          <br />
          against the popularity baseline
        </span>
      </div>
      <div className="table-wrap">
        <table className="metrics-table">
          <thead>
            <tr>
              <th>Metric @{metrics.k}</th>
              <th>Collaborative</th>
              <th>Popularity</th>
            </tr>
          </thead>
          <tbody>
            {METRICS.map(([key, label]) => (
              <tr key={key}>
                <td>
                  {label}
                  {key === "coverage" ? "*" : ""}
                </td>
                <td>
                  <strong>{percentage(metrics.collaborative[key])}</strong>
                </td>
                <td>{percentage(metrics.popularity[key])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details>
        <summary>Evaluation protocol & limitations</summary>
        <p>
          Neighbor count is selected on November purchases. The model is
          refitted through November and tested on December. Only previously
          unpurchased products in the training catalog are targets. Both methods
          use the same users and exclusions.
        </p>
        <p>
          {metrics.cohort.cold_start_users} new customers and{" "}
          {metrics.cohort.users_without_eligible_targets} customers without
          eligible targets are excluded from the warm-user metrics. *Coverage is
          the fraction of the test catalog appearing in top-{metrics.k} lists.
        </p>
        <p>
          The live demo uses all cleaned history. These are historical ranking
          results, not an online engagement or conversion experiment.
        </p>
      </details>
      <p className="metric-note">
        Offline ranking quality does not establish user-engagement lift.
      </p>
    </section>
  );
}
