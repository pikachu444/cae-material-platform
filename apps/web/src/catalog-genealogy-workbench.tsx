import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
} from "./shared/api";
import {
  createMaterialLot,
  createProcessDefinition,
  createProcessRun,
  createStateGenealogy,
  getStateGenealogy,
  listMaterialLots,
  listProcessDefinitions,
  listProcessRuns,
  reviseStateGenealogy,
} from "./features/materials";
import {
  createSpecimenSource,
  getSpecimenSource,
  listSpecimensForMaterialState,
} from "./features/test-data";
import type {
  LotKind,
  BalanceBasis,
  MaterialLotResponse,
  MaterialStateResponse,
  ProcessDefinitionResponse,
  ProcessRunCreateInput,
  ProcessRunResponse,
  ProcessKind,
  StateGenealogyResponse,
} from "./features/materials/contracts";
import type {
  SpecimenResponse,
  SpecimenSourceResponse,
} from "./features/test-data/contracts";

interface FlowDraft {
  key: number;
  lotId: string;
  quantity: string;
  unit: string;
}

function initialFlow(key: number): FlowDraft {
  return { key, lotId: "", quantity: "", unit: "kg" };
}

function message(cause: unknown): string {
  return cause instanceof ApiError || cause instanceof Error
    ? cause.message
    : "Catalog genealogy request failed.";
}

