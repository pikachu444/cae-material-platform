import { lazy, Suspense, useEffect, useMemo, useState } from "react";

import { ApiError, getMaterialDetail, listMaterials, type ApiConfig } from "./api";
import { CommonProcessingWorkbench, type ModelingTrack } from "./common-processing-workbench";
import type {
  MaterialDetail,
  MaterialResponse,
  MaterialStateResponse,
  PropertySetResponse,
} from "./types";

const ReferenceElastoplasticWorkbench = lazy(() =>
  import("./reference-elastoplastic-workbench").then((module) => ({
    default: module.ReferenceElastoplasticWorkbench,
  })),
);
const ReferenceLinearViscoelasticWorkbench = lazy(() =>
  import("./reference-linear-viscoelastic-workbench").then((module) => ({
    default: module.ReferenceLinearViscoelasticWorkbench,
  })),
);
const ReferenceOgdenPronyWorkbench = lazy(() =>
  import("./reference-ogden-prony-workbench").then((module) => ({
    default: module.ReferenceOgdenPronyWorkbench,
  })),
);

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
}

function errorMessage(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  return cause instanceof Error ? cause.message : "The selected material context could not be loaded.";
}

function FamilyModelingPanel({
  config,
  track,
  materials,
  detail,
  selectedMaterialId,
  selectedStateId,
  loading,
  error,
  onMaterialChange,
  onStateChange,
  onNavigate,
  onOpenConnection,
}: {
  config: ApiConfig;
  track: ModelingTrack;
  materials: MaterialResponse[];
  detail: MaterialDetail | null;
  selectedMaterialId: string;
  selectedStateId: string;
  loading: boolean;
  error: string | null;
  onMaterialChange: (materialId: string) => void;
  onStateChange: (stateId: string) => void;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
}) {
  const state = detail?.states.find((item) => item.material_state_id === selectedStateId);
  const propertySet = detail?.property_sets.find((item) => item.material_state_id === selectedStateId);
  const familyLabel = track === "metal"
    ? "Metal elastoplastic"
    : track === "polymer"
      ? "Polymer viscoelastic"
      : "Elastomer hyper-viscoelastic";

  return (
    <div className="family-modeling-panel">
      <header className="family-modeling-heading">
        <div>
          <p className="eyebrow">Material context · exact revisions</p>
          <h2>{familyLabel} model and solver delivery</h2>
          <p>
            Processing evidence above becomes a model candidate here. The selected Material State
            and typed properties remain pinned while you create the neutral model and solver card.
          </p>
        </div>
        <span className={`status-chip ${loading ? "warning" : "success"}`}>
          {loading ? "Loading context" : `${materials.length} ${track} materials`}
        </span>
      </header>

      <div className="family-context-bar">
        <label>
          Material
          <select
            aria-label="Modeling material"
            value={selectedMaterialId}
            disabled={loading || materials.length === 0}
            onChange={(event) => onMaterialChange(event.target.value)}
          >
            {materials.map((item) => (
              <option key={item.material_id} value={item.material_id}>
                {item.current_revision.content.name} · r{item.current_revision.revision_no}
              </option>
            ))}
          </select>
        </label>
        <label>
          Material State
          <select
            aria-label="Modeling material state"
            value={selectedStateId}
            disabled={loading || !detail?.states.length}
            onChange={(event) => onStateChange(event.target.value)}
          >
            {(detail?.states ?? []).map((item) => (
              <option key={item.material_state_id} value={item.material_state_id}>
                {item.current_revision.content.name} · r{item.current_revision.revision_no}
              </option>
            ))}
          </select>
        </label>
        <button
          className="button secondary"
          type="button"
          disabled={!selectedMaterialId}
          onClick={() => onNavigate(`/materials/${selectedMaterialId}/models`)}
        >
          Open full datasheet
        </button>
      </div>

      {error ? (
        <div className="inline-error family-context-error">
          <p>{error}</p>
          <button className="text-button" type="button" onClick={onOpenConnection}>Reconnect</button>
        </div>
      ) : null}
      {!loading && materials.length === 0 ? (
        <div className="empty-tab-state">
          <strong>No {track} Material is available</strong>
          <p>Create a classified Material, State and typed property set in the Material Database first.</p>
          <button className="button primary" type="button" onClick={() => onNavigate("/database")}>Open Material Database</button>
        </div>
      ) : null}
      {!loading && detail && (!state || !propertySet) ? (
        <div className="empty-tab-state">
          <strong>The selected State has no compatible typed property set</strong>
          <p>Add density and the required mechanical properties before creating a model.</p>
          <button className="button primary" type="button" onClick={() => onNavigate(`/materials/${selectedMaterialId}`)}>Add properties</button>
        </div>
      ) : null}
      {state && propertySet ? (
        <Suspense fallback={<p className="loading-state">Loading the {familyLabel} engine…</p>}>
          {track === "metal" ? (
            <ReferenceElastoplasticWorkbench
              key={`metal-${propertySet.current_revision.id}`}
              config={config}
              state={state}
              propertySet={propertySet}
            />
          ) : null}
          {track === "polymer" ? (
            <ReferenceLinearViscoelasticWorkbench
              key={`polymer-${propertySet.current_revision.id}`}
              config={config}
              state={state}
              propertySet={propertySet}
            />
          ) : null}
          {track === "elastomer" ? (
            <ReferenceOgdenPronyWorkbench
              key={`elastomer-${propertySet.current_revision.id}`}
              config={config}
              state={state}
              propertySet={propertySet}
            />
          ) : null}
        </Suspense>
      ) : null}
    </div>
  );
}

