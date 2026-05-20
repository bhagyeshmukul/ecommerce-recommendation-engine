import { useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import MetricsPanel from '../components/MetricsPanel';
import PopularProducts from '../components/PopularProducts';
import RecommendationList from '../components/RecommendationList';
import UserHistory from '../components/UserHistory';
import UserSelector from '../components/UserSelector';
import {
  fetchLogs,
  fetchMetrics,
  fetchPopularProducts,
  fetchRecommendations,
  fetchUserHistory,
  fetchUsers,
} from '../services/api';

export default function RecommendationDashboard() {
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState('');
  const [recommendationResponse, setRecommendationResponse] = useState(null);
  const [history, setHistory] = useState([]);
  const [popular, setPopular] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    async function bootstrap() {
      try {
        setLoading(true);
        const [userIds, popularProducts, modelMetrics, latestLogs] = await Promise.all([
          fetchUsers(),
          fetchPopularProducts(),
          fetchMetrics(),
          fetchLogs(),
        ]);
        setUsers(userIds);
        setSelectedUser(userIds[0] || 'COLD_START_USER');
        setPopular(popularProducts);
        setMetrics(modelMetrics);
        setLogs(latestLogs);
      } catch (err) {
        setError(err.message || 'Failed to load dashboard data.');
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, []);

  useEffect(() => {
    if (!selectedUser) return;
    loadRecommendations(selectedUser);
  }, [selectedUser]);

  async function loadRecommendations(userId) {
    try {
      setLoading(true);
      setError('');
      const [recs, userHistory] = await Promise.all([
        fetchRecommendations(userId, 5),
        userId === 'COLD_START_USER' ? Promise.resolve([]) : fetchUserHistory(userId),
      ]);
      setRecommendationResponse(recs);
      setHistory(userHistory);
      setLogs(await fetchLogs());
    } catch (err) {
      setError(err.message || 'Recommendation request failed.');
    } finally {
      setLoading(false);
    }
  }

  const recommendations = useMemo(
    () => recommendationResponse?.recommended_products || [],
    [recommendationResponse],
  );

  return (
    <main className="dashboard">
      <header className="topbar">
        <div>
          <p className="eyebrow">ML Recommendation System</p>
          <h1>E-commerce Recommendation Engine</h1>
        </div>
        <div className="controls">
          <UserSelector users={users} selectedUser={selectedUser} onSelect={setSelectedUser} disabled={loading} />
          <button className="icon-button" onClick={() => loadRecommendations(selectedUser)} disabled={loading} title="Refresh">
            <RefreshCw size={18} />
          </button>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="strategy-strip">
        <span>User: {selectedUser || '-'}</span>
        <span>Strategy: {recommendationResponse?.recommendation_strategy || '-'}</span>
      </section>

      <RecommendationList recommendations={recommendations} loading={loading && !recommendations.length} />

      <section className="secondary-grid">
        <UserHistory history={history} />
        <PopularProducts products={popular} />
        <MetricsPanel metrics={metrics} />
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Latest Recommendation Logs</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>User</th>
                <th>Top K</th>
                <th>Strategy</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td>{log.user_id}</td>
                  <td>{log.top_k}</td>
                  <td>{log.recommendation_strategy}</td>
                  <td>{new Date(log.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
