import { lazy, Suspense, useEffect } from "react";

import type { ApiConfig } from "../../../shared/api/http";
import { publishWorkspaceStatus } from "../../../design/application-shell";
import "../ui/administration.css";
import "../ui/administration-fe07b.css";

const ConfigurableCatalogAdmin = lazy(() =>
  import("../database-design/database-design-workspace").then((module) => ({
    default: module.ConfigurableCatalogAdmin,
  })),
);
const ConfigurableCatalogRecords = lazy(() =>
  import("../records/configurable-catalog-records").then((module) => ({
    default: module.ConfigurableCatalogRecords,
  })),
);
const SchemaDefinitionBundleAdmin = lazy(() =>
  import("../definition-bundles/schema-definition-bundle-admin").then((module) => ({
    default: module.SchemaDefinitionBundleAdmin,
  })),
);
const ProductAccessCenter = lazy(() =>
  import("../access/product-access-center").then((module) => ({
    default: module.ProductAccessCenter,
  })),
);

export type AdministrationSection = "database" | "bundles" | "records" | "access";

const administrationTasks: ReadonlyArray<{
  section: AdministrationSection;
  label: string;
  path: string;
}> = [
  { section: "database", label: "Database", path: "/administration/database" },
  { section: "bundles", label: "Format definitions", path: "/administration/schema-bundles" },
  { section: "records", label: "Records", path: "/administration/records" },
  { section: "access", label: "Access", path: "/administration/access" },
];

export interface AdministrationWorkspaceProps {
  config: ApiConfig;
  locationSearch: string;
  navigate: (path: string) => void;
  onOpenConnection: () => void;
  section: AdministrationSection;
}

export function AdministrationWorkspace({
  config,
  locationSearch,
  navigate,
  onOpenConnection,
  section,
}: AdministrationWorkspaceProps) {
  useEffect(() => {
    if (section === "database" || section === "bundles" || section === "records") return;
    const selection = administrationTasks.find((task) => task.section === section)?.label ?? "Administration";
    const publish = window.setTimeout(() => {
      publishWorkspaceStatus({
        selection,
        revision: "",
        jobs: "",
        warnings: "",
        connection: "online",
      });
    });
    return () => window.clearTimeout(publish);
  }, [section]);

  return (
    <div className="administration-workspace">
      <header className="administration-taskbar">
        <nav aria-label="Administration tasks">
          {administrationTasks.map((task) => (
            <button
              aria-current={section === task.section ? "page" : undefined}
              className={section === task.section ? "active" : ""}
              key={task.section}
              onClick={() => navigate(task.path)}
              type="button"
            >
              {task.label}
            </button>
          ))}
        </nav>
      </header>
      <section className="administration-content" data-administration-section={section}>
        <Suspense fallback={<p className="loading-state">Loading Administration…</p>}>
          {section === "database" ? (
            <ConfigurableCatalogAdmin
              config={config}
              locationSearch={locationSearch}
              onNavigate={navigate}
              onOpenConnection={onOpenConnection}
              productMode
            />
          ) : null}
          {section === "records" ? (
            <ConfigurableCatalogRecords
              config={config}
              locationSearch={locationSearch}
              onNavigate={navigate}
              onOpenConnection={onOpenConnection}
              productMode
            />
          ) : null}
          {section === "bundles" ? (
            <SchemaDefinitionBundleAdmin
              config={config}
              locationSearch={locationSearch}
              onNavigate={navigate}
              onOpenConnection={onOpenConnection}
            />
          ) : null}
          {section === "access" ? (
            <ProductAccessCenter config={config} onOpenConnection={onOpenConnection} productMode />
          ) : null}
        </Suspense>
      </section>
    </div>
  );
}
