import { useState } from "react";

import {
  ApiError,
  type ApiConfig,
} from "./shared/api";
import {
  deliverExactTargetPreview,
  type TargetDeliveryResponse,
  type TargetPreviewResponse,
} from "./features/modeling";

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Delivery failed.";
}

function deliveredAt(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function TargetDeliveryAction({ config, preview, source, onDelivered }: {
  config: ApiConfig;
  preview: TargetPreviewResponse;
  source: { processingOutputId: string; processingOutputRevisionId: string; neutralMaterialId: string; neutralMaterialRevisionId: string };
  onDelivered?: () => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [delivery, setDelivery] = useState<TargetDeliveryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requiresAck = Boolean(preview.acknowledgement_identity);

  async function deliver(): Promise<void> {
    setBusy(true); setError(null);
    try {
      const result = await deliverExactTargetPreview(config, {
        processing_output_id: source.processingOutputId,
        processing_output_revision_id: source.processingOutputRevisionId,
        neutral_material_id: source.neutralMaterialId,
        neutral_material_revision_id: source.neutralMaterialRevisionId,
        target: {
          solver: preview.target.solver,
          version: preview.target.version,
          unit_system: preview.target.unit_system,
        },
        solver_material_id: preview.target.solver_material_id,
        material_name: preview.target.material_name, preview_identity: preview.preview_identity,
        expected_mapping_report_sha256: preview.mapping_report_sha256,
        acknowledgement_identity: requiresAck && acknowledged ? preview.acknowledgement_identity ?? undefined : undefined,
      });
      if (result.data.delivery_identity !== preview.preview_identity) throw new Error("Delivery receipt is not for the current exact preview.");
      setDelivery(result.data);
      onDelivered?.();
    } catch (caught) { setError(message(caught)); } finally { setBusy(false); }
  }

  return <section className="target-delivery-action" aria-label="Target delivery">
    {requiresAck && !delivery ? <label className="delivery-acknowledgement"><input aria-label="Acknowledge mapped approximations" type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)}/>I acknowledge the mapping warnings for this exact preview.</label> : null}
    {!delivery ? <button className="ux-button primary" type="button" disabled={busy || (requiresAck && !acknowledged)} onClick={() => void deliver()}>{busy ? "Creating solver card…" : "Create solver card"}</button> : null}
    {error ? <p className="ux-notice error" role="alert">{error}</p> : null}
    {delivery ? <p className="ux-notice success" role="status"><strong>Solver card delivered</strong> · <a href={delivery.links.preview}>{delivery.filename}</a> · {deliveredAt(delivery.occurred_at)} · <a href={delivery.links.receipt}>Receipt</a></p> : null}
  </section>;
}
