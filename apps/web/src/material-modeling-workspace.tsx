import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, getMaterialDetail, listMaterials, type ApiConfig } from "./api";
import type { ModelingTrack } from "./common-processing-workbench";
import { dispatchModelingSession, loadModelingSession, saveModelingSession, type ModelingMaterialFamily, type ModelingSessionSummary } from "./modeling-session-context";
import { PolymerTemperatureShiftInspector } from "./polymer-temperature-shift-inspector";
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
const CommonProcessingWorkbench = lazy(() =>
  import("./common-processing-workbench").then((module) => ({
    default: module.CommonProcessingWorkbench,
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
  locationSearch?: string;
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
  preferredSourceDocumentId,
  preferredProcessingOutputId,
}: {
  config: ApiConfig;
  track: ModelingTrack;
  materials: MaterialResponse[];
  detail: MaterialDetail | null;
  selectedMaterialId: string;
  selectedStateId: string;
  loading: boolean;
  error: string | null;
  onMaterialChange: (materialId: string, explicit: boolean) => void;
  onStateChange: (stateId: string, explicit: boolean) => void;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
  preferredSourceDocumentId?: string;
  preferredProcessingOutputId?: string;
}) {
  const materialSelectionArmed = useRef(false);
  const stateSelectionArmed = useRef(false);
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
            onPointerDown={() => { materialSelectionArmed.current = true; }}
            onKeyDown={() => { materialSelectionArmed.current = true; }}
            onChange={(event) => {
              onMaterialChange(event.target.value, materialSelectionArmed.current);
              materialSelectionArmed.current = false;
            }}
          >
            <option value="">Choose Material context</option>
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
            onPointerDown={() => { stateSelectionArmed.current = true; }}
            onKeyDown={() => { stateSelectionArmed.current = true; }}
            onChange={(event) => {
              onStateChange(event.target.value, stateSelectionArmed.current);
              stateSelectionArmed.current = false;
            }}
          >
            <option value="">Choose Material State</option>
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
              onNavigate={onNavigate}
              embedded
              preferredProcessingOutputId={preferredProcessingOutputId}
            />
          ) : null}
          {track === "polymer" ? (
            <ReferenceLinearViscoelasticWorkbench
              key={`polymer-${propertySet.current_revision.id}`}
              config={config}
              state={state}
              propertySet={propertySet}
              onNavigate={onNavigate}
              embedded
              preferredSourceDocumentId={preferredSourceDocumentId}
              preferredProcessingOutputId={preferredProcessingOutputId}
            />
          ) : null}
          {track === "elastomer" ? (
            <ReferenceOgdenPronyWorkbench
              key={`elastomer-${propertySet.current_revision.id}`}
              config={config}
              state={state}
              propertySet={propertySet}
              onNavigate={onNavigate}
              embedded
            />
          ) : null}
        </Suspense>
      ) : null}
    </div>
  );
}

