/**
 * Bounded API compatibility facade.
 *
 * New and migrated consumers use feature/resource public entry points. The
 * remaining production consumers are app/legacy-route-pages.tsx,
 * common-processing-workbench.tsx, material-library.tsx,
 * reference-voce-calibration-workbench.tsx, and
 * scalar-distribution-workbench.tsx; #331 removes those legacy composition
 * boundaries. api.test.ts and material-library-activity.test.tsx verify the
 * compatibility contract. Remove this facade only after #331 and #361 migrate
 * those consumers and tests and a zero-consumer search is recorded.
 */
export * from "./shared/api";
export * from "./features/catalog/api/catalog-api";
export * from "./features/materials/api/materials-api";
export * from "./features/modeling/api/modeling-resource-api";
export * from "./features/activity/api/activity-api";
export * from "./features/test-data/api/test-data-api";
export {
  grantProductAccess,
  listProductAccessAssignments,
  revokeProductAccess,
} from "./features/administration/access/access-api";
export {
  applySchemaDefinitionBundle,
  downloadSchemaDefinitionBundle,
  getSchemaDefinitionBundleApplication,
  planSchemaDefinitionBundle,
  uploadSchemaDefinitionBundle,
} from "./features/administration/definition-bundles/definition-bundle-api";
