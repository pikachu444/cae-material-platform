import {
  getCatalogWorkflowGraph,
  getConfigurableCatalogRecord,
  getMaterialDetail,
  getMaterialRevisions,
  listConfigurableCatalogRecordRevisions,
  resolveCatalogDomainRevision,
  type ApiConfig,
} from "../../../api";
import type {
  CatalogWorkflowGraphResponse,
  ConfigurableCatalogRecordResponse,
  DomainRevisionBinding,
  MaterialDetail,
  MaterialResponse,
} from "../../../types";
import {
  previewSolverCardText as previewExactSolverCardText,
  type SolverCardSummary,
} from "../../../solver-card-delivery";
import type { MaterialRevisionPin } from "../model/materials-route-state";

export interface MaterialExperience {
  detail: MaterialDetail;
  graph: CatalogWorkflowGraphResponse | null;
  cards: SolverCardSummary[];
  representativeResponse: {
    kind: "true_stress_true_plastic_strain";
    points: Array<{ x: number; y: number }>;
  } | null;
  catalogRecord: ConfigurableCatalogRecordResponse | null;
}

function solverFor(
  name: string,
): Pick<SolverCardSummary, "solver" | "extension"> {
  const normalized = name.toLowerCase();
  if (normalized.includes("openradioss") || normalized.includes("radioss")) {
    return { solver: "OpenRadioss", extension: ".rad" };
  }
  if (normalized.includes("abaqus"))
    return { solver: "Abaqus", extension: ".inp" };
  return { solver: "Solver", extension: ".txt" };
}

export function solverCardSummaryFromEndpoint(
  node: CatalogWorkflowGraphResponse["nodes"][number],
): SolverCardSummary | null {
  const binding = nodeBindings(node).find(
    (candidate) =>
      candidate.kind === "neutral_solver_card" ||
      candidate.kind === "solver_card",
  );
  if (!binding) return null;
  return {
    id: binding.object_id,
    revisionId: binding.revision_id,
    kind: binding.kind as SolverCardSummary["kind"],
    label: node.name,
    ...solverFor(node.name),
  };
}

