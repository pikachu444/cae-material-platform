import type { DataClassification } from "../../../shared/model/core-contracts";

import type { FeatureGrant, ProductRole } from "../../../shared/api/auth-contracts";

export type { DataClassification } from "../../../shared/model/core-contracts";

export type {

  FeatureGrant,

  ProductAccessSummary,

  ProductRole,

} from "../../../shared/api/auth-contracts";

export interface ProductAccessAssignment {
  assignment_id: string;
  organization_id: string;
  project_id: string | null;
  subject_type: "principal" | "group";
  principal_id: string | null;
  group_issuer: string | null;
  group_name: string | null;
  product_role: ProductRole;
  feature_grants: FeatureGrant[];
  max_classification: Exclude<DataClassification, "export_controlled">;
  allow_export_controlled: boolean;
  valid_from: string;
  expires_at: string | null;
  revoked_at: string | null;
}

export interface GrantProductAccessInput {
  subject_type: "principal" | "group";
  principal_id: string | null;
  group_issuer: string | null;
  group_name: string | null;
  product_role: ProductRole;
  feature_grants: FeatureGrant[];
  max_classification: Exclude<DataClassification, "export_controlled">;
  allow_export_controlled: boolean;
  organization_wide: boolean;
  expires_at: string | null;
  grant_reason: string;
}
