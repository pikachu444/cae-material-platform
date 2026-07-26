import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  promoteModelToNeutralMaterial,
  promoteProcessingOutputToTabulatedPlasticity,
  type ApiConfig,
} from "./api";
import type { ExportPrerequisite } from "./modeling-export-eligibility";
import type { ModelingSessionEvent, ModelingSessionSummary } from "./modeling-session-context";
import type { CommonProcessingOutputResponse, PropertySetResponse } from "./types";

interface UpstreamModelRef {
  id: string;
  revisionId: string;
  revisionNo: number;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "The exact metal model chain could not be prepared.";
}

function sourcePrerequisitesCurrent(prerequisites: ExportPrerequisite[]): boolean {
  return prerequisites
    .filter((item) => !["Material Model IR", "Neutral representation", "Ephemeral target preview producer"].includes(item.label))
    .every((item) => item.status === "current");
}

function currentPropertySet(
  session: ModelingSessionSummary | null | undefined,
  propertySet: PropertySetResponse | undefined,
): boolean {
  return Boolean(session?.materialState && propertySet
    && propertySet.material_state_id === session.materialState.id
    && propertySet.current_revision.content.material_state_revision_id === session.materialState.revisionId);
}

function exactPromotionMatches(
  session: ModelingSessionSummary,
  output: CommonProcessingOutputResponse,
  propertySet: PropertySetResponse,
  model: Awaited<ReturnType<typeof promoteProcessingOutputToTabulatedPlasticity>>["data"],
): boolean {
  const content = model.current_revision.content;
  const projection = content.processing_projection;
  return content.material_id === session.material?.id
    && content.material_revision_id === session.material?.revisionId
    && content.material_state_id === session.materialState?.id
    && content.material_state_revision_id === session.materialState?.revisionId
    && content.property_set_id === propertySet.property_set_id
    && content.property_set_revision_id === propertySet.current_revision.id
    && projection?.output_id === output.processing_output_id
    && projection?.output_revision_id === output.current_revision.id
    && projection?.output_sha256 === `sha256:${output.output_sha256}`;
}

