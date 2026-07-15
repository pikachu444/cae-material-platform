import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createMaterialLot,
  createProcessDefinition,
  createStateGenealogy,
  getStateGenealogy,
  listMaterialLots,
  listProcessDefinitions,
  reviseStateGenealogy,
} from "./api";
import type {
  LotKind,
  MaterialLotResponse,
  MaterialStateResponse,
  ProcessDefinitionResponse,
  ProcessKind,
  StateGenealogyResponse,
} from "./types";

function message(cause: unknown): string {
  return cause instanceof ApiError || cause instanceof Error
    ? cause.message
    : "Catalog genealogy request failed.";
}

function revisionEtag(value: StateGenealogyResponse): string {
  const revision = value.current_revision;
  return `"revision:${revision.revision_no}:sha256:${revision.content_hash}"`;
}

export function CatalogGenealogyWorkbench({
  config,
  state,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
}) {
  const [processes, setProcesses] = useState<ProcessDefinitionResponse[]>([]);
  const [lots, setLots] = useState<MaterialLotResponse[]>([]);
  const [genealogy, setGenealogy] = useState<StateGenealogyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manufacturingId, setManufacturingId] = useState("");
  const [heatTreatmentId, setHeatTreatmentId] = useState("");
  const [lotId, setLotId] = useState("");
  const [note, setNote] = useState("");
  const [processKind, setProcessKind] = useState<ProcessKind>("manufacturing");
  const [processCode, setProcessCode] = useState("");
  const [processName, setProcessName] = useState("");
  const [lotCode, setLotCode] = useState("");
  const [lotKind, setLotKind] = useState<LotKind>("batch");
  const [manufacturer, setManufacturer] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [processResult, lotResult, genealogyResult] = await Promise.all([
        listProcessDefinitions(config),
        listMaterialLots(config, state.material_id),
        getStateGenealogy(config, state.material_state_id),
      ]);
      setProcesses(processResult.data.items);
      setLots(lotResult.data.items);
      setGenealogy(genealogyResult.data);
      const content = genealogyResult.data?.current_revision.content;
      setManufacturingId(content?.manufacturing_process_id ?? "");
      setHeatTreatmentId(content?.heat_treatment_process_id ?? "");
      setLotId(content?.material_lot_id ?? "");
      setNote(content?.note ?? "");
      setError(null);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setLoading(false);
    }
  }, [config, state.material_id, state.material_state_id]);

  useEffect(() => {
    void load();
  }, [load]);

  const manufacturingProcesses = useMemo(
    () => processes.filter((item) => item.current_revision.content.kind === "manufacturing"),
    [processes],
  );
  const heatProcesses = useMemo(
    () => processes.filter((item) => item.current_revision.content.kind === "heat_treatment"),
    [processes],
  );

  async function addProcess(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSaving(true);
    try {
      const created = await createProcessDefinition(config, {
        classification: state.current_revision.classification,
        content: {
          process_code: processCode.trim(),
          name: processName.trim(),
          kind: processKind,
          description: null,
        },
        change_reason: "Register governed process for Material State genealogy",
      });
      setProcessCode("");
      setProcessName("");
      await load();
      if (processKind === "manufacturing") {
        setManufacturingId(created.data.process_definition_id);
      } else if (processKind === "heat_treatment") {
        setHeatTreatmentId(created.data.process_definition_id);
      }
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSaving(false);
    }
  }

  async function addLot(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSaving(true);
    try {
      const created = await createMaterialLot(config, state.material_id, {
        content: {
          material_revision_id: state.current_revision.content.material_revision_id,
          lot_code: lotCode.trim(),
          kind: lotKind,
          manufacturer: manufacturer.trim() || null,
          supplier: null,
          description: null,
        },
        change_reason: "Register Lot/Batch for Material State genealogy",
      });
      setLotCode("");
      setManufacturer("");
      await load();
      setLotId(created.data.material_lot_id);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSaving(false);
    }
  }

  async function saveLinks(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const manufacturing = processes.find(
      (item) => item.process_definition_id === manufacturingId,
    );
    const heat = processes.find((item) => item.process_definition_id === heatTreatmentId);
    const lot = lots.find((item) => item.material_lot_id === lotId);
    if (!manufacturing && !heat && !lot) {
      setError("Select at least one governed Process or Lot/Batch revision.");
      return;
    }
    const input = {
      content: {
        material_state_revision_id: state.current_revision.id,
        manufacturing_process_id: manufacturing?.process_definition_id ?? null,
        manufacturing_process_revision_id: manufacturing?.current_revision.id ?? null,
        heat_treatment_process_id: heat?.process_definition_id ?? null,
        heat_treatment_process_revision_id: heat?.current_revision.id ?? null,
        material_lot_id: lot?.material_lot_id ?? null,
        material_lot_revision_id: lot?.current_revision.id ?? null,
        note: note.trim() || null,
      },
      change_reason: genealogy
        ? "Revise exact Material State genealogy links"
        : "Establish exact Material State genealogy links",
    };
    setSaving(true);
    try {
      if (genealogy) {
        await reviseStateGenealogy(
          config,
          genealogy.state_genealogy_id,
          revisionEtag(genealogy),
          input,
        );
      } else {
        await createStateGenealogy(config, state.material_state_id, input);
      }
      await load();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="property-summary genealogy-workbench">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">Catalog genealogy</p>
          <h4>Exact Process and Lot revision links</h4>
        </div>
        {genealogy ? (
          <span className="revision-chip">r{genealogy.current_revision.revision_no}</span>
        ) : null}
      </div>
      <p className="muted">
        Governed identities are separate from immutable revisions. Existing free-text State
        fields remain as historical source metadata.
      </p>
      {loading ? <p className="muted">Loading genealogy…</p> : null}
      {error ? <p className="error-notice">{error}</p> : null}
      <form className="genealogy-link-form" onSubmit={saveLinks}>
        <label>
          Manufacturing process
          <select value={manufacturingId} onChange={(event) => setManufacturingId(event.target.value)}>
            <option value="">Not linked</option>
            {manufacturingProcesses.map((item) => (
              <option key={item.process_definition_id} value={item.process_definition_id}>
                {item.current_revision.content.process_code} · {item.current_revision.content.name} · r{item.current_revision.revision_no}
              </option>
            ))}
          </select>
        </label>
        <label>
          Heat-treatment process
          <select value={heatTreatmentId} onChange={(event) => setHeatTreatmentId(event.target.value)}>
            <option value="">Not linked</option>
            {heatProcesses.map((item) => (
              <option key={item.process_definition_id} value={item.process_definition_id}>
                {item.current_revision.content.process_code} · {item.current_revision.content.name} · r{item.current_revision.revision_no}
              </option>
            ))}
          </select>
        </label>
        <label>
          Lot / Batch
          <select value={lotId} onChange={(event) => setLotId(event.target.value)}>
            <option value="">Not linked</option>
            {lots.map((item) => (
              <option key={item.material_lot_id} value={item.material_lot_id}>
                {item.current_revision.content.lot_code} · {item.current_revision.content.kind} · r{item.current_revision.revision_no}
              </option>
            ))}
          </select>
        </label>
        <label>Genealogy note<input value={note} onChange={(event) => setNote(event.target.value)} /></label>
        <button className="button primary" type="submit" disabled={saving || loading}>
          {saving ? "Saving…" : genealogy ? "Append genealogy revision" : "Establish genealogy"}
        </button>
      </form>
      <div className="genealogy-create-grid">
        <form className="mini-form" onSubmit={addProcess}>
          <strong>Register Process</strong>
          <select value={processKind} onChange={(event) => setProcessKind(event.target.value as ProcessKind)}>
            <option value="manufacturing">Manufacturing</option>
            <option value="heat_treatment">Heat treatment</option>
          </select>
          <input aria-label="Process code" placeholder="Process code" value={processCode} onChange={(event) => setProcessCode(event.target.value)} required />
          <input aria-label="Process name" placeholder="Process name" value={processName} onChange={(event) => setProcessName(event.target.value)} required />
          <button className="text-button" type="submit" disabled={saving}>Create revision 1</button>
        </form>
        <form className="mini-form" onSubmit={addLot}>
          <strong>Register Lot / Batch</strong>
          <select value={lotKind} onChange={(event) => setLotKind(event.target.value as LotKind)}>
            <option value="batch">Batch</option>
            <option value="lot">Lot</option>
          </select>
          <input aria-label="Lot code" placeholder="Lot / batch code" value={lotCode} onChange={(event) => setLotCode(event.target.value)} required />
          <input aria-label="Manufacturer" placeholder="Manufacturer (optional)" value={manufacturer} onChange={(event) => setManufacturer(event.target.value)} />
          <button className="text-button" type="submit" disabled={saving}>Create revision 1</button>
        </form>
      </div>
    </section>
  );
}
