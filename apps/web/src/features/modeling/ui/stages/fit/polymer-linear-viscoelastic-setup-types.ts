import type { CanonicalTestDataDocumentResponse } from "../../../../test-data/contracts";
import type { CommonProcessingOutputResponse } from "../../../model/common-processing-contracts";
import type {
  LinearViscoelasticParameterBound,
  LinearViscoelasticCandidateScopeMode,
  LinearViscoelasticPointPartition,
  ProcessedLinearViscoelasticFitInput,
  LinearViscoelasticWeights,
} from "../../../model/linear-viscoelastic-calibration-contracts";
import type {
  POLYMER_AVAILABILITY_FIELDS,
  PolymerDraftAvailability,
  PolymerFitSourceChoice,
  PolymerOptimizerDraft,
  PolymerSourceCurveMode,
  PolymerSourceSnapshot,
} from "../../../model/linear-viscoelastic-calibration-draft";
import type { ModelingSessionRecordRef } from "../../../model/session-controller";

export interface PolymerFitSetupViewModel {
  sourceChoice: PolymerFitSourceChoice;
  processedAvailable: boolean;
  processedInputStatus: "idle" | "loading" | "ready" | "error";
  processedInputError: string | null;
  processedFitInput: ProcessedLinearViscoelasticFitInput | null;
  sourceDisplayLabel?: string;
  testData?: CanonicalTestDataDocumentResponse;
  testDataRef?: ModelingSessionRecordRef;
  processingOutput?: CommonProcessingOutputResponse;
  activeDirectMode: PolymerSourceCurveMode;
  snapshot: PolymerSourceSnapshot;
  selectedTemperature: string;
  candidateScopeMode: LinearViscoelasticCandidateScopeMode;
  availableTemperatures: number[];
  availability: Record<typeof POLYMER_AVAILABILITY_FIELDS[number], PolymerDraftAvailability>;
  partitions: Array<LinearViscoelasticPointPartition | null>;
  partitionCounts: { calibration: number; holdout: number; excluded: number; unresolved: number };
  fitObservationCount: number;
  termCounts: number[];
  bounds: Record<string, LinearViscoelasticParameterBound[]>;
  weights: LinearViscoelasticWeights;
  optimizer: PolymerOptimizerDraft;
  setupName: string;
  baseSetupName?: string;
  overrideReason: string;
  changeReason: string;
  serverDiff?: Record<string, unknown> | null;
  reviewStatus?: "idle" | "submitting" | "pending" | "error";
  directBlockers: string[];
  modelBlockers: string[];
  solverBlockers: string[];
}

export interface PolymerFitSetupActions {
  chooseSource: (source: PolymerFitSourceChoice) => void;
  setSelectedTemperature: (value: string) => void;
  setAvailability: (key: typeof POLYMER_AVAILABILITY_FIELDS[number], value: PolymerDraftAvailability) => void;
  setPartition: (ordinal: number, partition: LinearViscoelasticPointPartition) => void;
  markAllCalibration: () => void;
  excludeOtherTemperatures: () => void;
  toggleTerm: (term: number) => void;
  setCandidateScopeMode: (mode: LinearViscoelasticCandidateScopeMode) => void;
  updateBound: (term: number, index: number, key: "lower" | "start" | "upper", value: string) => void;
  setWeight: (key: keyof Pick<LinearViscoelasticWeights,
    "relaxation_weight" | "dma_storage_weight" | "dma_loss_weight" | "relaxation_scale_pa" | "dma_storage_scale_pa" | "dma_loss_scale_pa"
  >, value: string) => void;
  setOptimizer: (key: keyof PolymerOptimizerDraft, value: string) => void;
  setSetupName: (value: string) => void;
  setOverrideReason: (value: string) => void;
  setChangeReason: (value: string) => void;
}
