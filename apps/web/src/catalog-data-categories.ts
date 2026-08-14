import type {
  CatalogDataCategory,
  ConfigurableLinkEndpoint,
  DomainRevisionBinding,
} from "./types";

export const CATALOG_DATA_CATEGORIES: ReadonlyArray<{
  key: CatalogDataCategory;
  label: string;
}> = [
  { key: "technical_data", label: "Technical Data" },
  { key: "test_data", label: "Test Data" },
  { key: "simulation_data", label: "Simulation Data" },
  { key: "solver_cards", label: "Solver Cards" },
];

const CATEGORY_BY_BINDING: Partial<
  Record<DomainRevisionBinding["kind"], CatalogDataCategory>
> = {
  material: "technical_data",
  material_state: "technical_data",
  specimen: "test_data",
  test_run: "test_data",
  test_data: "test_data",
  processing_output: "simulation_data",
  material_model: "simulation_data",
  neutral_material: "simulation_data",
  solver_card: "solver_cards",
  neutral_solver_card: "solver_cards",
};

export function dataCategoryForEndpoint(
  endpoint: ConfigurableLinkEndpoint,
): CatalogDataCategory | null {
  const bindings = endpoint.domain_bindings?.length
    ? endpoint.domain_bindings
    : endpoint.domain_binding
      ? [endpoint.domain_binding]
      : [];
  for (const binding of bindings) {
    const category = CATEGORY_BY_BINDING[binding.kind];
    if (category) return category;
  }
  return endpoint.data_category;
}
