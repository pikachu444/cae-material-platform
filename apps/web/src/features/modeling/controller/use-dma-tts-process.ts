import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { listGovernedImportProfiles } from "../../test-data";
import type { CanonicalTestDataDocumentResponse, GovernedImportProfileResponse } from "../../test-data/contracts";
import type { ApiConfig } from "../../../shared/api";
import {
  createDmaTts,
  dmaTtsErrorMessage,
  getDmaTtsRevision,
  recommendDmaTts,
  recommendMultiDmaTts,
} from "../api/dma-tts-api";
import { getProcessedLinearViscoelasticFitInput } from "../api/linear-viscoelastic-calibration-api";
import type {
  CreateDmaTtsResponse,
  DmaTtsInputMode,
  DmaTtsMultiRecommendationResponse,
  DmaTtsOutputPin,
  DmaTtsPartition,
  DmaTtsReadResponse,
  DmaTtsRecommendationResponse,
  DmaTtsSourceClassification,
} from "../model/dma-tts-contracts";
import {
  buildCreateDmaTtsRequest,
  classifyDmaTtsSource,
  dmaTtsDraftReady,
  draftFromDmaTtsRecommendation,
  exactDmaTtsPins,
  type DmaTtsDraft,
} from "../model/dma-tts-draft";
import type { ProcessedLinearViscoelasticFitInput } from "../model/linear-viscoelastic-calibration-contracts";

export type DmaTtsProcessStatus =
  | "loading"
  | "ready"
  | "preparing"
  | "saving"
  | "saved"
  | "read_error"
  | "save_outcome_unknown"
  | "error";

interface UseDmaTtsProcessInput {
  config: ApiConfig;
  testData: CanonicalTestDataDocumentResponse;
  sourceDocument: Record<string, unknown>;
  sourceLabel: string;
  initialOutput?: { id: string; revisionId: string; contentSha256: string };
  onSaved: (created: CreateDmaTtsResponse, readBack?: DmaTtsReadResponse) => Promise<void> | void;
}

function exactPinEqual(
  left: { document_id: string; revision_id: string; content_sha256: string },
  right: { document_id: string; revision_id: string; content_sha256: string },
): boolean {
  return left.document_id === right.document_id
    && left.revision_id === right.revision_id
    && left.content_sha256 === right.content_sha256;
}

function outputPinEqual(left: DmaTtsOutputPin, right: DmaTtsOutputPin): boolean {
  return left.output_id === right.output_id
    && left.revision_id === right.revision_id
    && left.content_sha256 === right.content_sha256;
}

function validateReadBack(
  readBack: DmaTtsReadResponse,
  created: CreateDmaTtsResponse,
  pins: { test_data: { document_id: string; revision_id: string; content_sha256: string }; import_profile: { profile_id: string; revision_id: string; content_sha256: string } },
  inputMode: DmaTtsInputMode,
): DmaTtsReadResponse {
  if (!outputPinEqual(readBack.output, created.master_curve_output)
    || readBack.input_mode !== inputMode
    || !exactPinEqual(readBack.test_data, pins.test_data)
    || readBack.import_profile.document_id !== pins.import_profile.profile_id
    || readBack.import_profile.revision_id !== pins.import_profile.revision_id
    || readBack.import_profile.content_sha256 !== pins.import_profile.content_sha256
    || !Array.isArray(readBack.isotherms)) {
    throw new Error("The saved DMA response did not read back with its exact source and profile pins.");
  }
  return readBack;
}

function sourceReason(classification: DmaTtsSourceClassification): string {
  return classification.kind === "blocked" ? classification.reason : "";
}

