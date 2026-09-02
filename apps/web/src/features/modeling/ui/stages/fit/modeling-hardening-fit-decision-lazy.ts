import { lazy } from "react";

export const LazyHardeningFitDecision = lazy(() =>
  import("./modeling-hardening-fit-decision").then((module) => ({
    default: module.HardeningFitDecision,
  })),
);
