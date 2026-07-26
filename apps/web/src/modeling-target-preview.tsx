import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError, createExactTargetPreview, type ApiConfig } from "./api";
import type { CommonProcessingOutputResponse, TargetPreviewResponse } from "./types";
import type { ExportPrerequisite } from "./modeling-export-eligibility";
import type { ModelingSessionEvent, ModelingSessionSummary } from "./modeling-session-context";

// Mirrors the two reference/non-production tuples declared by
// neutral_hyperelastic_capability_manifest; this UI does not claim a production matrix.
const TARGETS = [
  { value: "abaqus", label: "Abaqus 2025 · kg-m-s" },
  { value: "openradioss", label: "OpenRadioss 2025 · kg-m-s" },
] as const;

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Target preview could not be generated.";
}

function sourceKey(session: ModelingSessionSummary | null | undefined): string {
  return [
    session?.processingOutput?.id,
    session?.processingOutput?.revisionId,
    session?.neutralModel?.id,
    session?.neutralModel?.revisionId,
  ].join("/");
}

function responseMatchesCurrentSource(
  response: TargetPreviewResponse,
  session: ModelingSessionSummary,
  output: CommonProcessingOutputResponse,
): boolean {
  return response.source.processing_output_id === output.processing_output_id
    && response.source.processing_output_revision_id === output.current_revision.id
    && response.source.processing_output_sha256 === output.output_sha256
    && response.source.material_id === session.material?.id
    && response.source.material_revision_id === session.material?.revisionId
    && response.source.material_state_id === session.materialState?.id
    && response.source.material_state_revision_id === session.materialState?.revisionId
    // The neutral document owns its embedded canonical IR identity.  The
    // upstream Material Model pointer remains a separate session concern
    // (for example, Validation uses it) and is never substituted here.
    && response.source.material_model_ir_revision_id === session.neutralModel?.revisionId
    && response.source.neutral_material_id === session.neutralModel?.id
    && response.source.neutral_material_revision_id === session.neutralModel?.revisionId;
}

function responseMatchesRequestedTarget(
  response: TargetPreviewResponse,
  target: { solver: string; version: string; unit_system: string },
  solverMaterialId: number,
  materialName: string,
): boolean {
  return response.target.solver === target.solver
    && response.target.version === target.version
    && response.target.unit_system === target.unit_system
    && response.target.solver_material_id === solverMaterialId
    && response.target.material_name === materialName;
}

