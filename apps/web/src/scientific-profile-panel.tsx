import { useEffect, useState } from "react";

import {
  type ApiConfig,
  createOgdenScientificProfile,
  listScientificProfiles,
} from "./api";
import type { ScientificProfileResponse } from "./types";

function errorMessage(cause: unknown): string {
  return cause instanceof Error ? cause.message : "The scientific profile request failed.";
}

export function OgdenScientificProfilePanel({ config }: { config: ApiConfig }) {
  const [profiles, setProfiles] = useState<ScientificProfileResponse[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reload(): Promise<void> {
    const result = await listScientificProfiles(config, "elastomer_ogden_prony");
    setProfiles(result.data);
  }

  useEffect(() => {
    setError(null);
    void reload().catch((cause: unknown) => setError(errorMessage(cause)));
  }, [config.baseUrl, config.accessToken]);

  async function createProfile(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await createOgdenScientificProfile(config);
      await reload();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  const profile = profiles[0];
  return (
    <div className="scientific-profile-panel">
      <div>
        <p className="eyebrow">T-43 · versioned scientific policy</p>
        <h5>Calibration profile</h5>
        <p className="muted">
          Bounds, scaling, objective aggregation, multistart and uncertainty policy are an
          immutable revision. A reference profile is not domain approval.
        </p>
      </div>
      {profile ? (
        <div className="profile-summary" data-testid="ogden-scientific-profile">
          <strong>{profile.current_revision.content.profile_label}</strong>
          <span className="revision-chip">
            r{profile.current_revision.revision_no} ·{" "}
            {profile.current_revision.content.approval_status.replaceAll("_", " ")}
          </span>
          <small>
            μ {Number(profile.current_revision.content.parameters.mu_lower_pa).toExponential(2)}–
            {Number(profile.current_revision.content.parameters.mu_upper_pa).toExponential(2)} Pa ·
            α {profile.current_revision.content.parameters.alpha_lower}–
            {profile.current_revision.content.parameters.alpha_upper} ·{" "}
            {profile.current_revision.content.multistart_count} starts
          </small>
          <small>
            {profile.current_revision.content.uncertainty_policy.replaceAll("_", " ")}
          </small>
        </div>
      ) : (
        <button
          className="button secondary"
          type="button"
          disabled={busy}
          onClick={() => void createProfile()}
        >
          {busy ? "Creating…" : "Create reference scientific profile"}
        </button>
      )}
      {error ? <p className="error-notice" role="alert">{error}</p> : null}
    </div>
  );
}
