import type { CanonicalTestDataDocumentResponse } from "../../test-data/contracts";
import type {
  CommonMappingProfileContent,
  CommonMappingProfileResponse,
  CommonProcessingStep,
} from "./common-processing-contracts";
import {
  DEFAULT_PROFILE,
  POLYMER_DMA_PROFILE,
  POLYMER_DMA_STEPS,
  POLYMER_RELAXATION_PROFILE,
  POLYMER_RELAXATION_STEPS,
  documentIsPolymerDma,
  documentIsPolymerDmaTemperatureSweep,
} from "./processing-registry";

interface PolymerProcessingDefaults {
  profileId: string;
  profile: CommonMappingProfileContent;
  steps: CommonProcessingStep[];
}

export function polymerProcessingDefaults(
  document: CanonicalTestDataDocumentResponse,
  profiles: CommonMappingProfileResponse[],
): PolymerProcessingDefaults {
  if (documentIsPolymerDmaTemperatureSweep(document)) {
    return { profileId: "", profile: DEFAULT_PROFILE, steps: [] };
  }

  const dma = documentIsPolymerDma(document);
  const template = dma ? POLYMER_DMA_PROFILE : POLYMER_RELAXATION_PROFILE;
  const steps = dma ? POLYMER_DMA_STEPS : POLYMER_RELAXATION_STEPS;
  const compatible = profiles.find((candidate) => candidate.content.profile_key === template.profile_key)
    ?? profiles.find((candidate) => candidate.content.independent_quantity === template.independent_quantity
      && candidate.content.bindings.every((binding) => template.bindings.some(
        (expected) => expected.target_quantity === binding.target_quantity,
      )));

  return {
    profileId: compatible?.mapping_profile_id ?? "",
    profile: compatible?.content ?? template,
    steps,
  };
}