export function ModelingTargetPreview({
  config,
  session,
  output,
  prerequisites,
  onSessionEvent,
}: {
  config: ApiConfig;
  session: ModelingSessionSummary | null | undefined;
  output: CommonProcessingOutputResponse | undefined;
  prerequisites: ExportPrerequisite[];
  onSessionEvent?: (event: ModelingSessionEvent) => void;
}) {
  const [targetSolver, setTargetSolver] = useState<"" | "abaqus" | "openradioss">("");
  const [solverMaterialId, setSolverMaterialId] = useState("1");
  const [materialName, setMaterialName] = useState("");
  const [preview, setPreview] = useState<TargetPreviewResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestGeneration = useRef(0);
  const currentSourceKey = sourceKey(session);
  const exactRequirementsCurrent = prerequisites
    .filter((item) => item.label !== "Ephemeral target preview producer")
    .every((item) => item.status === "current");
  const hasExactRefs = Boolean(
    output
    && session?.processingOutput
    && session.material
    && session.materialState
    && session.materialModelIr
    && session.neutralModel,
  );
  const canGenerate = exactRequirementsCurrent && hasExactRefs && targetSolver !== ""
    && /^[1-9][0-9]{0,9}$/.test(solverMaterialId)
    && /^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(materialName)
    && !busy;

  useEffect(() => {
    requestGeneration.current += 1;
    setPreview(null);
    setError(null);
  }, [currentSourceKey]);

  const selectedTarget = useMemo(() => targetSolver
    ? { solver: targetSolver, version: "2025", unit_system: "kg_m_s" }
    : null, [targetSolver]);

  function changeTarget(value: "" | "abaqus" | "openradioss"): void {
    requestGeneration.current += 1;
    setTargetSolver(value);
    setPreview(null);
    setError(null);
    onSessionEvent?.({ type: "CHANGE_EXPORT_TARGET" });
  }

  function invalidateTargetPreview(): void {
    requestGeneration.current += 1;
    setPreview(null);
    setError(null);
    onSessionEvent?.({ type: "CHANGE_EXPORT_TARGET" });
  }

  async function generate(): Promise<void> {
    if (!canGenerate || !output || !selectedTarget || !session?.processingOutput
      || !session.neutralModel) return;
    const generation = requestGeneration.current + 1;
    requestGeneration.current = generation;
    const requestedTarget = selectedTarget;
    const requestedSolverMaterialId = Number(solverMaterialId);
    const requestedMaterialName = materialName;
    setBusy(true);
    setError(null);
    try {
      const result = await createExactTargetPreview(config, {
        processing_output_id: session.processingOutput.id,
        processing_output_revision_id: session.processingOutput.revisionId,
        neutral_material_id: session.neutralModel.id,
        neutral_material_revision_id: session.neutralModel.revisionId,
        target: requestedTarget,
        solver_material_id: requestedSolverMaterialId,
        material_name: requestedMaterialName,
      });
      if (generation !== requestGeneration.current) return;
      if (!responseMatchesCurrentSource(result.data, session, output)
        || !responseMatchesRequestedTarget(
          result.data,
          requestedTarget,
          requestedSolverMaterialId,
          requestedMaterialName,
        )) {
        throw new Error("The server response does not match the current exact Export request.");
      }
      setPreview(result.data);
    } catch (caught) {
      if (generation !== requestGeneration.current) return;
      setError(errorMessage(caught));
      setPreview(null);
    } finally {
      setBusy(false);
    }
  }

  return <section className="modeling-target-preview" aria-label="Target preview">
    <header>
      <div><p className="workspace-caption">Exact target preview</p><h2>Native preview</h2></div>
      <span className="status-chip warning">Reference / non-production</span>
    </header>
    <p>Select an explicit target. This only produces ephemeral text; it never creates a card, artifact, receipt, download, or Activity entry.</p>
    <div className="target-preview-controls">
      <label>Solver target
        <select aria-label="Solver target" value={targetSolver} onChange={(event) => changeTarget(event.target.value as "" | "abaqus" | "openradioss")}>
          <option value="">Select a target</option>
          {TARGETS.map((target) => <option key={target.value} value={target.value}>Reference target · {target.label}</option>)}
        </select>
      </label>
      <label>Solver material ID<input aria-label="Solver material ID" value={solverMaterialId} inputMode="numeric" onChange={(event) => { setSolverMaterialId(event.target.value); invalidateTargetPreview(); }} /></label>
      <label>Native material name<input aria-label="Native material name" value={materialName} onChange={(event) => { setMaterialName(event.target.value); invalidateTargetPreview(); }} /></label>
      <button className="ux-button primary" type="button" onClick={() => void generate()} disabled={!canGenerate}>{busy ? "Generating preview…" : "Generate preview"}</button>
    </div>
    {!exactRequirementsCurrent ? <p className="ux-notice" role="status">Current E-01–04 exact source prerequisites are required before a target preview can be generated.</p> : null}
    {error ? <p className="ux-notice error" role="alert">{error}</p> : null}
    {preview ? <div className="target-preview-result">
      <section aria-label="Target mapping preflight"><h3>Target mapping</h3><ul>{preview.mapping.items.map((item) => <li key={`${item.name}-${item.ir_path}`}><span className={`mapping-status ${item.status}`}>{item.status}</span><span><strong>{item.name}</strong><small>{item.detail}</small></span></li>)}</ul>{preview.acknowledgement_identity ? <><p className="ux-notice" role="status">Acknowledgement required before delivery. This preview only identifies the required UXC-06C2 delivery input; it does not record an acknowledgement.</p><details><summary>Evidence</summary><code>{preview.acknowledgement_identity}</code></details></> : null}</section>
      <section aria-label="Native preview"><h3>{preview.filename}</h3><pre>{preview.native_text}</pre></section>
    </div> : null}
    <p className="ux-notice" role="status">Deliver is unavailable — UXC-06C2 atomic delivery receipt pending.</p>
  </section>;
}