export function useDmaTtsProcess({
  config,
  testData,
  sourceDocument,
  sourceLabel,
  initialOutput,
  onSaved,
}: UseDmaTtsProcessInput) {
  const [profile, setProfile] = useState<GovernedImportProfileResponse | undefined>();
  const [pins, setPins] = useState<ReturnType<typeof exactDmaTtsPins> | null>(null);
  const [classification, setClassification] = useState<DmaTtsSourceClassification>({ kind: "blocked", reason: "Loading exact DMA source…" });
  const [status, setStatus] = useState<DmaTtsProcessStatus>("loading");
  const [error, setError] = useState("");
  const [recommendation, setRecommendation] = useState<DmaTtsRecommendationResponse | DmaTtsMultiRecommendationResponse | null>(null);
  const [draft, setDraft] = useState<DmaTtsDraft | null>(null);
  const [readBack, setReadBack] = useState<DmaTtsReadResponse | null>(null);
  const [output, setOutput] = useState<DmaTtsOutputPin | null>(null);
  const [createdOutput, setCreatedOutput] = useState<CreateDmaTtsResponse | null>(null);
  const [fitInput, setFitInput] = useState<ProcessedLinearViscoelasticFitInput | null>(null);
  const [selectedReferenceSweepOrdinal, setSelectedReferenceSweepOrdinal] = useState<number | null>(null);
  const [visibleSweepOrdinals, setVisibleSweepOrdinals] = useState<number[]>([]);
  const generation = useRef(0);
  const sourceKey = `${testData.test_data_document_id}:${testData.current_revision.id}:${testData.current_revision.content_hash}`;
  const source = classification.kind === "fixed" || classification.kind === "multi" ? classification.source : null;
  const inputMode: DmaTtsInputMode | null = classification.kind === "fixed"
    ? "fixed_frequency_temperature_sweep"
    : classification.kind === "multi" ? "multi_frequency_isotherms" : null;
  const label = `${sourceLabel} · ${inputMode === "fixed_frequency_temperature_sweep" ? "Fixed-frequency reduced-frequency projection" : "Multi-frequency WLF master curve"}`;

  useEffect(() => {
    const currentGeneration = generation.current + 1;
    generation.current = currentGeneration;
    let active = true;
    setStatus("loading");
    setError("");
    setProfile(undefined);
    setPins(null);
    setRecommendation(null);
    setDraft(null);
    setReadBack(null);
    setOutput(null);
    setCreatedOutput(null);
    setFitInput(null);
    setSelectedReferenceSweepOrdinal(null);
    setVisibleSweepOrdinals([]);
    setClassification({ kind: "blocked", reason: "Loading exact DMA source…" });
    void listGovernedImportProfiles(config).then((result) => {
      if (!active || generation.current !== currentGeneration) return;
      const exactPins = exactDmaTtsPins(testData, result.data);
      const exactProfile = result.data.find((item) => exactPins?.import_profile.profile_id === item.import_profile_id
        && exactPins.import_profile.revision_id === item.current_revision.id);
      if (!exactPins || !exactProfile) throw new Error("The exact governed Import Profile for this Test Data is not available.");
      const nextClassification = classifyDmaTtsSource(sourceDocument, exactProfile);
      setProfile(exactProfile);
      setPins(exactPins);
      setClassification(nextClassification);
      if (nextClassification.kind === "multi") {
        const defaultReference = nextClassification.source.sweeps[Math.floor(nextClassification.source.sweeps.length / 2)]?.sourceSweepOrdinal ?? null;
        setSelectedReferenceSweepOrdinal(defaultReference);
        setVisibleSweepOrdinals(nextClassification.source.sweeps.map((item) => item.sourceSweepOrdinal));
      }
      if (nextClassification.kind === "blocked" || nextClassification.kind === "direct") {
        setStatus("error");
        setError(nextClassification.kind === "direct"
          ? "This single-temperature DMA source belongs in direct Fit, not the DMA Process."
          : nextClassification.reason);
      } else {
        setStatus("ready");
      }
    }).catch((caught: unknown) => {
      if (!active || generation.current !== currentGeneration) return;
      setStatus("error");
      setError(dmaTtsErrorMessage(caught, "The exact DMA source could not be loaded."));
    });
    return () => { active = false; };
  }, [config.accessToken, config.baseUrl, sourceDocument, sourceKey, testData]);

  useEffect(() => {
    if (!initialOutput || !pins || !inputMode || readBack || output) return;
    // A list result is only a pointer. The exact content-addressed GET effect below
    // must still restore and validate the result before Fit can use it. Keep this
    // hydration separate from source loading so adopting a newly saved output does
    // not reset the in-flight exact POST -> GET -> common-link journey.
    setOutput({
      output_id: initialOutput.id,
      revision_id: initialOutput.revisionId,
      content_sha256: initialOutput.contentSha256,
      metadata_artifact_id: "",
      metadata_sha256: "",
      result_artifact_id: "",
      result_sha256: "",
      result_schema_ref: "",
      result_media_type: "application/vnd.apache.parquet",
    });
  }, [initialOutput, inputMode, output, pins, readBack]);

  const prepareRecommendation = useCallback(async () => {
    if (!pins || !profile || (classification.kind !== "fixed" && classification.kind !== "multi")) return false;
    const currentGeneration = generation.current;
    setStatus("preparing");
    setError("");
    try {
      const result = classification.kind === "multi"
        ? await recommendMultiDmaTts(config, {
          ...pins,
          reference_sweep_ordinal: selectedReferenceSweepOrdinal ?? classification.source.sweeps[0]?.sourceSweepOrdinal ?? 0,
        })
        : await recommendDmaTts(config, pins);
      if (generation.current !== currentGeneration) return false;
      setRecommendation(result.data);
      setDraft(draftFromDmaTtsRecommendation(result.data, classification.kind === "fixed" ? classification.source.rows.length : 0));
      setStatus("ready");
      return true;
    } catch (caught: unknown) {
      if (generation.current !== currentGeneration) return false;
      setStatus("error");
      setError(dmaTtsErrorMessage(caught, "The DMA TTS recommendation could not be prepared."));
      return false;
    }
  }, [classification, config, pins, profile, selectedReferenceSweepOrdinal]);

  const readExactAndBind = useCallback(async (created: CreateDmaTtsResponse): Promise<boolean> => {
    if (!pins || !inputMode) return false;
    const currentGeneration = generation.current;
    setStatus("saving");
    setError("");
    try {
      const result = await getDmaTtsRevision(
        config,
        created.master_curve_output.output_id,
        created.master_curve_output.revision_id,
        created.master_curve_output.content_sha256,
      );
      if (generation.current !== currentGeneration) return false;
      const exact = validateReadBack(result.data, created, pins, inputMode);
      setReadBack(exact);
      setOutput(exact.output);
      await onSaved(created, exact);
      if (generation.current !== currentGeneration) return false;
      setStatus("saved");
      return true;
    } catch (caught: unknown) {
      if (generation.current !== currentGeneration) return false;
      setStatus("read_error");
      setError(dmaTtsErrorMessage(caught, "The saved DMA response could not be read back or linked to Fit."));
      return false;
    }
  }, [config, inputMode, onSaved, pins]);

  useEffect(() => {
    if (!output || !readBack) {
      setFitInput(null);
      return undefined;
    }
    let active = true;
    void getProcessedLinearViscoelasticFitInput(config, output.output_id, output.revision_id).then((result) => {
      if (!active) return;
      setFitInput(result.data);
    }).catch((caught: unknown) => {
      if (!active) return;
      setStatus("read_error");
      setError(dmaTtsErrorMessage(caught, "The exact saved DMA response is ready, but Fit input could not be linked."));
    });
    return () => { active = false; };
  }, [config.accessToken, config.baseUrl, output?.output_id, output?.revision_id, readBack]);

  useEffect(() => {
    if (!initialOutput || !output || readBack || !pins || !inputMode) return undefined;
    let active = true;
    const created: CreateDmaTtsResponse = { master_curve_output: output };
    void getDmaTtsRevision(config, output.output_id, output.revision_id, output.content_sha256).then(async (result) => {
      if (!active) return;
      try {
        const exact = validateReadBack(result.data, created, pins, inputMode);
        setReadBack(exact);
        setOutput(exact.output);
        await onSaved(created, exact);
        if (!active) return;
        setStatus("saved");
      } catch (caught: unknown) {
        if (!active) return;
        setStatus("read_error");
        setError(dmaTtsErrorMessage(caught, "The exact saved DMA response could not be verified or linked to Fit."));
      }
    }).catch((caught: unknown) => {
      if (!active) return;
      setStatus("read_error");
      setError(dmaTtsErrorMessage(caught, "The exact saved DMA response could not be loaded."));
    });
    return () => { active = false; };
  }, [config, initialOutput, inputMode, onSaved, output, pins, readBack]);

  const updateDraft = useCallback((patch: Partial<DmaTtsDraft>) => {
    setDraft((current) => current ? { ...current, ...patch } : current);
  }, []);
  const setDisposition = useCallback((ordinal: number, partition: DmaTtsPartition) => {
    setDraft((current) => current?.inputMode === "fixed_frequency_temperature_sweep" ? {
      ...current,
      dispositions: current.dispositions.map((item, index) => index === ordinal
        ? { partition, exclusionReason: partition === "EXCLUDED" ? item.exclusionReason : "" }
        : item),
    } : current);
  }, []);
  const setExclusionReason = useCallback((ordinal: number, exclusionReason: string) => {
    setDraft((current) => current?.inputMode === "fixed_frequency_temperature_sweep" ? {
      ...current,
      dispositions: current.dispositions.map((item, index) => index === ordinal ? { ...item, exclusionReason } : item),
    } : current);
  }, []);
  const setSweepDisposition = useCallback((ordinal: number, partition: DmaTtsPartition) => {
    setDraft((current) => {
      if (current?.inputMode !== "multi_frequency_isotherms") return current;
      const sweepDispositions = current.sweepDispositions.map((item) => item.source_sweep_ordinal === ordinal
        ? { ...item, partition, exclusion_reason: partition === "EXCLUDED" ? item.exclusion_reason : null }
        : item);
      if (current.shiftLawKind !== "manual_tabulated") return { ...current, sweepDispositions };
      const manualTable = sweepDispositions
        .filter((item) => item.partition !== "EXCLUDED")
        .map((item) => {
          const existing = current.manualTable.find((row) => Number(row.temperatureK) === item.representative_temperature_k);
          return {
            temperatureK: String(item.representative_temperature_k),
            log10At: existing?.log10At ?? (item.source_sweep_ordinal === current.referenceSweepOrdinal ? "0" : ""),
          };
        });
      return { ...current, sweepDispositions, manualTable };
    });
  }, []);
  const setSweepExclusionReason = useCallback((ordinal: number, reason: string) => {
    setDraft((current) => current?.inputMode === "multi_frequency_isotherms" ? {
      ...current,
      sweepDispositions: current.sweepDispositions.map((item) => item.source_sweep_ordinal === ordinal
        ? { ...item, exclusion_reason: reason }
        : item),
    } : current);
  }, []);
  const setReferenceSweep = useCallback((ordinal: number) => {
    setSelectedReferenceSweepOrdinal(ordinal);
    setRecommendation(null);
    setDraft(null);
    setReadBack(null);
    setOutput(null);
    setFitInput(null);
    setError("");
    setStatus("ready");
  }, []);
  const toggleSweepVisibility = useCallback((ordinal: number) => {
    setVisibleSweepOrdinals((current) => current.includes(ordinal)
      ? current.filter((item) => item !== ordinal)
      : [...current, ordinal]);
  }, []);

  const save = useCallback(async () => {
    if (createdOutput) return readExactAndBind(createdOutput);
    if (!draft || !recommendation || !pins || !classification || !source) return false;
    const payload = buildCreateDmaTtsRequest(testData, pins, recommendation, draft, label);
    if (!payload) {
      setStatus("ready");
      setError("Review the shift settings, included sweeps, and confirmation reason.");
      return false;
    }
    setStatus("saving");
    setError("");
    try {
      const created = await createDmaTts(config, payload);
      setCreatedOutput(created.data);
      return readExactAndBind(created.data);
    } catch (caught: unknown) {
      const knownClientFailure = caught instanceof Error && "status" in caught
        && typeof (caught as { status?: unknown }).status === "number"
        && (caught as { status: number }).status < 500;
      setStatus(knownClientFailure ? "ready" : "save_outcome_unknown");
      setError(dmaTtsErrorMessage(caught, knownClientFailure
        ? "The DMA TTS result was not saved. Correct the draft and retry."
        : "Save outcome unknown. Do not submit again; retry the exact read-back when the service is available."));
      return false;
    }
  }, [classification, config, createdOutput, draft, label, pins, readExactAndBind, recommendation, source, testData]);

  const retry = useCallback(() => {
    if (createdOutput) {
      void readExactAndBind(createdOutput);
      return;
    }
    if (status === "save_outcome_unknown") {
      setError("Save outcome unknown. The create request will not be retried automatically.");
      return;
    }
    void prepareRecommendation();
  }, [createdOutput, prepareRecommendation, readExactAndBind, status]);

  const canSave = Boolean(draft && recommendation && dmaTtsDraftReady(draft, label));
  const canPrepare = Boolean(pins && profile && (classification.kind === "fixed" || classification.kind === "multi"));
  const multiSource = classification.kind === "multi" ? classification.source : null;
  const fixedSource = classification.kind === "fixed" ? classification.source : null;
  return {
    source,
    fixedSource,
    multiSource,
    classification,
    inputMode,
    status,
    error: error || sourceReason(classification),
    recommendation,
    draft,
    readBack,
    fitInput,
    output,
    createdOutput,
    label,
    selectedReferenceSweepOrdinal,
    visibleSweepOrdinals,
    canPrepare,
    canSave,
    prepareRecommendation,
    updateDraft,
    setDisposition,
    setExclusionReason,
    setSweepDisposition,
    setSweepExclusionReason,
    setReferenceSweep,
    toggleSweepVisibility,
    save,
    retry,
  };
}
