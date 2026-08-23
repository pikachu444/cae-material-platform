import { useEffect, useMemo, useState } from "react";

import "./features/modeling/ui/modeling-viscoelastic-workbenches.css";

import {
  type ApiConfig,
  listShearRelaxationDatasetsForMaterialState,
  listTestRunsForMaterialState,
} from "./api";
import type { MaterialStateResponse, ShearRelaxationDatasetResponse, TestRunResponse } from "./types";
import { ViscoelasticMasterWorkbench } from "./viscoelastic-master-workbench";

function message(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Temperature-shift evidence could not be loaded.";
}

export function PolymerTemperatureShiftInspector({
  config,
  state,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
}) {
  const [datasets, setDatasets] = useState<ShearRelaxationDatasetResponse[]>([]);
  const [runs, setRuns] = useState<TestRunResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void Promise.all([
      listShearRelaxationDatasetsForMaterialState(config, state.material_state_id),
      listTestRunsForMaterialState(config, state.material_state_id),
    ]).then(([datasetResult, runResult]) => {
      if (!active) return;
      setDatasets(datasetResult.data.items);
      setRuns(runResult.data.items);
      setLoading(false);
    }).catch((cause: unknown) => {
      if (!active) return;
      setError(message(cause));
      setLoading(false);
    });
    return () => { active = false; };
  }, [config, state.material_state_id]);

  const temperatures = useMemo(() => new Set(runs
    .map((run) => run.current_revision.content.test_temperature_k)
    .filter((value): value is number => value != null)).size, [runs]);
  const eligible = datasets.filter((item) => item.current_revision.content.representation !== "raw").length;

  return <details
    className="polymer-temperature-shift-inspector"
    open={open}
    onToggle={(event) => setOpen(event.currentTarget.open)}
  >
    <summary><span><strong>Temperature shift &amp; master curve</strong><small>{loading ? "Loading exact datasets…" : `${eligible} curves · ${temperatures} temperatures`}</small></span><span>{open ? "Close" : "Configure"}</span></summary>
    {error ? <p className="error-notice" role="alert">{error}</p> : null}
    {!loading && !error ? <ViscoelasticMasterWorkbench config={config} state={state} datasets={datasets} runs={runs} compact /> : null}
  </details>;
}
