import { useEffect, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  getMaterialDetail,
  listMaterials,
} from "./api";
import { GovernedImportWorkbench } from "./governed-import-workbench";
import { loadModelingSession } from "./features/modeling";
import type { MaterialDetail, MaterialStateResponse } from "./types";

interface ImportContext {
  detail: MaterialDetail;
  state: MaterialStateResponse;
}

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "No Material State is available for governed tabular import.";
}

function chooseState(detail: MaterialDetail, preferredStateId?: string): MaterialStateResponse | null {
  return detail.states.find((state) => state.material_state_id === preferredStateId)
    ?? detail.states[0]
    ?? null;
}

async function loadImportContext(config: ApiConfig): Promise<ImportContext> {
  const session = loadModelingSession();
  const preferredMaterialId = session?.material?.id;
  const preferredStateId = session?.materialState?.id;

  if (preferredMaterialId) {
    try {
      const result = await getMaterialDetail(config, preferredMaterialId);
      const state = chooseState(result.data, preferredStateId);
      if (state) return { detail: result.data, state };
    } catch {
      // A stale browser session must not make the governed intake route unusable.
    }
  }

  const materials = await listMaterials(config, "");
  const candidates = materials.data.items
    .filter((material) => material.material_id !== preferredMaterialId)
    .slice(0, 12);

  for (const material of candidates) {
    const result = await getMaterialDetail(config, material.material_id);
    const state = chooseState(result.data);
    if (state) return { detail: result.data, state };
  }

  throw new Error("No Material State is available for governed tabular import.");
}

export function GovernedImportRoute({ config, onNavigate, onOpenConnection }: Props) {
  const [context, setContext] = useState<ImportContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!config.accessToken.trim()) {
      setLoading(false);
      return;
    }
    let current = true;
    setLoading(true);
    setError("");
    void loadImportContext(config)
      .then((result) => current && setContext(result))
      .catch((cause: unknown) => current && setError(errorMessage(cause)))
      .finally(() => current && setLoading(false));
    return () => {
      current = false;
    };
  }, [config]);

  if (!config.accessToken.trim()) {
    return (
      <section className="governed-import-empty" aria-live="polite">
        <h1>Sign in to import test data</h1>
        <button className="button primary" type="button" onClick={onOpenConnection}>Try again</button>
      </section>
    );
  }

  if (loading) return <p className="loading-state">Restoring the exact Material State…</p>;

  if (!context) {
    return (
      <section className="governed-import-empty" role="alert">
        <h1>Choose a Material State first</h1>
        <p>{error}</p>
        <button className="button primary" type="button" onClick={() => onNavigate("/modeling")}>Return to Modeling</button>
      </section>
    );
  }

  const material = context.detail.material.current_revision.content;
  const state = context.state.current_revision;

  return (
    <div className="governed-import-route">
      <header className="governed-import-route-header">
        <div>
          <p className="eyebrow">Modeling / Data / Advanced import</p>
          <h1>Map tabular test data</h1>
          <p>
            <strong>{material.name}</strong>
            {material.material_code ? ` · ${material.material_code}` : ""}
            {` · ${state.content.name} · r${state.revision_no}`}
          </p>
        </div>
        <button className="button secondary" type="button" onClick={() => onNavigate("/modeling")}>← Modeling Data</button>
      </header>
      <GovernedImportWorkbench config={config} state={context.state} />
    </div>
  );
}
