import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  type ApiConfig,
} from "./shared/api";
import {
  getOperationalObservability,
} from "./features/activity";
import type { OperationalSnapshotResponse } from "./types";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "The redacted operations snapshot could not be loaded.";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(new Date(value));
}

export function OperationsDashboard({ config }: { config: ApiConfig }) {
  const [snapshot, setSnapshot] = useState<OperationalSnapshotResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getOperationalObservability(config);
      setSnapshot(result.data);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setLoading(false);
    }
  }, [config]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="content-card" aria-labelledby="operations-dashboard-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Operations · redacted telemetry</p>
          <h2 id="operations-dashboard-title">API observability</h2>
        </div>
        <button className="button secondary" type="button" onClick={() => void load()} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh snapshot"}
        </button>
      </div>
      <p className="muted">
        This auditor view shows one API process using bounded route templates. It never exposes URLs,
        query strings, request bodies, test-data payloads, credentials, or workspace identifiers. The
        OpenTelemetry backend remains authoritative across replicas and workers.
      </p>
      {error ? <p className="error-notice" role="alert">{error}</p> : null}
      {snapshot ? (
        <>
          <dl className="metric-grid">
            <div><dt>Requests</dt><dd>{snapshot.request_count.toLocaleString()}</dd></div>
            <div><dt>Server errors</dt><dd>{snapshot.error_count.toLocaleString()}</dd></div>
            <div><dt>Active</dt><dd>{snapshot.active_requests.toLocaleString()}</dd></div>
            <div><dt>Observed</dt><dd>{formatDate(snapshot.observed_at)}</dd></div>
          </dl>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Method</th><th>Route template</th><th>Status</th><th>Count</th><th>Errors</th><th>p95 ≤</th>
                </tr>
              </thead>
              <tbody>
                {snapshot.series.map((row) => (
                  <tr key={`${row.method}-${row.route}-${row.status_family}`}>
                    <td>{row.method}</td>
                    <td><code>{row.route}</code></td>
                    <td>{row.status_family}</td>
                    <td>{row.request_count.toLocaleString()}</td>
                    <td>{row.error_count.toLocaleString()}</td>
                    <td>{row.p95_upper_bound_ms.toLocaleString()} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!snapshot.series.length ? <p className="muted">No completed request has been observed yet.</p> : null}
          <p className="source-line">{snapshot.service} {snapshot.version} · process started {formatDate(snapshot.started_at)}</p>
        </>
      ) : null}
    </section>
  );
}
