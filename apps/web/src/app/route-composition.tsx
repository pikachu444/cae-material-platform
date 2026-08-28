import { lazy } from "react";
import {
  type ApiConfig,
} from "../shared/api";
import { MaterialCreatePage, ModuleHubPage } from "./legacy-route-pages";
import type { Navigate } from "./navigation";
import type { AppRoute } from "./routes";

const AdministrationWorkspace = lazy(() =>
  import("../features/administration").then((module) => ({
    default: module.AdministrationWorkspace,
  })),
);
const MaterialSearchPage = lazy(() =>
  import("../features/materials").then((module) => ({
    default: module.MaterialSearchPage,
  })),
);
const MaterialDetailPage = lazy(() =>
  import("../features/materials").then((module) => ({
    default: module.MaterialDetailPage,
  })),
);
const ExactRecordDatasheetPage = lazy(() =>
  import("../features/materials").then((module) => ({
    default: module.ExactRecordDatasheetPage,
  })),
);
const SolverCardPreviewPage = lazy(() =>
  import("../features/materials").then((module) => ({
    default: module.SolverCardPreviewPage,
  })),
);

/**
 * Bounded FE-08A compatibility roots and their only consumers:
 * - ActivityPage: /activity and /jobs-reviews until Activity has a public feature entry.
 * - MaterialModelingWorkspace: /modeling and /datasets/processing until the root
 *   workspace can move behind the Modeling public entry without creating a cycle.
 * - CatalogExplorer, governed import, bulk export, canonical Test Data and exact
 *   domain pages: only their descriptors below; retire each root import after its
 *   owning feature exposes the same route-level contract in an approved follow-up.
 * FE-08B/08C own API/type movement; #331 owns legacy UI/CSS retirement.
 */
const ActivityPage = lazy(() =>
  import("../material-library").then((module) => ({
    default: module.ActivityPage,
  })),
);
const MaterialModelingWorkspace = lazy(() =>
  import("../material-modeling-workspace").then((module) => ({
    default: module.MaterialModelingWorkspace,
  })),
);
const CatalogExplorer = lazy(() =>
  import("../catalog-explorer").then((module) => ({
    default: module.CatalogExplorer,
  })),
);
const GovernedImportRoute = lazy(() =>
  import("../governed-import-route").then((module) => ({
    default: module.GovernedImportRoute,
  })),
);
const BulkExportCenter = lazy(() =>
  import("../bulk-export-center").then((module) => ({
    default: module.BulkExportCenter,
  })),
);
const CanonicalTestDataWorkbench = lazy(() =>
  import("../canonical-test-data-workbench").then((module) => ({
    default: module.CanonicalTestDataWorkbench,
  })),
);
const ExactMaterialModelPage = lazy(() =>
  import("../exact-domain-pages").then((module) => ({
    default: module.ExactMaterialModelPage,
  })),
);
const ExactNeutralMaterialPage = lazy(() =>
  import("../exact-domain-pages").then((module) => ({
    default: module.ExactNeutralMaterialPage,
  })),
);
const ExactSolverCardPage = lazy(() =>
  import("../exact-domain-pages").then((module) => ({
    default: module.ExactSolverCardPage,
  })),
);
export interface RouteCompositionProps {
  route: AppRoute;
  config: ApiConfig;
  navigate: Navigate;
  onOpenConnection: () => void;
}

export function RouteComposition({
  route,
  config,
  navigate,
  onOpenConnection,
}: RouteCompositionProps) {
  switch (route.id) {
    case "exact-solver-card":
      return (
        <ExactSolverCardPage
          config={config}
          cardId={route.cardId}
          revisionId={route.revisionId}
          kind={route.kind}
          onNavigate={navigate}
        />
      );
    case "exact-material-model":
      return (
        <ExactMaterialModelPage
          config={config}
          materialModelId={route.materialModelId}
          revisionId={route.revisionId}
          onNavigate={navigate}
        />
      );
    case "exact-neutral-material":
      return (
        <ExactNeutralMaterialPage
          config={config}
          neutralMaterialId={route.neutralMaterialId}
          revisionId={route.revisionId}
          onNavigate={navigate}
        />
      );
    case "material-card":
      return (
        <SolverCardPreviewPage
          config={config}
          materialId={route.materialId}
          cardId={route.cardId}
          exactPin={route.exactPin}
          onNavigate={navigate}
        />
      );
    case "material-record":
      return (
        <ExactRecordDatasheetPage
          config={config}
          recordId={route.recordId}
          revisionId={route.revisionId}
          onNavigate={navigate}
        />
      );
    case "catalog-explorer":
      return (
        <CatalogExplorer
          config={config}
          initialRecordId={route.recordId}
          initialRevisionId={route.revisionId}
          onNavigate={navigate}
          onOpenConnection={onOpenConnection}
        />
      );
    case "material-create":
      return (
        <MaterialCreatePage
          config={config}
          navigate={navigate}
          onOpenConnection={onOpenConnection}
        />
      );
    case "material-detail":
      return (
        <MaterialDetailPage
          config={config}
          materialId={route.materialId}
          activeTab={route.tab}
          exactPin={route.exactPin}
          onNavigate={navigate}
        />
      );
    case "material-search":
    case "root-redirect":
    case "unknown":
      return (
        <MaterialSearchPage
          config={config}
          onNavigate={navigate}
          locationSearch={route.search}
        />
      );
    case "administration":
      return (
        <AdministrationWorkspace
          config={config}
          locationSearch={route.search}
          navigate={navigate}
          onOpenConnection={onOpenConnection}
          section={route.section}
        />
      );
    case "bulk-export":
      return (
        <BulkExportCenter
          config={config}
          onOpenConnection={onOpenConnection}
        />
      );
    case "module-hub":
      return (
        <ModuleHubPage
          area={route.area}
          config={config}
          navigate={navigate}
          onOpenConnection={onOpenConnection}
          locationSearch={route.search}
        />
      );
    case "canonical-test-data":
      return (
        <CanonicalTestDataWorkbench
          config={config}
          onNavigate={navigate}
          onOpenConnection={onOpenConnection}
          locationSearch={route.search}
        />
      );
    case "governed-import":
      return (
        <GovernedImportRoute
          config={config}
          onNavigate={navigate}
          onOpenConnection={onOpenConnection}
        />
      );
    case "modeling":
      return (
        <MaterialModelingWorkspace
          config={config}
          onNavigate={navigate}
          onOpenConnection={onOpenConnection}
          locationSearch={route.search}
        />
      );
    case "activity":
      return (
        <ActivityPage
          config={config}
          onNavigate={navigate}
          locationSearch={route.search}
        />
      );
  }
}
