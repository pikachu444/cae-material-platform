import { useCallback, useEffect, useMemo, useReducer } from "react";

import type { ApiConfig } from "../../../shared/api/http";
import {
  previewJsonRecordRegistration,
  saveJsonRecordRegistration,
  uploadJsonRegistrationFiles,
} from "./json-registration-api";
import { detectedContentLabel } from "./json-registration-model";
import type {
  JsonDataClassification,
  JsonRegistrationArtifact,
  JsonRegistrationFileResult,
  JsonRegistrationPreviewResponse,
  JsonRegistrationSaveResponse,
} from "./json-registration-model";

export type SourceFamily = "json" | "tabular" | "mixed" | "unsupported" | null;
export type RegistrationPhase =
  | "empty"
  | "ready"
  | "previewing"
  | "invalid"
  | "valid"
  | "stale"
  | "preview-error"
  | "saving"
  | "save-error"
  | "saved"
  | "error";

const INTERNAL_CLASSIFICATION: JsonDataClassification = "internal";

export interface JsonRegistrationControllerOptions {
  config: ApiConfig;
  selectedTable?: { tableId: string; revisionId: string } | null;
  onClose: () => void;
  onTabularFiles?: (files: File[], table: { tableId: string; revisionId: string }) => void;
  onChooseRecordType?: () => void;
  onOpenRecords?: (input: {
    tableId: string;
    tableRevisionId: string;
  }) => void;
}

interface State {
  selectedFiles: File[];
  family: SourceFamily;
  selectedFilename: string | null;
  artifacts: JsonRegistrationArtifact[];
  preview: JsonRegistrationPreviewResponse | null;
  saved: JsonRegistrationSaveResponse | null;
  reason: string;
  phase: RegistrationPhase;
  uploading: boolean;
  error: string | null;
}

type Action =
  | { type: "files-selected"; files: File[]; family: SourceFamily; selectedFilename: string }
  | { type: "upload-started" }
  | { type: "upload-succeeded"; artifact: JsonRegistrationArtifact }
  | { type: "preview-started" }
  | { type: "preview-succeeded"; preview: JsonRegistrationPreviewResponse }
  | { type: "preview-failed"; message: string }
  | { type: "save-started" }
  | { type: "save-succeeded"; saved: JsonRegistrationSaveResponse }
  | { type: "save-failed"; message: string }
  | { type: "tabular-table-selected" }
  | { type: "filename-selected"; filename: string }
  | { type: "reason-changed"; reason: string }
  | { type: "error"; message: string };

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The record import command could not be completed.";
}

export function sourceFamily(file: File): Exclude<SourceFamily, "mixed" | null> {
  const name = file.name.toLowerCase();
  if (file.type === "application/json" || name.endsWith(".json")) {
    return "json";
  }
  if (
    file.type === "text/csv"
    || name.endsWith(".csv")
    || name.endsWith(".tsv")
    || name.endsWith(".xlsx")
  ) {
    return "tabular";
  }
  return "unsupported";
}

export function detectSourceFamily(files: File[]): SourceFamily {
  if (!files.length) return null;
  const families = new Set(files.map(sourceFamily));
  if (families.size > 1) return "mixed";
  return [...families][0] ?? "unsupported";
}

function initialState(): State {
  return {
    selectedFiles: [],
    family: null,
    selectedFilename: null,
    artifacts: [],
    preview: null,
    saved: null,
    reason: "",
    phase: "empty",
    uploading: false,
    error: null,
  };
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "files-selected":
      return {
        ...state,
        selectedFiles: action.files,
        family: action.family,
        selectedFilename: action.selectedFilename,
        artifacts: [],
        saved: null,
        phase: state.preview ? "stale" : action.files.length ? "ready" : "empty",
        error: null,
      };
    case "upload-started":
      return { ...state, uploading: true, error: null };
    case "upload-succeeded":
      return {
        ...state,
        artifacts: [action.artifact],
        uploading: false,
        phase: state.preview ? "stale" : "ready",
        error: null,
      };
    case "preview-started":
      return { ...state, phase: "previewing", error: null };
    case "preview-succeeded":
      return {
        ...state,
        preview: action.preview,
        phase: action.preview.valid ? "valid" : "invalid",
        error: null,
      };
    case "preview-failed":
      return {
        ...state,
        phase: "preview-error",
        error: action.message,
      };
    case "save-started":
      return { ...state, phase: "saving", error: null };
    case "save-succeeded":
      return {
        ...state,
        saved: action.saved,
        phase: "saved",
        error: null,
      };
    case "save-failed":
      return { ...state, phase: "save-error", error: action.message };
    case "tabular-table-selected":
      if (state.family !== "tabular" || state.selectedFiles.length !== 1) return state;
      return {
        ...state,
        phase: state.phase === "error" ? "ready" : state.phase,
        error: null,
      };
    case "filename-selected":
      return { ...state, selectedFilename: action.filename };
    case "reason-changed":
      return { ...state, reason: action.reason };
    case "error":
      return { ...state, phase: "error", uploading: false, error: action.message };
    default:
      return state;
  }
}

