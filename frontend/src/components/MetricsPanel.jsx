import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip } from 'recharts';

export default function MetricsPanel({ metrics }) {
  const data = metrics
    ? [
        { name: 'Precision', value: metrics.precision_at_k },
        { name: 'Recall', value: metrics.recall_at_k },
        { name: 'MAP', value: metrics.map_at_k },
        { name: 'Coverage', value: metrics.coverage },
      ]
    : [];

  return (
    <section className="panel metrics-panel">
      <div className="panel-header">
        <h2>Model Metrics</h2>
      </div>
      <ResponsiveContainer width="100%" height={210}>
        <BarChart data={data}>
          <XAxis dataKey="name" />
          <YAxis domain={[0, 1]} />
          <Tooltip />
          <Bar dataKey="value" fill="#0f766e" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}
