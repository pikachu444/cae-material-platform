import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import "./features/test-data/ui/canonical-test-data-workbench.css";

import {
  ApiError,
  type ApiConfig,
  createInstrument,
  createInstrumentCalibration,
  createTestCampaign,
  createTestCondition,
  createTestRunContext,
  getTestRunContext,
  listInstrumentCalibrations,
  listInstruments,
  listTestCampaigns,
  listTestMethods,
  listTestRunsForMaterialState,
} from "./api";
import type {
  InstrumentCalibrationResponse,
  InstrumentResponse,
  MaterialStateResponse,
  StandardConformance,
  TestCampaignResponse,
  TestMethodResponse,
  TestRunContextResponse,
  TestRunResponse,
} from "./types";

function message(cause: unknown): string {
  return cause instanceof ApiError || cause instanceof Error
    ? cause.message
    : "Test execution context request failed.";
}

function localDateTime(value: Date): string {
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

export function TestContextWorkbench({
  config,
  state,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
}) {
  const now = useMemo(() => new Date(), []);
  const nextYear = useMemo(() => new Date(now.getTime() + 365 * 86_400_000), [now]);
  const [methods, setMethods] = useState<TestMethodResponse[]>([]);
  const [runs, setRuns] = useState<TestRunResponse[]>([]);
  const [campaigns, setCampaigns] = useState<TestCampaignResponse[]>([]);
  const [instruments, setInstruments] = useState<InstrumentResponse[]>([]);
  const [calibrations, setCalibrations] = useState<InstrumentCalibrationResponse[]>([]);
  const [contexts, setContexts] = useState<Record<string, TestRunContextResponse>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [campaignMethodId, setCampaignMethodId] = useState("");
  const [campaignCode, setCampaignCode] = useState("");
  const [campaignName, setCampaignName] = useState("");
  const [conformance, setConformance] = useState<StandardConformance>("conformant");
  const [designation, setDesignation] = useState("ISO 6892-1");
  const [edition, setEdition] = useState("2019");
  const [deviation, setDeviation] = useState("");

  const [instrumentCode, setInstrumentCode] = useState("");
  const [instrumentName, setInstrumentName] = useState("");
  const [serialNumber, setSerialNumber] = useState("");
  const [selectedInstrumentId, setSelectedInstrumentId] = useState("");
  const [calibrationCode, setCalibrationCode] = useState("");
  const [certificate, setCertificate] = useState("");
  const [provider, setProvider] = useState("");
  const [validFrom, setValidFrom] = useState(localDateTime(now));
  const [validUntil, setValidUntil] = useState(localDateTime(nextYear));

  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [selectedCalibrationId, setSelectedCalibrationId] = useState("");
  const [temperature, setTemperature] = useState("296.15");
  const [loadingRate, setLoadingRate] = useState("2");
  const [orientation, setOrientation] = useState("rolling");
  const [medium, setMedium] = useState("air");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [methodResult, runResult, campaignResult, instrumentResult] = await Promise.all([
        listTestMethods(config),
        listTestRunsForMaterialState(config, state.material_state_id),
        listTestCampaigns(config),
        listInstruments(config),
      ]);
      setMethods(methodResult.data.items);
      setRuns(runResult.data.items);
      setCampaigns(campaignResult.data.items);
      setInstruments(instrumentResult.data.items);
      const contextPairs = await Promise.all(
        runResult.data.items.map(async (run) => [run.test_run_id, (await getTestRunContext(config, run.test_run_id)).data] as const),
      );
      setContexts(Object.fromEntries(contextPairs.filter((pair): pair is readonly [string, TestRunContextResponse] => pair[1] !== null)));
      setCampaignMethodId((value) => value || methodResult.data.items[0]?.test_method_id || "");
      setSelectedRunId((value) => value || runResult.data.items[0]?.test_run_id || "");
      setSelectedInstrumentId((value) => value || instrumentResult.data.items[0]?.resource_id || "");
    } catch (cause) {
      setError(message(cause));
    } finally {
      setLoading(false);
    }
  }, [config, state.material_state_id]);

  useEffect(() => void refresh(), [refresh]);

  useEffect(() => {
    if (!selectedInstrumentId) {
      setCalibrations([]);
      return;
    }
    void listInstrumentCalibrations(config, selectedInstrumentId)
      .then((result) => {
        setCalibrations(result.data.items);
        setSelectedCalibrationId((value) => value || result.data.items[0]?.resource_id || "");
      })
      .catch((cause: unknown) => setError(message(cause)));
  }, [config, selectedInstrumentId]);

  const selectedRun = runs.find((item) => item.test_run_id === selectedRunId);
  const selectedMethod = methods.find((item) => item.test_method_id === campaignMethodId);
  const selectedInstrument = instruments.find((item) => item.resource_id === selectedInstrumentId);
  const eligibleCampaigns = campaigns.filter(
    (item) =>
      selectedRun &&
      item.current_revision.content.test_method_id === selectedRun.current_revision.content.test_method_id &&
      item.current_revision.content.test_method_revision_id === selectedRun.current_revision.content.test_method_revision_id,
  );
  const eligibleCalibrations = calibrations.filter((item) => {
    if (!selectedRun) return false;
    const content = item.current_revision.content;
    const performed = Date.parse(selectedRun.current_revision.content.performed_at);
    return (
      content.result !== "failed" &&
      content.instrument_revision_id === selectedInstrument?.current_revision.id &&
      Date.parse(content.valid_from) <= performed &&
      performed < Date.parse(content.valid_until)
    );
  });

  async function addCampaign(event: FormEvent) {
    event.preventDefault();
    if (!selectedMethod) return;
    setSaving(true);
    setError(null);
    try {
      await createTestCampaign(config, {
        test_method_id: selectedMethod.test_method_id,
        test_method_revision_id: selectedMethod.current_revision.id,
        campaign_code: campaignCode,
        name: campaignName,
        objective: "Characterize material response for the selected State",
        population_description: "Explicitly governed specimen population",
        planned_specimen_count: 3,
        standard_conformance: conformance,
        standard_designation: conformance === "not_claimed" ? null : designation,
        standard_edition: conformance === "not_claimed" ? null : edition,
        standard_deviation_reason: conformance === "deviation_approved" ? deviation : null,
        reference_only: true,
      });
      setCampaignCode("");
      setCampaignName("");
      setNotice("Campaign revision 1 created with an exact Test Method revision pin.");
      await refresh();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSaving(false);
    }
  }

  async function addInstrument(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      const result = await createInstrument(config, state.current_revision.classification, {
        instrument_code: instrumentCode,
        name: instrumentName,
        serial_number: serialNumber,
        manufacturer: null,
        model: null,
        location: null,
        description: null,
      });
      setSelectedInstrumentId(result.data.resource_id);
      setNotice("Instrument revision 1 created.");
      await refresh();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSaving(false);
    }
  }

  async function addCalibration(event: FormEvent) {
    event.preventDefault();
    if (!selectedInstrument) return;
    setSaving(true);
    try {
      await createInstrumentCalibration(config, selectedInstrument.resource_id, {
        instrument_revision_id: selectedInstrument.current_revision.id,
        calibration_code: calibrationCode,
        certificate_reference: certificate,
        provider,
        calibrated_at: new Date(validFrom).toISOString(),
        valid_from: new Date(validFrom).toISOString(),
        valid_until: new Date(validUntil).toISOString(),
        result: "passed",
        limitation_note: null,
      });
      setNotice("Calibration recorded; overlapping usable intervals are rejected.");
      const result = await listInstrumentCalibrations(config, selectedInstrument.resource_id);
      setCalibrations(result.data.items);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSaving(false);
    }
  }

  async function bindContext(event: FormEvent) {
    event.preventDefault();
    const campaign = eligibleCampaigns.find((item) => item.resource_id === selectedCampaignId);
    const calibration = eligibleCalibrations.find((item) => item.resource_id === selectedCalibrationId);
    if (!selectedRun || !campaign || !calibration || !selectedInstrument) {
      setError("Select an exact Campaign and a calibration valid at the Test Run execution time.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const condition = await createTestCondition(config, {
        test_method_id: selectedRun.current_revision.content.test_method_id,
        test_method_revision_id: selectedRun.current_revision.content.test_method_revision_id,
        captured_at: selectedRun.current_revision.content.performed_at,
        temperature_setpoint_k: null,
        temperature_observed_k: temperature,
        humidity_setpoint_pct: null,
        humidity_observed_pct: null,
        loading_rate_value: loadingRate,
        loading_rate_unit: "mm/min",
        orientation,
        medium,
        note: null,
      });
      await createTestRunContext(config, selectedRun.test_run_id, {
        test_run_revision_id: selectedRun.current_revision.id,
        test_campaign_id: campaign.resource_id,
        test_campaign_revision_id: campaign.current_revision.id,
        test_condition_id: condition.data.resource_id,
        test_condition_revision_id: condition.data.current_revision.id,
        instrument_id: selectedInstrument.resource_id,
        instrument_revision_id: selectedInstrument.current_revision.id,
        calibration_id: calibration.resource_id,
        calibration_revision_id: calibration.current_revision.id,
        note: null,
      });
      setNotice("Test Run now pins exact Campaign, Condition, Instrument and calibration revisions.");
      await refresh();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="property-summary test-context-workbench">
      <div className="section-heading compact-heading">
        <div><p className="eyebrow">Test execution governance</p><h4>Campaign, Instrument and exact conditions</h4></div>
        <span className="revision-chip">{Object.keys(contexts).length}/{runs.length} bound</span>
      </div>
      <p className="muted">A completed Test Run remains pinned to the calibration and Method revision that were valid when it was performed. No current-head lookup is used.</p>
      {loading ? <p className="muted">Loading execution context…</p> : null}
      {error ? <p className="error-notice">{error}</p> : null}
      {notice ? <p className="success-notice">{notice}</p> : null}
      <div className="genealogy-create-grid">
        <form className="mini-form" onSubmit={addCampaign}>
          <strong>1. Register Campaign</strong>
          <select aria-label="Campaign method" value={campaignMethodId} onChange={(event) => setCampaignMethodId(event.target.value)} required>
            <option value="">Select Test Method</option>
            {methods.map((item) => <option key={item.test_method_id} value={item.test_method_id}>{item.current_revision.content.display_name} · r{item.current_revision.revision_no}</option>)}
          </select>
          <input aria-label="Campaign code" placeholder="Campaign code" value={campaignCode} onChange={(event) => setCampaignCode(event.target.value)} required />
          <input aria-label="Campaign name" placeholder="Campaign name" value={campaignName} onChange={(event) => setCampaignName(event.target.value)} required />
          <select aria-label="Standard conformance" value={conformance} onChange={(event) => setConformance(event.target.value as StandardConformance)}>
            <option value="conformant">Conformant</option><option value="deviation_approved">Approved deviation</option><option value="not_claimed">Standard not claimed</option>
          </select>
          {conformance !== "not_claimed" ? <><input aria-label="Standard designation" value={designation} onChange={(event) => setDesignation(event.target.value)} required /><input aria-label="Standard edition" value={edition} onChange={(event) => setEdition(event.target.value)} required /></> : null}
          {conformance === "deviation_approved" ? <input aria-label="Approved deviation reason" value={deviation} onChange={(event) => setDeviation(event.target.value)} required /> : null}
          <button className="text-button" type="submit" disabled={saving}>Create Campaign r1</button>
        </form>
        <form className="mini-form" onSubmit={addInstrument}>
          <strong>2. Register Instrument</strong>
          <input aria-label="Instrument code" placeholder="Instrument code" value={instrumentCode} onChange={(event) => setInstrumentCode(event.target.value)} required />
          <input aria-label="Instrument name" placeholder="Instrument name" value={instrumentName} onChange={(event) => setInstrumentName(event.target.value)} required />
          <input aria-label="Serial number" placeholder="Serial number" value={serialNumber} onChange={(event) => setSerialNumber(event.target.value)} required />
          <button className="text-button" type="submit" disabled={saving}>Create Instrument r1</button>
        </form>
        <form className="mini-form" onSubmit={addCalibration}>
          <strong>3. Record Calibration</strong>
          <select aria-label="Calibration instrument" value={selectedInstrumentId} onChange={(event) => { setSelectedInstrumentId(event.target.value); setSelectedCalibrationId(""); }} required>
            <option value="">Select Instrument</option>
            {instruments.map((item) => <option key={item.resource_id} value={item.resource_id}>{item.current_revision.content.instrument_code} · r{item.current_revision.revision_no}</option>)}
          </select>
          <input aria-label="Calibration code" placeholder="Calibration code" value={calibrationCode} onChange={(event) => setCalibrationCode(event.target.value)} required />
          <input aria-label="Certificate reference" placeholder="Certificate reference" value={certificate} onChange={(event) => setCertificate(event.target.value)} required />
          <input aria-label="Calibration provider" placeholder="Calibration provider" value={provider} onChange={(event) => setProvider(event.target.value)} required />
          <label>Valid from<input type="datetime-local" value={validFrom} onChange={(event) => setValidFrom(event.target.value)} required /></label>
          <label>Valid until<input type="datetime-local" value={validUntil} onChange={(event) => setValidUntil(event.target.value)} required /></label>
          <button className="text-button" type="submit" disabled={saving}>Record calibration</button>
        </form>
        <form className="mini-form" onSubmit={bindContext}>
          <strong>4. Bind exact Run context</strong>
          <select aria-label="Context Test Run" value={selectedRunId} onChange={(event) => { setSelectedRunId(event.target.value); setSelectedCampaignId(""); setSelectedCalibrationId(""); }} required>
            <option value="">Select Test Run</option>
            {runs.map((item) => <option key={item.test_run_id} value={item.test_run_id}>{item.current_revision.content.run_label} · r{item.current_revision.revision_no}{contexts[item.test_run_id] ? " · bound" : ""}</option>)}
          </select>
          <select aria-label="Context Campaign" value={selectedCampaignId} onChange={(event) => setSelectedCampaignId(event.target.value)} required>
            <option value="">Select matching Campaign</option>
            {eligibleCampaigns.map((item) => <option key={item.resource_id} value={item.resource_id}>{item.current_revision.content.campaign_code} · exact r{item.current_revision.revision_no}</option>)}
          </select>
          <select aria-label="Context calibration" value={selectedCalibrationId} onChange={(event) => setSelectedCalibrationId(event.target.value)} required>
            <option value="">Select calibration valid at Run time</option>
            {eligibleCalibrations.map((item) => <option key={item.resource_id} value={item.resource_id}>{item.current_revision.content.calibration_code} · exact r{item.current_revision.revision_no}</option>)}
          </select>
          {selectedRun && calibrations.length > 0 && eligibleCalibrations.length === 0 ? <p className="error-notice">No selected Instrument calibration is valid at {new Date(selectedRun.current_revision.content.performed_at).toLocaleString()}.</p> : null}
          <input aria-label="Observed temperature K" value={temperature} onChange={(event) => setTemperature(event.target.value)} required />
          <input aria-label="Loading rate mm/min" value={loadingRate} onChange={(event) => setLoadingRate(event.target.value)} required />
          <input aria-label="Specimen orientation" value={orientation} onChange={(event) => setOrientation(event.target.value)} required />
          <input aria-label="Test medium" value={medium} onChange={(event) => setMedium(event.target.value)} required />
          <button className="button primary" type="submit" disabled={saving || Boolean(selectedRunId && contexts[selectedRunId])}>{selectedRunId && contexts[selectedRunId] ? "Context already bound" : "Capture and bind revisions"}</button>
        </form>
      </div>
      <div className="process-run-list" aria-label="Bound Test Run contexts">
        {runs.filter((run) => contexts[run.test_run_id]).map((run) => {
          const context = contexts[run.test_run_id];
          return <article className="genealogy-run-card" key={run.test_run_id}><div><strong>{run.current_revision.content.run_label}</strong><span className="revision-chip">context r{context.current_revision.revision_no}</span></div><small>Run exact r{run.current_revision.revision_no} · Campaign revision {context.current_revision.content.test_campaign_revision_id.slice(0, 8)} · Calibration revision {context.current_revision.content.calibration_revision_id.slice(0, 8)}</small></article>;
        })}
      </div>
    </section>
  );
}