function revisionEtag(value: StateGenealogyResponse): string {
  const revision = value.current_revision;
  return `"revision:${revision.revision_no}:sha256:${revision.content_hash}"`;
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
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
  const [runs, setRuns] = useState<ProcessRunResponse[]>([]);
  const [specimens, setSpecimens] = useState<SpecimenResponse[]>([]);
  const [specimenSources, setSpecimenSources] = useState<Record<string, SpecimenSourceResponse>>({});
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
  const [runCode, setRunCode] = useState("");
  const [runProcessId, setRunProcessId] = useState("");
  const [balanceBasis, setBalanceBasis] = useState<BalanceBasis>("mass");
  const [balanceTolerance, setBalanceTolerance] = useState("0.001");
  const [notAssessedReason, setNotAssessedReason] = useState("");
  const [inputFlows, setInputFlows] = useState<FlowDraft[]>([initialFlow(1)]);
  const [outputFlows, setOutputFlows] = useState<FlowDraft[]>([initialFlow(2)]);
  const [nextFlowKey, setNextFlowKey] = useState(3);
  const [sourceSpecimenId, setSourceSpecimenId] = useState("");
  const [sourceLotIds, setSourceLotIds] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [processResult, lotResult, genealogyResult, runResult, specimenResult] = await Promise.all([
        listProcessDefinitions(config),
        listMaterialLots(config, state.material_id),
        getStateGenealogy(config, state.material_state_id),
        listProcessRuns(config, state.material_state_id),
        listSpecimensForMaterialState(config, state.material_state_id),
      ]);
      setProcesses(processResult.data.items);
      setLots(lotResult.data.items);
      setGenealogy(genealogyResult.data);
      setRuns(runResult.data.items);
      setSpecimens(specimenResult.data.items);
      const sourceResults = await Promise.all(
        specimenResult.data.items.map(async (item) => ({
          specimenId: item.specimen_id,
          source: (await getSpecimenSource(config, item.specimen_id)).data,
        })),
      );
      setSpecimenSources(
        Object.fromEntries(
          sourceResults
            .filter((item) => item.source !== null)
            .map((item) => [item.specimenId, item.source as SpecimenSourceResponse]),
        ),
      );
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

  function updateFlow(
    role: "input" | "output",
    key: number,
    field: "lotId" | "quantity" | "unit",
    value: string,
  ): void {
    const setter = role === "input" ? setInputFlows : setOutputFlows;
    setter((items) => items.map((item) => (item.key === key ? { ...item, [field]: value } : item)));
  }

  function addFlow(role: "input" | "output"): void {
    const draft = initialFlow(nextFlowKey);
    setNextFlowKey((value) => value + 1);
    (role === "input" ? setInputFlows : setOutputFlows)((items) => [...items, draft]);
  }

  function removeFlow(role: "input" | "output", key: number): void {
    const setter = role === "input" ? setInputFlows : setOutputFlows;
    setter((items) => (items.length > 1 ? items.filter((item) => item.key !== key) : items));
  }

  async function addProcessRun(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const process = processes.find((item) => item.process_definition_id === runProcessId);
    if (!process) {
      setError("Select a governed Process revision for the Process Run.");
      return;
    }
    function encodeFlows(items: FlowDraft[]) {
      return items.map((item) => {
        const lot = lots.find((candidate) => candidate.material_lot_id === item.lotId);
        if (!lot || !item.quantity.trim()) {
          throw new Error("Every Process Run flow requires a Lot revision and quantity.");
        }
        return {
          material_lot_id: lot.material_lot_id,
          material_lot_revision_id: lot.current_revision.id,
          original_quantity: item.quantity.trim(),
          original_unit: item.unit,
        };
      });
    }
    setSaving(true);
    try {
      const input: ProcessRunCreateInput = {
        content: {
          process_definition_id: process.process_definition_id,
          process_definition_revision_id: process.current_revision.id,
          material_state_revision_id: state.current_revision.id,
          run_code: runCode.trim(),
          started_at: new Date().toISOString(),
          ended_at: null,
          operator_name: null,
          equipment_reference: null,
          balance_basis: balanceBasis,
          balance_tolerance_fraction: balanceBasis === "not_assessed" ? null : balanceTolerance,
          balance_not_assessed_reason:
            balanceBasis === "not_assessed" ? notAssessedReason.trim() : null,
          inputs: encodeFlows(inputFlows),
          outputs: encodeFlows(outputFlows),
          note: null,
        },
        change_reason: "Record exact Process Run Lot input/output flow",
      };
      await createProcessRun(config, state.material_state_id, input);
      setRunCode("");
      setInputFlows([initialFlow(nextFlowKey)]);
      setOutputFlows([initialFlow(nextFlowKey + 1)]);
      setNextFlowKey((value) => value + 2);
      await load();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSaving(false);
    }
  }

  async function addSpecimenSource(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const specimen = specimens.find((item) => item.specimen_id === sourceSpecimenId);
    const selectedLots = sourceLotIds
      .map((id) => lots.find((item) => item.material_lot_id === id))
      .filter((item): item is MaterialLotResponse => item !== undefined);
    if (!specimen || selectedLots.length === 0) {
      setError("Select a Specimen revision and at least one source Lot revision.");
      return;
    }
    if (specimenSources[specimen.specimen_id]) {
      setError("This Specimen already has a source genealogy head.");
      return;
    }
    setSaving(true);
    try {
      await createSpecimenSource(config, specimen.specimen_id, {
        content: {
          specimen_revision_id: specimen.current_revision.id,
          sources: selectedLots.map((lot) => ({
            material_lot_id: lot.material_lot_id,
            material_lot_revision_id: lot.current_revision.id,
            note: null,
          })),
          note: "Pinned from Material State genealogy workbench",
        },
        change_reason: "Pin exact source Lot revisions for Specimen",
      });
      setSourceLotIds([]);
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
      <div className="process-run-workbench">
        <div className="section-heading compact-heading">
          <div>
            <p className="eyebrow">Physical execution</p>
            <h4>Process Run input / output Lots</h4>
          </div>
          <span className="revision-chip">{runs.length} runs</span>
        </div>
        <p className="muted">
          Quantities retain the entered unit and an explicit normalized SI value. Add rows for
          merge or split operations; exact Lot revisions are pinned when you save.
        </p>
        <form className="process-run-form" onSubmit={addProcessRun}>
          <div className="genealogy-link-form">
            <label>
              Process revision
              <select
                aria-label="Process Run process"
                value={runProcessId}
                onChange={(event) => setRunProcessId(event.target.value)}
                required
              >
                <option value="">Select Process</option>
                {processes.map((item) => (
                  <option key={item.process_definition_id} value={item.process_definition_id}>
                    {item.current_revision.content.process_code} · r{item.current_revision.revision_no}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Run code
              <input aria-label="Process Run code" value={runCode} onChange={(event) => setRunCode(event.target.value)} required />
            </label>
            <label>
              Balance basis
              <select aria-label="Balance basis" value={balanceBasis} onChange={(event) => setBalanceBasis(event.target.value as BalanceBasis)}>
                <option value="mass">Mass</option>
                <option value="volume">Volume</option>
                <option value="count">Count</option>
                <option value="not_assessed">Not assessed</option>
              </select>
            </label>
            {balanceBasis === "not_assessed" ? (
              <label>
                Not-assessed reason
                <input aria-label="Not assessed reason" value={notAssessedReason} onChange={(event) => setNotAssessedReason(event.target.value)} required />
              </label>
            ) : (
              <label>
                Relative tolerance
                <input aria-label="Balance tolerance" type="number" min="0" max="1" step="0.000001" value={balanceTolerance} onChange={(event) => setBalanceTolerance(event.target.value)} required />
              </label>
            )}
          </div>
          {(["input", "output"] as const).map((role) => {
            const flows = role === "input" ? inputFlows : outputFlows;
            return (
              <fieldset className="flow-fieldset" key={role}>
                <legend>{role === "input" ? "Consumed Lots" : "Produced Lots"}</legend>
                {flows.map((flow, ordinal) => (
                  <div className="flow-row" key={flow.key}>
                    <span>{ordinal + 1}</span>
                    <select aria-label={`${role} Lot ${ordinal + 1}`} value={flow.lotId} onChange={(event) => updateFlow(role, flow.key, "lotId", event.target.value)} required>
                      <option value="">Select Lot revision</option>
                      {lots.map((item) => (
                        <option key={item.material_lot_id} value={item.material_lot_id}>
                          {item.current_revision.content.lot_code} · r{item.current_revision.revision_no}
                        </option>
                      ))}
                    </select>
                    <input aria-label={`${role} quantity ${ordinal + 1}`} type="number" min="0.000000001" step="any" placeholder="Quantity" value={flow.quantity} onChange={(event) => updateFlow(role, flow.key, "quantity", event.target.value)} required />
                    <select aria-label={`${role} unit ${ordinal + 1}`} value={flow.unit} onChange={(event) => updateFlow(role, flow.key, "unit", event.target.value)}>
                      <option value="kg">kg</option><option value="g">g</option><option value="mg">mg</option>
                      <option value="m3">m3</option><option value="L">L</option><option value="mL">mL</option><option value="cm3">cm3</option><option value="1">1</option>
                    </select>
                    <button className="text-button" type="button" onClick={() => removeFlow(role, flow.key)} disabled={flows.length === 1}>Remove</button>
                  </div>
                ))}
                <button className="text-button" type="button" onClick={() => addFlow(role)}>Add {role} Lot</button>
              </fieldset>
            );
          })}
          <button className="button primary" type="submit" disabled={saving || lots.length < 2 || processes.length === 0}>
            {saving ? "Saving…" : "Create Process Run revision 1"}
          </button>
        </form>
        <div className="process-run-list">
          {runs.map((run) => {
            const content = run.current_revision.content;
            return (
              <article className="genealogy-run-card" key={run.process_run_id}>
                <div><strong>{content.run_code}</strong><span>r{run.current_revision.revision_no}</span></div>
                <p>{content.inputs.length} input → {content.outputs.length} output</p>
                <small>
                  {content.balance
                    ? `${content.balance.input_total} → ${content.balance.output_total} ${content.inputs[0]?.normalized_unit ?? "SI"} · difference ${content.balance.relative_difference}`
                    : `Not assessed · ${content.balance_not_assessed_reason}`}
                </small>
              </article>
            );
          })}
        </div>
      </div>
      <div className="specimen-source-workbench">
        <div className="section-heading compact-heading">
          <div><p className="eyebrow">Testing genealogy</p><h4>Specimen source Lots</h4></div>
        </div>
        {specimens.length === 0 ? (
          <p className="muted">Create a Specimen in Test Data before pinning its source Lots.</p>
        ) : (
          <form className="genealogy-link-form" onSubmit={addSpecimenSource}>
            <label>
              Specimen revision
              <select aria-label="Source specimen" value={sourceSpecimenId} onChange={(event) => setSourceSpecimenId(event.target.value)} required>
                <option value="">Select Specimen</option>
                {specimens.map((item) => (
                  <option key={item.specimen_id} value={item.specimen_id} disabled={Boolean(specimenSources[item.specimen_id])}>
                    {item.current_revision.content.specimen_code} · r{item.current_revision.revision_no}{specimenSources[item.specimen_id] ? " · linked" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Source Lot revisions
              <select
                aria-label="Source Lots"
                multiple
                value={sourceLotIds}
                onChange={(event) => setSourceLotIds(Array.from(event.currentTarget.selectedOptions, (option) => option.value))}
                required
              >
                {lots.map((item) => (
                  <option key={item.material_lot_id} value={item.material_lot_id}>
                    {item.current_revision.content.lot_code} · r{item.current_revision.revision_no}
                  </option>
                ))}
              </select>
            </label>
            <button className="button primary" type="submit" disabled={saving}>Pin exact source revisions</button>
          </form>
        )}
        {Object.values(specimenSources).length > 0 ? (
          <div className="specimen-source-list" aria-label="Pinned Specimen source genealogy">
            {Object.values(specimenSources).map((source) => {
              const specimen = specimens.find((item) => item.specimen_id === source.specimen_id);
              return (
                <article className="genealogy-run-card" key={source.specimen_source_genealogy_id}>
                  <div>
                    <strong>{specimen?.current_revision.content.specimen_code ?? shortId(source.specimen_id)}</strong>
                    <span>source r{source.current_revision.revision_no}</span>
                  </div>
                  <p>Specimen r{specimen?.current_revision.revision_no ?? "?"} pins {source.current_revision.content.sources.length} source Lot revision(s)</p>
                  <ul className="specimen-source-lots">
                    {source.current_revision.content.sources.map((item) => {
                      const lot = lots.find((candidate) => candidate.material_lot_id === item.material_lot_id);
                      const exactHead = lot?.current_revision.id === item.material_lot_revision_id;
                      return (
                        <li key={item.material_lot_revision_id}>
                          <strong>{lot?.current_revision.content.lot_code ?? shortId(item.material_lot_id)}</strong>
                          <span>{exactHead ? `exact r${lot.current_revision.revision_no}` : `revision ${shortId(item.material_lot_revision_id)}`}</span>
                        </li>
                      );
                    })}
                  </ul>
                </article>
              );
            })}
          </div>
        ) : null}
      </div>
    </section>
  );
}
