export type ProductRole = "administrator" | "reviewer" | "user";

export interface AuthenticatedPrincipal {
  principal_id: string;
  principal_type: "user" | "service";
  display_name: string;
  organization_id: string;
  project_id: string;
  groups: string[];
  scopes: string[];
  request_id: string;
  trace_id: string;
}

export type FeatureGrant =
  | "schema_configuration"
  | "catalog_edit"
  | "processing_calibration"
  | "model_approval"
  | "solver_card_export";

export interface ProductAccessSummary {
  product_role: ProductRole;
  feature_grants: FeatureGrant[];
  legacy_compatible: boolean;
}
