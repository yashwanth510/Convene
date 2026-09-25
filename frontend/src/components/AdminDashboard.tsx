import { useEffect, useState } from "react";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { request } from "../lib/api";
import "./AdminDashboard.css";

interface Overview {
  generated_at: string;
  days: number;
  total_users: number;
  signups: number;
  total_conversations: number;
  active_users: number;
  submitted_runs: number;
  run_statuses: Record<string, number>;
  recorded_tokens: number;
  daily_signups: { date: string; count: number }[];
  users: {
    id: string;
    email: string;
    created: string;
    last_active: string | null;
  }[];
  page: number;
  page_size: number;
}
const number = (value: number) => value.toLocaleString();
const date = (value: string) => new Date(value).toLocaleString();

export default function AdminDashboard({ close }: { close: () => void }) {
  const [days, setDays] = useState(30);
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const key = `${days}:${page}:${refresh}`;
  const [result, setResult] = useState<{
    key: string;
    data: Overview | null;
    error: string;
  } | null>(null);
  const loading = result?.key !== key;
  const data = !loading ? result?.data : null;
  const error = !loading ? result?.error : "";
  useEffect(() => {
    const controller = new AbortController();
    request<Overview>(`/admin/overview?days=${days}&page=${page}`, {
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ key, data, error: "" });
      })
      .catch((e) => {
        if (!controller.signal.aborted)
          setResult({
            key,
            data: null,
            error: e instanceof Error ? e.message : "Could not load dashboard",
          });
      });
    return () => controller.abort();
  }, [days, page, key]);
  const metrics = data
    ? ([
        ["Registered users", data.total_users, "All time"],
        ["New signups", data.signups, `Last ${days} UTC days`],
        [
          "Active users",
          data.active_users,
          "Submitted at least one question in this period",
        ],
        [
          "Questions submitted",
          data.submitted_runs,
          "Includes subsequently deleted conversations",
        ],
        [
          "Conversations",
          data.total_conversations,
          "Currently saved, all time",
        ],
        [
          "Recorded tokens",
          data.recorded_tokens,
          "Saved runs in this period; not a billing total",
        ],
      ] as const)
    : [];
  return (
    <main className="admin-page">
      <div className="admin-content">
        <button className="admin-button" onClick={close}>
          <ArrowLeft size={16} /> Back to workspace
        </button>
        <header className="admin-heading">
          <div>
            <span className="eyebrow">Private administration</span>
            <h1>Dashboard</h1>
            <p>Registration and activity across Convene.</p>
          </div>
          <div className="admin-controls">
            <label>
              Period{" "}
              <select
                aria-label="Dashboard period"
                value={days}
                onChange={(e) => {
                  setDays(Number(e.target.value));
                  setPage(1);
                }}
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
              </select>
            </label>
            <button
              className="admin-button"
              disabled={loading}
              onClick={() => setRefresh((n) => n + 1)}
            >
              <RefreshCw size={16} /> Refresh
            </button>
          </div>
        </header>
        {loading && <p role="status">Loading statistics…</p>}
        {error && (
          <div className="error-banner" role="alert">
            {error}
            <button
              className="admin-button"
              onClick={() => setRefresh((n) => n + 1)}
            >
              Retry
            </button>
          </div>
        )}
        {data && (
          <>
            <p className="quiet small">
              Updated {date(data.generated_at)}. Date ranges include today;
              daily counts use UTC.
            </p>
            <section className="admin-metrics" aria-label="Usage overview">
              {metrics.map(([label, value, note]) => (
                <article className="admin-card" key={label}>
                  <h2>{label}</h2>
                  <strong>{number(value)}</strong>
                  <p>{note}</p>
                </article>
              ))}
            </section>
            <section className="admin-panel">
              <h2>Daily signups</h2>
              <div className="admin-table-scroll admin-daily">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Date (UTC)</th>
                      <th scope="col">Signups</th>
                      <th scope="col">Trend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.daily_signups
                      .slice()
                      .reverse()
                      .map((day) => (
                        <tr key={day.date}>
                          <td>{day.date}</td>
                          <td>{number(day.count)}</td>
                          <td>
                            <div
                              className="admin-bar"
                              aria-hidden="true"
                              style={{
                                width: `${(day.count / Math.max(1, ...data.daily_signups.map((d) => d.count))) * 100}%`,
                              }}
                            />
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section className="admin-panel">
              <h2>Run outcomes</h2>
              <p>
                Saved runs submitted in the selected period. Deleted runs are
                excluded from outcomes and token totals.
              </p>
              <div className="admin-outcomes">
                {[
                  "complete",
                  "partial",
                  "failed",
                  "cancelled",
                  "interrupted",
                  "queued",
                  "running",
                ].map((status) => (
                  <div key={status}>
                    <span>{status}</span>
                    <strong>{number(data.run_statuses[status] || 0)}</strong>
                  </div>
                ))}
              </div>
            </section>
            <section className="admin-panel">
              <h2>Registered users</h2>
              <p>
                All accounts, newest first. Last activity means the most recent
                submitted question.
              </p>
              <div className="admin-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Email</th>
                      <th scope="col">Registered</th>
                      <th scope="col">Last activity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.users.map((user) => (
                      <tr key={user.id}>
                        <td>{user.email}</td>
                        <td>{date(user.created)}</td>
                        <td>
                          {user.last_active
                            ? date(user.last_active)
                            : "No questions yet"}
                        </td>
                      </tr>
                    ))}
                    {!data.users.length && (
                      <tr>
                        <td colSpan={3}>No users on this page.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <nav className="admin-pagination" aria-label="User pages">
                <button
                  className="admin-button"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </button>
                <span>
                  Page {data.page} of{" "}
                  {Math.max(1, Math.ceil(data.total_users / data.page_size))}
                </span>
                <button
                  className="admin-button"
                  disabled={page * data.page_size >= data.total_users}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </nav>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