export function MaterialModelingWorkspace({ config, onNavigate, onOpenConnection, locationSearch = "" }: Props) {
  const initialQuery = useMemo(() => new URLSearchParams(locationSearch), [locationSearch]);
  const queryFamily = initialQuery.get("family");
  const queryMaterialId = initialQuery.get("material_id");
  const queryMaterialRevisionId = initialQuery.get("material_revision_id");
  const queryMaterialStateId = initialQuery.get("material_state_id");
  const queryMaterialStateRevisionId = initialQuery.get("material_state_revision_id");
  const queryContextRequested = Boolean(queryMaterialId || queryMaterialStateId);
  const [initialSession] = useState<ModelingSessionSummary | null>(() => loadModelingSession());
  const [session, setSession] = useState<ModelingSessionSummary | null>(initialSession);
  const [track, setTrack] = useState<ModelingTrack>(["metal", "polymer", "elastomer"].includes(String(queryFamily)) ? queryFamily as ModelingTrack : session?.materialFamily ?? "metal");
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [selectedMaterialId, setSelectedMaterialId] = useState("");
  const [detail, setDetail] = useState<MaterialDetail | null>(null);
  const [selectedStateId, setSelectedStateId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const contextGeneration = useRef(0);
  const contextSelectionEnabled = useRef(initialSession?.contextSelectionRequired !== true || queryContextRequested);
  const updateSession = useCallback((patch: Partial<Omit<ModelingSessionSummary, "version" | "updatedAt">>) => {
    setSession(saveModelingSession(patch));
  }, []);
  const applySessionEvent = useCallback((event: Parameters<typeof dispatchModelingSession>[0]) => {
    setSession(dispatchModelingSession(event));
  }, []);
  const startNewSession = useCallback((family: ModelingMaterialFamily) => {
    contextGeneration.current += 1;
    contextSelectionEnabled.current = false;
    const persisted = loadModelingSession();
    setSession(persisted?.contextSelectionRequired
      ? persisted
      : dispatchModelingSession({ type: "NEW_SESSION", materialFamily: family }));
    setSelectedMaterialId("");
    setSelectedStateId("");
    setDetail(null);
    setError(null);
  }, []);

  useEffect(() => {
    let active = true;
    const generation = contextGeneration.current;
    setLoading(true);
    setError(null);
    setDetail(null);
    setSelectedStateId("");
    void listMaterials(config, "", track)
      .then((result) => {
        if (!active) return;
        const items = result.data.items;
        setMaterials(items);
        if (generation !== contextGeneration.current || !contextSelectionEnabled.current) {
          setSelectedMaterialId("");
          setLoading(false);
          return;
        }
        const restored = queryMaterialId
          ? items.find((item) => item.material_id === queryMaterialId
            && (!queryMaterialRevisionId || item.current_revision.id === queryMaterialRevisionId))
          : items.find((item) => item.material_id === initialSession?.material?.id
            && item.current_revision.id === initialSession.material.revisionId);
        setSelectedMaterialId(restored?.material_id ?? items[0]?.material_id ?? "");
        if (queryMaterialId && !restored) {
          setSelectedMaterialId("");
          setError("The Processing Batch Material revision is no longer the current selectable head. Exact recovery is blocked until a new current context is chosen.");
        } else if (initialSession?.material && !restored) {
          setError(`The recent ${initialSession.material.label} r${initialSession.material.revisionNo} revision is no longer a current selectable head. A compatible current Material was selected for review.`);
        }
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
  }, [config, initialSession, queryMaterialId, queryMaterialRevisionId, track]);

  useEffect(() => {
    if (!selectedMaterialId) return;
    let active = true;
    const generation = contextGeneration.current;
    setLoading(true);
    setError(null);
    void getMaterialDetail(config, selectedMaterialId)
      .then((result) => {
        if (!active || generation !== contextGeneration.current || !contextSelectionEnabled.current) return;
        setDetail(result.data);
        const restored = queryMaterialStateId
          ? result.data.states.find((item) => item.material_state_id === queryMaterialStateId
            && (!queryMaterialStateRevisionId || item.current_revision.id === queryMaterialStateRevisionId))
          : result.data.states.find((item) => item.material_state_id === initialSession?.materialState?.id
            && item.current_revision.id === initialSession.materialState.revisionId);
        setSelectedStateId(restored?.material_state_id ?? result.data.states[0]?.material_state_id ?? "");
        if (queryMaterialStateId && !restored) {
          setSelectedStateId("");
          setError("The Processing Batch Material State revision is no longer the current selectable head. Exact recovery is blocked until a new current context is chosen.");
        }
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
  }, [config, initialSession, queryMaterialStateId, queryMaterialStateRevisionId, selectedMaterialId]);

  useEffect(() => {
    if (!contextSelectionEnabled.current) return;
    const material = materials.find((item) => item.material_id === selectedMaterialId);
    if (!material) return;
    updateSession({
      materialFamily: track,
      material: {
        id: material.material_id,
        revisionId: material.current_revision.id,
        label: material.current_revision.content.name,
        revisionNo: material.current_revision.revision_no,
      },
    });
  }, [materials, selectedMaterialId, track, updateSession]);

  useEffect(() => {
    if (!contextSelectionEnabled.current) return;
    const state = detail?.states.find((item) => item.material_state_id === selectedStateId);
    if (!state) return;
    updateSession({ materialState: {
      id: state.material_state_id,
      revisionId: state.current_revision.id,
      label: state.current_revision.content.name,
      revisionNo: state.current_revision.revision_no,
    } });
  }, [detail, selectedStateId, updateSession]);

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
      onMaterialChange={(materialId, explicit) => {
        if (!explicit && !contextSelectionEnabled.current) return;
        contextSelectionEnabled.current = true;
        updateSession({ contextSelectionRequired: false });
        setSelectedMaterialId(materialId);
      }}
      onStateChange={(stateId, explicit) => {
        if (!explicit && !contextSelectionEnabled.current) return;
        contextSelectionEnabled.current = true;
        setSelectedStateId(stateId);
      }}
      onNavigate={onNavigate}
      onOpenConnection={onOpenConnection}
      preferredSourceDocumentId={session?.testData?.id}
      preferredProcessingOutputId={session?.processingOutput?.id}
    />
  ), [config, detail, error, loading, materials, onNavigate, onOpenConnection, selectedMaterialId, selectedStateId, session?.processingOutput?.id, session?.testData?.id, track, updateSession]);
  const selectedState = detail?.states.find((item) => item.material_state_id === selectedStateId);
  const selectedMaterial = materials.find((item) => item.material_id === selectedMaterialId);
  const familyInspector = useMemo(() => track === "polymer" && selectedState ? (
    <PolymerTemperatureShiftInspector config={config} state={selectedState} />
  ) : null, [config, selectedState, track]);

  return (
    <Suspense fallback={<p className="loading-state">Loading Modeling workspace…</p>}>
      <CommonProcessingWorkbench
      config={config}
      onNavigate={onNavigate}
      onOpenConnection={onOpenConnection}
      onModelingTrackChange={setTrack}
      initialSession={session}
      onSessionChange={updateSession}
      onSessionEvent={applySessionEvent}
      onNewSession={startNewSession}
      familyWorkbench={familyWorkbench}
      familyInspector={familyInspector}
      material={selectedMaterial}
      materialState={selectedState}
      propertySet={detail?.property_sets.find((item) => item.material_state_id === selectedStateId)}
      locationSearch={locationSearch}
      />
    </Suspense>
  );
}