export interface JsonRegistrationFileRow {
  file: File;
  selected: boolean;
  record: string;
  status: string;
}

export interface JsonRegistrationControllerView {
  selectedFiles: File[];
  family: SourceFamily;
  selectedFilename: string | null;
  selectedResult: JsonRegistrationFileResult | null;
  detectedContent: string | null;
  preview: JsonRegistrationPreviewResponse | null;
  saved: JsonRegistrationSaveResponse | null;
  reason: string;
  phase: RegistrationPhase;
  error: string | null;
  uploading: boolean;
  rows: JsonRegistrationFileRow[];
  batchSummary: string | null;
  currentStep: 1 | 2 | 3;
  canPreview: boolean;
  showPreviewCommand: boolean;
  previewCommandLabel: "Preview" | "Retry" | null;
  canSave: boolean;
  showSave: boolean;
  tabularReady: boolean;
}

export interface JsonRegistrationControllerCommands {
  addFiles: (fileList: FileList | null) => void;
  selectFile: (filename: string) => void;
  setReason: (reason: string) => void;
  preview: () => void;
  retry: () => void;
  save: () => void;
  openRecords: () => void;
  continueTabular: () => void;
  chooseRecordType: () => void;
  cancel: () => void;
}

export function useJsonRegistrationController(
  options: JsonRegistrationControllerOptions,
): {
  view: JsonRegistrationControllerView;
  commands: JsonRegistrationControllerCommands;
} {
  const [state, dispatch] = useReducer(reducer, undefined, initialState);
  const {
    config,
    selectedTable,
    onClose,
    onTabularFiles,
    onChooseRecordType,
    onOpenRecords,
  } = options;

  const stageFiles = useCallback(
    async (fileList: FileList | File[]) => {
      const files = Array.from(fileList);
      if (!files.length) return;
      const family = detectSourceFamily(files);
      dispatch({
        type: "files-selected",
        files,
        family,
        selectedFilename: files[0].name,
      });
      if (family === "tabular" && files.length === 1 && selectedTable) return;
      if (family !== "json") {
        dispatch({
          type: "error",
          message:
            family === "tabular"
              ? files.length === 1
                ? "Choose the exact Record type to continue."
                : "Keep the selected files. Choose one tabular source file to continue."
              : family === "mixed"
                ? "Keep the selected files. Use one source family per import."
                : "Keep the selected files. Choose JSON or one tabular source file.",
        });
        return;
      }
      dispatch({ type: "upload-started" });
      try {
        const result = await uploadJsonRegistrationFiles(config, {
          files,
          classification: INTERNAL_CLASSIFICATION,
        });
        dispatch({ type: "upload-succeeded", artifact: result.data });
      } catch (error: unknown) {
        dispatch({ type: "error", message: errorMessage(error) });
      }
    },
    [config, selectedTable],
  );

  useEffect(() => {
    if (selectedTable && state.family === "tabular" && state.selectedFiles.length === 1) {
      dispatch({ type: "tabular-table-selected" });
    }
  }, [selectedTable?.revisionId, selectedTable?.tableId, state.family, state.selectedFiles.length]);

  const preview = useCallback(async () => {
    if (state.family !== "json" || !state.artifacts.length) return;
    dispatch({ type: "preview-started" });
    try {
      const result = await previewJsonRecordRegistration(config, {
        classification: INTERNAL_CLASSIFICATION,
        files: state.artifacts,
      });
      dispatch({ type: "preview-succeeded", preview: result.data });
    } catch (error: unknown) {
      dispatch({ type: "preview-failed", message: errorMessage(error) });
    }
  }, [config, state.artifacts, state.family]);

  const save = useCallback(async () => {
    if (!state.preview?.valid || !state.reason.trim()) return;
    dispatch({ type: "save-started" });
    try {
      const result = await saveJsonRecordRegistration(config, state.preview.preview_token, {
        package_sha256: state.preview.package.sha256,
        change_reason: state.reason.trim(),
      });
      dispatch({ type: "save-succeeded", saved: result.data });
    } catch (error: unknown) {
      dispatch({ type: "save-failed", message: errorMessage(error) });
    }
  }, [config, state.preview, state.reason]);

  const commands = useMemo<JsonRegistrationControllerCommands>(
    () => ({
      addFiles: (fileList) => void stageFiles(fileList ? Array.from(fileList) : []),
      selectFile: (filename) => dispatch({ type: "filename-selected", filename }),
      setReason: (reason) => dispatch({ type: "reason-changed", reason }),
      preview: () => void preview(),
      retry: () => {
        if (state.artifacts.length) void preview();
        else if (state.selectedFiles.length) void stageFiles(state.selectedFiles);
      },
      save: () => void save(),
      openRecords: () => {
        const table = state.preview?.format?.table;
        if (state.saved && table && onOpenRecords) {
          onOpenRecords({
            tableId: table.id,
            tableRevisionId: table.revision_id,
          });
        }
      },
      continueTabular: () => {
        if (state.family === "tabular" && state.selectedFiles.length === 1 && selectedTable) {
          onTabularFiles?.(state.selectedFiles, selectedTable);
        }
      },
      chooseRecordType: () => onChooseRecordType?.(),
      cancel: onClose,
    }),
    [
      onChooseRecordType,
      onClose,
      onTabularFiles,
      onOpenRecords,
      preview,
      save,
      selectedTable,
      stageFiles,
      state.artifacts.length,
      state.family,
      state.preview,
      state.saved,
      state.selectedFiles,
    ],
  );

  const resultByFilename = useMemo(
    () => new Map((state.preview?.files ?? []).map((item) => [item.filename, item])),
    [state.preview],
  );
  const rows = useMemo<JsonRegistrationFileRow[]>(
    () => state.selectedFiles.map((file) => {
      const result = resultByFilename.get(file.name);
      const status = result
        ? state.phase === "stale"
          ? "Preview stale"
          : result.valid
            ? "Ready"
            : "Needs attention"
        : state.uploading
          ? "Uploading…"
          : sourceFamily(file) === "unsupported"
            ? "Unsupported"
            : "Selected";
      return {
        file,
        selected: file.name === state.selectedFilename,
        record: result?.record_name ?? result?.external_key ?? "—",
        status,
      };
    }),
    [resultByFilename, state.phase, state.selectedFiles, state.selectedFilename, state.uploading],
  );
  const selectedResult = state.selectedFilename
    ? resultByFilename.get(state.selectedFilename) ?? null
    : null;
  const currentStep: 1 | 2 | 3 =
    state.phase === "saved" || state.phase === "valid" || state.phase === "save-error" ? 3
      : state.phase === "previewing" || state.phase === "preview-error" || state.phase === "invalid" ? 2
        : 1;
  const showPreviewCommand =
    state.family === "json"
    && (state.artifacts.length > 0 || state.selectedFiles.length > 0)
    && (
      state.phase === "ready"
      || state.phase === "stale"
      || state.phase === "invalid"
      || state.phase === "preview-error"
      || state.phase === "error"
    );
  const canPreview = showPreviewCommand;
  const previewRetryable = state.phase === "invalid"
    || state.phase === "preview-error"
    || state.phase === "error";
  const canSave =
    state.phase !== "saving"
    && state.phase !== "saved"
    && Boolean(state.preview?.valid && state.reason.trim());
  const view: JsonRegistrationControllerView = {
    selectedFiles: state.selectedFiles,
    family: state.family,
    selectedFilename: state.selectedFilename,
    selectedResult,
    detectedContent: detectedContentLabel(state.preview?.detected_record_type ?? null),
    preview: state.preview,
    saved: state.saved,
    reason: state.reason,
    phase: state.phase,
    error: state.error,
    uploading: state.uploading,
    rows,
    batchSummary: state.selectedFiles.length
      ? `${state.selectedFiles.length} selected${
        state.preview
        && (state.phase === "valid"
          || state.phase === "invalid"
          || state.phase === "saving"
          || state.phase === "save-error"
          || state.phase === "saved")
          ? ` · ${state.preview.files.filter((item) => item.valid).length} valid`
          : ""}`
      : null,
    currentStep,
    canPreview,
    showPreviewCommand,
    previewCommandLabel: showPreviewCommand ? (previewRetryable ? "Retry" : "Preview") : null,
    canSave,
    showSave: Boolean(
      state.preview?.valid
      && (state.phase === "valid" || state.phase === "saving" || state.phase === "save-error"),
    ),
    tabularReady: state.family === "tabular" && state.selectedFiles.length === 1 && Boolean(selectedTable),
  };
  return { view, commands };
}
