import type { AdministrationSection } from "../features/administration";
import type {
  MaterialRevisionPin,
  MaterialTab,
} from "../features/materials";

export type ModuleArea = "testing" | "datasets" | "models" | "governance";
export type ExactSolverCardKind = "solver_card" | "neutral_solver_card";

interface RouteLocation {
  pathname: string;
  search: string;
}

export type AppRoute =
  | (RouteLocation & { id: "root-redirect"; to: "/materials" })
  | (RouteLocation & {
      id: "material-search";
      source: "canonical";
    })
  | (RouteLocation & {
      id: "material-create";
    })
  | (RouteLocation & {
      id: "material-detail";
      materialId: string;
      tab: MaterialTab;
      exactPin?: MaterialRevisionPin;
      source: "canonical" | "legacy-area";
    })
  | (RouteLocation & {
      id: "material-record";
      recordId: string;
      revisionId: string;
    })
  | (RouteLocation & {
      id: "material-card";
      materialId: string;
      cardId: string;
      exactPin?: MaterialRevisionPin;
    })
  | (RouteLocation & {
      id: "catalog-explorer";
      recordId?: string;
      revisionId?: string;
    })
  | (RouteLocation & {
      id: "exact-material-model";
      materialModelId: string;
      revisionId: string;
    })
  | (RouteLocation & {
      id: "exact-neutral-material";
      neutralMaterialId: string;
      revisionId: string;
    })
  | (RouteLocation & {
      id: "exact-solver-card";
      cardId: string;
      revisionId: string;
      kind: ExactSolverCardKind;
    })
  | (RouteLocation & {
      id: "module-hub";
      area: ModuleArea;
    })
  | (RouteLocation & { id: "bulk-export" })
  | (RouteLocation & { id: "canonical-test-data" })
  | (RouteLocation & { id: "governed-import" })
  | (RouteLocation & { id: "modeling"; source: "canonical" | "legacy-datasets" })
  | (RouteLocation & { id: "activity"; source: "canonical" | "legacy-jobs-reviews" })
  | (RouteLocation & {
      id: "administration";
      section: AdministrationSection;
      source: "canonical" | "legacy-catalog" | "legacy-access";
    })
  | (RouteLocation & { id: "unknown" });

interface RouteMatchContext extends RouteLocation {
  parameters: URLSearchParams;
}

export interface AppRouteDefinition {
  id: Exclude<AppRoute["id"], "unknown">;
  match(context: RouteMatchContext): AppRoute | null;
}

function locationParts(location: string): RouteLocation {
  const queryIndex = location.indexOf("?");
  const pathname = (queryIndex >= 0 ? location.slice(0, queryIndex) : location) || "/";
  const search = queryIndex >= 0 ? location.slice(queryIndex) : "";
  return { pathname, search };
}

function exactPin(parameters: URLSearchParams): MaterialRevisionPin | undefined {
  const values = [
    parameters.get("record_id"),
    parameters.get("record_revision_id"),
    parameters.get("material_revision_id"),
  ];
  if (!values.some((value) => value !== null)) return undefined;
  return {
    recordId: values[0] ?? "",
    recordRevisionId: values[1] ?? "",
    materialRevisionId: values[2] ?? "",
  };
}

const legacyMaterialTabs: Record<string, MaterialTab> = {
  testing: "curves",
  datasets: "curves",
  models: "cards",
  governance: "evidence",
};

/**
 * Ordered app-owned route registry. Earlier entries own more specific deep links;
 * the final unknown descriptor deliberately preserves the historical Materials fallback.
 */
