import { useEffect, useState } from "react";

import type { ApiConfig } from "../../../shared/api/http";
import {
  downloadExactCsvSource,
  downloadExactJsonSource,
  getExactCatalogSourceAvailability,
  type ExactCatalogSourceFormat,
} from "../api/download-exact-json-source";

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function messageFor(cause: unknown): string {
  return cause instanceof Error
    ? cause.message
    : "The exact source download could not be completed.";
}

export function ExactSourceActions({
  config,
  recordId,
  revisionId,
}: {
  config: ApiConfig;
  recordId: string;
  revisionId: string;
}) {
  const [busy, setBusy] = useState<ExactCatalogSourceFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [availability, setAvailability] = useState<{
    available: boolean;
    published: boolean;
    ready: boolean;
  } | null>(null);
  const [failedFormat, setFailedFormat] = useState<ExactCatalogSourceFormat | null>(null);

  useEffect(() => {
    let active = true;
    setAvailability(null);
    void getExactCatalogSourceAvailability(config, recordId, revisionId)
      .then((result) => {
        if (active) setAvailability(result.data);
      })
      .catch(() => {
        if (active) setAvailability({ available: false, published: false, ready: false });
      });
    return () => {
      active = false;
    };
  }, [config.baseUrl, config.accessToken, recordId, revisionId]);

  async function download(format: ExactCatalogSourceFormat): Promise<void> {
    setBusy(format);
    setError(null);
    setFailedFormat(null);
    try {
      const result = format === "json"
        ? await downloadExactJsonSource(config, recordId, revisionId)
        : await downloadExactCsvSource(config, recordId, revisionId);
      saveBlob(result.data.blob, result.data.filename);
    } catch (cause: unknown) {
      setError(messageFor(cause));
      setFailedFormat(format);
    } finally {
      setBusy(null);
    }
  }

  if (!availability?.available || !availability.published || !availability.ready) return null;

  return (
    <div className="exact-source-actions" aria-label="Exact source downloads">
      <button
        className="ux-button tertiary"
        type="button"
        disabled={busy !== null}
        onClick={() => void download("json")}
      >
        {busy === "json" ? "Downloading…" : "Download JSON"}
      </button>
      <button
        className="ux-button tertiary"
        type="button"
        disabled={busy !== null}
        onClick={() => void download("csv")}
      >
        {busy === "csv" ? "Downloading…" : "Download CSV"}
      </button>
      {error ? (
        <span className="exact-source-error" role="alert">
          {error}
          {failedFormat ? (
            <button className="ux-button tertiary" type="button" onClick={() => void download(failedFormat)}>
              Retry
            </button>
          ) : null}
        </span>
      ) : null}
    </div>
  );
}