function ModelingMetalExportRecovery({
  config, session, output, propertySet, onSessionEvent,
}: {
  config: ApiConfig;
  session: ModelingSessionSummary;
  output: CommonProcessingOutputResponse;
  propertySet: PropertySetResponse;
  onSessionEvent?: (event: ModelingSessionEvent) => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [reason, setReason] = useState("Promote the selected exact fitted metal Processing Output for reference target preview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [promotedModel, setPromotedModel] = useState<UpstreamModelRef | null>(null);
  const exactSourceKey = useMemo(() => [
    session.material?.id,
    session.material?.revisionId,
    session.materialState?.id,
    session.materialState?.revisionId,
    output.processing_output_id,
    output.current_revision.id,
    propertySet.property_set_id,
    propertySet.current_revision.id,
  ].join("/"), [output.current_revision.id, output.processing_output_id, propertySet.current_revision.id, propertySet.property_set_id, session.material?.id, session.material?.revisionId, session.materialState?.id, session.materialState?.revisionId]);
  useEffect(() => {
    setPromotedModel(null);
    setError(null);
  }, [exactSourceKey]);
  const existingModel = session.materialModelIr ? {
    id: session.materialModelIr.id,
    revisionId: session.materialModelIr.revisionId,
    revisionNo: session.materialModelIr.revisionNo,
  } : null;
  const modelForNeutral = promotedModel ?? existingModel;
  const canPrepare = (modelForNeutral !== null || acknowledged) && reason.trim().length > 0 && !busy;

  function pinModel(model: UpstreamModelRef): void {
    setPromotedModel(model);
    onSessionEvent?.({ type: "SET_CURRENT", key: "materialModelIr", value: {
      id: model.id,
      revisionId: model.revisionId,
      label: "Selected metal tabulated-plasticity model",
      revisionNo: model.revisionNo,
    } });
  }

  async function promoteNeutral(model: UpstreamModelRef): Promise<void> {
    if (!session.material || !session.materialState) return;
    const neutral = await promoteModelToNeutralMaterial(config, "metal", {
      material_model_id: model.id,
      material_model_revision_id: model.revisionId,
      selection_reason: "Promote this exact selected hardening model for reference target preview.",
      change_reason: reason.trim(),
    });
    const embeddedIr = neutral.data.document.material_model_ir.model;
    const neutralSelection = neutral.data.document.candidate_selection.processing_output;
    if (embeddedIr.id !== neutral.data.neutral_material_id
      || embeddedIr.revision_id !== neutral.data.neutral_material_revision_id
      || neutral.data.document.sources.material?.id !== session.material.id
      || neutral.data.document.sources.material?.revision_id !== session.material.revisionId
      || neutral.data.document.sources.material_state?.id !== session.materialState.id
      || neutral.data.document.sources.material_state?.revision_id !== session.materialState.revisionId
      || neutralSelection?.id !== output.processing_output_id
      || neutralSelection?.revision_id !== output.current_revision.id) {
      throw new Error("The Neutral document does not prove the current exact model chain.");
    }
    // Keep the upstream model pointer distinct from Neutral's embedded IR.
    // The server resolves that embedded IR from the exact Neutral revision.
    onSessionEvent?.({ type: "SET_CURRENT", key: "neutralModel", value: {
      id: neutral.data.neutral_material_id,
      revisionId: neutral.data.neutral_material_revision_id,
      label: "Neutral Material with embedded canonical IR",
      revisionNo: neutral.data.revision_no,
    } });
  }

  async function prepare(): Promise<void> {
    if (!canPrepare || !session.material || !session.materialState) return;
    setBusy(true);
    setError(null);
    try {
      let model = modelForNeutral;
      if (!model) {
        const created = await promoteProcessingOutputToTabulatedPlasticity(config, output.processing_output_id, {
          material_state_id: session.materialState.id,
          property_set_revision_id: propertySet.current_revision.id,
          processing_output_revision_id: output.current_revision.id,
          acknowledge_bounded_extrapolation: true,
          change_reason: reason.trim(),
        });
        if (!exactPromotionMatches(session, output, propertySet, created.data)) {
          throw new Error("The promoted model does not match the current exact Output, Material, State, and Property Set revisions.");
        }
        model = {
          id: created.data.material_model_id,
          revisionId: created.data.current_revision.id,
          revisionNo: created.data.current_revision.revision_no,
        };
        // Preserve the successful immutable model even if Neutral promotion
        // fails. The next action retries Neutral only; it never creates a
        // duplicate model revision.
        pinModel(model);
      }
      await promoteNeutral(model);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return <section className="modeling-export-recovery" aria-label="Prepare exact metal export source">
    <h3>Prepare exact metal source</h3>
    <p>Promote only the selected Processing Output and its current Material, State, and Property Set revisions. This retains the bounded-extrapolation acknowledgement as immutable model evidence.</p>
    <label><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /> I acknowledge the selected bounded extrapolation for this reference model.</label>
    <label>Promotion reason<input aria-label="Metal promotion reason" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
    {modelForNeutral ? <p className="ux-notice" role="status">Exact model revision is pinned. Retry Neutral promotion without creating another model.</p> : null}
    <button className="button primary" type="button" disabled={!canPrepare} onClick={() => void prepare()}>{busy ? "Preparing exact source…" : modelForNeutral ? "Retry Neutral promotion" : "Prepare exact model and Neutral"}</button>
    {error ? <p className="ux-notice error" role="alert">{error}</p> : null}
  </section>;
}

export function ModelingExportPrerequisites({
  config,
  session,
  output,
  propertySet,
  prerequisites,
  onSessionEvent,
}: {
  config?: ApiConfig;
  session?: ModelingSessionSummary | null;
  output?: CommonProcessingOutputResponse;
  propertySet?: PropertySetResponse;
  prerequisites: ExportPrerequisite[];
  onSessionEvent?: (event: ModelingSessionEvent) => void;
}) {
  const outputStatus = prerequisites.find((item) => item.label === "Processing Output")?.status;
  const canPrepareMetal = session?.materialFamily === "metal"
    && sourcePrerequisitesCurrent(prerequisites)
    && Boolean(config && session && output && propertySet && currentPropertySet(session, propertySet));
  return (
    <section className="modeling-export-blocked" aria-label="Export prerequisites">
      <header>
        <div>
          <p className="workspace-caption">Exact Export</p>
          <h2>Exact target preview is gated</h2>
        </div>
        <span className="status-chip warning">Blocked</span>
      </header>
      <p>
        Native preview is produced only after the current source chain is proven by the server.
        A stale, different-material, or unverified output is never used as a fallback.
      </p>
      <ul className="modeling-export-prerequisite-list" aria-label="Exact Export prerequisite checklist">
        {prerequisites.map((item) => (
          <li key={item.label}>
            <span className={`mapping-status ${item.status}`}>{item.status.replaceAll("-", " ")}</span>
            <span><strong>{item.label}</strong><small>{item.detail}</small></span>
          </li>
        ))}
      </ul>
      <section className="modeling-export-lineage" aria-label="Exact Export lineage">
        <strong>Required lineage</strong>
        <ol>
          <li className={outputStatus === "current" ? "current" : outputStatus === "stale" ? "stale" : "missing"}>Processing Output</li>
          <li className="missing">Material Model IR</li>
          <li className="missing">Neutral representation</li>
          <li className="missing">Target mapping preflight and ephemeral native preview</li>
          <li className="missing">Reference delivery unavailable — UXC-06C2 atomic receipt pending</li>
        </ol>
        <small>Preview is <strong>reference / non-production</strong>. Review and Release remain <strong>Not configured</strong>; delivery has no primary action in this stage.</small>
      </section>
      {canPrepareMetal && config && session && output && propertySet
        ? <ModelingMetalExportRecovery config={config} session={session} output={output} propertySet={propertySet} onSessionEvent={onSessionEvent} />
        : session?.materialFamily !== "metal"
          ? <p className="ux-notice" role="status">Exact model promotion is Not configured for this material family. No substitute model or Neutral revision is selected.</p>
          : null}
    </section>
  );
}
