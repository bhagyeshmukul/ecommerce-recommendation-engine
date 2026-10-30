import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  Box,
  Check,
  Database,
  GitBranch,
  RefreshCw,
  ShoppingBasket,
  Users,
} from "lucide-react";
import { get } from "../services/api";
import RecommendationList from "../components/RecommendationList";
import UserSelector from "../components/UserSelector";
import UserHistory from "../components/UserHistory";
import PopularProducts from "../components/PopularProducts";
import MetricsPanel from "../components/MetricsPanel";

const count = (value) => Number(value || 0).toLocaleString();

export default function RecommendationDashboard() {
  const [base, setBase] = useState(null);
  const [selectedUser, setSelectedUser] = useState("");
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [method, setMethod] = useState("collaborative");
  const [view, setView] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const generation = useRef(0);

  const bootstrap = useCallback(async (signal) => {
    setError("");
    setLoading(true);
    try {
      const [users, metadata, metrics, popular] = await Promise.all([
        get("/users?limit=5000", signal),
        get("/model", signal),
        get("/metrics", signal),
        get("/products/popular", signal),
      ]);
      if (signal.aborted) return;
      setBase({
        users: users.users,
        metadata,
        metrics,
        popular: popular.products,
      });
      setSelectedUser(
        (current) =>
          current ||
          (users.users.includes("12347")
            ? "12347"
            : users.users[0] || "NEW_CUSTOMER"),
      );
    } catch (failure) {
      if (failure.name !== "AbortError") {
        setError(failure.message);
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    bootstrap(controller.signal);
    return () => controller.abort();
  }, [bootstrap, refresh]);

  useEffect(() => {
    if (!selectedUser || !base) return;
    const controller = new AbortController();
    const request = ++generation.current;
    setLoading(true);
    setError("");
    setView(null); // Never show the previous customer's recommendations under a new ID.
    async function load() {
      try {
        const id = encodeURIComponent(selectedUser);
        const [recommendations, history, neighbors] = await Promise.all([
          get(
            `/recommend/${id}?top_k=${topK}&strategy=${method}`,
            controller.signal,
          ),
          get(`/users/${id}/history?limit=8`, controller.signal),
          get(`/users/${id}/neighbors`, controller.signal),
        ]);
        // Request logs are fetched after serving, so this request is included.
        const logs = await get(
          "/recommendation-logs?limit=5",
          controller.signal,
        );
        if (request === generation.current && !controller.signal.aborted)
          setView({
            recommendations,
            history,
            neighbors: neighbors.neighbors,
            logs,
          });
      } catch (failure) {
        if (failure.name !== "AbortError" && request === generation.current)
          setError(failure.message);
      } finally {
        if (request === generation.current && !controller.signal.aborted)
          setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [selectedUser, topK, method, base]);

  const metadata = base?.metadata;
  const quality = metadata?.dataset.quality;
  const strategy = view?.recommendations.recommendation_strategy;
  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="#">
          <span className="brand-icon">
            <ShoppingBasket size={23} />
          </span>
          <span>
            basket<span className="brand-dot">.</span>
            <small>RECOMMENDATION LAB</small>
          </span>
        </a>
        <nav aria-label="Page sections">
          <a href="#recommendations">Discover</a>
          <a href="#evaluation">Evaluation</a>
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
            API <ArrowUpRight size={13} />
          </a>
        </nav>
        <span className="header-status">
          <span />
          {metadata ? "Model ready" : "Connecting"}
        </span>
      </header>
      <main>
        <section className="hero">
          <div>
            <p className="eyebrow">
              <span className="tiny-line" /> PURCHASE PATTERNS. PERSONAL
              DISCOVERIES.
            </p>
            <h1>
              A better next
              <br />
              <em>discovery.</em>
            </h1>
            <p className="hero-copy">
              Real purchase histories. Similar customers. Product suggestions
              with a reason you can inspect.
            </p>
            <div className="hero-tags">
              <span>
                <Check size={13} /> User-based filtering
              </span>
              <span>
                <Check size={13} /> Cosine similarity
              </span>
              <span>
                <Check size={13} /> Measured against popularity
              </span>
            </div>
          </div>
          <aside className="snapshot-card">
            <div className="snapshot-heading">
              <Database size={17} />
              <span>THE DATA BEHIND THE DISCOVERY</span>
            </div>
            <h2>Real retail. Real patterns.</h2>
            <p>UCI Online Retail · UK retailer · 2010–2011</p>
            <div className="snapshot-stats">
              <div>
                <strong>{count(quality?.users)}</strong>
                <span>customers</span>
              </div>
              <div>
                <strong>{count(quality?.products)}</strong>
                <span>products</span>
              </div>
              <div>
                <strong>
                  {quality
                    ? `${(quality.purchase_events / 1000).toFixed(1)}k`
                    : "—"}
                </strong>
                <span>purchase events</span>
              </div>
            </div>
            <div className="snapshot-bottom">
              <GitBranch size={14} />
              <span>
                {metadata
                  ? `${metadata.serving.neighbors} nearest neighbors · sparse cosine model`
                  : "Loading model snapshot…"}
              </span>
            </div>
          </aside>
        </section>
        {error && (
          <div className="error" role="alert">
            <strong>Couldn’t load the demo.</strong>
            <span>{error}</span>
            <button onClick={() => setRefresh((value) => value + 1)}>
              Try again
            </button>
          </div>
        )}
        <section id="recommendations" className="discovery-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">01 / THE PERSONALIZATION</p>
              <h2>Made for this customer</h2>
            </div>
            <span className="small-label">
              Explore a history. Follow the recommendation.
            </span>
          </div>
          <div className="control-bar">
            <UserSelector
              users={base?.users || []}
              query={query}
              onQuery={setQuery}
              selectedUser={selectedUser}
              onSelect={setSelectedUser}
              disabled={!base}
            />
            <div className="method-controls">
              <label>
                <span>Ranking method</span>
                <select
                  aria-label="Ranking method"
                  value={method}
                  onChange={(event) => setMethod(event.target.value)}
                >
                  <option value="collaborative">Collaborative filtering</option>
                  <option value="popularity">Popularity baseline</option>
                </select>
              </label>
              <label>
                <span>Suggestions</span>
                <select
                  aria-label="Suggestions"
                  value={topK}
                  onChange={(event) => setTopK(Number(event.target.value))}
                >
                  <option value={5}>Top 5</option>
                  <option value={10}>Top 10</option>
                </select>
              </label>
              <button
                className="refresh-button"
                aria-label="Refresh dashboard"
                onClick={() => setRefresh((value) => value + 1)}
                disabled={loading}
              >
                <RefreshCw size={17} />
              </button>
            </div>
          </div>
          <div className="strategy-line">
            <span className="badge">
              {selectedUser === "NEW_CUSTOMER" ? "COLD START" : "CUSTOMER"}{" "}
              {selectedUser === "NEW_CUSTOMER" ? "" : selectedUser}
            </span>
            <span>
              {loading
                ? "Scoring unseen products…"
                : strategy === "user_cosine"
                  ? "Personalized using similar purchase histories"
                  : strategy === "popularity"
                    ? "Popularity ranking · distinct purchasing customers"
                    : "Select a customer to explore"}
            </span>
          </div>
          {!error && (
            <RecommendationList
              recommendations={view?.recommendations.recommended_products || []}
              loading={loading}
            />
          )}
        </section>
        <div className="insight-grid">
          <UserHistory history={view?.history || []} />
          <section className="panel neighbors-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">THE CONNECTION</p>
                <h2>Similar customers</h2>
              </div>
              <Users size={20} />
            </div>
            <p className="muted small-copy">
              Cosine similarity of purchase vectors, from 0 to 1.
            </p>
            {view?.neighbors.length ? (
              <ol className="neighbor-list">
                {view.neighbors.map((person) => (
                  <li key={person.user_id}>
                    <span className="customer-avatar">
                      {person.user_id.slice(-2)}
                    </span>
                    <span>Customer {person.user_id}</span>
                    <div className="similarity-meter" aria-hidden="true">
                      <span style={{ width: `${person.similarity * 100}%` }} />
                    </div>
                    <strong>{person.similarity.toFixed(3)}</strong>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="empty-copy">
                No similar customers yet. Popular products provide a useful
                starting point.
              </p>
            )}
          </section>
        </div>
        <section id="evaluation" className="measurement-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">02 / THE EVIDENCE</p>
              <h2>How good are the suggestions?</h2>
            </div>
            <span className="small-label">
              A chronological holdout. A fair baseline.
            </span>
          </div>
          <div className="evidence-grid">
            <MetricsPanel metrics={base?.metrics} />
            <PopularProducts products={base?.popular || []} />
          </div>
        </section>
        <section className="panel logs-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">THE AUDIT TRAIL</p>
              <h2>Recent recommendation requests</h2>
            </div>
            <Box size={19} />
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Request</th>
                  <th>Customer</th>
                  <th>Suggestions</th>
                  <th>Strategy</th>
                  <th>Model version</th>
                </tr>
              </thead>
              <tbody>
                {view?.logs.map((log) => (
                  <tr key={log.id}>
                    <td>#{log.id}</td>
                    <td>{log.user_id}</td>
                    <td>{log.top_k}</td>
                    <td>
                      <span className="log-strategy">
                        {log.recommendation_strategy === "user_cosine"
                          ? "User cosine"
                          : "Popularity"}
                      </span>
                    </td>
                    <td className="mono">{log.model_version.slice(0, 12)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!view?.logs.length && (
              <p className="empty-copy">
                Requests appear here after recommendations are served.
              </p>
            )}
          </div>
        </section>
      </main>
      <footer>
        <span className="footer-brand">basket.</span>
        <span>
          Python · Pandas · Scikit-Learn · FastAPI · PostgreSQL · React
        </span>
        <a
          href="https://archive.ics.uci.edu/dataset/352/online-retail"
          target="_blank"
          rel="noreferrer"
        >
          UCI dataset · CC BY 4.0 <ArrowUpRight size={13} />
        </a>
      </footer>
    </div>
  );
}