export function nodeBindings(
  node: CatalogWorkflowGraphResponse["nodes"][number],
): DomainRevisionBinding[] {
  const bindings = node.domain_bindings?.length
    ? node.domain_bindings
    : node.domain_binding
      ? [node.domain_binding]
      : [];
  const seen = new Set<string>();
  return bindings.filter((binding) => {
    const key = `${node.record_id}:${node.record_revision_id}:${binding.kind}:${binding.object_id}:${binding.revision_id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function cardsFromGraph(
  graph: CatalogWorkflowGraphResponse | null,
): SolverCardSummary[] {
  if (!graph) return [];
  return graph.nodes
    .map(solverCardSummaryFromEndpoint)
    .filter((card): card is SolverCardSummary => card !== null)
    .sort((left, right) => left.solver.localeCompare(right.solver));
}

async function currentCards(
  config: ApiConfig,
  materialId: string,
  graph: CatalogWorkflowGraphResponse | null,
): Promise<SolverCardSummary[]> {
  const merged = new Map(
    cardsFromGraph(graph).map((card) => [
      `${card.kind}:${card.id}:${card.revisionId}`,
      card,
    ]),
  );
  void config;
  void materialId;
  return [...merged.values()].sort(
    (left, right) =>
      left.solver.localeCompare(right.solver) ||
      left.label.localeCompare(right.label),
  );
}

export function curveFromNativeCard(
  source: string,
): Array<{ x: number; y: number }> {
  const points: Array<{ x: number; y: number }> = [];
  let readingAbaqus = false;
  let readingRadioss = false;
  for (const rawLine of source.split("\n")) {
    const line = rawLine.trim();
    if (line.startsWith("*PLASTIC")) {
      readingAbaqus = true;
      readingRadioss = false;
      continue;
    }
    if (line.startsWith("/FUNCT/")) {
      readingRadioss = true;
      readingAbaqus = false;
      continue;
    }
    if (
      (readingAbaqus && line.startsWith("*")) ||
      (readingRadioss && line.startsWith("/END"))
    )
      break;
    if (!readingAbaqus && !readingRadioss) continue;
    if (!line || line.startsWith("#") || line.startsWith("CMP_")) continue;
    const values = line
      .split(/[\s,]+/)
      .filter(Boolean)
      .map(Number);
    if (
      values.length < 2 ||
      !Number.isFinite(values[0]) ||
      !Number.isFinite(values[1])
    )
      continue;
    points.push(
      readingAbaqus
        ? { x: values[1], y: values[0] }
        : { x: values[0], y: values[1] },
    );
  }
  return points;
}

export function trueStressPlasticStrainResponseFromNativeCard(source: string): {
  kind: "true_stress_true_plastic_strain";
  points: Array<{ x: number; y: number }>;
} | null {
  const hasDeclaredHardeningContract =
    /(?:^|\n)\s*\*PLASTIC\b/i.test(source) ||
    /(?:^|\n)\s*\/MAT\/LAW36\//i.test(source);
  if (!hasDeclaredHardeningContract) return null;
  const points = curveFromNativeCard(source);
  return points.length >= 2
    ? { kind: "true_stress_true_plastic_strain", points }
    : null;
}

export async function loadMaterialExperience(
  config: ApiConfig,
  material: MaterialResponse,
  includeCurve = false,
): Promise<MaterialExperience> {
  const detailResult = await getMaterialDetail(config, material.material_id);
  const bindingResult = await resolveCatalogDomainRevision(
    config,
    "material",
    material.material_id,
    material.current_revision.id,
  );
  const binding = bindingResult.data;
  if (!binding)
    throw new Error("This Material revision is not published in Materials.");
  const graph = (
    await getCatalogWorkflowGraph(
      config,
      binding.record_id,
      binding.record_revision_id,
      6,
      true,
    )
  ).data;
  const graphBinding = graph.root.domain_binding;
  if (
    graph.root.record_id !== binding.record_id ||
    graph.root.record_revision_id !== binding.record_revision_id ||
    !graphBinding ||
    graphBinding.kind !== "material" ||
    graphBinding.object_id !== material.material_id ||
    graphBinding.revision_id !== material.current_revision.id
  ) {
    throw new Error(
      "This Material revision is not the approved current Materials subject.",
    );
  }
  // Bulk-export candidate discovery is an internal Modeling surface.  Materials
  // cards must come only from the approved exact graph projection.
  const cards = await currentCards(config, material.material_id, graph);
  let representativeResponse: MaterialExperience["representativeResponse"] =
    null;
  if (includeCurve && cards.length) {
    const preferred =
      cards.find((card) => card.solver === "OpenRadioss") ?? cards[0];
    try {
      const preview = await previewExactSolverCardText(config, preferred);
      representativeResponse =
        trueStressPlasticStrainResponseFromNativeCard(preview.data);
    } catch {
      representativeResponse = null;
    }
  }
  return {
    detail: detailResult.data,
    graph,
    cards,
    representativeResponse,
    catalogRecord: null,
  };
}

export async function loadPinnedMaterialExperience(
  config: ApiConfig,
  materialId: string,
  pin: MaterialRevisionPin,
  includeCurve = false,
): Promise<MaterialExperience> {
  if (!pin.recordId || !pin.recordRevisionId || !pin.materialRevisionId) {
    throw new Error("The selected exact Material revision link is incomplete.");
  }
  const [
    detailResult,
    materialRevisionsResult,
    recordHeadResult,
    recordRevisionsResult,
  ] = await Promise.all([
    getMaterialDetail(config, materialId),
    getMaterialRevisions(config, materialId),
    getConfigurableCatalogRecord(config, pin.recordId),
    listConfigurableCatalogRecordRevisions(config, pin.recordId),
  ]);
  const materialRevision = materialRevisionsResult.data.revisions.find(
    (revision) => revision.id === pin.materialRevisionId,
  );
  if (!materialRevision)
    throw new Error("The selected Material revision is unavailable.");
  const recordRevision = recordRevisionsResult.data.items.find(
    (revision) => revision.id === pin.recordRevisionId,
  );
  if (!recordRevision)
    throw new Error("The selected Catalog record revision is unavailable.");
  if (recordHeadResult.data.record_id !== pin.recordId)
    throw new Error("The selected Catalog record is unavailable.");
  const graphResult = await getCatalogWorkflowGraph(
    config,
    pin.recordId,
    pin.recordRevisionId,
    6,
    true,
  );
  const graph = graphResult.data;
  const graphBinding = graph.root.domain_binding;
  if (
    graph.root.record_id !== pin.recordId ||
    graph.root.record_revision_id !== pin.recordRevisionId ||
    !graphBinding ||
    graphBinding.kind !== "material" ||
    graphBinding.object_id !== materialId ||
    graphBinding.revision_id !== pin.materialRevisionId
  ) {
    throw new Error(
      "The selected workflow graph does not match the requested Material revision.",
    );
  }
  const record = {
    ...recordHeadResult.data,
    current_revision: recordRevision,
    domain_binding: graphBinding,
  };
  const detail: MaterialDetail = {
    ...detailResult.data,
    material: {
      ...detailResult.data.material,
      current_revision: materialRevision,
    },
    states: detailResult.data.states.filter(
      (state) =>
        state.current_revision.content.material_revision_id ===
        pin.materialRevisionId,
    ),
  };
  const stateRevisionIds = new Set(
    detail.states.map((state) => state.current_revision.id),
  );
  detail.property_sets = detailResult.data.property_sets.filter((propertySet) =>
    stateRevisionIds.has(
      propertySet.current_revision.content.material_state_revision_id,
    ),
  );
  const cards = await currentCards(config, materialId, graph);
  let representativeResponse: MaterialExperience["representativeResponse"] =
    null;
  if (includeCurve && cards.length) {
    const preferred =
      cards.find((card) => card.solver === "OpenRadioss") ?? cards[0];
    try {
      const preview = await previewExactSolverCardText(config, preferred);
      representativeResponse =
        trueStressPlasticStrainResponseFromNativeCard(preview.data);
    } catch {
      representativeResponse = null;
    }
  }
  return { detail, graph, cards, representativeResponse, catalogRecord: record };
}
