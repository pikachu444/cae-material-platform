import { useCallback, useEffect, useMemo, useState } from "react";

import { listGovernedImportProfiles } from "../../test-data";
import type { CanonicalTestDataDocumentResponse } from "../../test-data/contracts";
import type { ApiConfig } from "../../../shared/api";
import { createDmaTts, recommendDmaTts } from "../api/dma-tts-api";
import { getProcessedLinearViscoelasticFitInput } from "../api/linear-viscoelastic-calibration-api";
import type { CreateDmaTtsResponse, DmaTtsOutputPin, DmaTtsPartition } from "../model/dma-tts-contracts";
import {
  buildCreateDmaTtsRequest,
  dmaTtsDraftReady,
  draftFromDmaTtsRecommendation,
  exactDmaTtsPins,
  parseDmaTemperatureSweep,
  type DmaTtsDraft,
} from "../model/dma-tts-draft";
import type { ProcessedLinearViscoelasticFitInput } from "../model/linear-viscoelastic-calibration-contracts";

type LoadState = "loading" | "ready" | "saving" | "saved" | "error";

interface UseDmaTtsProcessInput {
  config: ApiConfig;
  testData: CanonicalTestDataDocumentResponse;
  sourceDocument: Record<string, unknown>;
  sourceLabel: string;
  initialOutput?: { id: string; revisionId: string };
  onSaved: (created: CreateDmaTtsResponse) => Promise<void> | void;
}

export function useDmaTtsProcess({
  config,
  testData,
  sourceDocument,
  sourceLabel,
  initialOutput,
  onSaved,
}: UseDmaTtsProcessInput) {
  const source = useMemo(() => parseDmaTemperatureSweep(sourceDocument), [sourceDocument]);
  const [status, setStatus] = useState<LoadState>(initialOutput ? "loading" : "loading");
  const [error, setError] = useState("");
  const [recommendation, setRecommendation] = useState<Awaited<ReturnType<typeof recommendDmaTts>>["data"] | null>(null);
  const [draft, setDraft] = useState<DmaTtsDraft | null>(null);
  const [output, setOutput] = useState<Pick<DmaTtsOutputPin, "output_id" | "revision_id"> | null>(initialOutput ? {
    output_id: initialOutput.id,
    revision_id: initialOutput.revisionId,
  } : null);
  const [createdOutput, setCreatedOutput] = useState<CreateDmaTtsResponse | null>(null);
  const [fitInput, setFitInput] = useState<ProcessedLinearViscoelasticFitInput | null>(null);
  const [retryVersion, setRetryVersion] = useState(0);
  const label = `${sourceLabel} · Shifted DMA response`;
  const sourceKey = `${testData.test_data_document_id}:${testData.current_revision.id}`;

  useEffect(() => {
    let active = true;
    setError("");
    setRecommendation(null);
    setDraft(null);
    setCreatedOutput(null);
    if (!source) {
      setStatus("error");
      setError("This Test Data is not a fixed-frequency shear DMA temperature sweep.");
      return () => { active = false; };
    }
    void listGovernedImportProfiles(config).then(async (profiles) => {
      if (!active) return;
      const pins = exactDmaTtsPins(testData, profiles.data);
      if (!pins) throw new Error("The exact governed Import Profile for this Test Data is not available.");
      const result = await recommendDmaTts(config, pins);
      if (!active) return;
      setRecommendation(result.data);
      setDraft(draftFromDmaTtsRecommendation(result.data, source.rows.length));
      setStatus(initialOutput ? "saved" : "ready");
    }).catch((caught: unknown) => {
      if (!active) return;
      setStatus("error");
      setError(caught instanceof Error ? caught.message : "DMA TTS settings could not be prepared.");
    });
    return () => { active = false; };
  }, [config.accessToken, config.baseUrl, retryVersion, sourceKey, source]);

  useEffect(() => {
    if (!output) {
      setFitInput(null);
      return undefined;
    }
    let active = true;
    void getProcessedLinearViscoelasticFitInput(config, output.output_id, output.revision_id).then((result) => {
      if (!active) return;
      setFitInput(result.data);
      setStatus("saved");
      setError("");
    }).catch((caught: unknown) => {
      if (!active) return;
      setStatus("error");
      setError(caught instanceof Error ? caught.message : "The saved DMA response could not be loaded.");
    });
    return () => { active = false; };
  }, [config.accessToken, config.baseUrl, output?.output_id, output?.revision_id, retryVersion]);

  const updateDraft = useCallback((patch: Partial<DmaTtsDraft>) => {
    setDraft((current) => current ? { ...current, ...patch } : current);
  }, []);
  const setDisposition = useCallback((ordinal: number, partition: DmaTtsPartition) => {
    setDraft((current) => current ? {
      ...current,
      dispositions: current.dispositions.map((item, index) => index === ordinal
        ? { partition, exclusionReason: partition === "EXCLUDED" ? item.exclusionReason : "" }
        : item),
    } : current);
  }, []);
  const setExclusionReason = useCallback((ordinal: number, exclusionReason: string) => {
    setDraft((current) => current ? {
      ...current,
      dispositions: current.dispositions.map((item, index) => index === ordinal ? { ...item, exclusionReason } : item),
    } : current);
  }, []);

  const bindCreatedOutput = useCallback(async (created: CreateDmaTtsResponse) => {
    setStatus("saving");
    setError("");
    try {
      await onSaved(created);
      setOutput(created.master_curve_output);
      return true;
    } catch (caught) {
      setStatus("error");
      setError(caught instanceof Error ? caught.message : "The saved DMA response could not be linked to Fit.");
      return false;
    }
  }, [onSaved]);

  const save = useCallback(async () => {
    if (createdOutput) return bindCreatedOutput(createdOutput);
    if (!draft || !recommendation || !source) return false;
    setStatus("saving");
    setError("");
    try {
      const profiles = await listGovernedImportProfiles(config);
      const pins = exactDmaTtsPins(testData, profiles.data);
      const payload = pins ? buildCreateDmaTtsRequest(testData, pins, recommendation, draft, label) : null;
      if (!payload) {
        setStatus("ready");
        setError("Review the shift settings, included temperatures, and confirmation reason.");
        return false;
      }
      const created = await createDmaTts(config, payload);
      setCreatedOutput(created.data);
      return bindCreatedOutput(created.data);
    } catch (caught) {
      setStatus("error");
      setError(caught instanceof Error ? caught.message : "The shifted DMA response was not saved.");
      return false;
    }
  }, [bindCreatedOutput, config, createdOutput, draft, label, recommendation, source, testData]);

  const canSave = Boolean(draft && recommendation && dmaTtsDraftReady(draft, label));

  return {
    source,
    status,
    error,
    recommendation,
    draft,
    fitInput,
    label,
    canSave,
    updateDraft,
    setDisposition,
    setExclusionReason,
    save,
    retry: () => {
      if (output) setRetryVersion((value) => value + 1);
      else if (createdOutput) void bindCreatedOutput(createdOutput);
      else setRetryVersion((value) => value + 1);
    },
  };
}