export function MaterialModelingWorkspace({ config, onNavigate, onOpenConnection }: Props) {
  const [track, setTrack] = useState<ModelingTrack>("metal");
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [selectedMaterialId, setSelectedMaterialId] = useState("");
  const [detail, setDetail] = useState<MaterialDetail | null>(null);
  const [selectedStateId, setSelectedStateId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setDetail(null);
    setSelectedStateId("");
    void listMaterials(config, "", track)
      .then((result) => {
        if (!active) return;
        const items = result.data.items;
        setMaterials(items);
        setSelectedMaterialId(items[0]?.material_id ?? "");
        if (!items.length) setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setMaterials([]);
        setSelectedMaterialId("");
        setError(errorMessage(cause));
        setLoading(false);
      });
    return () => { active = false; };
  }, [config, track]);

  useEffect(() => {
    if (!selectedMaterialId) return;
    let active = true;
    setLoading(true);
    setError(null);
    void getMaterialDetail(config, selectedMaterialId)
      .then((result) => {
        if (!active) return;
        setDetail(result.data);
        setSelectedStateId(result.data.states[0]?.material_state_id ?? "");
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setDetail(null);
        setSelectedStateId("");
        setError(errorMessage(cause));
        setLoading(false);
      });
    return () => { active = false; };
  }, [config, selectedMaterialId]);

  const familyWorkbench = useMemo(() => (
    <FamilyModelingPanel
      config={config}
      track={track}
      materials={materials}
      detail={detail}
      selectedMaterialId={selectedMaterialId}
      selectedStateId={selectedStateId}
      loading={loading}
      error={error}
      onMaterialChange={setSelectedMaterialId}
      onStateChange={setSelectedStateId}
      onNavigate={onNavigate}
      onOpenConnection={onOpenConnection}
    />
  ), [config, detail, error, loading, materials, onNavigate, onOpenConnection, selectedMaterialId, selectedStateId, track]);

  return (
    <CommonProcessingWorkbench
      config={config}
      onNavigate={onNavigate}
      onOpenConnection={onOpenConnection}
      onModelingTrackChange={setTrack}
      familyWorkbench={familyWorkbench}
    />
  );
}