export const appRouteRegistry: readonly AppRouteDefinition[] = [
  {
    id: "root-redirect",
    match: ({ pathname, search }) =>
      pathname === "/"
        ? { id: "root-redirect", pathname, search, to: "/materials" }
        : null,
  },
  {
    id: "exact-solver-card",
    match: ({ pathname, search, parameters }) => {
      const match = pathname.match(
        /^\/exports\/cards\/([^/]+)\/revisions\/([^/]+)$/,
      );
      if (!match) return null;
      const kind = parameters.get("kind");
      return kind === "solver_card" || kind === "neutral_solver_card"
        ? {
            id: "exact-solver-card",
            pathname,
            search,
            cardId: match[1],
            revisionId: match[2],
            kind,
          }
        : null;
    },
  },
  {
    id: "exact-material-model",
    match: ({ pathname, search }) => {
      const match = pathname.match(
        /^\/models\/material-models\/([^/]+)\/revisions\/([^/]+)$/,
      );
      return match
        ? {
            id: "exact-material-model",
            pathname,
            search,
            materialModelId: match[1],
            revisionId: match[2],
          }
        : null;
    },
  },
  {
    id: "exact-neutral-material",
    match: ({ pathname, search }) => {
      const match = pathname.match(
        /^\/models\/neutral-materials\/([^/]+)\/revisions\/([^/]+)$/,
      );
      return match
        ? {
            id: "exact-neutral-material",
            pathname,
            search,
            neutralMaterialId: match[1],
            revisionId: match[2],
          }
        : null;
    },
  },
  {
    id: "material-card",
    match: ({ pathname, search, parameters }) => {
      const match = pathname.match(/^\/materials\/([^/]+)\/cards\/([^/]+)$/);
      return match
        ? {
            id: "material-card",
            pathname,
            search,
            materialId: match[1],
            cardId: match[2],
            exactPin: exactPin(parameters),
          }
        : null;
    },
  },
  {
    id: "material-record",
    match: ({ pathname, search }) => {
      const match = pathname.match(
        /^\/materials\/records\/([^/]+)\/revisions\/([^/]+)$/,
      );
      return match
        ? {
            id: "material-record",
            pathname,
            search,
            recordId: match[1],
            revisionId: match[2],
          }
        : null;
    },
  },
  {
    id: "catalog-explorer",
    match: ({ pathname, search }) => {
      const match = pathname.match(
        /^\/catalog\/explorer(?:\/records\/([^/]+)\/revisions\/([^/]+))?$/,
      );
      return match
        ? {
            id: "catalog-explorer",
            pathname,
            search,
            recordId: match[1],
            revisionId: match[2],
          }
        : null;
    },
  },
  {
    id: "material-create",
    match: ({ pathname, search }) =>
      pathname === "/materials/new"
        ? { id: "material-create", pathname, search }
        : null,
  },
  {
    id: "material-detail",
    match: ({ pathname, search, parameters }) => {
      const match = pathname.match(
        /^\/materials\/([^/]+)(?:\/(overview|properties|curves|cards|evidence))?$/,
      );
      return match
        ? {
            id: "material-detail",
            pathname,
            search,
            materialId: match[1],
            tab: (match[2] ?? "overview") as MaterialTab,
            exactPin: exactPin(parameters),
            source: "canonical",
          }
        : null;
    },
  },
  {
    id: "material-detail",
    match: ({ pathname, search }) => {
      const match = pathname.match(
        /^\/materials\/([^/]+)\/(testing|datasets|models|governance)$/,
      );
      return match
        ? {
            id: "material-detail",
            pathname,
            search,
            materialId: match[1],
            tab: legacyMaterialTabs[match[2]],
            source: "legacy-area",
          }
        : null;
    },
  },
  {
    id: "material-search",
    match: ({ pathname, search }) =>
      pathname === "/materials"
        ? {
            id: "material-search",
            pathname,
            search,
            source: "canonical",
          }
        : null,
  },
  {
    id: "administration",
    match: ({ pathname, search }) => {
      if (pathname === "/catalog/schema") {
        return {
          id: "administration",
          pathname,
          search,
          section: "database",
          source: "legacy-catalog",
        };
      }
      if (pathname === "/catalog/records") {
        return {
          id: "administration",
          pathname,
          search,
          section: "records",
          source: "legacy-catalog",
        };
      }
      return null;
    },
  },
  {
    id: "bulk-export",
    match: ({ pathname, search }) =>
      pathname === "/exports" ? { id: "bulk-export", pathname, search } : null,
  },
  {
    id: "module-hub",
    match: ({ pathname, search }) => {
      const areaByPath: Partial<Record<string, ModuleArea>> = {
        "/tests": "testing",
        "/datasets": "datasets",
        "/models": "models",
        "/governance": "governance",
      };
      const area = areaByPath[pathname];
      return area ? { id: "module-hub", pathname, search, area } : null;
    },
  },
  {
    id: "canonical-test-data",
    match: ({ pathname, search }) =>
      pathname === "/datasets/test-json"
        ? { id: "canonical-test-data", pathname, search }
        : null,
  },
  {
    id: "governed-import",
    match: ({ pathname, search }) =>
      pathname === "/datasets/import"
        ? { id: "governed-import", pathname, search }
        : null,
  },
  {
    id: "modeling",
    match: ({ pathname, search }) => {
      if (pathname === "/modeling") {
        return { id: "modeling", pathname, search, source: "canonical" };
      }
      if (pathname === "/datasets/processing") {
        return {
          id: "modeling",
          pathname,
          search,
          source: "legacy-datasets",
        };
      }
      return null;
    },
  },
  {
    id: "activity",
    match: ({ pathname, search }) => {
      if (pathname === "/activity") {
        return { id: "activity", pathname, search, source: "canonical" };
      }
      if (pathname === "/jobs-reviews") {
        return {
          id: "activity",
          pathname,
          search,
          source: "legacy-jobs-reviews",
        };
      }
      return null;
    },
  },
  {
    id: "administration",
    match: ({ pathname, search }) => {
      if (pathname === "/access") {
        return {
          id: "administration",
          pathname,
          search,
          section: "access",
          source: "legacy-access",
        };
      }
      const sectionByPath: Partial<Record<string, AdministrationSection>> = {
        "/administration": "database",
        "/administration/access": "access",
        "/administration/database": "database",
        "/administration/schema-bundles": "bundles",
        "/administration/records": "records",
      };
      const section = sectionByPath[pathname];
      return section
        ? {
            id: "administration",
            pathname,
            search,
            section,
            source: "canonical",
          }
        : null;
    },
  },
];

export function parseAppRoute(location: string): AppRoute {
  const parts = locationParts(location);
  const context: RouteMatchContext = {
    ...parts,
    parameters: new URLSearchParams(parts.search),
  };
  for (const definition of appRouteRegistry) {
    const route = definition.match(context);
    if (route) return route;
  }
  return { id: "unknown", ...parts };
}
